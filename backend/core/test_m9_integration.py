import datetime
import json
from unittest.mock import MagicMock, patch
from django.contrib.auth import get_user_model
from django.test import TestCase
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
from core.github_sync import (
    GitHubAPIError,
    GitHubAuthenticationError,
    GitHubMergeConflictError,
    GitHubNetworkError,
    GitHubRateLimitError,
    GitHubResourceNotFoundError,
)
from core.merge_service import execute_merge, claim_next_approved_contribution
from core.points import award_points_for_contribution
from core.state_machine import transition_contribution
from core.validation import validate_contribution
from core.webhook_processing import process_webhook_event

User = get_user_model()


class M9T2EndToEndPipelineIntegrationTests(TestCase):
    """
    M9-T2: End-to-End Contribution Pipeline Integration Suite (PRD §10, §11, §12, §13, §14, plan.md M9-T2).
    Simulates complete real-world flow from Webhook Event -> Validation -> Merge Bot -> Point Award -> Leaderboard.
    """

    def setUp(self):
        self.config = EventConfig.get_solo()
        self.config.submissions_paused = False
        self.config.validation_paused = False
        self.config.merge_paused = False
        self.config.leaderboard_frozen = False
        self.config.max_contributions_per_day = 5
        self.config.max_points_per_day = 500
        self.config.merge_concurrency = 5
        self.config.save()

        self.user = User.objects.create_user(username='integrator_sam', password='Password123!')
        self.participant = Participant.objects.create(
            user=self.user,
            github_id=990001,
            github_username='integrator_sam',
            total_points=0,
            merged_count=0,
        )

        self.project = Project.objects.create(
            github_repo_id=770001,
            owner='hackit-integ',
            name='pipeline-service',
            full_name='hackit-integ/pipeline-service',
            language='Python',
            is_enabled=True,
        )

        self.issue = Issue.objects.create(
            github_issue_id=550001,
            project=self.project,
            number=42,
            title='Implement streaming response decoder',
            points=100,
            difficulty='intermediate',
            category='backend',
            status='open',
            created_by_github_id=110001,  # Legitimate third-party author
        )

    @patch('core.tasks.process_merge_queue_task.delay')
    @patch('core.merge_service.GitHubClient')
    def test_full_successful_pipeline_flow(self, mock_gh_class, mock_merge_queue_delay):
        """1. Full canonical flow: Webhook -> Contribution -> Validation -> Merge -> Points -> Invariants."""
        # 1. Inbound PR Opened Webhook
        payload = {
            'action': 'opened',
            'pull_request': {
                'id': 880042,
                'number': 105,
                'title': 'Fixes #42 Implement streaming response decoder',
                'body': 'Closes #42 with unit tests.',
                'head': {'sha': 'deadbeef12345678', 'ref': 'feat-decoder'},
                'user': {'id': 990001, 'login': 'integrator_sam'},
                'merged': False,
                'merged_at': None,
            },
            'repository': {
                'id': 770001,
                'name': 'pipeline-service',
                'full_name': 'hackit-integ/pipeline-service',
                'owner': {'login': 'hackit-integ'},
            },
        }

        webhook_event = WebhookEvent.objects.create(
            delivery_id='delivery-integ-001',
            event_type='pull_request',
            payload=payload,
        )

        webhook_res = process_webhook_event(webhook_event)
        self.assertEqual(webhook_res['status'], 'contribution_created')

        contrib = Contribution.objects.get(pull_request__github_pr_id=880042)
        self.assertEqual(contrib.status, 'PENDING')
        self.assertEqual(contrib.participant, self.participant)
        self.assertEqual(contrib.issue, self.issue)

        # 2. Pre-check Stage: PENDING -> QUEUED
        from core.state_machine import process_pending_contribution
        queued_contrib, q_status = process_pending_contribution(contrib.id)
        self.assertEqual(q_status, 'QUEUED')
        self.assertEqual(queued_contrib.status, 'QUEUED')

        # 3. Validation Stage: QUEUED -> APPROVED
        val_res = validate_contribution(contrib.id)
        self.assertEqual(val_res['status'], 'approved')
        mock_merge_queue_delay.assert_called_once()

        contrib.refresh_from_db()
        self.assertEqual(contrib.status, 'APPROVED')
        self.assertIsNotNone(contrib.approved_at)

        # 3. Merge Queue Dispatch & Execution
        mock_client = MagicMock()
        mock_gh_class.return_value = mock_client
        mock_client.merge_pull_request.return_value = {
            'sha': 'merged_sha_99999',
            'merged': True,
            'message': 'Pull Request successfully merged',
        }
        mock_client.get_pull_request.return_value = {
            'id': 880042,
            'number': 105,
            'merged': True,
            'merged_at': timezone.now().isoformat(),
        }

        merge_res = execute_merge(contrib.id, client=mock_client)
        self.assertEqual(merge_res['status'], 'success')
        self.assertTrue(merge_res['merged'])
        self.assertEqual(merge_res['points']['status'], 'AWARDED')
        self.assertEqual(merge_res['points']['points'], 100)

        # 4. Invariant Verification
        contrib.refresh_from_db()
        self.assertEqual(contrib.status, 'MERGED')
        self.assertIsNotNone(contrib.merged_at)

        self.participant.refresh_from_db()
        self.assertEqual(self.participant.total_points, 100)
        self.assertEqual(self.participant.merged_count, 1)

        # Point transaction ledger
        pt = PointTransaction.objects.get(contribution=contrib, status='AWARDED')
        self.assertEqual(pt.points, 100)

        # Daily usage
        today = timezone.now().date()
        usage = DailyContributionUsage.objects.get(participant=self.participant, date=today)
        self.assertEqual(usage.contributions_count, 1)
        self.assertEqual(usage.points_count, 100)

    @patch('core.tasks.validate_contribution_task.delay')
    def test_self_created_issue_abuse_rejection(self, mock_val_delay):
        """2. PR against issue created by same author is rejected per PRD §22 anti-farming rules."""
        farming_issue = Issue.objects.create(
            github_issue_id=550002,
            project=self.project,
            number=99,
            title='Self created farming issue',
            points=100,
            status='open',
            created_by_github_id=990001,  # Same as participant github_id!
        )

        pr = PullRequest.objects.create(
            github_pr_id=880099,
            repo=self.project,
            number=106,
            author_github_id=self.participant.github_id,
            author_participant=self.participant,
        )
        contrib = Contribution.objects.create(
            participant=self.participant,
            issue=farming_issue,
            pull_request=pr,
            status='QUEUED',
        )

        val_res = validate_contribution(contrib.id)
        self.assertEqual(val_res['status'], 'rejected')
        self.assertIn('Self-created issue', val_res['reason'])

        contrib.refresh_from_db()
        self.assertEqual(contrib.status, 'REJECTED')
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.total_points, 0)

    @patch('core.merge_service.GitHubClient')
    def test_merge_conflict_retry_and_exhaustion_escalation(self, mock_gh_class):
        """3. Merge conflict transitions to RETRY, and upon exhaustion escalates to FLAGGED."""
        mock_client = MagicMock()
        mock_gh_class.return_value = mock_client
        mock_client.merge_pull_request.side_effect = GitHubMergeConflictError("Merge conflict on PR #107")
        mock_client.get_pull_request.return_value = {'merged': False}

        pr = PullRequest.objects.create(
            github_pr_id=880107,
            repo=self.project,
            number=107,
            author_github_id=self.participant.github_id,
            author_participant=self.participant,
        )
        contrib = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=pr,
            status='APPROVED',
            retry_count=0,
        )

        # Attempt 1: should transition to RETRY with retry_count = 1
        res1 = execute_merge(contrib.id, client=mock_client)
        self.assertEqual(res1['status'], 'retry')

        contrib.refresh_from_db()
        self.assertEqual(contrib.status, 'RETRY')
        self.assertEqual(contrib.retry_count, 1)

        # Attempt 2 (exhausted retries): should escalate to FLAGGED
        contrib.status = 'APPROVED'
        contrib.retry_count = 1  # MAX_MERGE_RETRIES = 1 for conflict
        contrib.save()

        res2 = execute_merge(contrib.id, client=mock_client)
        self.assertEqual(res2['status'], 'flagged')

        contrib.refresh_from_db()
        self.assertEqual(contrib.status, 'FLAGGED')
        self.assertIn('conflict', contrib.flagged_reason.lower())

    @patch('core.merge_service.GitHubClient')
    def test_github_rate_limit_429_preserves_state_for_requeue(self, mock_gh_class):
        """4. GitHub 429 rate limit returns rate_limited status without corrupting contribution."""
        mock_client = MagicMock()
        mock_gh_class.return_value = mock_client
        mock_client.merge_pull_request.side_effect = GitHubRateLimitError(
            message="Rate limit reached",
            remaining=0,
            limit=5000,
            reset_timestamp=int(timezone.now().timestamp()) + 60,
            retry_after=60,
        )

        pr = PullRequest.objects.create(
            github_pr_id=880108,
            repo=self.project,
            number=108,
            author_github_id=self.participant.github_id,
            author_participant=self.participant,
        )
        contrib = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=pr,
            status='APPROVED',
        )

        res = execute_merge(contrib.id, client=mock_client)
        self.assertEqual(res['status'], 'rate_limited')
        self.assertGreaterEqual(res['retry_after'], 10)

        contrib.refresh_from_db()
        self.assertEqual(contrib.status, 'MERGING')  # Active in-flight merge state preserved for task retry

    @patch('core.merge_service.GitHubClient')
    def test_github_transient_500_exponential_backoff_and_exhaustion(self, mock_gh_class):
        """5. GitHub 500 error retries with backoff and escalates to FLAGGED after max attempts."""
        mock_client = MagicMock()
        mock_gh_class.return_value = mock_client
        mock_client.merge_pull_request.side_effect = GitHubAPIError("Internal Server Error HTTP 500")

        pr = PullRequest.objects.create(
            github_pr_id=880109,
            repo=self.project,
            number=109,
            author_github_id=self.participant.github_id,
            author_participant=self.participant,
        )
        contrib = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=pr,
            status='APPROVED',
            retry_count=0,
        )

        # Attempt 1: retry
        res1 = execute_merge(contrib.id, client=mock_client)
        self.assertEqual(res1['status'], 'retry')
        self.assertEqual(res1['countdown'], 1)  # 2^0 = 1s

        # Attempt 5 (max retries reached): escalates to FLAGGED
        contrib.status = 'APPROVED'
        contrib.retry_count = 5
        contrib.save()

        res5 = execute_merge(contrib.id, client=mock_client)
        self.assertEqual(res5['status'], 'flagged')

        contrib.refresh_from_db()
        self.assertEqual(contrib.status, 'FLAGGED')
        self.assertIn('500', contrib.flagged_reason)

    @patch('core.merge_service.GitHubClient')
    def test_idempotent_duplicate_merge_calls(self, mock_gh_class):
        """6. Multiple sequential execute_merge calls on already MERGED contribution do not duplicate points."""
        mock_client = MagicMock()
        mock_gh_class.return_value = mock_client
        mock_client.merge_pull_request.return_value = {
            'sha': 'sha_idem_123',
            'merged': True,
        }
        mock_client.get_pull_request.return_value = {
            'id': 880110,
            'number': 110,
            'merged': True,
            'merged_at': timezone.now().isoformat(),
        }

        pr = PullRequest.objects.create(
            github_pr_id=880110,
            repo=self.project,
            number=110,
            author_github_id=self.participant.github_id,
            author_participant=self.participant,
        )
        contrib = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=pr,
            status='APPROVED',
        )

        res1 = execute_merge(contrib.id, client=mock_client)
        self.assertEqual(res1['status'], 'success')
        self.assertTrue(res1['merged'])
        self.assertEqual(res1['points']['status'], 'AWARDED')
        self.assertEqual(res1['points']['points'], 100)

        # Second execute_merge call
        res2 = execute_merge(contrib.id, client=mock_client)
        self.assertEqual(res2['status'], 'success')
        self.assertTrue(res2['merged'])
        self.assertEqual(res2['points']['status'], 'ALREADY_AWARDED')

        self.participant.refresh_from_db()
        self.assertEqual(self.participant.total_points, 100)  # Exactly 100, not 200!
        self.assertEqual(PointTransaction.objects.filter(contribution=contrib, status='AWARDED').count(), 1)

