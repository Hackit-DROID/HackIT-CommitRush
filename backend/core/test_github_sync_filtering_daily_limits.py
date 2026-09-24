import logging
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone as dt_timezone
import zoneinfo
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.github_sync import (
    GitHubClient,
    GitHubNetworkError,
    sync_issues_for_project,
    sync_project,
    sync_repository_and_issues,
)
from core.models import (
    Contribution,
    DailyContributionUsage,
    EventConfig,
    Issue,
    IssueLabel,
    Participant,
    Project,
    PullRequest,
    ScoringBreakdown,
)
from core.leaderboard import invalidate_leaderboard_cache
from core.scoring.engine import ScoringEngine
from core.timezone import get_challenge_today

User = get_user_model()


class TestGitHubSyncPaginationAndPRFiltering(TestCase):
    """
    Tests for Part 1, Part 2, and Part 3:
    - Robust GitHub pagination across multiple pages following Link headers
    - Complete exclusion of pull request payloads
    - Idempotent upserting
    - Structured logging metrics
    """

    def setUp(self):
        self.client = GitHubClient(token='test-token', timeout=10)
        self.project = Project.objects.create(
            github_repo_id=999901,
            owner='Hackit-DROID',
            name='Open-Source-Contribution-Drive',
            full_name='Hackit-DROID/Open-Source-Contribution-Drive',
            language='Python',
            description='Test Repo',
        )

    @patch('core.github_sync.requests.Session.get')
    def test_multi_page_pagination_and_pr_exclusion(self, mock_get):
        """Verify that get_issues iterates through multiple pages and excludes PRs."""
        # Page 1: 2 issues, 1 PR, Link header pointing to page 2
        page1_data = [
            {'id': 1001, 'number': 1, 'title': 'Issue 1', 'state': 'open', 'created_at': '2026-09-01T00:00:00Z'},
            {'id': 1002, 'number': 2, 'title': 'PR 2', 'state': 'open', 'pull_request': {'url': 'https://...'}, 'created_at': '2026-09-01T00:00:00Z'},
            {'id': 1003, 'number': 3, 'title': 'Issue 3', 'state': 'open', 'created_at': '2026-09-01T00:00:00Z'},
        ]
        resp1 = MagicMock()
        resp1.status_code = 200
        resp1.json.return_value = page1_data
        resp1.headers = {
            'Link': '<https://api.github.com/repositories/999901/issues?page=2>; rel="next"',
            'X-RateLimit-Remaining': '4990',
            'X-RateLimit-Limit': '5000',
        }

        # Page 2: 1 issue, 1 PR, no next Link header
        page2_data = [
            {'id': 1004, 'number': 4, 'title': 'Issue 4', 'state': 'open', 'created_at': '2026-09-02T00:00:00Z'},
            {'id': 1005, 'number': 5, 'title': 'PR 5', 'state': 'closed', 'pull_request': {'url': 'https://...'}, 'created_at': '2026-09-02T00:00:00Z'},
        ]
        resp2 = MagicMock()
        resp2.status_code = 200
        resp2.json.return_value = page2_data
        resp2.headers = {
            'X-RateLimit-Remaining': '4989',
            'X-RateLimit-Limit': '5000',
        }

        mock_get.side_effect = [resp1, resp2]

        issues = self.client.get_issues('Hackit-DROID', 'Open-Source-Contribution-Drive')

        # Should have fetched 2 pages
        self.assertEqual(mock_get.call_count, 2)
        # 3 issues returned total, 2 PRs excluded
        self.assertEqual(len(issues), 3)
        issue_ids = [item['id'] for item in issues]
        self.assertEqual(issue_ids, [1001, 1003, 1004])

        # Verify metrics tracked on client
        metrics = self.client.last_sync_metrics
        self.assertEqual(metrics['pages_fetched'], 2)
        self.assertEqual(metrics['github_items_seen'], 5)
        self.assertEqual(metrics['pull_requests_skipped'], 2)

    def test_sync_issues_for_project_idempotent_and_skips_prs(self):
        """Verify that sync_issues_for_project is idempotent and PRs are never saved as Issues."""
        payloads = [
            {'id': 2001, 'number': 10, 'title': 'First Issue', 'state': 'open', 'labels': [{'name': 'difficulty:easy'}]},
            {'id': 2002, 'number': 11, 'title': 'Pull Request', 'state': 'open', 'pull_request': {}},
            {'id': 2003, 'number': 12, 'title': 'Second Issue', 'state': 'open', 'labels': [{'name': 'difficulty:hard'}]},
        ]

        # First run: 2 issues created, 1 PR skipped
        created, updated = sync_issues_for_project(self.project, payloads)
        self.assertEqual(created, 2)
        self.assertEqual(updated, 0)
        self.assertEqual(Issue.objects.count(), 2)
        self.assertFalse(Issue.objects.filter(number=11).exists())

        # Second run: identical payloads should result in 0 created, 2 updated
        created2, updated2 = sync_issues_for_project(self.project, payloads)
        self.assertEqual(created2, 0)
        self.assertEqual(updated2, 2)
        self.assertEqual(Issue.objects.count(), 2)

    @patch('core.github_sync.logger.info')
    @patch('core.github_sync.GitHubClient.get_issues')
    @patch('core.github_sync.GitHubClient.get_repository')
    def test_structured_logging_on_sync(self, mock_get_repo, mock_get_issues, mock_log_info):
        """Verify structured log format during synchronization."""
        mock_get_repo.return_value = {
            'id': 999901,
            'owner': {'login': 'Hackit-DROID'},
            'name': 'Open-Source-Contribution-Drive',
            'full_name': 'Hackit-DROID/Open-Source-Contribution-Drive',
            'language': 'Python',
            'description': 'Test',
        }
        mock_get_issues.return_value = [
            {'id': 3001, 'number': 20, 'title': 'Issue 20', 'state': 'open'},
            {'id': 3002, 'number': 21, 'title': 'Issue 21', 'state': 'open'},
        ]

        client = GitHubClient(token='test')
        client.last_sync_metrics = {
            'pages_fetched': 3,
            'github_items_seen': 25,
            'pull_requests_skipped': 5,
        }

        project, repo_created, issues_created, issues_updated = sync_repository_and_issues(
            'Hackit-DROID/Open-Source-Contribution-Drive',
            client=client,
            sync_issues_flag=True,
        )

        self.assertEqual(issues_created, 2)
        # Check structured log was called
        log_calls = [str(call) for call in mock_log_info.call_args_list]
        found_sync_log = any("GitHub sync:" in c and "Hackit-DROID/Open-Source-Contribution-Drive" in c for c in log_calls)
        self.assertTrue(found_sync_log, f"Expected structured sync log not found in calls: {log_calls}")


