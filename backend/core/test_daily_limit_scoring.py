"""
Comprehensive Test Suite for HackIT CommitRush 120-Point Daily Limit & Competition Rules.
Tests:
- Each difficulty level (Beginner 5, Easy 10, Medium 20, Hard 30, Master 50)
- Exact 120 boundary (e.g. 70 + 50 = 120)
- Contribution below 120
- Contribution that would exceed 120 (e.g. 115 + 10 = 125 -> 0 points, daily score remains 115)
- Participant already at 120 (any further PR -> 0 points)
- Daily reset at 00:00 IST
- Duplicate PR (idempotency)
- Duplicate issue (single issue scoring)
- Unmerged PR (merged=False)
- Invalid CR issue
- Missing difficulty
- Different participants (independent quotas)
- Multiple PRs on the same day
- PRs merged on different days
- Rerunning workflow (idempotency)
- IST vs UTC boundary (proves 00:00 IST reset, not UTC midnight)
"""

import datetime
import os
from zoneinfo import ZoneInfo
from django.contrib.auth import get_user_model
from django.test import TestCase
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
    ScoringBreakdown,
)
from core.points import award_points_for_contribution
from core.scoring.constants import (
    DAILY_POINTS_CAP,
    DIFFICULTY_POINTS,
    EVENT_TIMEZONE,
    get_event_today,
)
from scripts.process_pr_scoring import process_merged_pr
from scripts.check_pr_daily_limit import evaluate_pr_daily_limit

User = get_user_model()


