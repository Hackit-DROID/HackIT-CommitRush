from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import (
    Contribution,
    Issue,
    IssueLabel,
    Participant,
    Project,
    PullRequest,
)

User = get_user_model()


class CoreReadAPIsTestCase(TestCase):
    """
    Test suite for M3: Core Read APIs (M3-T1, M3-T2, M3-T3, M3-T4, M3-T5).
    Verifies endpoints, parameter parsing, query filtering, slug resolution (AMB-9),
    chronological sorting (M3-T3 correction), issue detail (M3-T4), rate throttling (M3-T5),
    and zero-network invariant.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.now = timezone.now()

        # Create sample projects
        self.proj_python = Project.objects.create(
            github_repo_id=101,
            owner='hackit',
            name='fast-api-core',
            full_name='hackit/fast-api-core',
            language='Python',
            is_enabled=True,
            description='High performance backend microservice for CommitRush',
        )
        self.proj_ts = Project.objects.create(
            github_repo_id=102,
            owner='hackit',
            name='commitrush-ui',
            full_name='hackit/commitrush-ui',
            language='TypeScript',
            is_enabled=True,
            description='Frontend Single Page Application built with React and Tailwind',
        )
        self.proj_disabled = Project.objects.create(
            github_repo_id=103,
            owner='hackit',
            name='legacy-docs',
            full_name='hackit/legacy-docs',
            language='Markdown',
            is_enabled=False,
            description='Archived repository documentation',
        )

        # Create sample labels
        self.label_bug = IssueLabel.objects.create(name='bug', color='d73a4a')
        self.label_good_first = IssueLabel.objects.create(name='good first issue', color='7057ff')
        self.label_backend = IssueLabel.objects.create(name='backend', color='008672')

        # Create sample issues with explicit created_at timestamps
        self.issue1 = Issue.objects.create(
            github_issue_id=201,  # Created earliest (4 days ago)
            project=self.proj_python,
            number=10,
            title='Implement health check ping',
            points=25,
            difficulty='beginner',
            category='backend',
            status='open',
            is_featured=False,
            created_at=self.now - timedelta(days=4),
        )
        self.issue1.labels.add(self.label_good_first, self.label_backend)

        self.issue2 = Issue.objects.create(
            github_issue_id=202,  # Created 3 days ago
            project=self.proj_python,
            number=20,
            title='Fix race condition in database pool',
            points=100,
            difficulty='advanced',
            category='backend',
            status='open',
            is_featured=True,
            created_at=self.now - timedelta(days=3),
        )
        self.issue2.labels.add(self.label_bug, self.label_backend)

        self.issue3 = Issue.objects.create(
            github_issue_id=203,  # Created 2 days ago
            project=self.proj_ts,
            number=5,
            title='Design dark mode theme switcher',
            points=50,
            difficulty='intermediate',
            category='frontend',
            status='open',
            is_featured=True,
            created_at=self.now - timedelta(days=2),
        )
        self.issue3.labels.add(self.label_good_first)

        self.issue4 = Issue.objects.create(
            github_issue_id=204,  # Created latest (1 day ago)
            project=self.proj_ts,
            number=12,
            title='Close resolved navbar bug',
            points=25,
            difficulty='beginner',
            category='frontend',
            status='closed',
            is_featured=False,
            created_at=self.now - timedelta(days=1),
        )

        # Create sample participant and contributions for project detail metrics
        self.user = User.objects.create_user(username='octo_coder', email='octo@example.com')
        self.participant = Participant.objects.create(
            user=self.user,
            github_id=9001,
            github_username='octo_coder',
        )
        self.pr1 = PullRequest.objects.create(
            github_pr_id=501,
            repo=self.proj_python,
            number=101,
            author_github_id=9001,
            author_participant=self.participant,
            merged=True,
        )
        self.pr2 = PullRequest.objects.create(
            github_pr_id=502,
            repo=self.proj_python,
            number=102,
            author_github_id=9001,
            author_participant=self.participant,
            merged=False,
        )
        self.contrib1 = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue2,
            pull_request=self.pr1,
            status='MERGED',
        )
        self.contrib2 = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue1,
            pull_request=self.pr2,
            status='UNDER_REVIEW',
        )

    def tearDown(self):
        cache.clear()

    # =========================================================================
    # M3-T1: GET /api/v1/projects/ (Project List Endpoint)
    # =========================================================================

    def test_m3_t1_project_list_public_access(self):
        """Unauthenticated clients can access project listings (HTTP 200)."""
        response = self.client.get('/api/v1/projects/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('count', data)
        self.assertIn('results', data)
        self.assertEqual(data['count'], 3)

    def test_m3_t1_project_list_response_shape(self):
        """Verify the exact field structure of each project list result."""
        response = self.client.get('/api/v1/projects/')
        self.assertEqual(response.status_code, 200)
        first_item = response.json()['results'][0]
        expected_keys = {
            'id',
            'github_repo_id',
            'owner',
            'name',
            'full_name',
            'language',
            'is_enabled',
            'description',
        }
        self.assertEqual(set(first_item.keys()), expected_keys)
        self.assertEqual(first_item['owner'], 'hackit')

    def test_m3_t1_project_list_search_by_name(self):
        """Filter projects by name partial match."""
        response = self.client.get('/api/v1/projects/?search=fast-api')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['name'], 'fast-api-core')

    def test_m3_t1_project_list_search_by_full_name(self):
        """Filter projects by full_name partial match."""
        response = self.client.get('/api/v1/projects/?search=hackit/commitrush')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['full_name'], 'hackit/commitrush-ui')

    def test_m3_t1_project_list_search_by_description(self):
        """Filter projects by description partial match."""
        response = self.client.get('/api/v1/projects/?search=microservice')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['name'], 'fast-api-core')

    def test_m3_t1_project_list_filter_language_case_insensitive(self):
        """Filter projects by programming language (case-insensitive)."""
        response = self.client.get('/api/v1/projects/?language=python')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['language'], 'Python')

    def test_m3_t1_project_list_filter_enabled_true(self):
        """Filter enabled projects using 'true', '1', 'yes'."""
        for val in ['true', 'True', '1', 'yes']:
            with self.subTest(val=val):
                response = self.client.get(f'/api/v1/projects/?enabled={val}')
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(data['count'], 2)
                for item in data['results']:
                    self.assertTrue(item['is_enabled'])

    def test_m3_t1_project_list_filter_enabled_false(self):
        """Filter disabled projects using 'false', '0', 'no'."""
        for val in ['false', 'False', '0', 'no']:
            with self.subTest(val=val):
                response = self.client.get(f'/api/v1/projects/?enabled={val}')
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(data['count'], 1)
                self.assertEqual(data['results'][0]['name'], 'legacy-docs')
                self.assertFalse(data['results'][0]['is_enabled'])

    def test_m3_t1_project_list_invalid_enabled_returns_400(self):
        """Passing an invalid boolean to 'enabled' returns HTTP 400 Bad Request."""
        response = self.client.get('/api/v1/projects/?enabled=maybe')
        self.assertEqual(response.status_code, 400)
        self.assertIn('enabled', response.json())

    def test_m3_t1_project_list_pagination(self):
        """Verify custom page size and pagination next/previous links."""
        response = self.client.get('/api/v1/projects/?page_size=1')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 3)
        self.assertEqual(len(data['results']), 1)
        self.assertIsNotNone(data['next'])
        self.assertIsNone(data['previous'])

        # Page 2
        response_page2 = self.client.get('/api/v1/projects/?page=2&page_size=1')
        self.assertEqual(response_page2.status_code, 200)
        data_page2 = response_page2.json()
        self.assertEqual(len(data_page2['results']), 1)
        self.assertIsNotNone(data_page2['previous'])

    def test_m3_t1_project_list_deterministic_ordering(self):
        """Projects are deterministically ordered by full_name and id."""
        response = self.client.get('/api/v1/projects/')
        self.assertEqual(response.status_code, 200)
        full_names = [p['full_name'] for p in response.json()['results']]
        self.assertEqual(
            full_names,
            ['hackit/commitrush-ui', 'hackit/fast-api-core', 'hackit/legacy-docs']
        )

    def test_m3_t1_project_list_root_and_versioned_parity(self):
        """Both root /projects/ and /api/v1/projects/ return identical results."""
        res_root = self.client.get('/projects/')
        res_v1 = self.client.get('/api/v1/projects/')
        self.assertEqual(res_root.status_code, 200)
        self.assertEqual(res_v1.status_code, 200)
        self.assertEqual(res_root.json()['count'], res_v1.json()['count'])

    # =========================================================================
    # M3-T2: GET /api/v1/projects/{slug}/ (Project Detail Endpoint)
    # =========================================================================

    def test_m3_t2_project_detail_public_access(self):
        """Unauthenticated clients can access project detail (HTTP 200)."""
        response = self.client.get('/api/v1/projects/hackit/fast-api-core/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['name'], 'fast-api-core')
        self.assertEqual(data['full_name'], 'hackit/fast-api-core')

    def test_m3_t2_project_detail_response_shape(self):
        """Verify all required metadata, issue count, and contribution metrics."""
        response = self.client.get('/api/v1/projects/hackit/fast-api-core/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        expected_keys = {
            'id',
            'github_repo_id',
            'owner',
            'name',
            'full_name',
            'language',
            'is_enabled',
            'description',
            'issue_count',
            'open_issue_count',
            'contribution_activity',
        }
        self.assertEqual(set(data.keys()), expected_keys)
        self.assertEqual(data['issue_count'], 2)
        self.assertEqual(data['open_issue_count'], 2)
        self.assertEqual(data['contribution_activity'], {
            'total_contributions': 2,
            'merged_contributions': 1,
            'in_progress_contributions': 1,
        })

    def test_m3_t2_project_detail_slug_resolution_full_name(self):
        """Resolve slug in 'owner/name' format (e.g. /projects/hackit/fast-api-core/)."""
        response = self.client.get('/api/v1/projects/hackit/fast-api-core/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], self.proj_python.id)

    def test_m3_t2_project_detail_slug_resolution_hyphenated(self):
        """Resolve slug in 'owner-name' format without schema alteration (AMB-9)."""
        response = self.client.get('/api/v1/projects/hackit-fast-api-core/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], self.proj_python.id)

    def test_m3_t2_project_detail_slug_resolution_name_only(self):
        """Resolve slug by repository name only."""
        response = self.client.get('/api/v1/projects/fast-api-core/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], self.proj_python.id)

    def test_m3_t2_project_detail_case_insensitivity(self):
        """Slug resolution is case-insensitive."""
        response = self.client.get('/api/v1/projects/HACKIT/FAST-API-CORE/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], self.proj_python.id)

    def test_m3_t2_project_detail_not_found(self):
        """Non-existent project slug returns HTTP 404 with descriptive detail."""
        response = self.client.get('/api/v1/projects/non-existent-repo/')
        self.assertEqual(response.status_code, 404)
        self.assertIn('detail', response.json())

    def test_m3_t2_project_detail_zero_activity(self):
        """Project with no issues or contributions returns zero metrics cleanly."""
        response = self.client.get('/api/v1/projects/hackit/legacy-docs/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['issue_count'], 0)
        self.assertEqual(data['open_issue_count'], 0)
        self.assertEqual(data['contribution_activity'], {
            'total_contributions': 0,
            'merged_contributions': 0,
            'in_progress_contributions': 0,
        })

    # =========================================================================
    # M3-T3: GET /api/v1/issues/ (Issue List Endpoint) & Newest Chronology Fix
    # =========================================================================

    def test_m3_t3_issue_list_public_access(self):
        """Unauthenticated clients can access issue list (HTTP 200)."""
        response = self.client.get('/api/v1/issues/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 4)

    def test_m3_t3_issue_list_response_shape(self):
        """Matches the example request/response shape in PRD §16."""
        response = self.client.get('/api/v1/issues/')
        self.assertEqual(response.status_code, 200)
        results = response.json()['results']
        first = results[0]
        expected_keys = {
            'id',
            'title',
            'project',
            'github_number',
            'points',
            'difficulty',
            'category',
            'status',
            'is_featured',
            'labels',
            'github_url',
            'created_at',
        }
        self.assertEqual(set(first.keys()), expected_keys)
        self.assertIsInstance(first['labels'], list)
        self.assertTrue(first['github_url'].startswith('https://github.com/'))

    def test_m3_t3_sort_newest_cross_project_chronology(self):
        """
        M3-T3 Blocker 1 Fix:
        Proves that sort=newest uses explicit created_at timestamps across projects,
        NOT repository issue number or github_issue_id.
        
        Setup:
        - Project A issue #100 was created EARLIER (created_at = 10 days ago, github_issue_id=9999)
        - Project B issue #1 was created LATER (created_at = 1 hour ago, github_issue_id=1111)
        
        Under created_at sorting (-created_at, -id), Project B issue #1 correctly appears before Project A issue #100.
        """
        proj_a = Project.objects.create(
            github_repo_id=701,
            owner='test-org',
            name='repo-a',
            full_name='test-org/repo-a',
        )
        proj_b = Project.objects.create(
            github_repo_id=702,
            owner='test-org',
            name='repo-b',
            full_name='test-org/repo-b',
        )

        # Older issue with higher github_issue_id and higher issue number
        older_issue = Issue.objects.create(
            github_issue_id=9999,
            project=proj_a,
            number=100,
            title='Older issue created 10 days ago',
            points=50,
            created_at=self.now - timedelta(days=10),
        )
        # Newer issue with lower github_issue_id and lower issue number
        newer_issue = Issue.objects.create(
            github_issue_id=1111,
            project=proj_b,
            number=1,
            title='Newer issue created 1 hour ago',
            points=50,
            created_at=self.now - timedelta(hours=1),
        )

        # Query with sort=newest
        response = self.client.get('/api/v1/issues/?sort=newest')
        self.assertEqual(response.status_code, 200)
        data = response.json()['results']

        # Filter only the two newly created issues in this test
        matching_ids = [item['id'] for item in data if item['id'] in (older_issue.id, newer_issue.id)]
        
        # Newest must place newer_issue before older_issue based on created_at
        self.assertEqual(matching_ids, [newer_issue.id, older_issue.id])

    def test_m3_t3_sort_oldest_cross_project_chronology(self):
        """sort=oldest uses ascending created_at with deterministic secondary tie-breaker."""
        response = self.client.get('/api/v1/issues/?sort=oldest')
        self.assertEqual(response.status_code, 200)
        data = response.json()['results']
        ids = [item['id'] for item in data]
        # Issue 1 (4 days ago), Issue 2 (3 days ago), Issue 3 (2 days ago), Issue 4 (1 day ago)
        self.assertEqual(ids, [self.issue1.id, self.issue2.id, self.issue3.id, self.issue4.id])

    def test_m3_t3_sort_newest_deterministic_tie_breaker(self):
        """When two issues have identical created_at, secondary ordering by -id is deterministic."""
        same_time = self.now - timedelta(days=5)
        tied1 = Issue.objects.create(
            github_issue_id=8881,
            project=self.proj_python,
            number=301,
            title='Tied Issue 1',
            points=10,
            created_at=same_time,
        )
        tied2 = Issue.objects.create(
            github_issue_id=8882,
            project=self.proj_python,
            number=302,
            title='Tied Issue 2',
            points=10,
            created_at=same_time,
        )

        response = self.client.get('/api/v1/issues/?sort=newest')
        self.assertEqual(response.status_code, 200)
        data = response.json()['results']
        matching_ids = [item['id'] for item in data if item['id'] in (tied1.id, tied2.id)]
        self.assertEqual(matching_ids, [tied2.id, tied1.id])  # tied2 has higher id

    def test_m3_t3_issue_list_filter_project_full_name(self):
        """Filter issues by project full_name (e.g., ?project=hackit/fast-api-core)."""
        response = self.client.get('/api/v1/issues/?project=hackit/fast-api-core')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 2)
        for issue in data['results']:
            self.assertEqual(issue['project'], 'hackit/fast-api-core')

    def test_m3_t3_issue_list_filter_project_hyphenated_slug(self):
        """Filter issues by hyphenated project slug (e.g., ?project=hackit-fast-api-core)."""
        response = self.client.get('/api/v1/issues/?project=hackit-fast-api-core')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 2)
        for issue in data['results']:
            self.assertEqual(issue['project'], 'hackit/fast-api-core')

    def test_m3_t3_issue_list_filter_language(self):
        """Filter issues by project language."""
        response = self.client.get('/api/v1/issues/?language=TypeScript')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 2)
        for issue in data['results']:
            self.assertEqual(issue['project'], 'hackit/commitrush-ui')

    def test_m3_t3_issue_list_filter_difficulty(self):
        """Filter issues by difficulty tier."""
        response = self.client.get('/api/v1/issues/?difficulty=beginner')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 2)
        for issue in data['results']:
            self.assertEqual(issue['difficulty'], 'beginner')

    def test_m3_t3_issue_list_filter_category(self):
        """Filter issues by category domain."""
        response = self.client.get('/api/v1/issues/?category=backend')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 2)
        for issue in data['results']:
            self.assertEqual(issue['category'], 'backend')

    def test_m3_t3_issue_list_filter_status(self):
        """Filter issues by status ('open' or 'closed')."""
        response_open = self.client.get('/api/v1/issues/?status=open')
        self.assertEqual(response_open.status_code, 200)
        self.assertEqual(response_open.json()['count'], 3)

        response_closed = self.client.get('/api/v1/issues/?status=closed')
        self.assertEqual(response_closed.status_code, 200)
        self.assertEqual(response_closed.json()['count'], 1)
        self.assertEqual(response_closed.json()['results'][0]['status'], 'closed')

    def test_m3_t3_issue_list_filter_is_featured(self):
        """Filter issues by featured flag."""
        response = self.client.get('/api/v1/issues/?is_featured=true')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 2)
        for issue in data['results']:
            self.assertTrue(issue['is_featured'])

    def test_m3_t3_issue_list_filter_points_min_and_max(self):
        """Filter issues within a point range (points_min and points_max)."""
        response = self.client.get('/api/v1/issues/?points_min=50&points_max=100')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 2)
        points_list = [i['points'] for i in data['results']]
        self.assertEqual(sorted(points_list), [50, 100])

    def test_m3_t3_issue_list_filter_inverted_points_range_returns_empty(self):
        """When points_min > points_max, an empty list is returned."""
        response = self.client.get('/api/v1/issues/?points_min=100&points_max=20')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 0)
        self.assertEqual(data['results'], [])

    def test_m3_t3_issue_list_invalid_points_params_returns_400(self):
        """Non-integer or negative point bounds return HTTP 400 Bad Request."""
        res1 = self.client.get('/api/v1/issues/?points_min=abc')
        self.assertEqual(res1.status_code, 400)
        self.assertIn('points_min', res1.json())

        res2 = self.client.get('/api/v1/issues/?points_min=-10')
        self.assertEqual(res2.status_code, 400)
        self.assertIn('points_min', res2.json())

        res3 = self.client.get('/api/v1/issues/?points_max=xyz')
        self.assertEqual(res3.status_code, 400)
        self.assertIn('points_max', res3.json())

    def test_m3_t3_issue_list_sorting_points(self):
        """Verify sorting by points descending (-points) and ascending (points)."""
        res_desc = self.client.get('/api/v1/issues/?sort=-points')
        self.assertEqual(res_desc.status_code, 200)
        points_desc = [i['points'] for i in res_desc.json()['results']]
        self.assertEqual(points_desc, [100, 50, 25, 25])

        res_asc = self.client.get('/api/v1/issues/?sort=points')
        self.assertEqual(res_asc.status_code, 200)
        points_asc = [i['points'] for i in res_asc.json()['results']]
        self.assertEqual(points_asc, [25, 25, 50, 100])

    def test_m3_t3_issue_list_invalid_sort_returns_400(self):
        """Invalid sort option returns HTTP 400 with helpful error message."""
        response = self.client.get('/api/v1/issues/?sort=unsupported_sort')
        self.assertEqual(response.status_code, 400)
        self.assertIn('sort', response.json())

    def test_m3_t3_issue_list_prd_section16_example(self):
        """
        Exact test of PRD §16 example request:
        ?project=hackit-fast-api-core&difficulty=advanced&points_min=50&sort=-points
        """
        url = '/api/v1/issues/?project=hackit-fast-api-core&difficulty=advanced&points_min=50&sort=-points'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 1)
        res = data['results'][0]
        self.assertEqual(res['id'], self.issue2.id)
        self.assertEqual(res['title'], 'Fix race condition in database pool')
        self.assertEqual(res['project'], 'hackit/fast-api-core')
        self.assertEqual(res['github_number'], 20)
        self.assertEqual(res['points'], 100)
        self.assertEqual(res['difficulty'], 'advanced')
        self.assertEqual(res['category'], 'backend')
        self.assertEqual(res['status'], 'open')
        self.assertEqual(res['github_url'], 'https://github.com/hackit/fast-api-core/issues/20')
        self.assertIn('bug', res['labels'])
        self.assertIn('backend', res['labels'])

    def test_m3_t3_issue_list_empty_labels(self):
        """Issue with no labels returns an empty list, not null."""
        response = self.client.get(f'/api/v1/issues/?difficulty=beginner&category=frontend')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['labels'], [])

    def test_m3_t3_issue_list_server_side_pagination(self):
        """Server-side pagination limits response size per page and provides valid page traversal."""
        response = self.client.get('/api/v1/issues/?page_size=2')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 4)
        self.assertEqual(len(data['results']), 2)
        self.assertIsNotNone(data['next'])
        self.assertIsNone(data['previous'])

        # Fetch page 2
        response_p2 = self.client.get(data['next'])
        self.assertEqual(response_p2.status_code, 200)
        data_p2 = response_p2.json()
        self.assertEqual(len(data_p2['results']), 2)
        self.assertIsNotNone(data_p2['previous'])

    def test_m3_t3_issue_list_pagination_out_of_bounds(self):
        """Requesting a page beyond total pages returns HTTP 404."""
        response = self.client.get('/api/v1/issues/?page=999')
        self.assertEqual(response.status_code, 404)

    # =========================================================================
    # M3-T4: GET /api/v1/issues/{id}/ (Issue Detail Endpoint)
    # =========================================================================

    def test_m3_t4_issue_detail_public_access(self):
        """Unauthenticated clients can access issue detail (HTTP 200)."""
        response = self.client.get(f'/api/v1/issues/{self.issue2.id}/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['id'], self.issue2.id)
        self.assertEqual(data['title'], self.issue2.title)

    def test_m3_t4_issue_detail_response_shape(self):
        """Issue detail contains required metadata and canonical GitHub issue URL."""
        response = self.client.get(f'/api/v1/issues/{self.issue2.id}/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        expected_keys = {
            'id',
            'github_issue_id',
            'title',
            'project',
            'project_id',
            'project_name',
            'github_number',
            'points',
            'difficulty',
            'category',
            'status',
            'is_featured',
            'labels',
            'github_url',
            'created_at',
        }
        self.assertEqual(set(data.keys()), expected_keys)
        self.assertEqual(data['project'], 'hackit/fast-api-core')
        self.assertEqual(data['project_id'], self.proj_python.id)
        self.assertEqual(data['project_name'], 'fast-api-core')
        self.assertEqual(data['github_number'], 20)
        self.assertEqual(data['github_url'], 'https://github.com/hackit/fast-api-core/issues/20')
        self.assertEqual(data['points'], 100)
        self.assertIn('bug', data['labels'])

    def test_m3_t4_issue_detail_not_found(self):
        """Nonexistent issue ID returns HTTP 404."""
        response = self.client.get('/api/v1/issues/999999/')
        self.assertEqual(response.status_code, 404)
        self.assertIn('detail', response.json())

    # =========================================================================
    # M3-T5: DRF Throttling Tests
    # =========================================================================

    def test_m3_t5_normal_request_rate_allowed(self):
        """Normal requests under the rate limit succeed with HTTP 200."""
        res_proj = self.client.get('/api/v1/projects/')
        self.assertEqual(res_proj.status_code, 200)
        res_issues = self.client.get('/api/v1/issues/')
        self.assertEqual(res_issues.status_code, 200)

    @override_settings(
        REST_FRAMEWORK={
            'DEFAULT_AUTHENTICATION_CLASSES': [
                'rest_framework.authentication.SessionAuthentication',
            ],
            'DEFAULT_PERMISSION_CLASSES': [
                'rest_framework.permissions.IsAuthenticated',
            ],
            'DEFAULT_THROTTLE_CLASSES': [],
            'DEFAULT_THROTTLE_RATES': {
                'projects_list': '2/minute',
                'issues_list': '2/minute',
                'anon': '100/minute',
                'user': '100/minute',
            },
        }
    )
    def test_m3_t5_projects_endpoint_throttling_exceeded_returns_429(self):
        """Anonymous rate limit exceeded on /projects/ returns HTTP 429, while detail view is NOT throttled."""
        cache.clear()
        # Request 1 -> 200
        res1 = self.client.get('/api/v1/projects/')
        self.assertEqual(res1.status_code, 200)
        # Request 2 -> 200
        res2 = self.client.get('/api/v1/projects/')
        self.assertEqual(res2.status_code, 200)
        # Request 3 -> 429 Throttled
        res3 = self.client.get('/api/v1/projects/')
        self.assertEqual(res3.status_code, 429)
        self.assertIn('detail', res3.json())
        self.assertTrue('throttled' in res3.json()['detail'].lower())

        # Detail endpoint (/projects/{slug}/) must NOT be throttled even after list limit exceeded
        for _ in range(5):
            res_detail = self.client.get(f'/api/v1/projects/{self.proj_python.full_name}/')
            self.assertEqual(res_detail.status_code, 200)

    @override_settings(
        REST_FRAMEWORK={
            'DEFAULT_AUTHENTICATION_CLASSES': [
                'rest_framework.authentication.SessionAuthentication',
            ],
            'DEFAULT_PERMISSION_CLASSES': [
                'rest_framework.permissions.IsAuthenticated',
            ],
            'DEFAULT_THROTTLE_CLASSES': [],
            'DEFAULT_THROTTLE_RATES': {
                'projects_list': '2/minute',
                'issues_list': '2/minute',
                'anon': '100/minute',
                'user': '100/minute',
            },
        }
    )
    def test_m3_t5_issues_endpoint_throttling_exceeded_returns_429(self):
        """Anonymous rate limit exceeded on /issues/ returns HTTP 429, while issue detail is NOT throttled."""
        cache.clear()
        # Request 1 -> 200
        res1 = self.client.get('/api/v1/issues/')
        self.assertEqual(res1.status_code, 200)
        # Request 2 -> 200
        res2 = self.client.get('/api/v1/issues/')
        self.assertEqual(res2.status_code, 200)
        # Request 3 -> 429 Throttled
        res3 = self.client.get('/api/v1/issues/')
        self.assertEqual(res3.status_code, 429)
        self.assertIn('detail', res3.json())

        # Issue detail endpoint (/issues/{id}/) must NOT be throttled
        for _ in range(5):
            res_detail = self.client.get(f'/api/v1/issues/{self.issue1.id}/')
            self.assertEqual(res_detail.status_code, 200)

    @override_settings(
        REST_FRAMEWORK={
            'DEFAULT_AUTHENTICATION_CLASSES': [
                'rest_framework.authentication.SessionAuthentication',
            ],
            'DEFAULT_PERMISSION_CLASSES': [
                'rest_framework.permissions.IsAuthenticated',
            ],
            'DEFAULT_THROTTLE_CLASSES': [],
            'DEFAULT_THROTTLE_RATES': {
                'projects_list': '2/minute',
                'issues_list': '2/minute',
                'anon': '100/minute',
                'user': '100/minute',
            },
        }
    )
    def test_m3_t5_authenticated_user_throttling(self):
        """Authenticated users are throttled per-user budget on list endpoints without affecting detail views."""
        cache.clear()
        auth_client = APIClient()
        auth_client.force_authenticate(user=self.user)

        res1 = auth_client.get('/api/v1/issues/')
        self.assertEqual(res1.status_code, 200)
        res2 = auth_client.get('/api/v1/issues/')
        self.assertEqual(res2.status_code, 200)
        res3 = auth_client.get('/api/v1/issues/')
        self.assertEqual(res3.status_code, 429)

        # Detail endpoint succeeds for authenticated user even after list limit exceeded
        res_detail = auth_client.get(f'/api/v1/issues/{self.issue1.id}/')
        self.assertEqual(res_detail.status_code, 200)

    @override_settings(
        REST_FRAMEWORK={
            'DEFAULT_AUTHENTICATION_CLASSES': [
                'rest_framework.authentication.SessionAuthentication',
            ],
            'DEFAULT_PERMISSION_CLASSES': [
                'rest_framework.permissions.IsAuthenticated',
            ],
            'DEFAULT_THROTTLE_CLASSES': [],
            'DEFAULT_THROTTLE_RATES': {
                'projects_list': '1/minute',
                'issues_list': '1/minute',
            },
        }
    )
    def test_m3_t5_detail_endpoints_unthrottled_under_high_volume(self):
        """Detail endpoints have no throttle classes and remain unthrottled under high request volume."""
        cache.clear()
        # 10 consecutive requests to project detail
        for _ in range(10):
            res = self.client.get(f'/api/v1/projects/{self.proj_python.full_name}/')
            self.assertEqual(res.status_code, 200)

        # 10 consecutive requests to issue detail
        for _ in range(10):
            res = self.client.get(f'/api/v1/issues/{self.issue2.id}/')
            self.assertEqual(res.status_code, 200)

    # =========================================================================
    # INVARIANTS & SAFETY TESTS
    # =========================================================================

    @patch('urllib.request.urlopen')
    @patch('http.client.HTTPConnection')
    @patch('http.client.HTTPSConnection')
    def test_m3_zero_github_network_calls(self, mock_https, mock_http, mock_urlopen):
        """
        Verify the non-negotiable invariant:
        All M3 read API requests are served purely from PostgreSQL with 0 external network requests.
        """
        mock_urlopen.side_effect = AssertionError("M3 must NEVER make urllib network calls!")
        mock_http.side_effect = AssertionError("M3 must NEVER make HTTP network calls!")
        mock_https.side_effect = AssertionError("M3 must NEVER make HTTPS network calls!")

        endpoints = [
            '/api/v1/projects/',
            '/api/v1/projects/hackit/fast-api-core/',
            '/api/v1/projects/hackit-fast-api-core/',
            '/api/v1/issues/',
            f'/api/v1/issues/{self.issue1.id}/',
            '/api/v1/issues/?project=hackit-fast-api-core&difficulty=advanced&points_min=50&sort=-points',
        ]
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                res = self.client.get(endpoint)
                self.assertEqual(res.status_code, 200)

    def test_m3_query_efficiency_no_n_plus_one(self):
        """
        Verify that fetching issues uses select_related / prefetch_related
        so that query count remains O(1) regardless of number of items.
        """
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get('/api/v1/issues/')
            self.assertEqual(response.status_code, 200)
            # Expecting 1 COUNT query for pagination, 1 query for issues + project join, 1 query for labels prefetch
            # Total queries must be <= 4, never N+1
            self.assertLessEqual(len(ctx.captured_queries), 4)