class TestIssueFilteringSortingAndPagination(TestCase):
    """
    Tests for Part 4, Part 5, Part 6, Part 7, Part 8:
    - Repository search / filter (partial match, case-insensitive)
    - Language, Difficulty, Category, Status, Points range filters
    - Multi-filter AND semantics
    - Stable sorting with secondary tie-breakers
    - Application pagination after server-side filtering
    """

    def setUp(self):
        self.api_client = APIClient()
        self.project_a = Project.objects.create(
            github_repo_id=10001,
            owner='Hackit-DROID',
            name='Open-Source-Contribution-Drive',
            full_name='Hackit-DROID/Open-Source-Contribution-Drive',
            language='Python',
            is_enabled=True,
        )
        self.project_b = Project.objects.create(
            github_repo_id=10002,
            owner='Hackit-DROID',
            name='Frontend-Showcase',
            full_name='Hackit-DROID/Frontend-Showcase',
            language='TypeScript',
            is_enabled=True,
        )

        # Create distinct test issues
        self.issue1 = Issue.objects.create(
            github_issue_id=50001,
            project=self.project_a,
            number=1,
            title='Fix auth bug in backend',
            points=25,
            difficulty='beginner',
            category='bug',
            status='open',
            created_at=datetime(2026, 9, 1, 10, 0, tzinfo=dt_timezone.utc),
            updated_at=datetime(2026, 9, 5, 12, 0, tzinfo=dt_timezone.utc),
        )
        self.issue2 = Issue.objects.create(
            github_issue_id=50002,
            project=self.project_a,
            number=2,
            title='Add user profile features',
            points=50,
            difficulty='medium',
            category='feature',
            status='open',
            created_at=datetime(2026, 9, 2, 10, 0, tzinfo=dt_timezone.utc),
            updated_at=datetime(2026, 9, 4, 12, 0, tzinfo=dt_timezone.utc),
        )
        self.issue3 = Issue.objects.create(
            github_issue_id=50003,
            project=self.project_a,
            number=3,
            title='Sandbox security enhancement',
            points=100,
            difficulty='master',
            category='security',
            status='closed',
            created_at=datetime(2026, 9, 3, 10, 0, tzinfo=dt_timezone.utc),
            updated_at=datetime(2026, 9, 3, 12, 0, tzinfo=dt_timezone.utc),
        )
        self.issue4 = Issue.objects.create(
            github_issue_id=50004,
            project=self.project_b,
            number=4,
            title='Update landing page animations',
            points=50,
            difficulty='easy',
            category='frontend',
            status='open',
            created_at=datetime(2026, 9, 4, 10, 0, tzinfo=dt_timezone.utc),
            updated_at=datetime(2026, 9, 6, 12, 0, tzinfo=dt_timezone.utc),
        )

    def test_repository_filter_partial_and_case_insensitive(self):
        """Repository filter matches partial name and is case-insensitive."""
        # Exact partial name lowercase
        resp = self.api_client.get('/api/v1/issues/?project=open-source')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 3)

        # Full name with mixed case
        resp2 = self.api_client.get('/api/v1/issues/?project=Hackit-DROID/Frontend-Showcase')
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.data['count'], 1)
        self.assertEqual(resp2.data['results'][0]['github_number'], 4)

    def test_difficulty_canonical_tier_mapping(self):
        """Difficulty queries map canonical aliases (e.g. beginner -> beginner/starter/easy)."""
        # 'beginner' maps to easy/beginner/starter -> issue1 (beginner) and issue4 (easy)
        resp = self.api_client.get('/api/v1/issues/?difficulty=beginner')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 2)
        returned_numbers = {i['github_number'] for i in resp.data['results']}
        self.assertEqual(returned_numbers, {1, 4})

        # 'intermediate' maps to intermediate/medium -> issue2 (medium)
        resp_inter = self.api_client.get('/api/v1/issues/?difficulty=intermediate')
        self.assertEqual(resp_inter.data['count'], 1)
        self.assertEqual(resp_inter.data['results'][0]['github_number'], 2)

        # 'advanced' maps to advanced/hard/master/expert -> issue3 (master)
        resp_adv = self.api_client.get('/api/v1/issues/?difficulty=advanced')
        self.assertEqual(resp_adv.data['count'], 1)
        self.assertEqual(resp_adv.data['results'][0]['github_number'], 3)

    def test_category_filter_normalization(self):
        """Category filter normalizes plural synonyms (features -> feature, bugs -> bug)."""
        resp = self.api_client.get('/api/v1/issues/?category=features')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['github_number'], 2)

        resp_bug = self.api_client.get('/api/v1/issues/?category=bugs')
        self.assertEqual(resp_bug.data['count'], 1)
        self.assertEqual(resp_bug.data['results'][0]['github_number'], 1)

    def test_multi_filter_strict_and_combination(self):
        """Multiple filters are combined with AND logic, not OR."""
        # project matches Open-Source-Contribution-Drive AND status=open AND points_max=30
        resp = self.api_client.get('/api/v1/issues/?project=Open-Source&status=open&points_max=30')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['github_number'], 1)

        # When an impossible combination is requested, returns 0 items
        resp_none = self.api_client.get('/api/v1/issues/?project=Frontend-Showcase&category=bug')
        self.assertEqual(resp_none.data['count'], 0)

    def test_points_range_filter(self):
        """Points min and max range filters work correctly."""
        resp = self.api_client.get('/api/v1/issues/?points_min=30&points_max=60')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 2)  # issue2 (50) and issue4 (50)

    def test_stable_server_side_sorting(self):
        """Sorting happens server-side with secondary deterministic tie-breaker."""
        # Sort points descending (-points)
        resp_desc = self.api_client.get('/api/v1/issues/?sort=-points')
        numbers_desc = [i['github_number'] for i in resp_desc.data['results']]
        # issue3 (100), issue4 (50, num 4), issue2 (50, num 2), issue1 (25)
        self.assertEqual(numbers_desc, [3, 4, 2, 1])

        # Sort points ascending (points)
        resp_asc = self.api_client.get('/api/v1/issues/?sort=points')
        numbers_asc = [i['github_number'] for i in resp_asc.data['results']]
        self.assertEqual(numbers_asc, [1, 2, 4, 3])

        # Sort newest first (-created_at)
        resp_new = self.api_client.get('/api/v1/issues/?sort=newest')
        numbers_new = [i['github_number'] for i in resp_new.data['results']]
        self.assertEqual(numbers_new, [4, 3, 2, 1])

        # Sort recently updated (-updated_at)
        resp_upd = self.api_client.get('/api/v1/issues/?sort=updated')
        numbers_upd = [i['github_number'] for i in resp_upd.data['results']]
        self.assertEqual(numbers_upd, [4, 1, 2, 3])

    def test_application_pagination_after_filtering(self):
        """Pagination returns accurate pages after filtering."""
        resp = self.api_client.get('/api/v1/issues/?page_size=2&page=1')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 4)
        self.assertEqual(len(resp.data['results']), 2)

        resp2 = self.api_client.get('/api/v1/issues/?page_size=2&page=2')
        self.assertEqual(len(resp2.data['results']), 2)


