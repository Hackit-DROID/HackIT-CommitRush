import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from core.consistency_checker import PipelineConsistencyChecker
from core.github_sync import GitHubClient, SyncResult, sync_repository_and_issues
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
from core.monitoring import HealthMonitor
from core.notifications import AlertSeverity, NotificationManager
from core.pipeline_tracer import PipelineStage, PipelineTracer
from core.reconciliation import reconcile_recent_repositories, reconcile_repository
from core.scoring.constants import DAILY_POINTS_CAP, get_event_today
from core.tasks import (
    beat_heartbeat_task,
    pipeline_health_monitor_task,
    reconcile_recent_repositories_task,
    sync_repository_task,
    worker_heartbeat_task,
)
from core.webhook_processing import handle_pull_request_event

User = get_user_model()


class SelfHealingPipelineTests(TestCase):
    def setUp(self):
        cache.clear()
        self.config = EventConfig.get_solo()
        self.config.submissions_paused = False
        self.config.is_frozen = False
        self.config.target_branch = 'main'
        self.config.max_points_per_day = DAILY_POINTS_CAP
        self.config.save()

        self.project = Project.objects.create(
            github_repo_id=987654,
            name='Open-Source-Contribution-Drive',
            owner='Hackit-DROID',
            full_name='Hackit-DROID/Open-Source-Contribution-Drive',
            is_enabled=True,
        )

        self.user = User.objects.create_user(username='test_dev', password='password123')
        self.participant = Participant.objects.create(
            user=self.user,
            github_id=1234567,
            github_username='test_dev',
            total_points=0,
            merged_count=0,
        )

        self.issue = Issue.objects.create(
            project=self.project,
            github_issue_id=55555,
            number=100,
            title='Implement Distributed Lock Engine (CR-100)',
            difficulty='HARD',
            category='BACKEND',
            points=50,
            status='open',
        )

    def test_01_normal_merged_pr_webhook_flow(self):
        """Authoritative merged PR webhook triggers ingestion, contribution creation, scoring, and total update."""
        payload = {
            'action': 'closed',
            'pull_request': {
                'id': 9001,
                'number': 101,
                'title': 'feat: Implement Lock Engine (CR-100)',
                'body': 'Closes #100',
                'head': {'sha': 'abcdef123456', 'ref': 'feature-lock'},
                'base': {'ref': 'main'},
                'user': {'id': self.participant.github_id, 'login': 'test_dev'},
                'merged': True,
                'merged_at': timezone.now().isoformat(),
            },
            'repository': {
                'id': self.project.github_repo_id,
                'full_name': self.project.full_name,
            },
        }

        res = handle_pull_request_event(payload)
        self.assertEqual(res['status'], 'pr_merged')

        pr = PullRequest.objects.get(github_pr_id=9001)
        self.assertTrue(pr.merged)

        contrib = Contribution.objects.get(pull_request=pr)
        self.assertEqual(contrib.status, 'MERGED')
        self.assertEqual(contrib.issue, self.issue)

        txn = PointTransaction.objects.get(contribution=contrib)
        self.assertEqual(txn.status, 'AWARDED')
        self.assertEqual(txn.points, 50)

        self.participant.refresh_from_db()
        self.assertEqual(self.participant.total_points, 50)
        self.assertEqual(self.participant.merged_count, 1)

    def test_02_closed_without_merge_treated_as_rejected(self):
        """PR closed without merge must NEVER award points and must transition to REJECTED."""
        payload = {
            'action': 'closed',
            'pull_request': {
                'id': 9002,
                'number': 102,
                'title': 'feat: Incomplete attempt (CR-100)',
                'body': 'Resolves #100',
                'head': {'sha': '11112222', 'ref': 'wip'},
                'base': {'ref': 'main'},
                'user': {'id': self.participant.github_id, 'login': 'test_dev'},
                'merged': False,
                'merged_at': None,
            },
            'repository': {
                'id': self.project.github_repo_id,
                'full_name': self.project.full_name,
            },
        }

        res = handle_pull_request_event(payload)
        self.assertEqual(res['status'], 'pr_rejected')

        pr = PullRequest.objects.get(github_pr_id=9002)
        self.assertFalse(pr.merged)

        txns = PointTransaction.objects.filter(contribution__pull_request=pr)
        self.assertEqual(txns.count(), 0)

        self.participant.refresh_from_db()
        self.assertEqual(self.participant.total_points, 0)

    def test_03_missed_webhook_recovered_by_reconciliation(self):
        """Missed webhook delivery is discovered and processed by Celery reconciliation."""
        mock_client = MagicMock(spec=GitHubClient)
        mock_client.get_issues.return_value = []
        mock_client.get_pull_requests.return_value = [
            {
                'id': 9003,
                'number': 103,
                'title': 'feat: Solve #100',
                'body': 'Fixes #100',
                'head': {'sha': 'deadbeef9999', 'ref': 'patch-1'},
                'base': {'ref': 'main'},
                'user': {'id': self.participant.github_id, 'login': 'test_dev'},
                'state': 'closed',
                'merged': True,
                'merged_at': timezone.now().isoformat(),
            }
        ]

        result = reconcile_repository(self.project, client=mock_client)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['prs_reconciled'], 1)

        pr = PullRequest.objects.get(github_pr_id=9003)
        self.assertTrue(pr.merged)

        contrib = Contribution.objects.get(pull_request=pr)
        self.assertEqual(contrib.status, 'MERGED')

        self.participant.refresh_from_db()
        self.assertEqual(self.participant.total_points, 50)

    def test_04_idempotent_repeated_delivery(self):
        """Repeated webhook or reconciliation delivery does not create duplicate points."""
        payload = {
            'action': 'closed',
            'pull_request': {
                'id': 9004,
                'number': 104,
                'title': 'feat: Implement (CR-100)',
                'body': 'Fixes #100',
                'head': {'sha': 'aaaa1111', 'ref': 'main'},
                'base': {'ref': 'main'},
                'user': {'id': self.participant.github_id, 'login': 'test_dev'},
                'merged': True,
                'merged_at': timezone.now().isoformat(),
            },
            'repository': {
                'id': self.project.github_repo_id,
                'full_name': self.project.full_name,
            },
        }

        # First delivery
        handle_pull_request_event(payload)
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.total_points, 50)
        self.assertEqual(PointTransaction.objects.filter(participant=self.participant).count(), 1)

        # Second delivery (duplicate)
        res2 = handle_pull_request_event(payload)
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.total_points, 50)
        self.assertEqual(PointTransaction.objects.filter(participant=self.participant).count(), 1)

    def test_05_daily_cap_enforced(self):
        """Enforces 120-pt daily cap in IST timezone."""
        issue2 = Issue.objects.create(
            project=self.project,
            github_issue_id=66666,
            number=102,
            title='Issue 2 (CR-102)',
            difficulty='HARD',
            category='BACKEND',
            points=50,
            status='open',
        )
        issue3 = Issue.objects.create(
            project=self.project,
            github_issue_id=77777,
            number=103,
            title='Issue 3 (CR-103)',
            difficulty='HARD',
            category='BACKEND',
            points=50,
            status='open',
        )

        for idx, iss in enumerate([self.issue, issue2, issue3], start=1):
            payload = {
                'action': 'closed',
                'pull_request': {
                    'id': 9100 + idx,
                    'number': 200 + idx,
                    'title': f'Fix {iss.number}',
                    'body': f'Fixes #{iss.number}',
                    'head': {'sha': f'sha{idx}', 'ref': 'main'},
                    'base': {'ref': 'main'},
                    'user': {'id': self.participant.github_id, 'login': 'test_dev'},
                    'merged': True,
                    'merged_at': timezone.now().isoformat(),
                },
                'repository': {
                    'id': self.project.github_repo_id,
                    'full_name': self.project.full_name,
                },
            }
            handle_pull_request_event(payload)

        self.participant.refresh_from_db()
        # First 50 + second 50 + third capped at 20 = 120 max
        self.assertEqual(self.participant.total_points, 120)

    def test_06_pipeline_consistency_checker_identifies_broken_stage(self):
        """Checker accurately identifies first broken stage when contribution or transaction is missing."""
        checker = PipelineConsistencyChecker()

        # Create a PR that was merged on GitHub but has no contribution
        pr = PullRequest.objects.create(
            repo=self.project,
            github_pr_id=9999,
            number=999,
            author_github_id=self.participant.github_id,
            author_participant=self.participant,
            merged=True,
            merged_at=timezone.now(),
        )

        check_res = checker.check_single_pr(pr.number, auto_repair=False)
        self.assertFalse(check_res['is_consistent'])
        self.assertEqual(check_res['first_broken_stage'], 'contribution_missing')

        # Auto repair fixes it
        repair_res = checker.check_single_pr(pr.number, auto_repair=True)
        self.assertTrue(repair_res['repaired'])

    def test_07_health_monitor_probes_subsystems(self):
        """HealthMonitor returns healthy subsystem statuses and heartbeats."""
        HealthMonitor.record_worker_heartbeat()
        HealthMonitor.record_beat_heartbeat()

        monitor = HealthMonitor()
        status_report = monitor.check_system_health(include_consistency=False)

        self.assertIn(status_report['overall_status'], ('HEALTHY', 'DEGRADED'))
        self.assertIn(status_report['database']['status'], ('HEALTHY', 'DEGRADED'))
        self.assertIn(status_report['redis']['status'], ('HEALTHY', 'DEGRADED'))
        self.assertEqual(status_report['celery_worker']['status'], 'HEALTHY')
        self.assertEqual(status_report['celery_beat']['status'], 'HEALTHY')

    def test_08_alerting_deduplication_and_resolution(self):
        """Alerts are deduplicated and resolution alerts are dispatched automatically."""
        mgr = NotificationManager()

        # First alert dispatched
        res1 = mgr.send_alert(
            title="Pipeline Interruption Test",
            message="Test error",
            severity=AlertSeverity.ERROR,
            alert_key="test:alert:1",
            context={"pr": 999},
        )
        self.assertTrue(res1)

        # Immediate duplicate suppressed
        res2 = mgr.send_alert(
            title="Pipeline Interruption Test",
            message="Test error duplicate",
            severity=AlertSeverity.ERROR,
            alert_key="test:alert:1",
        )
        self.assertFalse(res2)

        # Resolution dispatched
        res3 = mgr.resolve_alert(
            title="Pipeline Interruption Test",
            resolution_message="System self-healed.",
            alert_key="test:alert:1",
        )
        self.assertTrue(res3)

    def test_09_pipeline_tracer_logs_cleanly(self):
        """Pipeline tracer records structured state transitions without credentials."""
        tracer = PipelineTracer(repo="Hackit-DROID/Open-Source-Contribution-Drive", pr_number=1530)
        tracer.trace(PipelineStage.WEBHOOK_RECEIVED, details={"delivery_id": "wh_123"})
        tracer.trace(PipelineStage.SCORING_COMPLETED, details={"points": 50, "status": "AWARDED"})

        history = tracer.get_history()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]['stage'], 'webhook_received')
        self.assertEqual(history[1]['stage'], 'scoring_completed')

    def test_10_celery_heartbeat_and_monitor_tasks(self):
        """Beat, worker, and monitor Celery tasks run successfully."""
        res_beat = beat_heartbeat_task()
        self.assertEqual(res_beat['status'], 'ok')

        res_worker = worker_heartbeat_task()
        self.assertEqual(res_worker['status'], 'ok')

        res_mon = pipeline_health_monitor_task()
        self.assertIn('overall_status', res_mon)
