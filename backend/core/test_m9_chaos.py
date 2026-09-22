import datetime
from datetime import timedelta
import json
import time
from unittest.mock import MagicMock, patch
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.contrib.auth import get_user_model
from django.db import connection, close_old_connections
from django.test import TransactionTestCase, TestCase
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
from core.crash_recovery import requeue_stale_contributions
from core.github_sync import (
    GitHubAPIError,
    GitHubMergeConflictError,
    GitHubNetworkError,
    GitHubRateLimitError,
)
from core.leaderboard import fetch_leaderboard_data
from core.merge_service import claim_next_approved_contribution, execute_merge
from core.points import award_points_for_contribution
from core.semaphore import RedisMergeSemaphore, RedisContributionLock
from core.state_machine import transition_contribution
from core.stats import fetch_event_stats
from core.validation import validate_contribution
from core.webhook_processing import process_webhook_event

User = get_user_model()


class M9T4ChaosAndFailureTests(TransactionTestCase):
    """
    M9-T4: Failure, Chaos & Resilience Test Suite (PRD §10, §11.2, §12.3, §12.4, §12.6, §13.6, plan.md M9-T4).
    Simulates:
    1. Celery worker crash recovery (stale UNDER_REVIEW / MERGING sweeping).
    2. Redis outage & graceful degradation (semaphore, leaderboard, stats fallback).
    3. GitHub 500/502/503 transient backoff & FLAGGED escalation.
    4. GitHub 429 rate limit requeuing without budget exhaustion.
    5. Duplicate webhook bursts (1x, 2x, 5x deliveries).
    6. Daily limit race conditions under concurrent merge workers.
    7. Independent emergency pause switches (submissions, validation, merge, leaderboard).
    """

    def setUp(self):
        super().setUp()
        self.config = EventConfig.get_solo()
        self.config.submissions_paused = False
        self.config.validation_paused = False
        self.config.merge_paused = False
        self.config.leaderboard_frozen = False
        self.config.max_contributions_per_day = 2
        self.config.max_points_per_day = 100
        self.config.category_multipliers = {'feature': 1.0}
        self.config.allow_partial_daily_points = False
        self.config.merge_concurrency = 5
        self.config.save()

        self.user = User.objects.create_user(username='chaos_tester', password='Password123!')
        self.participant = Participant.objects.create(
            user=self.user,
            github_id=888001,
            github_username='chaos_tester',
            total_points=0,
            merged_count=0,
        )

        self.project = Project.objects.create(
            github_repo_id=999001,
            owner='chaos-org',
            name='chaos-engine',
            full_name='chaos-org/chaos-engine',
            language='Python',
            is_enabled=True,
        )

        self.issue = Issue.objects.create(
            github_issue_id=777001,
            project=self.project,
            number=1,
            title='Chaos test issue',
            points=50,
            status='open',
            created_by_github_id=111001,
        )

    def test_scenario_1_worker_crash_and_stale_requeue_sweep(self):
        """1. Celery worker crash recovery: Stale UNDER_REVIEW and MERGING contributions revert cleanly."""
        stale_time = timezone.now() - timedelta(minutes=20)

        # 1. Stale validating contribution (simulates worker dying during validation)
        pr1 = PullRequest.objects.create(
            github_pr_id=666001, repo=self.project, number=11,
            author_github_id=self.participant.github_id, author_participant=self.participant,
        )
        c_val = Contribution.objects.create(
            participant=self.participant, issue=self.issue, pull_request=pr1,
            status='UNDER_REVIEW', sub_status='VALIDATING', locked_at=stale_time,
        )

        # 2. Stale merging contribution (simulates worker dying during merge)
        pr2 = PullRequest.objects.create(
            github_pr_id=666002, repo=self.project, number=12,
            author_github_id=self.participant.github_id, author_participant=self.participant,
        )
        c_merge = Contribution.objects.create(
            participant=self.participant, issue=self.issue, pull_request=pr2,
            status='MERGING', locked_at=stale_time,
        )

        # 3. Active (non-stale) contribution should NOT be reverted
        fresh_time = timezone.now() - timedelta(minutes=2)
        pr3 = PullRequest.objects.create(
            github_pr_id=666003, repo=self.project, number=13,
            author_github_id=self.participant.github_id, author_participant=self.participant,
        )
        c_fresh = Contribution.objects.create(
            participant=self.participant, issue=self.issue, pull_request=pr3,
            status='MERGING', locked_at=fresh_time,
        )

        # Run recovery sweep (default 10 minute threshold)
        sweep_res = requeue_stale_contributions(timeout_minutes=10, re_enqueue=False)
        self.assertEqual(len(sweep_res['recovered_under_review']), 1)
        self.assertEqual(len(sweep_res['recovered_merging']), 1)
        self.assertEqual(sweep_res['total_recovered'], 2)

        c_val.refresh_from_db()
        self.assertEqual(c_val.status, 'QUEUED')
        self.assertIsNone(c_val.locked_at)

        c_merge.refresh_from_db()
        self.assertEqual(c_merge.status, 'APPROVED')
        self.assertIsNone(c_merge.locked_at)

        c_fresh.refresh_from_db()
        self.assertEqual(c_fresh.status, 'MERGING')  # Active task preserved
        self.assertIsNotNone(c_fresh.locked_at)

    @patch('django.core.cache.cache.get')
    @patch('core.semaphore.RedisMergeSemaphore.get_redis_client')
    def test_scenario_2_redis_outage_graceful_degradation(self, mock_sem_redis, mock_cache_get):
        """2. Redis outage: Semaphore, Leaderboard, and Stats degrade gracefully without crashing."""
        import redis
        mock_sem_redis.side_effect = redis.exceptions.ConnectionError("Redis connection refused")
        mock_cache_get.side_effect = Exception("Redis cache connection refused")

        # 1. Semaphore returns False gracefully (doesn't raise unhandled exception)
        sem = RedisMergeSemaphore()
        acquired = sem.acquire()
        self.assertFalse(acquired)

        # 2. Leaderboard calculation still functions directly from PostgreSQL
        lead_data = fetch_leaderboard_data(page=1, page_size=10)
        self.assertEqual(lead_data['page'], 1)
        self.assertEqual(lead_data['count'], 1)
        self.assertEqual(lead_data['results'][0]['github_username'], 'chaos_tester')

        # 3. Aggregate Stats calculation still functions directly from PostgreSQL
        stats_data = fetch_event_stats()
        self.assertEqual(stats_data['participants']['total'], 1)
        self.assertIn('contributions', stats_data)

    @patch('core.merge_service.GitHubClient')
    def test_scenario_3_github_500_502_503_backoff_and_flagged_escalation(self, mock_gh_class):
        """3. GitHub 5xx errors: Retries with exponential countdown and escalates to FLAGGED after 5 attempts."""
        mock_client = MagicMock()
        mock_gh_class.return_value = mock_client
        mock_client.merge_pull_request.side_effect = GitHubAPIError("502 Bad Gateway from GitHub")

        pr = PullRequest.objects.create(
            github_pr_id=666004, repo=self.project, number=14,
            author_github_id=self.participant.github_id, author_participant=self.participant,
        )
        contrib = Contribution.objects.create(
            participant=self.participant, issue=self.issue, pull_request=pr,
            status='APPROVED', retry_count=0,
        )

        # Retries 1 through 4
        expected_countdowns = [1, 2, 4, 8]  # 2^0, 2^1, 2^2, 2^3
        for i in range(4):
            res = execute_merge(contrib.id, client=mock_client)
            self.assertEqual(res['status'], 'retry')
            self.assertEqual(res['countdown'], expected_countdowns[i])
            contrib.refresh_from_db()
            self.assertEqual(contrib.status, 'RETRY')
            self.assertEqual(contrib.retry_count, i + 1)
            # Worker reset for next attempt
            contrib.status = 'APPROVED'
            contrib.save()

        # Attempt 5 (exhaustion)
        res5 = execute_merge(contrib.id, client=mock_client)
        self.assertEqual(res5['status'], 'flagged')
        contrib.refresh_from_db()
        self.assertEqual(contrib.status, 'FLAGGED')
        self.assertIn('502 Bad Gateway', contrib.flagged_reason)

    @patch('core.merge_service.GitHubClient')
    def test_scenario_4_github_429_rate_limit_backoff_preserves_state(self, mock_gh_class):
        """4. GitHub 429 rate limit: Requeue countdown returned without burning transient failure count."""
        mock_client = MagicMock()
        mock_gh_class.return_value = mock_client
        reset_time = int(time.time()) + 120
        mock_client.merge_pull_request.side_effect = GitHubRateLimitError(
            message="API rate limit exceeded",
            remaining=0,
            limit=5000,
            reset_timestamp=reset_time,
            retry_after=120,
        )

        pr = PullRequest.objects.create(
            github_pr_id=666005, repo=self.project, number=15,
            author_github_id=self.participant.github_id, author_participant=self.participant,
        )
        contrib = Contribution.objects.create(
            participant=self.participant, issue=self.issue, pull_request=pr,
            status='APPROVED', retry_count=0,
        )

        res = execute_merge(contrib.id, client=mock_client)
        self.assertEqual(res['status'], 'rate_limited')
        self.assertEqual(res['retry_after'], 120)

        contrib.refresh_from_db()
        # retry_count must NOT be incremented for rate limit delays
        self.assertEqual(contrib.retry_count, 0)

    def test_scenario_5_duplicate_webhook_burst_resilience(self):
        """5. Duplicate webhook deliveries (1x, 2x, 5x bursts) are discarded as no-ops."""
        delivery_id = "chaos-delivery-burst-999"
        payload = {
            'action': 'opened',
            'pull_request': {
                'id': 666006,
                'number': 16,
                'title': 'Fixes #1 Burst PR',
                'body': 'Closes #1',
                'head': {'sha': 'burst_sha_123', 'ref': 'feat-burst'},
                'user': {'id': self.participant.github_id, 'login': self.participant.github_username},
                'merged': False,
                'merged_at': None,
            },
            'repository': {
                'id': self.project.github_repo_id,
                'name': self.project.name,
                'full_name': self.project.full_name,
                'owner': {'login': self.project.owner},
            },
        }

        # Simulate 5 concurrent webhook deliveries of the EXACT same delivery_id
        def send_duplicate():
            close_old_connections()
            try:
                event, created = WebhookEvent.objects.get_or_create(
                    delivery_id=delivery_id,
                    defaults={'event_type': 'pull_request', 'payload': payload},
                )
                if created:
                    process_webhook_event(event)
                    return 'created'
                return 'duplicate'
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(send_duplicate) for _ in range(5)]
            results = [f.result() for f in as_completed(futures)]

        self.assertEqual(results.count('created'), 1)
        self.assertEqual(results.count('duplicate'), 4)
        self.assertEqual(WebhookEvent.objects.filter(delivery_id=delivery_id).count(), 1)
        self.assertEqual(Contribution.objects.filter(pull_request__github_pr_id=666006).count(), 1)

    @patch('core.merge_service.GitHubClient')
    def test_scenario_6_daily_limit_race_condition_protection(self, mock_gh_class):
        """6. Daily limit race condition: Concurrent merge completions enforce max daily points/contributions."""
        mock_client = MagicMock()
        mock_gh_class.return_value = mock_client
        mock_client.merge_pull_request.return_value = {'sha': 'race_sha', 'merged': True}
        mock_client.get_pull_request.return_value = {'merged': True, 'merged_at': timezone.now().isoformat()}

        # EventConfig: max_contributions_per_day = 2, max_points_per_day = 100
        # Create 5 approved contributions of 50 points each for the same participant
        contributions = []
        for i in range(5):
            iss = Issue.objects.create(
                github_issue_id=777010 + i,
                project=self.project,
                number=20 + i,
                title=f'Daily race issue {i}',
                points=50,
                status='open',
                created_by_github_id=111001,
            )
            pr = PullRequest.objects.create(
                github_pr_id=666010 + i,
                repo=self.project,
                number=30 + i,
                author_github_id=self.participant.github_id,
                author_participant=self.participant,
            )
            c = Contribution.objects.create(
                participant=self.participant,
                issue=iss,
                pull_request=pr,
                status='APPROVED',
            )
            contributions.append(c)

        # Concurrently merge all 5 contributions
        def run_merge(contrib_id: int):
            close_old_connections()
            try:
                return execute_merge(contrib_id, client=mock_client)
            finally:
                close_old_connections()

        max_workers = 1 if connection.vendor == 'sqlite' else 5
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(run_merge, c.id) for c in contributions]
            results = [f.result() for f in as_completed(futures)]

        self.participant.refresh_from_db()
        # Exactly 2 contributions awarded (100 points), remaining 3 deferred (0 points)
        self.assertEqual(self.participant.total_points, 100)
        self.assertEqual(self.participant.merged_count, 5)  # All 5 merged

        awarded_txns = PointTransaction.objects.filter(participant=self.participant, status='AWARDED')
        deferred_txns = PointTransaction.objects.filter(participant=self.participant, status='DEFERRED')

        self.assertEqual(awarded_txns.count(), 2)
        self.assertEqual(deferred_txns.count(), 3)

        today = timezone.now().date()
        usage = DailyContributionUsage.objects.get(participant=self.participant, date=today)
        self.assertEqual(usage.contributions_count, 2)
        self.assertEqual(usage.points_count, 100)

    def test_scenario_7_independent_emergency_pause_switches(self):
        """7. Emergency pause switches operate completely independently."""
        # 1. submissions_paused stops new contribution creation on PR webhook
        self.config.submissions_paused = True
        self.config.save()

        pr_payload = {
            'action': 'opened',
            'pull_request': {
                'id': 666099,
                'number': 99,
                'title': 'Fixes #1 Paused Submission',
                'body': 'Closes #1',
                'head': {'sha': 'paused_sha', 'ref': 'feat-paused'},
                'user': {'id': self.participant.github_id, 'login': self.participant.github_username},
                'merged': False,
                'merged_at': None,
            },
            'repository': {
                'id': self.project.github_repo_id,
                'name': self.project.name,
                'full_name': self.project.full_name,
                'owner': {'login': self.project.owner},
            },
        }
        event = WebhookEvent.objects.create(delivery_id='pause-del-01', event_type='pull_request', payload=pr_payload)
        res = process_webhook_event(event)
        self.assertEqual(res['status'], 'submissions_paused')
        self.assertEqual(Contribution.objects.filter(pull_request__github_pr_id=666099).count(), 0)

        # 2. validation_paused defers validation
        self.config.submissions_paused = False
        self.config.validation_paused = True
        self.config.save()

        pr2 = PullRequest.objects.create(
            github_pr_id=666100, repo=self.project, number=100,
            author_github_id=self.participant.github_id, author_participant=self.participant,
        )
        c_val = Contribution.objects.create(
            participant=self.participant, issue=self.issue, pull_request=pr2, status='QUEUED',
        )
        val_res = validate_contribution(c_val.id)
        self.assertEqual(val_res['status'], 'paused')
        c_val.refresh_from_db()
        self.assertEqual(c_val.status, 'QUEUED')  # State preserved

        # 3. merge_paused defers merge execution
        self.config.validation_paused = False
        self.config.merge_paused = True
        self.config.save()

        c_val.status = 'APPROVED'
        c_val.save()

        claimed = claim_next_approved_contribution()
        self.assertIsNone(claimed)

        merge_res = execute_merge(c_val.id)
        self.assertEqual(merge_res['status'], 'paused')
        c_val.refresh_from_db()
        self.assertEqual(c_val.status, 'APPROVED')  # State preserved