class TestDailyLimitAndPointsEnforcement(TestCase):
    """
    Tests for Part 9, Part 10, Part 11:
    - DAILY_POINTS_LIMIT = 120 authoritative configuration
    - API response exposes daily_limit: 120 and remaining calculation
    - Server-side points cap enforcement in scoring engine
    - Timezone-aware date evaluation in Asia/Kolkata
    """

    def setUp(self):
        cache.clear()
        invalidate_leaderboard_cache()
        self.api_client = APIClient()
        self.config = EventConfig.get_solo()
        self.config.max_points_per_day = 120
        self.config.save()

        self.user = User.objects.create_user(username='testparticipant', password='password')
        self.participant = Participant.objects.create(
            user=self.user,
            github_id=888123,
            github_username='testparticipant',
            total_points=0,
            merged_count=0,
        )

        self.project = Project.objects.create(
            github_repo_id=77701,
            owner='Hackit-DROID',
            name='Open-Source-Contribution-Drive',
            full_name='Hackit-DROID/Open-Source-Contribution-Drive',
            language='Python',
            is_enabled=True,
        )

    def tearDown(self):
        cache.clear()
        invalidate_leaderboard_cache()

    def test_daily_points_limit_setting_and_model_default(self):
        """Verify DAILY_POINTS_LIMIT is 120 in settings and EventConfig."""
        self.assertEqual(getattr(settings, 'DAILY_POINTS_LIMIT', None), 120)
        self.assertEqual(self.config.max_points_per_day, 120)

    def test_dashboard_api_returns_authoritative_daily_limit_120(self):
        """Verify /api/v1/dashboard/ returns max_points=120 and correct remaining allowance."""
        self.api_client.force_authenticate(user=self.user)
        resp = self.api_client.get('/api/v1/dashboard/')
        self.assertEqual(resp.status_code, 200)
        daily_usage = resp.data['daily_usage']
        self.assertEqual(daily_usage['max_points'], 120)
        self.assertEqual(daily_usage['points_count'], 0)

    def test_leaderboard_api_returns_daily_limit_120(self):
        """Verify /api/v1/leaderboard/ returns daily_limit=120 and remaining_daily_allowance=120."""
        resp = self.api_client.get('/api/v1/leaderboard/')
        self.assertEqual(resp.status_code, 200)
        results = resp.data.get('results', resp.data)
        participant_entry = next((e for e in results if e['github_username'] == 'testparticipant'), None)
        self.assertIsNotNone(participant_entry)
        self.assertEqual(participant_entry['daily_limit'], 120)
        self.assertEqual(participant_entry['remaining_daily_allowance'], 120)

    def test_today_points_calculation_and_cap_enforcement(self):
        """
        Verify that earning points decreases remaining allowance and enforces 120 cap:
        - User earns 40 points -> remaining 80
        - User earns next 80 points -> remaining 0
        - Submitting further points is capped or deferred
        """
        today = get_challenge_today()
        daily_usage = DailyContributionUsage.objects.create(
            participant=self.participant,
            date=today,
            points_count=40,
            contributions_count=1,
        )

        # Check leaderboard calculation
        resp = self.api_client.get('/api/v1/leaderboard/')
        entry = next((e for e in resp.data.get('results', resp.data) if e['github_username'] == 'testparticipant'), None)
        self.assertEqual(entry['points_today'], 40)
        self.assertEqual(entry['remaining_daily_allowance'], 80)

        # Now simulate user with 120 points reached
        daily_usage.points_count = 120
        daily_usage.save()
        invalidate_leaderboard_cache()

        resp2 = self.api_client.get('/api/v1/leaderboard/')
        entry2 = next((e for e in resp2.data.get('results', resp2.data) if e['github_username'] == 'testparticipant'), None)
        self.assertEqual(entry2['points_today'], 120)
        self.assertEqual(entry2['remaining_daily_allowance'], 0)
        self.assertTrue(entry2['is_daily_limit_reached'])

    def test_scoring_engine_caps_at_daily_allowance(self):
        """
        Verify award_contribution_points strictly respects daily cap of 120.
        If user has 100 points today and 50 points are calculated, only 20 points are awarded.
        """
        today = get_challenge_today()
        DailyContributionUsage.objects.create(
            participant=self.participant,
            date=today,
            points_count=100,
            contributions_count=1,
        )

        issue = Issue.objects.create(
            github_issue_id=60001,
            project=self.project,
            number=99,
            title='Big Feature',
            points=50,
            difficulty='medium',
            category='feature',
            status='open',
        )
        pr = PullRequest.objects.create(
            github_pr_id=70001,
            repo=self.project,
            number=99,
            author_github_id=self.participant.github_id,
        )
        contrib = Contribution.objects.create(
            participant=self.participant,
            issue=issue,
            pull_request=pr,
            status='APPROVED',
        )

        # Award points: remaining allowance is 120 - 100 = 20
        # Contribution has 50 points * 1.0 (default multiplier) = 50 calculated
        # Allowed points should be min(50, 20) = 20
        result = ScoringEngine.award_points_for_contribution(contrib)
        self.assertEqual(result['status'], 'AWARDED')
        self.assertEqual(result['points'], 20)

        breakdown = ScoringBreakdown.objects.get(contribution=contrib)
        self.assertEqual(breakdown.daily_points_cap, 120)
        self.assertEqual(breakdown.daily_points_before, 100)
        self.assertEqual(breakdown.daily_allowance_remaining, 20)
        self.assertEqual(breakdown.final_awarded_points, 20)
        self.assertEqual(breakdown.cap_applied, 'Daily limit')

        # Total points today is now exactly 120
        usage = DailyContributionUsage.objects.get(participant=self.participant, date=today)
        self.assertEqual(usage.points_count, 120)