class CommitRushDailyLimitScoringTests(TestCase):
    """
    Test suite verifying the 120-point daily limit and anti-exploit requirements.
    """

    def setUp(self):
        self.config = EventConfig.get_solo()
        self.config.max_points_per_day = 120
        self.config.allow_partial_daily_points = False
        self.config.per_pr_max_points = 50
        self.config.target_branch = 'main'
        self.config.category_multipliers = {}  # Pure difficulty points
        self.config.save()

        self.project = Project.objects.create(
            github_repo_id=99901,
            owner='Hackit-DROID',
            name='Open-Source-Contribution-Drive',
            full_name='Hackit-DROID/Open-Source-Contribution-Drive',
            is_enabled=True,
        )

        self.user1 = User.objects.create_user(username='alice', password='password123')
        self.participant1 = Participant.objects.create(
            user=self.user1,
            github_id=1001,
            github_username='alice',
            total_points=0,
        )

        self.user2 = User.objects.create_user(username='bob', password='password123')
        self.participant2 = Participant.objects.create(
            user=self.user2,
            github_id=1002,
            github_username='bob',
            total_points=0,
        )
        self._cleanup_test_files()

    def tearDown(self):
        super().tearDown()
        self._cleanup_test_files()

    def _cleanup_test_files(self):
        for f in ['test_boundary_leaderboard.json', 'test_eval_leaderboard.json']:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except OSError:
                    pass

    def _create_contrib(
        self,
        participant: Participant,
        difficulty: str = 'easy',
        points: int | None = None,
        pr_number: int | None = None,
        issue_number: int | None = None,
        merged: bool = True,
        base_branch: str = 'main',
    ) -> Contribution:
        pts = points if points is not None else DIFFICULTY_POINTS.get(difficulty.lower(), 10)
        iss_num = issue_number or (Issue.objects.count() + 100)
        issue = Issue.objects.create(
            github_issue_id=Issue.objects.count() + 8000,
            project=self.project,
            number=iss_num,
            title=f"CR-{iss_num}: Sample {difficulty} task",
            difficulty=difficulty,
            points=pts,
            status='open',
        )
        pr_num = pr_number or (PullRequest.objects.count() + 200)
        pr = PullRequest.objects.create(
            github_pr_id=PullRequest.objects.count() + 9000,
            repo=self.project,
            number=pr_num,
            author_github_id=participant.github_id,
            author_participant=participant,
            merged=merged,
            merged_at=timezone.now() if merged else None,
            base_branch=base_branch,
        )
        return Contribution.objects.create(
            participant=participant,
            issue=issue,
            pull_request=pr,
            status='MERGED' if merged else 'PENDING',
            merged_at=timezone.now() if merged else None,
        )

    # 1. Test Each Difficulty Level
    def test_difficulty_levels_points(self):
        """Verify each difficulty level awards its exact defined points: 5, 10, 20, 30, 50."""
        difficulties = [
            ('beginner', 5),
            ('easy', 10),
            ('medium', 20),
            ('hard', 30),
            ('master', 50),
        ]
        for diff_name, expected_pts in difficulties:
            with self.subTest(difficulty=diff_name, expected=expected_pts):
                user = User.objects.create_user(username=f'user_{diff_name}')
                participant = Participant.objects.create(
                    user=user,
                    github_id=Issue.objects.count() + 20000,
                    github_username=f'user_{diff_name}',
                )
                contrib = self._create_contrib(participant=participant, difficulty=diff_name)
                res = award_points_for_contribution(contrib.id)

                self.assertEqual(res['status'], 'AWARDED')
                self.assertEqual(res['points'], expected_pts)
                participant.refresh_from_db()
                self.assertEqual(participant.total_points, expected_pts)

    # 2. Test Exact 120 Boundary
    def test_exact_120_boundary(self):
        """Example 4: Participant has 70 points, merges Master (50). 70 + 50 = 120. Full 50 points count."""
        today = get_event_today()
        DailyContributionUsage.objects.create(
            participant=self.participant1,
            date=today,
            contributions_count=2,
            points_count=70,
        )
        self.participant1.total_points = 70
        self.participant1.save()

        contrib = self._create_contrib(participant=self.participant1, difficulty='master', points=50)
        res = award_points_for_contribution(contrib.id)

        self.assertEqual(res['status'], 'AWARDED')
        self.assertEqual(res['points'], 50)
        self.participant1.refresh_from_db()
        self.assertEqual(self.participant1.total_points, 120)

        usage = DailyContributionUsage.objects.get(participant=self.participant1, date=today)
        self.assertEqual(usage.points_count, 120)

    # 3. Test Contribution Below 120
    def test_contribution_below_120(self):
        """Contribution below 120 is fully credited."""
        contrib1 = self._create_contrib(participant=self.participant1, difficulty='hard', points=30)
        contrib2 = self._create_contrib(participant=self.participant1, difficulty='medium', points=20)

        res1 = award_points_for_contribution(contrib1.id)
        res2 = award_points_for_contribution(contrib2.id)

        self.assertEqual(res1['points'], 30)
        self.assertEqual(res2['points'], 20)
        self.participant1.refresh_from_db()
        self.assertEqual(self.participant1.total_points, 50)

    # 4. Test Contribution That Would Exceed 120 (Example 2)
    def test_contribution_that_would_exceed_120_defers_to_zero(self):
        """
        Example 2: Participant has 115 points.
        They submit a valid Easy issue worth 10. 115 + 10 = 125.
        Because this exceeds 120:
        -> PR receives 0 competition points.
        -> Daily score remains 115.
        -> Reason clearly marks NOT COUNTED - DAILY LIMIT.
        """
        today = get_event_today()
        DailyContributionUsage.objects.create(
            participant=self.participant1,
            date=today,
            contributions_count=4,
            points_count=115,
        )
        self.participant1.total_points = 115
        self.participant1.save()

        easy_contrib = self._create_contrib(participant=self.participant1, difficulty='easy', points=10)
        res = award_points_for_contribution(easy_contrib.id)

        self.assertEqual(res['status'], 'DEFERRED')
        self.assertEqual(res['points'], 0)
        self.assertIn('NOT COUNTED - DAILY LIMIT', res['reason'])

        # Verify daily score and total score remained 115
        self.participant1.refresh_from_db()
        self.assertEqual(self.participant1.total_points, 115)

        usage = DailyContributionUsage.objects.get(participant=self.participant1, date=today)
        self.assertEqual(usage.points_count, 115)

        # Verify contribution sub_status is marked
        easy_contrib.refresh_from_db()
        self.assertEqual(easy_contrib.sub_status, 'DAILY_LIMIT_REACHED')

    # 5. Test Participant Already at 120 (Example 3)
    def test_participant_already_at_120_receives_zero(self):
        """
        Example 3: Participant has exactly 120 points.
        Any additional valid PR that day receives 0 competition points.
        """
        today = get_event_today()
        DailyContributionUsage.objects.create(
            participant=self.participant1,
            date=today,
            contributions_count=3,
            points_count=120,
        )
        self.participant1.total_points = 120
        self.participant1.save()

        contrib = self._create_contrib(participant=self.participant1, difficulty='beginner', points=5)
        res = award_points_for_contribution(contrib.id)

        self.assertEqual(res['status'], 'DEFERRED')
        self.assertEqual(res['points'], 0)
        self.assertIn('DAILY LIMIT REACHED', res['reason'])

        self.participant1.refresh_from_db()
        self.assertEqual(self.participant1.total_points, 120)

    # 6. Test Daily Reset at 00:00 IST
    def test_daily_reset_in_ist(self):
        """
        Daily counter resets at 00:00 IST every day.
        Points from yesterday do not prevent points today.
        """
        yesterday_ist = get_event_today() - datetime.timedelta(days=1)
        DailyContributionUsage.objects.create(
            participant=self.participant1,
            date=yesterday_ist,
            contributions_count=3,
            points_count=120,  # Maxed out yesterday
        )
        self.participant1.total_points = 120
        self.participant1.save()

        # Today's contribution
        today_contrib = self._create_contrib(participant=self.participant1, difficulty='master', points=50)
        res = award_points_for_contribution(today_contrib.id)

        self.assertEqual(res['status'], 'AWARDED')
        self.assertEqual(res['points'], 50)
        self.participant1.refresh_from_db()
        self.assertEqual(self.participant1.total_points, 170)

        today = get_event_today()
        today_usage = DailyContributionUsage.objects.get(participant=self.participant1, date=today)
        self.assertEqual(today_usage.points_count, 50)

    # 7. Test Duplicate PR Idempotency
    def test_duplicate_pr_idempotency(self):
        """Processing the same contribution multiple times must not award points again."""
        contrib = self._create_contrib(participant=self.participant1, difficulty='medium', points=20)
        res1 = award_points_for_contribution(contrib.id)
        self.assertEqual(res1['status'], 'AWARDED')
        self.assertEqual(res1['points'], 20)

        # Second call
        res2 = award_points_for_contribution(contrib.id)
        self.assertEqual(res2['status'], 'ALREADY_AWARDED')
        self.assertEqual(res2['points'], 20)

        self.participant1.refresh_from_db()
        self.assertEqual(self.participant1.total_points, 20)

    # 8. Test Duplicate Issue Scoring Prevention
    def test_duplicate_issue_scoring_prevented_across_prs(self):
        """A single CommitRush issue must not award points more than once across PRs."""
        issue = Issue.objects.create(
            github_issue_id=8899,
            project=self.project,
            number=901,
            title='[CR-901] Implement query sanitizer',
            difficulty='hard',
            points=30,
            status='open',
        )

        pr1 = PullRequest.objects.create(
            github_pr_id=11111,
            repo=self.project,
            number=1,
            author_github_id=self.participant1.github_id,
            author_participant=self.participant1,
            merged=True,
            base_branch='main',
        )
        contrib1 = Contribution.objects.create(
            participant=self.participant1,
            issue=issue,
            pull_request=pr1,
            status='MERGED',
        )
        res1 = award_points_for_contribution(contrib1.id)
        self.assertEqual(res1['status'], 'AWARDED')
        self.assertEqual(res1['points'], 30)

        # Another participant attempts to score for the same issue CR-901 in PR #2
        pr2 = PullRequest.objects.create(
            github_pr_id=22222,
            repo=self.project,
            number=2,
            author_github_id=self.participant2.github_id,
            author_participant=self.participant2,
            merged=True,
            base_branch='main',
        )
        contrib2 = Contribution.objects.create(
            participant=self.participant2,
            issue=issue,
            pull_request=pr2,
            status='MERGED',
        )
        res2 = award_points_for_contribution(contrib2.id)

        self.assertEqual(res2['status'], 'DEFERRED')
        self.assertEqual(res2['points'], 0)
        self.assertIn('Duplicate issue scoring prevented', res2['reason'])

        self.participant2.refresh_from_db()
        self.assertEqual(self.participant2.total_points, 0)

    # 9. Test Unmerged PR
    def test_unmerged_pr_awards_zero_points(self):
        """Closed/unmerged PRs must not award points."""
        contrib = self._create_contrib(participant=self.participant1, difficulty='easy', points=10, merged=False)
        res = award_points_for_contribution(contrib.id)

        self.assertEqual(res['status'], 'DEFERRED')
        self.assertEqual(res['points'], 0)
        self.assertIn('PR is not merged', res['reason'])

        self.participant1.refresh_from_db()
        self.assertEqual(self.participant1.total_points, 0)

    # 10. Test Invalid Branch Protection
    def test_pr_targeting_wrong_branch_deferred(self):
        """PR targeting branch other than designated main branch is deferred."""
        contrib = self._create_contrib(
            participant=self.participant1,
            difficulty='easy',
            points=10,
            base_branch='develop',  # Not main
        )
        res = award_points_for_contribution(contrib.id)

        self.assertEqual(res['status'], 'DEFERRED')
        self.assertEqual(res['points'], 0)
        self.assertIn("does not target designated event branch 'main'", res['reason'])

    # 11. Test Missing Difficulty Defaults
    def test_missing_difficulty_defaults_gracefully(self):
        """Issues with missing difficulty string default to Easy tier (10 points)."""
        contrib = self._create_contrib(participant=self.participant1, difficulty='', points=None)
        res = award_points_for_contribution(contrib.id)

        self.assertEqual(res['status'], 'AWARDED')
        self.assertEqual(res['points'], 10)

    # 12. Test Different Participants Have Independent Daily Limits
    def test_different_participants_independent_daily_limits(self):
        """One participant reaching 120 points does not affect another participant."""
        today = get_event_today()
        # Alice at 120
        DailyContributionUsage.objects.create(
            participant=self.participant1,
            date=today,
            contributions_count=3,
            points_count=120,
        )
        self.participant1.total_points = 120
        self.participant1.save()

        # Bob submits Master (50 points)
        bob_contrib = self._create_contrib(participant=self.participant2, difficulty='master', points=50)
        res = award_points_for_contribution(bob_contrib.id)

        self.assertEqual(res['status'], 'AWARDED')
        self.assertEqual(res['points'], 50)
        self.participant2.refresh_from_db()
        self.assertEqual(self.participant2.total_points, 50)

    # 13. Test Multiple PRs on Same Day (Example 1)
    def test_multiple_prs_on_same_day_accumulate(self):
        """
        Example 1: Beginner (5) + Easy (10) + Medium (20) + Hard (30) + Master (50) = 115 points.
        All five count.
        """
        items = [
            ('beginner', 5),
            ('easy', 10),
            ('medium', 20),
            ('hard', 30),
            ('master', 50),
        ]
        total = 0
        for diff, pts in items:
            c = self._create_contrib(participant=self.participant1, difficulty=diff, points=pts)
            r = award_points_for_contribution(c.id)
            self.assertEqual(r['status'], 'AWARDED')
            self.assertEqual(r['points'], pts)
            total += pts

        self.assertEqual(total, 115)
        self.participant1.refresh_from_db()
        self.assertEqual(self.participant1.total_points, 115)

    # 14. Test IST vs UTC Boundary
    def test_ist_vs_utc_boundary_resets_at_midnight_ist(self):
        """
        Verify that 23:30 UTC on day N (which is 05:00 IST on day N+1)
        resets the daily counter because in IST it is already day N+1.
        """
        # Create a mock UTC datetime: 2026-09-22 23:30:00 UTC
        utc_time = datetime.datetime(2026, 9, 22, 23, 30, 0, tzinfo=datetime.timezone.utc)
        ist_time = utc_time.astimezone(EVENT_TIMEZONE)

        # In UTC, it is Sep 22. In IST, it is Sep 23!
        self.assertEqual(utc_time.date(), datetime.date(2026, 9, 22))
        self.assertEqual(ist_time.date(), datetime.date(2026, 9, 23))

        # Seed day 2026-09-22 IST usage with 120 points
        DailyContributionUsage.objects.create(
            participant=self.participant1,
            date=datetime.date(2026, 9, 22),
            contributions_count=3,
            points_count=120,
        )

        # Contribution merged at 23:30 UTC belongs to 2026-09-23 in IST
        date_str = ist_time.date().strftime('%Y-%m-%d')
        res = process_merged_pr(
            author_username='alice',
            pr_number=999,
            pr_title='[CR-555] Feature',
            base_branch='main',
            is_merged=True,
            merged_at_iso=utc_time.isoformat(),
            labels=['difficulty:medium'],
            leaderboard_file='test_boundary_leaderboard.json',
        )

        # Because it belongs to Sep 23 IST, it must be COUNTED and not blocked by Sep 22 usage!
        self.assertEqual(res['status'], 'AWARDED')
        self.assertEqual(res['points'], 20)
        self.assertEqual(res['today_points'], 20)

    # 15. Test Standalone Evaluation Script
    def test_check_pr_daily_limit_script(self):
        """Verify the check_pr_daily_limit evaluation outputs the exact expected format."""
        eval_res = evaluate_pr_daily_limit(
            author_username='charlie',
            pr_number=42,
            pr_title='Fixes CR-101',
            base_branch='main',
            labels=['difficulty:hard'],
            leaderboard_file='test_eval_leaderboard.json',
        )
        self.assertEqual(eval_res['result'], 'COUNTED')
        self.assertEqual(eval_res['pr_value'], 30)
        self.assertIn("CommitRush Daily Limit", eval_res['formatted_report'])
        self.assertIn("Today's points: 0 / 120", eval_res['formatted_report'])
        self.assertIn("PR value: 30", eval_res['formatted_report'])
        self.assertIn("New daily total: 30 / 120", eval_res['formatted_report'])
