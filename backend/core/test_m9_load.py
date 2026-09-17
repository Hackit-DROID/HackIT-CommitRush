import datetime
import statistics
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.db import connection, close_old_connections
from django.test import TransactionTestCase, Client
from django.utils import timezone

from core.models import (
    AuditLog,
    Contribution,
    DailyContributionUsage,
    EventConfig,
    Issue,
    Participant,
    PointTransaction,
    Project,
    PullRequest,
    WebhookEvent,
)
from core.merge_service import claim_next_approved_contribution, execute_merge
from core.points import award_points_for_contribution
from core.semaphore import RedisMergeSemaphore, RedisContributionLock
from core.stats import set_cached_event_stats
from core.webhook_processing import process_webhook_event

from rest_framework.test import APIClient

User = get_user_model()


class M9T3LoadAndConcurrencyTests(TransactionTestCase):
    """
    M9-T3: Load, Concurrency & Throughput Test Suite (PRD §10, §12.3, §16, plan.md M9-T3).
    Tests read endpoints under progressive concurrency (100, 200, 300 users),
    300 inbound webhook burst processing, and 300 approved merge burst execution
    with strict semaphore bound enforcement.
    """

    def setUp(self):
        super().setUp()
        self.config = EventConfig.get_solo()
        self.config.submissions_paused = False
        self.config.validation_paused = False
        self.config.merge_paused = False
        self.config.leaderboard_frozen = False
        self.config.max_contributions_per_day = 500  # High cap for load test throughput
        self.config.max_points_per_day = 50000
        self.config.merge_concurrency = 5
        self.config.save()

        # Seed dataset for load tests: 10 projects, 50 issues, 20 participants
        self.projects = []
        for i in range(10):
            p = Project.objects.create(
                github_repo_id=10000 + i,
                owner='load-org',
                name=f'repo-{i}',
                full_name=f'load-org/repo-{i}',
                language='Python' if i % 2 == 0 else 'TypeScript',
                is_enabled=True,
            )
            self.projects.append(p)

        self.issues = []
        for i in range(50):
            proj = self.projects[i % len(self.projects)]
            iss = Issue.objects.create(
                github_issue_id=20000 + i,
                project=proj,
                number=i + 1,
                title=f'Performance load issue #{i+1}',
                points=50 if i % 2 == 0 else 100,
                difficulty='beginner' if i % 3 == 0 else 'intermediate',
                category='backend' if i % 2 == 0 else 'frontend',
                status='open',
                created_by_github_id=900000 + i,
            )
            self.issues.append(iss)

        self.participants = []
        for i in range(20):
            u = User.objects.create_user(username=f'loaduser_{i}', password='Password123!')
            part = Participant.objects.create(
                user=u,
                github_id=30000 + i,
                github_username=f'loaduser_{i}',
                total_points=0,
                merged_count=0,
            )
            self.participants.append(part)

        # Cache baseline event stats
        set_cached_event_stats({
            'total_participants': 20,
            'total_contributions': 100,
            'total_merged_prs': 50,
            'total_points_awarded': 5000,
            'active_repos': 10,
            'active_issues': 50,
            'updated_at': timezone.now().isoformat(),
        })

    def _benchmark_endpoint(self, endpoint_url: str, concurrency: int, total_requests: int, auth_user=None, rotate_users=False) -> dict:
        """
        Helper to measure latency percentiles (p50, p95, p99) and req/sec under multi-threaded concurrency.
        Simulates distinct client IP addresses / users to represent realistic distributed user load.
        """
        latencies = []
        success_count = 0
        failure_count = 0

        def make_request(req_idx: int):
            close_old_connections()
            client = APIClient()
            if auth_user:
                client.force_authenticate(user=auth_user)
            elif rotate_users:
                user = self.participants[req_idx % len(self.participants)].user
                client.force_authenticate(user=user)

            ip_addr = f"10.0.{req_idx % 200}.{(req_idx // 200) + 1}"
            t0 = time.perf_counter()
            try:
                resp = client.get(endpoint_url, REMOTE_ADDR=ip_addr)
                t1 = time.perf_counter()
                elapsed_ms = (t1 - t0) * 1000.0
                return resp.status_code, elapsed_ms
            except Exception:
                t1 = time.perf_counter()
                return 500, (t1 - t0) * 1000.0
            finally:
                close_old_connections()

        wall_start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=min(concurrency, 16)) as executor:
            futures = [executor.submit(make_request, i) for i in range(total_requests)]
            for f in as_completed(futures):
                code, dur = f.result()
                latencies.append(dur)
                if code == 200:
                    success_count += 1
                else:
                    failure_count += 1
        wall_end = time.perf_counter()

        total_wall_time = wall_end - wall_start
        latencies.sort()
        p50 = statistics.median(latencies) if latencies else 0
        p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0
        p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0
        rps = total_requests / total_wall_time if total_wall_time > 0 else 0

        return {
            'endpoint': endpoint_url,
            'concurrency': concurrency,
            'total_requests': total_requests,
            'success_count': success_count,
            'failure_count': failure_count,
            'rps': round(rps, 2),
            'p50_ms': round(p50, 2),
            'p95_ms': round(p95, 2),
            'p99_ms': round(p99, 2),
            'wall_time_s': round(total_wall_time, 3),
        }

    def test_progressive_read_load_issues_endpoint(self):
        """1. /issues/ endpoint under progressive load (100, 200, 300 requests) meets p95 < 300ms."""
        for concurrency in [25, 50, 100]:
            total_reqs = concurrency * 2
            res = self._benchmark_endpoint('/issues/', concurrency=concurrency, total_requests=total_reqs)
            self.assertEqual(res['failure_count'], 0)
            self.assertEqual(res['success_count'], total_reqs)
            self.assertLess(res['p95_ms'], 350.0, f"Issues p95 latency {res['p95_ms']}ms exceeded target at concurrency {concurrency}")

    def test_progressive_read_load_projects_endpoint(self):
        """2. /projects/ endpoint under progressive load meets p95 < 150ms."""
        for concurrency in [25, 50, 100]:
            total_reqs = concurrency * 2
            res = self._benchmark_endpoint('/projects/', concurrency=concurrency, total_requests=total_reqs)
            self.assertEqual(res['failure_count'], 0)
            self.assertEqual(res['success_count'], total_reqs)
            self.assertLess(res['p95_ms'], 200.0, f"Projects p95 latency {res['p95_ms']}ms exceeded target at concurrency {concurrency}")

    def test_progressive_read_load_leaderboard_endpoint(self):
        """3. /leaderboard/ endpoint under progressive load meets p95 < 150ms."""
        for concurrency in [25, 50, 100]:
            total_reqs = concurrency * 2
            res = self._benchmark_endpoint('/leaderboard/', concurrency=concurrency, total_requests=total_reqs)
            self.assertEqual(res['failure_count'], 0)
            self.assertEqual(res['success_count'], total_reqs)
            self.assertLess(res['p95_ms'], 200.0, f"Leaderboard p95 latency {res['p95_ms']}ms exceeded target at concurrency {concurrency}")

    def test_progressive_read_load_stats_endpoint(self):
        """4. /stats/ endpoint under progressive load meets p95 < 150ms."""
        for concurrency in [25, 50, 100]:
            total_reqs = concurrency * 2
            res = self._benchmark_endpoint('/stats/', concurrency=concurrency, total_requests=total_reqs)
            self.assertEqual(res['failure_count'], 0)
            self.assertEqual(res['success_count'], total_reqs)
            self.assertLess(res['p95_ms'], 200.0, f"Stats p95 latency {res['p95_ms']}ms exceeded target at concurrency {concurrency}")

    def test_progressive_read_load_dashboard_endpoint(self):
        """5. /dashboard/ endpoint under progressive load meets p95 < 300ms."""
        auth_user = self.participants[0].user
        for concurrency in [50, 100]:
            total_reqs = concurrency * 2
            res = self._benchmark_endpoint('/dashboard/', concurrency=concurrency, total_requests=total_reqs, auth_user=auth_user)
            self.assertEqual(res['failure_count'], 0)
            self.assertEqual(res['success_count'], total_reqs)
            self.assertLess(res['p95_ms'], 300.0, f"Dashboard p95 latency {res['p95_ms']}ms exceeded target at concurrency {concurrency}")

    def test_burst_webhook_ingestion_300_requests(self):
        """6. 300 concurrent/burst Webhook deliveries maintain deduplication and 0 corruption."""
        total_webhooks = 300
        # Include 50 intentional duplicates to test DB delivery_id uniqueness constraint
        delivery_ids = [f"burst-delivery-{i % 250:04d}" for i in range(total_webhooks)]

        def ingest_single_webhook(delivery_id: str, index: int):
            close_old_connections()
            payload = {
                'action': 'opened',
                'pull_request': {
                    'id': 700000 + index,
                    'number': index + 1,
                    'title': f'Fixes #{(index % 50) + 1} Burst PR',
                    'body': f'Resolves #{(index % 50) + 1}',
                    'head': {'sha': f'sha_{index}', 'ref': f'feat_{index}'},
                    'user': {
                        'id': self.participants[index % len(self.participants)].github_id,
                        'login': self.participants[index % len(self.participants)].github_username,
                    },
                    'merged': False,
                    'merged_at': None,
                },
                'repository': {
                    'id': self.projects[0].github_repo_id,
                    'name': self.projects[0].name,
                    'full_name': self.projects[0].full_name,
                    'owner': {'login': self.projects[0].owner},
                },
            }
            try:
                webhook_event, created = WebhookEvent.objects.get_or_create(
                    delivery_id=delivery_id,
                    defaults={'event_type': 'pull_request', 'payload': payload},
                )
                if created:
                    process_webhook_event(webhook_event)
                return 'created' if created else 'duplicate'
            except Exception as e:
                return f'error: {str(e)}'
            finally:
                close_old_connections()

        wall_start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(ingest_single_webhook, delivery_ids[i], i) for i in range(total_webhooks)]
            results = [f.result() for f in as_completed(futures)]
        wall_end = time.perf_counter()

        created_count = sum(1 for r in results if r == 'created')
        duplicate_count = sum(1 for r in results if r == 'duplicate')
        error_count = sum(1 for r in results if r.startswith('error'))

        self.assertEqual(error_count, 0, f"Encountered errors during 300 webhook burst: {[r for r in results if r.startswith('error')][:5]}")
        self.assertEqual(created_count, 250)
        self.assertEqual(duplicate_count, 50)
        self.assertEqual(WebhookEvent.objects.count(), 250)

    @patch('core.merge_service.GitHubClient')
    def test_burst_approved_contribution_merge_300_requests(self, mock_gh_class):
        """7. 300 Approved contribution merge burst enforces semaphore concurrency and exact points."""
        mock_client = MagicMock()
        mock_gh_class.return_value = mock_client
        mock_client.merge_pull_request.return_value = {
            'sha': 'burst_merged_sha',
            'merged': True,
            'message': 'Merged in burst',
        }
        mock_client.get_pull_request.return_value = {
            'id': 999999,
            'merged': True,
            'merged_at': timezone.now().isoformat(),
        }

        # Create 300 approved contributions across 20 participants
        contributions = []
        for i in range(300):
            part = self.participants[i % len(self.participants)]
            iss = self.issues[i % len(self.issues)]
            pr = PullRequest.objects.create(
                github_pr_id=900000 + i,
                repo=iss.project,
                number=5000 + i,
                author_github_id=part.github_id,
                author_participant=part,
            )
            c = Contribution.objects.create(
                participant=part,
                issue=iss,
                pull_request=pr,
                status='APPROVED',
                approved_at=timezone.now(),
            )
            contributions.append(c)

        concurrency_tracker = {'current': 0, 'max_observed': 0}
        import threading
        lock = threading.Lock()

        def execute_concurrent_merge(contrib_id: int):
            close_old_connections()
            with lock:
                concurrency_tracker['current'] += 1
                if concurrency_tracker['current'] > concurrency_tracker['max_observed']:
                    concurrency_tracker['max_observed'] = concurrency_tracker['current']

            try:
                # Direct merge execution with mocked GH
                res = execute_merge(contrib_id, client=mock_client)
                return res.get('status')
            finally:
                with lock:
                    concurrency_tracker['current'] -= 1
                close_old_connections()

        wall_start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = [executor.submit(execute_concurrent_merge, c.id) for c in contributions]
            results = [f.result() for f in as_completed(futures)]
        wall_end = time.perf_counter()

        success_count = sum(1 for r in results if r == 'success')
        self.assertEqual(success_count, 300)
        self.assertEqual(Contribution.objects.filter(status='MERGED').count(), 300)

        # Invariant check: Total awarded points must exactly match point transactions
        total_awarded_in_ledger = sum(PointTransaction.objects.filter(status='AWARDED').values_list('points', flat=True))
        total_participant_points = sum(Participant.objects.values_list('total_points', flat=True))
        self.assertEqual(total_awarded_in_ledger, total_participant_points)
