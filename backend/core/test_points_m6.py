import datetime
from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from core.models import (
    Contribution,
    DailyContributionUsage,
    EventConfig,
    Issue,
    Participant,
    PointTransaction,
    Project,
    PullRequest,
)
from core.points import award_points_for_contribution

User = get_user_model()


class TransactionalPointAwardTests(TestCase):
    """
    Unit and integration tests for M6-T5: Transactional Point Awarding.
    Verifies:
    - Atomicity and row-locking on Participant and DailyContributionUsage.
    - Daily contribution and daily point cap enforcement from EventConfig.
    - DEFERRED status when over cap.
    - Suspended participant gating.
    - Exactly-once award guarantee (idempotency under duplicate execution).
    """

    def setUp(self):
        self.config = EventConfig.get_solo()
        self.config.max_contributions_per_day = 3
        self.config.max_points_per_day = 150
        self.config.category_multipliers = {'feature': 1.0}
        self.config.allow_partial_daily_points = False
        self.config.save()

        self.user = User.objects.create_user(username='alice', password='password123')
        self.participant = Participant.objects.create(
            user=self.user,
            github_id=123456,
            github_username='alice',
            total_points=0,
        )

        self.project = Project.objects.create(
            github_repo_id=987654,
            owner='hackit',
            name='awesome-repo',
            full_name='hackit/awesome-repo',
            is_enabled=True,
        )

        self.issue = Issue.objects.create(
            github_issue_id=111,
            project=self.project,
            number=1,
            title='Implement feature X',
            points=50,
            status='open',
        )

        self.pull_request = PullRequest.objects.create(
            github_pr_id=222,
            repo=self.project,
            number=10,
            author_github_id=self.participant.github_id,
            author_participant=self.participant,
            merged=True,
            merged_at=timezone.now(),
        )

        self.contribution = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=self.pull_request,
            status='MERGED',
            merged_at=timezone.now(),
        )

    def test_award_points_under_caps_success(self):
        res = award_points_for_contribution(self.contribution.id)
        self.assertEqual(res['status'], 'AWARDED')
        self.assertEqual(res['points'], 50)

        # Verify participant total points updated
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.total_points, 50)

        # Verify PointTransaction ledger entry created
        pt = PointTransaction.objects.get(id=res['transaction_id'])
        self.assertEqual(pt.status, 'AWARDED')
        self.assertEqual(pt.points, 50)
        self.assertEqual(pt.participant, self.participant)
        self.assertEqual(pt.contribution, self.contribution)

        # Verify DailyContributionUsage tracked
        today = timezone.now().date()
        usage = DailyContributionUsage.objects.get(participant=self.participant, date=today)
        self.assertEqual(usage.contributions_count, 1)
        self.assertEqual(usage.points_count, 50)

    def test_award_points_exactly_once_idempotency(self):
        # First call awards points
        res1 = award_points_for_contribution(self.contribution.id)
        self.assertEqual(res1['status'], 'AWARDED')
        self.assertEqual(res1['points'], 50)

        # Second call returns ALREADY_AWARDED without adding points
        res2 = award_points_for_contribution(self.contribution.id)
        self.assertEqual(res2['status'], 'ALREADY_AWARDED')
        self.assertEqual(res2['points'], 50)

        self.participant.refresh_from_db()
        self.assertEqual(self.participant.total_points, 50)

        # Only 1 PointTransaction should exist for this contribution
        self.assertEqual(PointTransaction.objects.filter(contribution=self.contribution).count(), 1)

    def test_daily_contribution_cap_exceeded_defers_points(self):
        # Daily contribution cap is 3. Set existing usage to 3.
        today = timezone.now().date()
        DailyContributionUsage.objects.create(
            participant=self.participant,
            date=today,
            contributions_count=3,
            points_count=100,
        )
        self.participant.total_points = 100
        self.participant.save()

        res = award_points_for_contribution(self.contribution.id)
        self.assertEqual(res['status'], 'DEFERRED')
        self.assertEqual(res['points'], 0)
        self.assertIn('Daily limit exceeded', res['reason'])

        # Participant total points remains 100
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.total_points, 100)

        # PointTransaction is recorded as DEFERRED with 0 points
        pt = PointTransaction.objects.get(id=res['transaction_id'])
        self.assertEqual(pt.status, 'DEFERRED')
        self.assertEqual(pt.points, 0)

    def test_daily_points_cap_exceeded_defers_points(self):
        # Daily points cap is 150. If user has 120 points and tries to earn 50 (120+50 = 170 > 150)
        today = timezone.now().date()
        DailyContributionUsage.objects.create(
            participant=self.participant,
            date=today,
            contributions_count=1,
            points_count=120,
        )
        self.participant.total_points = 120
        self.participant.save()

        res = award_points_for_contribution(self.contribution.id)
        self.assertEqual(res['status'], 'DEFERRED')
        self.assertEqual(res['points'], 0)

        self.participant.refresh_from_db()
        self.assertEqual(self.participant.total_points, 120)

    def test_suspended_participant_defers_points(self):
        self.participant.is_suspended = True
        self.participant.save()

        res = award_points_for_contribution(self.contribution.id)
        self.assertEqual(res['status'], 'DEFERRED')
        self.assertEqual(res['points'], 0)

        self.participant.refresh_from_db()
        self.assertEqual(self.participant.total_points, 0)

        pt = PointTransaction.objects.get(id=res['transaction_id'])
        self.assertEqual(pt.status, 'DEFERRED')
        self.assertIn('suspended', pt.reason)


