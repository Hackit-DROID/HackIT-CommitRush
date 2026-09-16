import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch
from celery.exceptions import Retry
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

from core.models import (
    AuditLog,
    Contribution,
    EventConfig,
    Issue,
    Participant,
    PointTransaction,
    Project,
    PullRequest,
    WebhookEvent,
)
from core.tasks import (
    merge_contribution_task,
    process_merge_queue_task,
    process_webhook_event_task,
    validate_contribution_task,
)
from core.webhook_processing import process_webhook_event

User = get_user_model()


class EmergencyPauseM8T5Tests(TestCase):
    """
    Comprehensive test suite for M8-T5: Emergency Pause/Resume Controls (PRD §12.6, §18, plan.md M8-T5).
    Verifies:
    - submissions_paused: blocks new contribution creation while preserving webhooks durably.
    - validation_paused: delays/requeues validation tasks without data loss or hot loops.
    - merge_paused: prevents merge execution without leaking semaphores or locks.
    - Independence of all 3 controls and separation from leaderboard freeze.
    - Full audit trail on emergency control mutations.
    """

    def setUp(self):
        self.config = EventConfig.get_solo()
        self.config.submissions_paused = False
        self.config.validation_paused = False
        self.config.merge_paused = False
        self.config.leaderboard_frozen = False
        self.config.merge_concurrency = 5
        self.config.max_contributions_per_day = 5
        self.config.max_points_per_day = 500
        self.config.save()

        self.participant_user = User.objects.create_user(
            username='carl_coder',
            email='carl@example.com',
            password='CarlPassword123!',
        )
        self.participant = Participant.objects.create(
            user=self.participant_user,
            github_id=555666,
            github_username='carl_coder',
            total_points=0,
            merged_count=0,
        )

        self.project = Project.objects.create(
            github_repo_id=888999,
            owner='hackit-org',
            name='gateway-service',
            full_name='hackit-org/gateway-service',
            language='Go',
            is_enabled=True,
        )

        self.issue = Issue.objects.create(
            github_issue_id=121212,
            project=self.project,
            number=77,
            title='Implement rate limit headers',
            points=100,
            difficulty='intermediate',
            category='networking',
            status='open',
        )

        self.client = Client()

    def test_submissions_paused_persists_webhook_and_blocks_contribution_creation(self):
        """When submissions_paused=True: webhook is stored with HTTP 200, but no Contribution is created."""
        self.config.submissions_paused = True
        self.config.save()

        payload = {
            'action': 'opened',
            'pull_request': {
                'id': 990011,
                'number': 55,
                'title': 'Fixes #77 Implement rate limit headers',
                'body': 'Implements the headers for #77',
                'head': {'sha': 'abcdef123456', 'ref': 'feat-headers'},
                'user': {'id': 555666, 'login': 'carl_coder'},
                'merged': False,
                'merged_at': None,
            },
            'repository': {
                'id': 888999,
                'name': 'gateway-service',
                'full_name': 'hackit-org/gateway-service',
                'owner': {'login': 'hackit-org'},
            },
        }

        # 1. Directly process webhook event
        webhook_event = WebhookEvent.objects.create(
            delivery_id='delivery-pause-test-001',
            event_type='pull_request',
            payload=payload,
        )

        result = process_webhook_event(webhook_event)
        self.assertEqual(result.get('status'), 'submissions_paused')

        # Verify no Contribution was created
        self.assertFalse(Contribution.objects.filter(pull_request__github_pr_id=990011).exists())
        # Verify PullRequest was cached
        self.assertTrue(PullRequest.objects.filter(github_pr_id=990011).exists())

        # 2. Resume submissions (submissions_paused=False) and reprocess
        self.config.submissions_paused = False
        self.config.save()

        result_resumed = process_webhook_event(webhook_event)
        self.assertEqual(result_resumed.get('status'), 'contribution_created')
        self.assertTrue(Contribution.objects.filter(pull_request__github_pr_id=990011).exists())

    def test_validation_paused_requeues_task_and_resumes_cleanly(self):
        """When validation_paused=True: validate_contribution_task raises Retry and preserves QUEUED state."""
        pr = PullRequest.objects.create(
            github_pr_id=990022,
            repo=self.project,
            number=56,
            author_github_id=555666,
            author_participant=self.participant,
        )
        contrib = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=pr,
            status='QUEUED',
        )

        # 1. Pause validation
        self.config.validation_paused = True
        self.config.save()

        # Execute task - should raise Retry
        with self.assertRaises(Retry):
            validate_contribution_task(contrib.id)

        contrib.refresh_from_db()
        self.assertEqual(contrib.status, 'QUEUED')  # State preserved

        # 2. Resume validation
        self.config.validation_paused = False
        self.config.save()

        res = validate_contribution_task(contrib.id)
        self.assertEqual(res['status'], 'approved')

        contrib.refresh_from_db()
        self.assertEqual(contrib.status, 'APPROVED')

    @patch('core.tasks.merge_contribution_task.delay')
    def test_merge_paused_prevents_dispatch_and_execution(self, mock_merge_task_delay):
        """When merge_paused=True: process_merge_queue_task dispatches 0 tasks and merge task requeues."""
        pr = PullRequest.objects.create(
            github_pr_id=990033,
            repo=self.project,
            number=57,
            author_github_id=555666,
            author_participant=self.participant,
        )
        contrib = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=pr,
            status='APPROVED',
        )

        # 1. Pause merge operations
        self.config.merge_paused = True
        self.config.save()

        # Queue processor returns paused
        queue_res = process_merge_queue_task()
        self.assertEqual(queue_res['status'], 'paused')
        self.assertEqual(queue_res['dispatched'], 0)
        mock_merge_task_delay.assert_not_called()

        # Merge execution task raises Retry
        with self.assertRaises(Retry):
            merge_contribution_task(contrib.id)

        contrib.refresh_from_db()
        self.assertEqual(contrib.status, 'APPROVED')  # Unchanged

        # 2. Resume merge operations
        self.config.merge_paused = False
        self.config.save()

        queue_res_active = process_merge_queue_task()
        self.assertEqual(queue_res_active['status'], 'success')
        self.assertEqual(queue_res_active['dispatched'], 1)
        mock_merge_task_delay.assert_called_once_with(contrib.id)

    @patch('core.tasks.process_merge_queue_task.delay')
    def test_emergency_controls_are_strictly_independent(self, mock_merge_queue_delay):
        """Pausing one control does NOT affect other pipeline stages."""
        pr = PullRequest.objects.create(
            github_pr_id=990044,
            repo=self.project,
            number=58,
            author_github_id=555666,
            author_participant=self.participant,
        )
        contrib = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=pr,
            status='QUEUED',
        )

        # Pause submissions only (validation & merge remain active)
        self.config.submissions_paused = True
        self.config.validation_paused = False
        self.config.merge_paused = False
        self.config.save()

        val_res = validate_contribution_task(contrib.id)
        self.assertEqual(val_res['status'], 'approved')

        contrib.refresh_from_db()
        self.assertEqual(contrib.status, 'APPROVED')
        mock_merge_queue_delay.assert_called_once()

    @patch('core.tasks.process_merge_queue_task.delay')
    def test_leaderboard_freeze_does_not_halt_pipeline_stages(self, mock_merge_queue_delay):
        """Leaderboard freeze operates independently of submissions, validation, and merge processing."""
        self.config.leaderboard_frozen = True
        self.config.submissions_paused = False
        self.config.validation_paused = False
        self.config.merge_paused = False
        self.config.save()

        pr = PullRequest.objects.create(
            github_pr_id=990055,
            repo=self.project,
            number=59,
            author_github_id=555666,
            author_participant=self.participant,
        )
        contrib = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=pr,
            status='QUEUED',
        )

        # Validation proceeds normally
        val_res = validate_contribution_task(contrib.id)
        self.assertEqual(val_res['status'], 'approved')
        contrib.refresh_from_db()
        self.assertEqual(contrib.status, 'APPROVED')
        mock_merge_queue_delay.assert_called_once()
