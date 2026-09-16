from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.crash_recovery import requeue_stale_contributions
from core.models import (
    Contribution,
    Issue,
    Participant,
    Project,
    PullRequest,
)
from core.tasks import requeue_stale_contributions_task

User = get_user_model()


class CrashRecoveryM5TestCase(TestCase):
    """
    Unit & Integration test suite for M5-T3: Worker Crash Recovery Sweep.
    Verifies that stuck workers in UNDER_REVIEW/MERGING are recovered to
    their prior queued states after the lock timeout without corrupting
    active or terminal contributions.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='carol', email='carol@example.com')
        self.participant = Participant.objects.create(
            user=self.user,
            github_id=77777,
            github_username='carol',
            avatar_url='https://github.com/carol.png',
        )

        self.project = Project.objects.create(
            github_repo_id=3001,
            owner='hackit',
            name='recovery-repo',
            full_name='hackit/recovery-repo',
            language='Python',
            is_enabled=True,
        )

        self.issue = Issue.objects.create(
            github_issue_id=9001,
            project=self.project,
            number=1,
            title='Crash recovery benchmark issue',
            points=50,
            status='open',
        )

        self.pr = PullRequest.objects.create(
            github_pr_id=9101,
            repo=self.project,
            number=10,
            author_github_id=self.participant.github_id,
            author_participant=self.participant,
        )

    def test_requeue_stale_under_review_contribution(self):
        now = timezone.now()
        stale_time = now - timedelta(minutes=15)  # past 10-min timeout

        contrib = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=self.pr,
            status='UNDER_REVIEW',
            sub_status='VALIDATING',
            locked_at=stale_time,
        )

        with patch('core.tasks.validate_contribution_task.delay') as mock_delay:
            result = requeue_stale_contributions(timeout_minutes=10, re_enqueue=True)
            self.assertIn(contrib.id, result['recovered_under_review'])
            mock_delay.assert_called_once_with(contrib.id)

        contrib.refresh_from_db()
        self.assertEqual(contrib.status, 'QUEUED')
        self.assertEqual(contrib.sub_status, '')
        self.assertIsNone(contrib.locked_at)

    def test_active_under_review_contribution_not_requeued(self):
        now = timezone.now()
        active_time = now - timedelta(minutes=2)  # within 10-min timeout

        contrib = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=self.pr,
            status='UNDER_REVIEW',
            sub_status='VALIDATING',
            locked_at=active_time,
        )

        result = requeue_stale_contributions(timeout_minutes=10, re_enqueue=True)
        self.assertNotIn(contrib.id, result['recovered_under_review'])

        contrib.refresh_from_db()
        self.assertEqual(contrib.status, 'UNDER_REVIEW')
        self.assertEqual(contrib.locked_at, active_time)

    def test_requeue_stale_merging_contribution(self):
        now = timezone.now()
        stale_time = now - timedelta(minutes=20)

        contrib = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=self.pr,
            status='MERGING',
            locked_at=stale_time,
        )

        result = requeue_stale_contributions(timeout_minutes=10)
        self.assertIn(contrib.id, result['recovered_merging'])

        contrib.refresh_from_db()
        self.assertEqual(contrib.status, 'APPROVED')
        self.assertIsNone(contrib.locked_at)

    def test_active_merging_contribution_not_requeued(self):
        now = timezone.now()
        active_time = now - timedelta(minutes=3)

        contrib = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=self.pr,
            status='MERGING',
            locked_at=active_time,
        )

        result = requeue_stale_contributions(timeout_minutes=10)
        self.assertNotIn(contrib.id, result['recovered_merging'])

        contrib.refresh_from_db()
        self.assertEqual(contrib.status, 'MERGING')
        self.assertEqual(contrib.locked_at, active_time)

    def test_terminal_contributions_never_modified_by_sweep(self):
        stale_time = timezone.now() - timedelta(minutes=60)

        merged_contrib = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=self.pr,
            status='MERGED',
            locked_at=stale_time,
        )

        pr2 = PullRequest.objects.create(
            github_pr_id=9102,
            repo=self.project,
            number=11,
            author_github_id=self.participant.github_id,
        )
        rejected_contrib = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=pr2,
            status='REJECTED',
            locked_at=stale_time,
        )

        result = requeue_stale_contributions(timeout_minutes=10)
        self.assertEqual(result['total_recovered'], 0)

        merged_contrib.refresh_from_db()
        self.assertEqual(merged_contrib.status, 'MERGED')

        rejected_contrib.refresh_from_db()
        self.assertEqual(rejected_contrib.status, 'REJECTED')

    def test_requeue_stale_contributions_celery_task(self):
        now = timezone.now()
        stale_time = now - timedelta(minutes=15)

        contrib = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=self.pr,
            status='UNDER_REVIEW',
            locked_at=stale_time,
        )

        result = requeue_stale_contributions_task.apply().get()
        self.assertEqual(result['status'], 'completed')
        self.assertIn(contrib.id, result['recovered_under_review'])

        contrib.refresh_from_db()
        self.assertEqual(contrib.status, 'QUEUED')
