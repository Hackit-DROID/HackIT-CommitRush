import datetime
from unittest.mock import MagicMock, patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.github_sync import (
    GitHubAPIError,
    GitHubAuthenticationError,
    GitHubClient,
    GitHubMergeConflictError,
    GitHubNetworkError,
    GitHubRateLimitError,
    GitHubResourceNotFoundError,
)
from core.merge_service import (
    MERGE_CONFLICT_MAX_RETRIES,
    TRANSIENT_MERGE_MAX_RETRIES,
    claim_next_approved_contribution,
    execute_merge,
)
from core.models import (
    Contribution,
    EventConfig,
    Issue,
    Participant,
    PointTransaction,
    Project,
    PullRequest,
)
from core.tasks import merge_contribution_task, process_merge_queue_task

User = get_user_model()


class MergeServicePipelineAndRetryTests(TestCase):
    """
    Comprehensive test suite for M6-T2, M6-T3, and M6-T4.
    """

    def setUp(self):
        self.config = EventConfig.get_solo()
        self.config.merge_concurrency = 3
        self.config.merge_paused = False
        self.config.save()

        self.user = User.objects.create_user(username='charlie', password='password123')
        self.participant = Participant.objects.create(
            user=self.user,
            github_id=55555,
            github_username='charlie',
            total_points=0,
        )

        self.project = Project.objects.create(
            github_repo_id=999111,
            owner='hackit',
            name='merge-repo',
            full_name='hackit/merge-repo',
            is_enabled=True,
        )

        self.issue = Issue.objects.create(
            github_issue_id=333,
            project=self.project,
            number=42,
            title='Fix critical race condition',
            points=100,
            status='open',
        )

        self.pr = PullRequest.objects.create(
            github_pr_id=444,
            repo=self.project,
            number=101,
            author_github_id=self.participant.github_id,
            author_participant=self.participant,
            head_sha='abc123sha',
            merged=False,
        )

        self.contribution = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=self.pr,
            status='APPROVED',
            approved_at=timezone.now(),
        )

    # -------------------------------------------------------------------------
    # M6-T3: Priority and FIFO Ordering Tests
    # -------------------------------------------------------------------------

    def test_priority_item_claimed_before_older_non_priority_item(self):
        now = timezone.now()
        # Older non-priority contribution
        c_old = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=PullRequest.objects.create(
                github_pr_id=445,
                repo=self.project,
                number=102,
                author_github_id=self.participant.github_id,
            ),
            status='APPROVED',
            approved_at=now - datetime.timedelta(hours=2),
            is_priority=False,
        )
        # Newer priority contribution
        c_prio = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=PullRequest.objects.create(
                github_pr_id=446,
                repo=self.project,
                number=103,
                author_github_id=self.participant.github_id,
            ),
            status='APPROVED',
            approved_at=now - datetime.timedelta(minutes=5),
            is_priority=True,
        )

        # First claimed should be the priority contribution
        claimed1 = claim_next_approved_contribution()
        self.assertIsNotNone(claimed1)
        self.assertEqual(claimed1.id, c_prio.id)
        self.assertEqual(claimed1.status, 'MERGING')

        # Next claimed should be the older non-priority contribution
        claimed2 = claim_next_approved_contribution()
        self.assertIsNotNone(claimed2)
        self.assertEqual(claimed2.id, c_old.id)
        self.assertEqual(claimed2.status, 'MERGING')

    def test_fifo_ordering_for_same_priority_level(self):
        now = timezone.now()
        Contribution.objects.all().delete()

        c1 = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=PullRequest.objects.create(
                github_pr_id=501, repo=self.project, number=201, author_github_id=self.participant.github_id
            ),
            status='APPROVED',
            approved_at=now - datetime.timedelta(minutes=30),
            is_priority=False,
        )
        c2 = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=PullRequest.objects.create(
                github_pr_id=502, repo=self.project, number=202, author_github_id=self.participant.github_id
            ),
            status='APPROVED',
            approved_at=now - datetime.timedelta(minutes=10),
            is_priority=False,
        )

        claimed1 = claim_next_approved_contribution()
        self.assertEqual(claimed1.id, c1.id)

        claimed2 = claim_next_approved_contribution()
        self.assertEqual(claimed2.id, c2.id)

    def test_claim_respects_merge_paused(self):
        self.config.merge_paused = True
        self.config.save()

        claimed = claim_next_approved_contribution()
        self.assertIsNone(claimed)

        # Contribution remains in APPROVED status
        self.contribution.refresh_from_db()
        self.assertEqual(self.contribution.status, 'APPROVED')

    # -------------------------------------------------------------------------
    # M6-T2: Merge Pipeline Execution & GitHub State Authority Tests
    # -------------------------------------------------------------------------

    def test_execute_merge_happy_path_success(self):
        mock_client = MagicMock(spec=GitHubClient)
        mock_client.merge_pull_request.return_value = {
            'sha': 'commit_sha_merged',
            'merged': True,
            'message': 'Pull Request successfully merged',
        }
        mock_client.get_pull_request.return_value = {
            'id': 444,
            'number': 101,
            'merged': True,
            'merged_at': timezone.now().isoformat(),
        }

        res = execute_merge(self.contribution.id, client=mock_client)
        self.assertEqual(res['status'], 'success')
        self.assertTrue(res['merged'])

        # Verify Contribution status is MERGED
        self.contribution.refresh_from_db()
        self.assertEqual(self.contribution.status, 'MERGED')
        self.assertIsNotNone(self.contribution.merged_at)

        # Verify PullRequest record updated
        self.pr.refresh_from_db()
        self.assertTrue(self.pr.merged)

        # Verify points awarded
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.total_points, 100)
        self.assertTrue(PointTransaction.objects.filter(contribution=self.contribution, status='AWARDED').exists())

    def test_execute_merge_idempotency_already_merged(self):
        self.contribution.status = 'MERGED'
        self.contribution.merged_at = timezone.now()
        self.contribution.save()

        mock_client = MagicMock(spec=GitHubClient)
        res = execute_merge(self.contribution.id, client=mock_client)
        self.assertEqual(res['status'], 'success')

        # GitHub API should NOT be invoked if already merged
        mock_client.merge_pull_request.assert_not_called()

    # -------------------------------------------------------------------------
    # M6-T4: Bounded Retry Policy & Error Handling Tests
    # -------------------------------------------------------------------------

    def test_transient_5xx_error_retries_with_exponential_backoff(self):
        mock_client = MagicMock(spec=GitHubClient)
        mock_client.merge_pull_request.side_effect = GitHubAPIError("GitHub 500 Server Error")

        # Initial retry_count is 0
        self.assertEqual(self.contribution.retry_count, 0)

        res = execute_merge(self.contribution.id, client=mock_client)
        self.assertEqual(res['status'], 'retry')
        self.assertEqual(res['retry_type'], 'transient')
        self.assertEqual(res['countdown'], 1)  # 2^0 = 1s

        self.contribution.refresh_from_db()
        self.assertEqual(self.contribution.status, 'RETRY')
        self.assertEqual(self.contribution.retry_count, 1)

    def test_max_transient_retries_exceeded_escalates_to_flagged(self):
        self.contribution.retry_count = 4  # 5th attempt will exceed max retries (5)
        self.contribution.status = 'MERGING'
        self.contribution.save()

        mock_client = MagicMock(spec=GitHubClient)
        mock_client.merge_pull_request.side_effect = GitHubNetworkError("Connection timed out")

        res = execute_merge(self.contribution.id, client=mock_client)
        self.assertEqual(res['status'], 'flagged')

        self.contribution.refresh_from_db()
        self.assertEqual(self.contribution.status, 'FLAGGED')
        self.assertIn('Max transient merge retries', self.contribution.flagged_reason)

    def test_merge_conflict_first_attempt_transitions_to_retry(self):
        mock_client = MagicMock(spec=GitHubClient)
        mock_client.merge_pull_request.side_effect = GitHubMergeConflictError("Merge conflict on PR #101")
        mock_client.get_pull_request.return_value = {'merged': False}

        self.assertEqual(self.contribution.retry_count, 0)
        res = execute_merge(self.contribution.id, client=mock_client)
        self.assertEqual(res['status'], 'retry')
        self.assertEqual(res['retry_type'], 'conflict')

        self.contribution.refresh_from_db()
        self.assertEqual(self.contribution.status, 'RETRY')
        self.assertEqual(self.contribution.retry_count, 1)

    def test_merge_conflict_second_attempt_escalates_to_flagged(self):
        self.contribution.retry_count = 1  # 1 retry already performed
        self.contribution.status = 'MERGING'
        self.contribution.save()

        mock_client = MagicMock(spec=GitHubClient)
        mock_client.merge_pull_request.side_effect = GitHubMergeConflictError("Merge conflict on PR #101")
        mock_client.get_pull_request.return_value = {'merged': False}

        res = execute_merge(self.contribution.id, client=mock_client)
        self.assertEqual(res['status'], 'flagged')
        self.assertIn('Merge conflict', res['reason'])

        self.contribution.refresh_from_db()
        self.assertEqual(self.contribution.status, 'FLAGGED')
        self.assertIn('Merge conflict', self.contribution.flagged_reason)

    def test_github_rate_limit_returns_delay_without_flagging(self):
        mock_client = MagicMock(spec=GitHubClient)
        mock_client.merge_pull_request.side_effect = GitHubRateLimitError(
            "Rate limit reached",
            remaining=0,
            retry_after=120,
        )

        res = execute_merge(self.contribution.id, client=mock_client)
        self.assertEqual(res['status'], 'rate_limited')
        self.assertEqual(res['retry_after'], 120)

        # Contribution should not be flagged or fail
        self.contribution.refresh_from_db()
        self.assertNotEqual(self.contribution.status, 'FLAGGED')

    # -------------------------------------------------------------------------
    # Celery Tasks Integration Tests
    # -------------------------------------------------------------------------

    @patch('core.semaphore.RedisMergeSemaphore.acquire', return_value=True)
    @patch('core.semaphore.RedisMergeSemaphore.release', return_value=True)
    @patch('core.merge_service.execute_merge')
    def test_merge_contribution_task_runs_with_semaphore(self, mock_exec, mock_rel, mock_acq):
        mock_exec.return_value = {'status': 'success', 'contribution_id': self.contribution.id, 'merged': True}

        res = merge_contribution_task(self.contribution.id)
        self.assertEqual(res['status'], 'success')
        mock_acq.assert_called_once()
        mock_exec.assert_called_once_with(self.contribution.id)
        mock_rel.assert_called_once()

    @patch('core.tasks.merge_contribution_task.delay')
    def test_process_merge_queue_task_dispatches_approved_items(self, mock_delay):
        res = process_merge_queue_task(batch_size=5)
        self.assertEqual(res['status'], 'success')
        self.assertEqual(res['dispatched'], 1)
        mock_delay.assert_called_once_with(self.contribution.id)

    @patch('core.semaphore.RedisMergeSemaphore.acquire', return_value=True)
    @patch('core.semaphore.RedisMergeSemaphore.release', return_value=True)
    @patch('core.semaphore.RedisContributionLock.acquire')
    @patch('core.semaphore.RedisContributionLock.release')
    @patch('core.merge_service.execute_merge')
    def test_duplicate_merge_task_skipped_when_locked(self, mock_exec, mock_lock_rel, mock_lock_acq, mock_sem_rel, mock_sem_acq):
        # Simulate that RedisContributionLock.acquire() returns False (another worker holds lock)
        mock_lock_acq.return_value = False

        res = merge_contribution_task(self.contribution.id)
        self.assertEqual(res['status'], 'duplicate_skipped')
        self.assertEqual(res['contribution_id'], self.contribution.id)

        # execute_merge and global semaphore should NOT be called
        mock_exec.assert_not_called()
        mock_sem_acq.assert_not_called()