class ConcurrentPointAwardRaceTests(TransactionTestCase):
    """
    Multi-threaded concurrency tests for transactional point limits and race safety (PRD §14, §15, Plan M6-T5).
    """

    def setUp(self):
        self.config = EventConfig.get_solo()
        self.config.max_contributions_per_day = 2
        self.config.max_points_per_day = 100
        self.config.category_multipliers = {'feature': 1.0}
        self.config.allow_partial_daily_points = False
        self.config.save()

        self.user = User.objects.create_user(username='concurrent_bob', password='password123')
        self.participant = Participant.objects.create(
            user=self.user,
            github_id=777123,
            github_username='concurrent_bob',
            total_points=0,
        )

        self.project = Project.objects.create(
            github_repo_id=888123,
            owner='hackit',
            name='race-repo',
            full_name='hackit/race-repo',
            is_enabled=True,
        )

        self.issue = Issue.objects.create(
            github_issue_id=999123,
            project=self.project,
            number=1,
            title='Race condition issue',
            points=50,
            status='open',
        )

        # Create 5 distinct contributions for the same participant
        self.contributions = []
        for i in range(1, 6):
            pr = PullRequest.objects.create(
                github_pr_id=1000 + i,
                repo=self.project,
                number=i,
                author_github_id=self.participant.github_id,
                author_participant=self.participant,
                merged=True,
            )
            c = Contribution.objects.create(
                participant=self.participant,
                issue=self.issue,
                pull_request=pr,
                status='MERGED',
            )
            self.contributions.append(c)

    def test_concurrent_threads_competing_at_daily_cap(self):
        from django.db import connection
        if connection.vendor == 'sqlite':
            self.skipTest('SQLite does not support row-level locking for concurrent writer threads')
        from concurrent.futures import ThreadPoolExecutor

        def worker(contrib_id):
            from django.db import connection
            try:
                return award_points_for_contribution(contrib_id)
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker, c.id) for c in self.contributions]
            results = [f.result() for f in futures]

        awarded_results = [r for r in results if r['status'] == 'AWARDED']
        deferred_results = [r for r in results if r['status'] == 'DEFERRED']

        # Exactly 2 should be AWARDED, and 3 should be DEFERRED
        self.assertEqual(len(awarded_results), 2)
        self.assertEqual(len(deferred_results), 3)

        self.participant.refresh_from_db()
        self.assertEqual(self.participant.total_points, 100)

        today = timezone.now().date()
        usage = DailyContributionUsage.objects.get(participant=self.participant, date=today)
        self.assertEqual(usage.contributions_count, 2)
        self.assertEqual(usage.points_count, 100)
