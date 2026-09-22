import datetime
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import (
    Contribution,
    DailyContributionUsage,
    EventConfig,
    Issue,
    IssueLabel,
    Participant,
    PointTransaction,
    Project,
    PullRequest,
    ScoringBreakdown,
)
from core.scoring import (
    ScoringEngine,
    classify_contribution,
    detect_farming_signals,
)
from core.points import award_points_for_contribution

User = get_user_model()


class ScoringClassifierTests(TestCase):
    """
    Unit tests for deterministic contribution classification cascade.
    Cascade order:
    1. Issue.category (if set and resolvable)
    2. Issue cached labels
    3. Issue title / PR title prefix convention
    4. Fallback to ('feature', 'Feature')
    """

    def setUp(self):
        self.user = User.objects.create_user(username='test_coder', password='password123')
        self.participant = Participant.objects.create(
            user=self.user,
            github_id=10001,
            github_username='test_coder',
        )
        self.project = Project.objects.create(
            github_repo_id=20001,
            owner='hackit',
            name='classifier-repo',
            full_name='hackit/classifier-repo',
            is_enabled=True,
        )

    def _create_contribution(self, issue_category='', issue_labels=None, issue_title='Generic task'):
        issue = Issue.objects.create(
            github_issue_id=Issue.objects.count() + 100,
            project=self.project,
            number=Issue.objects.count() + 1,
            title=issue_title,
            category=issue_category,
            points=20,
            status='open',
        )
        if issue_labels:
            for lbl_name in issue_labels:
                lbl, _ = IssueLabel.objects.get_or_create(
                    name=lbl_name,
                    defaults={'color': 'cccccc'},
                )
                issue.labels.add(lbl)

        pr = PullRequest.objects.create(
            github_pr_id=PullRequest.objects.count() + 200,
            repo=self.project,
            number=PullRequest.objects.count() + 1,
            author_github_id=self.participant.github_id,
            author_participant=self.participant,
            merged=True,
            merged_at=timezone.now(),
        )
        return Contribution.objects.create(
            participant=self.participant,
            issue=issue,
            pull_request=pr,
            status='MERGED',
            merged_at=timezone.now(),
        )

    def test_cascade_1_issue_category_direct(self):
        contrib = self._create_contribution(issue_category='bug')
        cat_key, cat_label = classify_contribution(contrib)
        self.assertEqual(cat_key, 'bug')
        self.assertEqual(cat_label, 'Bug Fix')

    def test_cascade_1_issue_category_alias(self):
        contrib = self._create_contribution(issue_category='defect')
        cat_key, cat_label = classify_contribution(contrib)
        self.assertEqual(cat_key, 'bug')
        self.assertEqual(cat_label, 'Bug Fix')

        contrib_docs = self._create_contribution(issue_category='documentation')
        cat_key, cat_label = classify_contribution(contrib_docs)
        self.assertEqual(cat_key, 'docs')
        self.assertEqual(cat_label, 'Documentation')

    def test_cascade_2_issue_labels(self):
        contrib = self._create_contribution(
            issue_category='',
            issue_labels=['documentation'],
            issue_title='Update quickstart guide',
        )
        cat_key, cat_label = classify_contribution(contrib)
        self.assertEqual(cat_key, 'docs')
        self.assertEqual(cat_label, 'Documentation')

    def test_cascade_3_issue_title_prefix_feat(self):
        contrib = self._create_contribution(
            issue_category='',
            issue_labels=None,
            issue_title='feat: implement OAuth login flow',
        )
        cat_key, cat_label = classify_contribution(contrib)
        self.assertEqual(cat_key, 'feature')
        self.assertEqual(cat_label, 'Feature')

    def test_cascade_3_issue_title_prefix_fix_with_scope(self):
        contrib = self._create_contribution(
            issue_category='',
            issue_labels=None,
            issue_title='fix(db): prevent database connection pooling exhaustion',
        )
        cat_key, cat_label = classify_contribution(contrib)
        self.assertEqual(cat_key, 'bug')
        self.assertEqual(cat_label, 'Bug Fix')

    def test_cascade_3_bracket_prefix(self):
        contrib = self._create_contribution(
            issue_category='',
            issue_labels=None,
            issue_title='[test] add integration tests for points engine',
        )
        cat_key, cat_label = classify_contribution(contrib)
        self.assertEqual(cat_key, 'test')
        self.assertEqual(cat_label, 'Testing & QA')

    def test_cascade_4_fallback_to_feature(self):
        contrib = self._create_contribution(
            issue_category='',
            issue_labels=None,
            issue_title='Miscellaneous task without prefixes',
        )
        cat_key, cat_label = classify_contribution(contrib)
        self.assertEqual(cat_key, 'feature')
        self.assertEqual(cat_label, 'Feature')


class FarmingDetectionTests(TestCase):
    """
    Tests for farming heuristic tracking and non-banning signals.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='farming_user', password='password123')
        self.participant = Participant.objects.create(
            user=self.user,
            github_id=30001,
            github_username='farming_user',
        )
        self.project = Project.objects.create(
            github_repo_id=40001,
            owner='hackit',
            name='farm-target',
            full_name='hackit/farm-target',
            is_enabled=True,
        )

    def _create_contrib_history(self, count, category='feature', points=50, project=None, created_offset_minutes=0):
        project = project or self.project
        contribs = []
        now = timezone.now()
        for i in range(count):
            iss = Issue.objects.create(
                github_issue_id=Issue.objects.count() + 1000,
                project=project,
                number=Issue.objects.count() + 1,
                title=f'{category} issue #{i}',
                category=category,
                points=points,
                status='open',
            )
            pr = PullRequest.objects.create(
                github_pr_id=PullRequest.objects.count() + 2000,
                repo=project,
                number=PullRequest.objects.count() + 1,
                author_github_id=self.participant.github_id,
                author_participant=self.participant,
                merged=True,
            )
            c = Contribution.objects.create(
                participant=self.participant,
                issue=iss,
                pull_request=pr,
                status='MERGED',
            )
            c.created_at = now - datetime.timedelta(minutes=created_offset_minutes + (i * 2))
            c.save(update_fields=['created_at'])
            contribs.append(c)
        return contribs

    def test_no_farming_signals_for_clean_contribution(self):
        curr = self._create_contrib_history(1, category='feature', points=50)[0]
        signals = detect_farming_signals(curr, self.participant, base_points=50, category='feature')
        self.assertFalse(signals['has_signals'])
        self.assertEqual(signals['risk_level'], 'NONE')
        self.assertEqual(len(signals['signals']), 0)

    def test_rapid_burst_detection(self):
        # 3 previous contributions within last 15 mins + 1 current = 4 total in past 60 mins
        self._create_contrib_history(3, category='feature', points=40, created_offset_minutes=5)
        curr = self._create_contrib_history(1, category='feature', points=40, created_offset_minutes=0)[0]

        signals = detect_farming_signals(curr, self.participant, base_points=40, category='feature')
        self.assertTrue(signals['has_signals'])
        self.assertIn('rapid_burst', signals['signals'])

    def test_repeated_same_project_detection(self):
        # 4 contributions to the same repo within 24 hours
        self._create_contrib_history(3, category='feature', points=40, created_offset_minutes=120)
        curr = self._create_contrib_history(1, category='feature', points=40, created_offset_minutes=10)[0]

        signals = detect_farming_signals(curr, self.participant, base_points=40, category='feature')
        self.assertTrue(signals['has_signals'])
        self.assertIn('repeated_same_project', signals['signals'])

    def test_multiple_tiny_docs_detection(self):
        # 3 docs contributions within 24 hours
        self._create_contrib_history(2, category='docs', points=10, created_offset_minutes=90)
        curr = self._create_contrib_history(1, category='docs', points=10, created_offset_minutes=5)[0]

        signals = detect_farming_signals(curr, self.participant, base_points=10, category='docs')
        self.assertTrue(signals['has_signals'])
        self.assertIn('multiple_tiny_docs', signals['signals'])

    def test_very_low_impact_detection(self):
        # 4 contributions with <= 15 base points within 24 hours
        self._create_contrib_history(3, category='refactor', points=10, created_offset_minutes=180)
        curr = self._create_contrib_history(1, category='refactor', points=10, created_offset_minutes=10)[0]

        signals = detect_farming_signals(curr, self.participant, base_points=10, category='refactor')
        self.assertTrue(signals['has_signals'])
        self.assertIn('very_low_impact', signals['signals'])

    def test_burst_boundary_2_vs_3_prs(self):
        # 1 historical + 1 current = 2 total within 60 mins -> NO rapid_burst
        self._create_contrib_history(1, category='feature', points=40, created_offset_minutes=15)
        curr = self._create_contrib_history(1, category='feature', points=40, created_offset_minutes=0)[0]
        signals = detect_farming_signals(curr, self.participant, base_points=40, category='feature')
        self.assertNotIn('rapid_burst', signals['signals'])

        # Add 1 more -> 3 total within 60 mins -> DOES trigger rapid_burst
        self._create_contrib_history(1, category='feature', points=40, created_offset_minutes=10)
        signals3 = detect_farming_signals(curr, self.participant, base_points=40, category='feature')
        self.assertIn('rapid_burst', signals3['signals'])

    def test_same_project_boundary_3_vs_4_prs(self):
        # 2 historical + 1 current = 3 total to same repo in 24h -> NO repeated_same_project
        self._create_contrib_history(2, category='feature', points=40, created_offset_minutes=120)
        curr = self._create_contrib_history(1, category='feature', points=40, created_offset_minutes=10)[0]
        signals = detect_farming_signals(curr, self.participant, base_points=40, category='feature')
        self.assertNotIn('repeated_same_project', signals['signals'])

        # Add 1 more -> 4 total -> DOES trigger repeated_same_project
        self._create_contrib_history(1, category='feature', points=40, created_offset_minutes=60)
        signals4 = detect_farming_signals(curr, self.participant, base_points=40, category='feature')
        self.assertIn('repeated_same_project', signals4['signals'])

    def test_tiny_docs_boundary_2_vs_3_docs(self):
        # 1 historical + 1 current = 2 docs PRs in 24h -> NO multiple_tiny_docs
        self._create_contrib_history(1, category='docs', points=10, created_offset_minutes=90)
        curr = self._create_contrib_history(1, category='docs', points=10, created_offset_minutes=5)[0]
        signals = detect_farming_signals(curr, self.participant, base_points=10, category='docs')
        self.assertNotIn('multiple_tiny_docs', signals['signals'])

        # Add 1 more -> 3 total docs PRs -> DOES trigger multiple_tiny_docs
        self._create_contrib_history(1, category='docs', points=10, created_offset_minutes=45)
        signals3 = detect_farming_signals(curr, self.participant, base_points=10, category='docs')
        self.assertIn('multiple_tiny_docs', signals3['signals'])

    def test_low_impact_boundary_15_vs_16_base_points(self):
        # Base points = 16 is NOT low impact (> 15)
        self._create_contrib_history(4, category='bug', points=16, created_offset_minutes=60)
        curr = self._create_contrib_history(1, category='bug', points=16, created_offset_minutes=5)[0]
        signals = detect_farming_signals(curr, self.participant, base_points=16, category='bug')
        self.assertNotIn('very_low_impact', signals['signals'])

        # Base points = 15 IS low impact (<= 15)
        self._create_contrib_history(3, category='bug', points=15, created_offset_minutes=30)
        curr_15 = self._create_contrib_history(1, category='bug', points=15, created_offset_minutes=2)[0]
        signals_15 = detect_farming_signals(curr_15, self.participant, base_points=15, category='bug')
        self.assertIn('very_low_impact', signals_15['signals'])

    def test_repeated_trivial_changes_boundary_strictly_greater_than_60_percent(self):
        # 10 total PRs with exactly 6 low-impact = 60.0% (NOT > 60%) -> NO signal
        # 6 low impact (<=15) + 3 normal (50) + 1 current (50) = 6/10 = 60%
        self._create_contrib_history(6, category='refactor', points=10, created_offset_minutes=200)
        self._create_contrib_history(3, category='feature', points=50, created_offset_minutes=150)
        curr_60 = self._create_contrib_history(1, category='feature', points=50, created_offset_minutes=5)[0]

        signals = detect_farming_signals(curr_60, self.participant, base_points=50, category='feature')
        self.assertNotIn('repeated_trivial_changes', signals['signals'])

        # 7 low impact + 3 normal = 7/11 = 63.6% (> 60%) -> DOES trigger repeated_trivial_changes
        self._create_contrib_history(1, category='refactor', points=10, created_offset_minutes=100)
        signals7 = detect_farming_signals(curr_60, self.participant, base_points=50, category='feature')
        self.assertIn('repeated_trivial_changes', signals7['signals'])

    def test_window_boundary_older_than_24h(self):
        # Contributions older than 24 hours must be excluded from daily signals
        now = timezone.now()
        iss = Issue.objects.create(
            github_issue_id=Issue.objects.count() + 9000,
            project=self.project,
            number=Issue.objects.count() + 1,
            title='Old issue',
            category='feature',
            points=50,
        )
        pr = PullRequest.objects.create(
            github_pr_id=PullRequest.objects.count() + 9000,
            repo=self.project,
            number=PullRequest.objects.count() + 1,
            author_github_id=self.participant.github_id,
            author_participant=self.participant,
            merged=True,
        )
        old_c = Contribution.objects.create(
            participant=self.participant,
            issue=iss,
            pull_request=pr,
            status='MERGED',
        )
        old_c.created_at = now - datetime.timedelta(hours=25)
        old_c.save(update_fields=['created_at'])

        curr = self._create_contrib_history(1, category='feature', points=50)[0]
        signals = detect_farming_signals(curr, self.participant, base_points=50, category='feature')
        self.assertEqual(signals['metrics']['total_24h'], 1)

    def test_farming_does_not_ban_user(self):
        # Even with multiple heuristic flags, user is NOT banned/suspended
        self._create_contrib_history(5, category='docs', points=10, created_offset_minutes=10)
        curr = self._create_contrib_history(1, category='docs', points=10, created_offset_minutes=0)[0]

        signals = detect_farming_signals(curr, self.participant, base_points=10, category='docs')
        self.assertTrue(signals['has_signals'])
        self.participant.refresh_from_db()
        self.assertFalse(self.participant.is_suspended)


class ScoringEnginePipelineTests(TestCase):
    """
    End-to-end tests for ScoringEngine.award_points_for_contribution:
    - Multipliers
    - Per-PR cap
    - Daily count cap
    - Daily points cap (full and partial)
    - Suspended participant gating
    - Idempotency
    - ScoringBreakdown generation
    """

    def setUp(self):
        self.config = EventConfig.get_solo()
        self.config.max_contributions_per_day = 5
        self.config.max_points_per_day = 100
        self.config.per_pr_max_points = 50
        self.config.allow_partial_daily_points = True
        self.config.category_multipliers = {
            'feature': 1.5,
            'bug': 1.2,
            'docs': 0.8,
            'test': 1.0,
        }
        self.config.save()

        self.user = User.objects.create_user(username='alice', password='password123')
        self.participant = Participant.objects.create(
            user=self.user,
            github_id=50001,
            github_username='alice',
            total_points=0,
        )

        self.project = Project.objects.create(
            github_repo_id=60001,
            owner='hackit',
            name='scoring-repo',
            full_name='hackit/scoring-repo',
            is_enabled=True,
        )

    def _create_contribution(self, points=20, category='feature', title='feat: sample'):
        issue = Issue.objects.create(
            github_issue_id=Issue.objects.count() + 5000,
            project=self.project,
            number=Issue.objects.count() + 1,
            title=title,
            category=category,
            points=points,
            status='open',
        )
        pr = PullRequest.objects.create(
            github_pr_id=PullRequest.objects.count() + 6000,
            repo=self.project,
            number=PullRequest.objects.count() + 1,
            author_github_id=self.participant.github_id,
            author_participant=self.participant,
            merged=True,
            merged_at=timezone.now(),
        )
        return Contribution.objects.create(
            participant=self.participant,
            issue=issue,
            pull_request=pr,
            status='MERGED',
            merged_at=timezone.now(),
        )

    def test_standard_awarded_points_with_multiplier(self):
        # Base points: 20. Multiplier: 1.5. Calculated: 30. Per-PR cap: 50. Daily cap: 100.
        contrib = self._create_contribution(points=20, category='feature')
        res = award_points_for_contribution(contrib.id)

        self.assertEqual(res['status'], 'AWARDED')
        self.assertEqual(res['points'], 30)

        # Verify participant total points
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.total_points, 30)

        # Verify ScoringBreakdown record
        breakdown = ScoringBreakdown.objects.get(contribution=contrib)
        self.assertEqual(breakdown.base_points, 20)
        self.assertEqual(breakdown.category, 'feature')
        self.assertEqual(breakdown.multiplier, 1.5)
        self.assertEqual(breakdown.calculated_points, 30)
        self.assertEqual(breakdown.per_pr_cap, 50)
        self.assertEqual(breakdown.points_after_pr_cap, 30)
        self.assertEqual(breakdown.cap_applied, 'Not reached')
        self.assertEqual(breakdown.final_awarded_points, 30)

    def test_per_pr_cap_enforcement(self):
        # Base points: 40. Multiplier: 1.5. Calculated: 60. Per-PR cap: 50.
        # Should cap at 50.
        contrib = self._create_contribution(points=40, category='feature')
        res = award_points_for_contribution(contrib.id)

        self.assertEqual(res['status'], 'AWARDED')
        self.assertEqual(res['points'], 50)

        breakdown = ScoringBreakdown.objects.get(contribution=contrib)
        self.assertEqual(breakdown.calculated_points, 60)
        self.assertEqual(breakdown.points_after_pr_cap, 50)
        self.assertEqual(breakdown.cap_applied, 'Per-PR cap')
        self.assertEqual(breakdown.final_awarded_points, 50)

    def test_partial_daily_points_awarded_when_allowance_exceeded(self):
        # Daily limit: 100. Pre-seed daily usage with 80 points.
        today = timezone.now().date()
        DailyContributionUsage.objects.create(
            participant=self.participant,
            date=today,
            contributions_count=1,
            points_count=80,
        )
        self.participant.total_points = 80
        self.participant.save()

        # New contribution calculates to 30 points (20 * 1.5).
        # Remaining allowance is 100 - 80 = 20.
        # With allow_partial_daily_points=True, awards partial 20 points!
        contrib = self._create_contribution(points=20, category='feature')
        res = award_points_for_contribution(contrib.id)

        self.assertEqual(res['status'], 'AWARDED')
        self.assertEqual(res['points'], 20)

        self.participant.refresh_from_db()
        self.assertEqual(self.participant.total_points, 100)

        usage = DailyContributionUsage.objects.get(participant=self.participant, date=today)
        self.assertEqual(usage.points_count, 100)
        self.assertEqual(usage.contributions_count, 2)

        breakdown = ScoringBreakdown.objects.get(contribution=contrib)
        self.assertEqual(breakdown.daily_allowance_remaining, 20)
        self.assertEqual(breakdown.cap_applied, 'Daily limit')
        self.assertEqual(breakdown.final_awarded_points, 20)

    def test_partial_daily_points_disabled_defers_to_zero(self):
        # Configure allow_partial_daily_points = False
        self.config.allow_partial_daily_points = False
        self.config.save()

        today = timezone.now().date()
        DailyContributionUsage.objects.create(
            participant=self.participant,
            date=today,
            contributions_count=1,
            points_count=80,
        )
        self.participant.total_points = 80
        self.participant.save()

        # Calculated points: 30 > remaining allowance (20).
        # With allow_partial_daily_points=False, it should DEFER to 0 points.
        contrib = self._create_contribution(points=20, category='feature')
        res = award_points_for_contribution(contrib.id)

        self.assertEqual(res['status'], 'DEFERRED')
        self.assertEqual(res['points'], 0)

        self.participant.refresh_from_db()
        self.assertEqual(self.participant.total_points, 80)

        breakdown = ScoringBreakdown.objects.get(contribution=contrib)
        self.assertEqual(breakdown.cap_applied, 'Daily limit')
        self.assertEqual(breakdown.final_awarded_points, 0)

    def test_daily_points_exhausted_defers_points(self):
        today = timezone.now().date()
        DailyContributionUsage.objects.create(
            participant=self.participant,
            date=today,
            contributions_count=2,
            points_count=100,  # Cap reached
        )
        self.participant.total_points = 100
        self.participant.save()

        contrib = self._create_contribution(points=20, category='feature')
        res = award_points_for_contribution(contrib.id)

        self.assertEqual(res['status'], 'DEFERRED')
        self.assertEqual(res['points'], 0)
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.total_points, 100)

    def test_daily_contribution_count_limit_exceeded(self):
        today = timezone.now().date()
        DailyContributionUsage.objects.create(
            participant=self.participant,
            date=today,
            contributions_count=5,  # max_contributions_per_day is 5
            points_count=30,
        )
        self.participant.total_points = 30
        self.participant.save()

        contrib = self._create_contribution(points=20, category='feature')
        res = award_points_for_contribution(contrib.id)

        self.assertEqual(res['status'], 'DEFERRED')
        self.assertEqual(res['points'], 0)
        self.assertIn('Daily limit exceeded', res['reason'])

    def test_suspended_participant_defers_points(self):
        self.participant.is_suspended = True
        self.participant.save()

        contrib = self._create_contribution(points=20, category='feature')
        res = award_points_for_contribution(contrib.id)

        self.assertEqual(res['status'], 'DEFERRED')
        self.assertEqual(res['points'], 0)
        self.assertIn('suspended', res['reason'])

    def test_idempotency_exactly_once(self):
        contrib = self._create_contribution(points=20, category='feature')

        # First call awards points
        res1 = award_points_for_contribution(contrib.id)
        self.assertEqual(res1['status'], 'AWARDED')
        self.assertEqual(res1['points'], 30)

        # Second call is idempotent
        res2 = award_points_for_contribution(contrib.id)
        self.assertEqual(res2['status'], 'ALREADY_AWARDED')
        self.assertEqual(res2['points'], 30)

        # Ledger and breakdown counts must remain 1
        self.assertEqual(PointTransaction.objects.filter(contribution=contrib).count(), 1)
        self.assertEqual(ScoringBreakdown.objects.filter(contribution=contrib).count(), 1)

    def test_base_points_fallback_when_issue_points_none_or_zero(self):
        # When issue.points is None or 0, fallback base points must be 10 (not 50)
        contrib = self._create_contribution(points=0, category='feature')
        contrib.issue.points = 0
        contrib.issue.save()
        res = award_points_for_contribution(contrib.id)

        self.assertEqual(res['status'], 'AWARDED')
        # Base points: 10, multiplier 1.5 -> 15 calculated points
        self.assertEqual(res['points'], 15)
        breakdown = ScoringBreakdown.objects.get(contribution=contrib)
        self.assertEqual(breakdown.base_points, 10)
        self.assertEqual(breakdown.calculated_points, 15)
        self.assertEqual(breakdown.final_awarded_points, 15)


class LeaderboardDailyAllowanceAPITests(TestCase):
    """
    Tests for Leaderboard API calculating final_awarded_points and daily allowance fields.
    """

    def setUp(self):
        self.config = EventConfig.get_solo()
        self.config.max_points_per_day = 200
        self.config.save()

        self.user = User.objects.create_user(username='lead_coder', password='password123')
        self.participant = Participant.objects.create(
            user=self.user,
            github_id=70001,
            github_username='lead_coder',
            total_points=150,
            merged_count=3,
        )

        today = timezone.now().date()
        DailyContributionUsage.objects.create(
            participant=self.participant,
            date=today,
            contributions_count=3,
            points_count=150,
        )

        self.client = APIClient()

    def test_leaderboard_contains_daily_allowance_fields(self):
        response = self.client.get('/api/v1/leaderboard/')
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn('results', data)
        self.assertTrue(len(data['results']) >= 1)

        entry = data['results'][0]
        self.assertEqual(entry['github_username'], 'lead_coder')
        self.assertEqual(entry['total_points'], 150)
        self.assertEqual(entry['points_today'], 150)
        self.assertEqual(entry['daily_limit'], 200)
        self.assertEqual(entry['remaining_daily_allowance'], 50)
        self.assertFalse(entry['is_daily_limit_reached'])

    def test_leaderboard_me_contains_daily_allowance_fields(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/v1/leaderboard/')
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn('me', data)
        me = data['me']
        self.assertIsNotNone(me)
        self.assertEqual(me['points_today'], 150)
        self.assertEqual(me['daily_limit'], 200)
        self.assertEqual(me['remaining_daily_allowance'], 50)
        self.assertFalse(me['is_daily_limit_reached'])


class AdminFarmingReviewsAPITests(TestCase):
    """
    Tests for Admin Farming Reviews API (/api/v1/admin/farming-reviews/).
    """

    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_reviewer',
            password='password123',
            is_staff=True,
        )
        self.regular_user = User.objects.create_user(
            username='regular_joe',
            password='password123',
            is_staff=False,
        )
        self.participant = Participant.objects.create(
            user=self.regular_user,
            github_id=80001,
            github_username='regular_joe',
        )
        self.project = Project.objects.create(
            github_repo_id=90001,
            owner='hackit',
            name='review-repo',
            full_name='hackit/review-repo',
            is_enabled=True,
        )
        self.issue = Issue.objects.create(
            github_issue_id=95001,
            project=self.project,
            number=1,
            title='Sample issue',
            points=10,
        )
        self.pr = PullRequest.objects.create(
            github_pr_id=96001,
            repo=self.project,
            number=1,
            author_github_id=self.participant.github_id,
            author_participant=self.participant,
            merged=True,
        )
        self.contrib = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=self.pr,
            status='MERGED',
        )
        # Create a breakdown with farming signals
        self.breakdown = ScoringBreakdown.objects.create(
            contribution=self.contrib,
            base_points=10,
            category='docs',
            category_label='Documentation',
            multiplier=0.8,
            calculated_points=8,
            per_pr_cap=100,
            points_after_pr_cap=8,
            daily_points_cap=500,
            daily_points_before=0,
            daily_allowance_remaining=500,
            cap_applied='Not reached',
            final_awarded_points=8,
            farming_signals={
                'has_signals': True,
                'risk_level': 'HIGH',
                'signals': ['rapid_burst', 'repeated_same_project', 'multiple_tiny_docs'],
                'reasons': ['3 contributions in 60m', '4 in same project', '3 tiny docs'],
            },
        )
        self.client = APIClient()

    def test_anonymous_forbidden(self):
        response = self.client.get('/api/v1/admin/farming-reviews/')
        self.assertEqual(response.status_code, 401)

    def test_non_staff_forbidden(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get('/api/v1/admin/farming-reviews/')
        self.assertEqual(response.status_code, 403)

    def test_admin_can_list_and_filter_farming_reviews(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/farming-reviews/')
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(len(data['results']), 1)
        item = data['results'][0]
        self.assertEqual(item['participant_username'], 'regular_joe')
        self.assertEqual(item['farming_signals']['risk_level'], 'HIGH')
        self.assertEqual(len(item['farming_signals']['signals']), 3)
        self.assertIn('rapid_burst', item['farming_signals']['signals'])

        # Filter by risk_level=HIGH
        resp_high = self.client.get('/api/v1/admin/farming-reviews/?risk_level=HIGH')
        self.assertEqual(resp_high.status_code, 200)
        self.assertEqual(len(resp_high.json()['results']), 1)

        # Filter by risk_level=LOW
        resp_low = self.client.get('/api/v1/admin/farming-reviews/?risk_level=LOW')
        self.assertEqual(resp_low.status_code, 200)
        self.assertEqual(len(resp_low.json()['results']), 0)


class AdminScoringControlsAPITests(TestCase):
    """
    Tests for updating scoring parameters via Admin System Controls API (/api/v1/admin/controls/).
    """

    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_controller',
            password='password123',
            is_staff=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_admin_updates_scoring_controls(self):
        payload = {
            'per_pr_max_points': 75,
            'allow_partial_daily_points': False,
            'category_multipliers': {
                'feature': 2.0,
                'bug': 1.5,
                'docs': 0.5,
            },
        }
        response = self.client.patch('/api/v1/admin/controls/', payload, format='json')
        self.assertEqual(response.status_code, 200)

        config = EventConfig.get_solo()
        self.assertEqual(config.per_pr_max_points, 75)
        self.assertFalse(config.allow_partial_daily_points)
        self.assertEqual(config.category_multipliers.get('feature'), 2.0)
        self.assertEqual(config.category_multipliers.get('docs'), 0.5)

    def test_admin_updates_negative_per_pr_max_rejected(self):
        payload = {'per_pr_max_points': -10}
        response = self.client.patch('/api/v1/admin/controls/', payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('per_pr_max_points', response.json())

    def test_admin_updates_negative_multiplier_rejected(self):
        payload = {
            'category_multipliers': {
                'feature': -1.0,
            },
        }
        response = self.client.patch('/api/v1/admin/controls/', payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('category_multipliers', response.json())


class ScoringBreakdownPrivacyAPITests(TestCase):
    """
    Verifies that internal anti-abuse farming signals are NEVER exposed to normal participants
    on public/contributor endpoints and ONLY available to staff/admin users.
    """

    def setUp(self):
        self.staff_user = User.objects.create_user(username='staff_auditor', password='password123', is_staff=True)
        self.normal_user = User.objects.create_user(username='regular_dev', password='password123', is_staff=False)
        self.other_user = User.objects.create_user(username='intruder_dev', password='password123', is_staff=False)

        self.participant = Participant.objects.create(
            user=self.normal_user,
            github_id=88001,
            github_username='regular_dev',
        )
        self.project = Project.objects.create(
            github_repo_id=88002,
            owner='hackit',
            name='privacy-repo',
            full_name='hackit/privacy-repo',
            is_enabled=True,
        )
        self.issue = Issue.objects.create(
            github_issue_id=88003,
            project=self.project,
            number=1,
            title='Sample issue',
            points=20,
        )
        self.pr = PullRequest.objects.create(
            github_pr_id=88004,
            repo=self.project,
            number=1,
            author_github_id=self.participant.github_id,
            author_participant=self.participant,
            merged=True,
        )
        self.contrib = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=self.pr,
            status='MERGED',
        )
        self.breakdown = ScoringBreakdown.objects.create(
            contribution=self.contrib,
            base_points=20,
            category='feature',
            category_label='Feature',
            multiplier=1.5,
            calculated_points=30,
            per_pr_cap=100,
            points_after_pr_cap=30,
            daily_points_cap=500,
            daily_points_before=0,
            daily_allowance_remaining=500,
            cap_applied='Not reached',
            final_awarded_points=30,
            farming_signals={
                'has_signals': True,
                'risk_level': 'HIGH',
                'signals': ['rapid_burst'],
                'reasons': ['3 PRs in 60m'],
            },
        )
        self.client = APIClient()

    def test_regular_participant_cannot_see_farming_signals(self):
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.get(f'/api/v1/contributions/{self.contrib.id}/')
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn('scoring_breakdown', data)
        breakdown = data['scoring_breakdown']
        self.assertIsNotNone(breakdown)
        self.assertEqual(breakdown['base_points'], 20)
        self.assertEqual(breakdown['final_awarded_points'], 30)
        # farming_signals MUST NOT be exposed to normal participants
        self.assertNotIn('farming_signals', breakdown)

    def test_staff_user_can_see_farming_signals(self):
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get(f'/api/v1/contributions/{self.contrib.id}/')
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn('scoring_breakdown', data)
        breakdown = data['scoring_breakdown']
        self.assertIsNotNone(breakdown)
        self.assertIn('farming_signals', breakdown)
        self.assertEqual(breakdown['farming_signals']['risk_level'], 'HIGH')

    def test_idor_protection_other_participant_forbidden(self):
        self.client.force_authenticate(user=self.other_user)
        response = self.client.get(f'/api/v1/contributions/{self.contrib.id}/')
        self.assertEqual(response.status_code, 403)
