from io import StringIO
from unittest.mock import MagicMock, patch
import requests

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from core.github_sync import (
    GitHubClient,
    GitHubSyncError,
    GitHubConfigurationError,
    GitHubResourceNotFoundError,
    GitHubAuthenticationError,
    GitHubRateLimitError,
    GitHubAPIError,
    GitHubNetworkError,
    GitHubDataError,
    parse_repo_identifier,
    sync_project,
    sync_label,
    sync_issue,
    sync_issues_for_project,
    sync_repository_by_name,
    sync_repository_and_issues,
)
from core.models import Issue, IssueLabel, Project


SAMPLE_REPO_PAYLOAD = {
    'id': 12345678,
    'name': 'awesome-project',
    'full_name': 'hackit/awesome-project',
    'owner': {
        'login': 'hackit',
        'id': 99999,
        'type': 'Organization',
    },
    'language': 'Python',
    'description': 'An awesome open source project for HackIT',
    'html_url': 'https://github.com/hackit/awesome-project',
}

SAMPLE_ISSUE_PAYLOAD_1 = {
    'id': 100001,
    'number': 42,
    'title': 'Fix authentication state race condition',
    'state': 'open',
    'html_url': 'https://github.com/hackit/awesome-project/issues/42',
    'user': {'login': 'contributor1'},
    'labels': [
        {'id': 1, 'name': 'bug', 'color': 'd73a4a'},
        {'id': 2, 'name': 'security', 'color': 'b60205'},
    ],
}

SAMPLE_ISSUE_PAYLOAD_2 = {
    'id': 100002,
    'number': 43,
    'title': 'Add database health check endpoint',
    'state': 'closed',
    'html_url': 'https://github.com/hackit/awesome-project/issues/43',
    'user': {'login': 'contributor2'},
    'labels': [
        {'id': 3, 'name': 'enhancement', 'color': 'a2eeef'},
        {'id': 1, 'name': 'bug', 'color': 'd73a4a'},
    ],
}

SAMPLE_PR_PAYLOAD = {
    'id': 100003,
    'number': 44,
    'title': 'Add new feature pull request',
    'state': 'open',
    'pull_request': {
        'url': 'https://api.github.com/repos/hackit/awesome-project/pulls/44',
        'html_url': 'https://github.com/hackit/awesome-project/pull/44',
    },
    'labels': [{'id': 4, 'name': 'wip', 'color': 'ffffff'}],
}


class ParseRepoIdentifierTestCase(TestCase):
    def test_valid_identifiers(self):
        owner, name = parse_repo_identifier('hackit/commitrush')
        self.assertEqual(owner, 'hackit')
        self.assertEqual(name, 'commitrush')

        owner, name = parse_repo_identifier('  facebook/react  ')
        self.assertEqual(owner, 'facebook')
        self.assertEqual(name, 'react')

        owner, name = parse_repo_identifier('org-name/repo.js')
        self.assertEqual(owner, 'org-name')
        self.assertEqual(name, 'repo.js')

    def test_invalid_identifiers_raise_value_error(self):
        invalid_cases = [
            '',
            '   ',
            'just-a-name',
            'too/many/slashes/in/name',
            '/missing-owner',
            'missing-repo/',
            'invalid spaces/in name',
            'invalid/char$!name',
            'owner/..',
            'owner/.',
            '../repo',
            './repo',
            '.../repo',
            'owner/...',
        ]
        for invalid in invalid_cases:
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    parse_repo_identifier(invalid)


@override_settings(GITHUB_API_TOKEN='ghp_TEST_TOKEN_12345')
class GitHubClientTestCase(TestCase):
    def setUp(self):
        self.client = GitHubClient(token='ghp_TEST_TOKEN_12345')

    @patch('core.github_sync.requests.Session.get')
    def test_get_repository_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_REPO_PAYLOAD
        mock_get.return_value = mock_resp

        data = self.client.get_repository('hackit', 'awesome-project')
        self.assertEqual(data['id'], 12345678)
        self.assertEqual(data['full_name'], 'hackit/awesome-project')

        # Check call headers include Bearer token and user-agent
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertEqual(args[0], 'https://api.github.com/repos/hackit/awesome-project')
        self.assertEqual(kwargs['headers']['Authorization'], 'Bearer ghp_TEST_TOKEN_12345')
        self.assertEqual(kwargs['headers']['User-Agent'], 'HackIT-CommitRush-Sync/1.0')

    @patch('core.github_sync.requests.Session.get')
    def test_get_repository_404_not_found(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        with self.assertRaises(GitHubResourceNotFoundError) as ctx:
            self.client.get_repository('hackit', 'non-existent')
        self.assertIn('not found', str(ctx.exception).lower())

    @patch('core.github_sync.requests.Session.get')
    def test_get_repository_401_authentication_failure(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp

        with self.assertRaises(GitHubAuthenticationError) as ctx:
            self.client.get_repository('hackit', 'awesome-project')
        self.assertIn('authentication failed', str(ctx.exception).lower())

    @patch('core.github_sync.requests.Session.get')
    def test_get_repository_403_rate_limit_exceeded(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.headers = {'X-RateLimit-Remaining': '0'}
        mock_get.return_value = mock_resp

        with self.assertRaises(GitHubRateLimitError) as ctx:
            self.client.get_repository('hackit', 'awesome-project')
        self.assertIn('rate limit', str(ctx.exception).lower())

    @patch('core.github_sync.requests.Session.get')
    def test_get_repository_429_rate_limit_exceeded(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_get.return_value = mock_resp

        with self.assertRaises(GitHubRateLimitError):
            self.client.get_repository('hackit', 'awesome-project')

    @patch('core.github_sync.requests.Session.get')
    def test_get_repository_500_server_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp

        with self.assertRaises(GitHubAPIError) as ctx:
            self.client.get_repository('hackit', 'awesome-project')
        self.assertIn('500', str(ctx.exception))

    @patch('core.github_sync.requests.Session.get')
    def test_get_repository_timeout(self, mock_get):
        mock_get.side_effect = requests.Timeout("Connection timed out")

        with self.assertRaises(GitHubNetworkError) as ctx:
            self.client.get_repository('hackit', 'awesome-project')
        self.assertIn('timed out', str(ctx.exception).lower())
        self.assertNotIn('ghp_TEST_TOKEN_12345', str(ctx.exception))

    @patch('core.github_sync.requests.Session.get')
    def test_get_repository_network_failure(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("DNS failure")

        with self.assertRaises(GitHubNetworkError) as ctx:
            self.client.get_repository('hackit', 'awesome-project')
        self.assertNotIn('ghp_TEST_TOKEN_12345', str(ctx.exception))

    @patch('core.github_sync.requests.Session.get')
    def test_get_repository_invalid_json(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_resp

        with self.assertRaises(GitHubDataError):
            self.client.get_repository('hackit', 'awesome-project')

    @patch('core.github_sync.requests.Session.get')
    def test_get_repository_missing_required_fields(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'id': 123}  # missing name and full_name
        mock_get.return_value = mock_resp

        with self.assertRaises(GitHubDataError):
            self.client.get_repository('hackit', 'awesome-project')

    # ================= M2-T2 get_issues tests =================

    @patch('core.github_sync.requests.Session.get')
    def test_get_issues_success_filters_pull_requests(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.json.return_value = [
            SAMPLE_ISSUE_PAYLOAD_1,
            SAMPLE_PR_PAYLOAD,
            SAMPLE_ISSUE_PAYLOAD_2,
        ]
        mock_get.return_value = mock_resp

        issues = self.client.get_issues('hackit', 'awesome-project')

        self.assertEqual(len(issues), 2)
        issue_ids = [item['id'] for item in issues]
        self.assertIn(100001, issue_ids)
        self.assertIn(100002, issue_ids)
        self.assertNotIn(100003, issue_ids, "Pull requests must be filtered out")

    @patch('core.github_sync.requests.Session.get')
    def test_get_issues_multi_page_pagination_with_link_header(self, mock_get):
        resp_page1 = MagicMock()
        resp_page1.status_code = 200
        resp_page1.headers = {
            'Link': '<https://api.github.com/repos/hackit/awesome-project/issues?page=2>; rel="next", <https://api.github.com/repos/hackit/awesome-project/issues?page=2>; rel="last"'
        }
        resp_page1.json.return_value = [SAMPLE_ISSUE_PAYLOAD_1]

        resp_page2 = MagicMock()
        resp_page2.status_code = 200
        resp_page2.headers = {}
        resp_page2.json.return_value = [SAMPLE_ISSUE_PAYLOAD_2]

        mock_get.side_effect = [resp_page1, resp_page2]

        issues = self.client.get_issues('hackit', 'awesome-project')

        self.assertEqual(len(issues), 2)
        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(issues[0]['id'], 100001)
        self.assertEqual(issues[1]['id'], 100002)

    @patch('core.github_sync.requests.Session.get')
    def test_get_issues_404_not_found(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        with self.assertRaises(GitHubResourceNotFoundError):
            self.client.get_issues('hackit', 'non-existent')

    @patch('core.github_sync.requests.Session.get')
    def test_get_issues_401_authentication_failure(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp

        with self.assertRaises(GitHubAuthenticationError):
            self.client.get_issues('hackit', 'awesome-project')

    @patch('core.github_sync.requests.Session.get')
    def test_get_issues_403_rate_limit(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.headers = {'X-RateLimit-Remaining': '0'}
        mock_get.return_value = mock_resp

        with self.assertRaises(GitHubRateLimitError):
            self.client.get_issues('hackit', 'awesome-project')

    @patch('core.github_sync.requests.Session.get')
    def test_get_issues_429_rate_limit(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_get.return_value = mock_resp

        with self.assertRaises(GitHubRateLimitError):
            self.client.get_issues('hackit', 'awesome-project')

    @patch('core.github_sync.requests.Session.get')
    def test_get_issues_500_server_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp

        with self.assertRaises(GitHubAPIError):
            self.client.get_issues('hackit', 'awesome-project')

    @patch('core.github_sync.requests.Session.get')
    def test_get_issues_timeout(self, mock_get):
        mock_get.side_effect = requests.Timeout("Connection timeout")

        with self.assertRaises(GitHubNetworkError):
            self.client.get_issues('hackit', 'awesome-project')

    @patch('core.github_sync.requests.Session.get')
    def test_get_issues_invalid_json(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_resp

        with self.assertRaises(GitHubDataError):
            self.client.get_issues('hackit', 'awesome-project')

    @patch('core.github_sync.requests.Session.get')
    def test_get_issues_low_quota_below_10_percent_raises_rate_limit_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {
            'X-RateLimit-Remaining': '400',
            'X-RateLimit-Limit': '5000',
            'X-RateLimit-Reset': '1789518000',
        }
        mock_resp.json.return_value = [SAMPLE_ISSUE_PAYLOAD_1]
        mock_get.return_value = mock_resp

        with self.assertRaises(GitHubRateLimitError) as ctx:
            self.client.get_issues('hackit', 'awesome-project')

        exc = ctx.exception
        self.assertEqual(exc.remaining, 400)
        self.assertEqual(exc.limit, 5000)
        self.assertEqual(exc.reset_timestamp, 1789518000)
        self.assertIn("10%", str(exc))

    @patch('core.github_sync.requests.Session.get')
    def test_get_issues_pagination_quota_drop_on_second_page(self, mock_get):
        resp_page1 = MagicMock()
        resp_page1.status_code = 200
        resp_page1.headers = {
            'Link': '<https://api.github.com/repos/hackit/awesome-project/issues?page=2>; rel="next"',
            'X-RateLimit-Remaining': '2500',
            'X-RateLimit-Limit': '5000',
        }
        resp_page1.json.return_value = [SAMPLE_ISSUE_PAYLOAD_1]

        resp_page2 = MagicMock()
        resp_page2.status_code = 200
        resp_page2.headers = {
            'X-RateLimit-Remaining': '300',
            'X-RateLimit-Limit': '5000',
            'X-RateLimit-Reset': '1789518100',
        }
        resp_page2.json.return_value = [SAMPLE_ISSUE_PAYLOAD_2]

        mock_get.side_effect = [resp_page1, resp_page2]

        with self.assertRaises(GitHubRateLimitError) as ctx:
            self.client.get_issues('hackit', 'awesome-project')

        exc = ctx.exception
        self.assertEqual(exc.remaining, 300)
        self.assertEqual(exc.limit, 5000)
        self.assertEqual(exc.reset_timestamp, 1789518100)


class SyncProjectTestCase(TestCase):
    def test_sync_project_creates_new_record_with_model_defaults(self):
        project, created = sync_project(SAMPLE_REPO_PAYLOAD)

        self.assertTrue(created)
        self.assertEqual(project.github_repo_id, 12345678)
        self.assertEqual(project.owner, 'hackit')
        self.assertEqual(project.name, 'awesome-project')
        self.assertEqual(project.full_name, 'hackit/awesome-project')
        self.assertEqual(project.language, 'Python')
        self.assertEqual(project.description, 'An awesome open source project for HackIT')
        self.assertTrue(project.is_enabled)  # Model default is True

        # Verify record exists in DB
        db_project = Project.objects.get(github_repo_id=12345678)
        self.assertEqual(db_project.id, project.id)

    def test_sync_project_idempotent_no_duplicates(self):
        project1, created1 = sync_project(SAMPLE_REPO_PAYLOAD)
        self.assertTrue(created1)
        self.assertEqual(Project.objects.count(), 1)

        # Run again with identical payload
        project2, created2 = sync_project(SAMPLE_REPO_PAYLOAD)
        self.assertFalse(created2)
        self.assertEqual(project1.id, project2.id)
        self.assertEqual(Project.objects.count(), 1)

    def test_sync_project_updates_mutable_metadata(self):
        # Initial creation
        project, created = sync_project(SAMPLE_REPO_PAYLOAD)
        self.assertTrue(created)

        # Updated GitHub payload
        updated_payload = {
            'id': 12345678,
            'name': 'awesome-project-renamed',
            'full_name': 'hackit/awesome-project-renamed',
            'owner': {'login': 'hackit'},
            'language': 'TypeScript',
            'description': 'Updated project description from GitHub',
        }

        updated_project, created_again = sync_project(updated_payload)
        self.assertFalse(created_again)
        self.assertEqual(Project.objects.count(), 1)

        project.refresh_from_db()
        self.assertEqual(project.name, 'awesome-project-renamed')
        self.assertEqual(project.full_name, 'hackit/awesome-project-renamed')
        self.assertEqual(project.language, 'TypeScript')
        self.assertEqual(project.description, 'Updated project description from GitHub')

    def test_sync_project_preserves_is_enabled_override(self):
        # Create project with is_enabled=False (operator disabled)
        project = Project.objects.create(
            github_repo_id=12345678,
            owner='hackit',
            name='awesome-project',
            full_name='hackit/awesome-project',
            language='Python',
            description='Original',
            is_enabled=False,
        )

        # Run GitHub sync
        synced_project, created = sync_project(SAMPLE_REPO_PAYLOAD)
        self.assertFalse(created)
        self.assertEqual(synced_project.id, project.id)

        project.refresh_from_db()
        self.assertFalse(project.is_enabled, "Operator setting 'is_enabled=False' must be preserved on sync")

    def test_sync_project_handles_null_optional_fields(self):
        payload_with_nulls = {
            'id': 87654321,
            'name': 'minimal-project',
            'full_name': 'hackit/minimal-project',
            'owner': {'login': 'hackit'},
            'language': None,
            'description': None,
        }

        project, created = sync_project(payload_with_nulls)
        self.assertTrue(created)
        self.assertEqual(project.language, '')
        self.assertEqual(project.description, '')


class SyncLabelTestCase(TestCase):
    def test_sync_label_dict_creation(self):
        label_data = {'name': 'bug', 'color': 'd73a4a'}
        label, created = sync_label(label_data)

        self.assertTrue(created)
        self.assertEqual(label.name, 'bug')
        self.assertEqual(label.color, 'd73a4a')
        self.assertEqual(IssueLabel.objects.count(), 1)

    def test_sync_label_idempotent_no_duplicate(self):
        label_data = {'name': 'enhancement', 'color': 'a2eeef'}
        label1, created1 = sync_label(label_data)
        self.assertTrue(created1)

        label2, created2 = sync_label(label_data)
        self.assertFalse(created2)
        self.assertEqual(label1.id, label2.id)
        self.assertEqual(IssueLabel.objects.count(), 1)

    def test_sync_label_updates_color_if_changed(self):
        label_data_v1 = {'name': 'help-wanted', 'color': '008672'}
        label, created = sync_label(label_data_v1)
        self.assertTrue(created)
        self.assertEqual(label.color, '008672')

        label_data_v2 = {'name': 'help-wanted', 'color': '128A0C'}
        label_updated, created_again = sync_label(label_data_v2)
        self.assertFalse(created_again)
        self.assertEqual(label.id, label_updated.id)

        label.refresh_from_db()
        self.assertEqual(label.color, '128A0C')

    def test_sync_label_string_input(self):
        label, created = sync_label('documentation')
        self.assertTrue(created)
        self.assertEqual(label.name, 'documentation')
        self.assertEqual(label.color, '')

    def test_sync_label_empty_or_invalid_returns_none(self):
        self.assertEqual(sync_label(''), (None, False))
        self.assertEqual(sync_label('   '), (None, False))
        self.assertEqual(sync_label({'name': ''}), (None, False))
        self.assertEqual(sync_label(123), (None, False))
        self.assertEqual(sync_label(None), (None, False))


class SyncIssueTestCase(TestCase):
    def setUp(self):
        self.project = Project.objects.create(
            github_repo_id=12345678,
            owner='hackit',
            name='awesome-project',
            full_name='hackit/awesome-project',
            language='Python',
        )

    def test_sync_issue_creates_new_record_with_model_defaults(self):
        issue, created = sync_issue(self.project, SAMPLE_ISSUE_PAYLOAD_1)

        self.assertTrue(created)
        self.assertEqual(issue.github_issue_id, 100001)
        self.assertEqual(issue.project, self.project)
        self.assertEqual(issue.number, 42)
        self.assertEqual(issue.title, 'Fix authentication state race condition')
        self.assertEqual(issue.status, 'open')
        self.assertEqual(issue.points, 50)  # Model default
        self.assertEqual(issue.difficulty, '')  # Model default
        self.assertEqual(issue.category, '')  # Model default
        self.assertFalse(issue.is_featured)  # Model default

        # Verify in DB
        db_issue = Issue.objects.get(github_issue_id=100001)
        self.assertEqual(db_issue.id, issue.id)

    def test_sync_issue_closed_state_mapped_correctly(self):
        issue, created = sync_issue(self.project, SAMPLE_ISSUE_PAYLOAD_2)

        self.assertTrue(created)
        self.assertEqual(issue.github_issue_id, 100002)
        self.assertEqual(issue.number, 43)
        self.assertEqual(issue.status, 'closed')

    def test_sync_issue_idempotent_no_duplicates(self):
        issue1, created1 = sync_issue(self.project, SAMPLE_ISSUE_PAYLOAD_1)
        self.assertTrue(created1)
        self.assertEqual(Issue.objects.count(), 1)

        # Resync identical payload
        issue2, created2 = sync_issue(self.project, SAMPLE_ISSUE_PAYLOAD_1)
        self.assertFalse(created2)
        self.assertEqual(issue1.id, issue2.id)
        self.assertEqual(Issue.objects.count(), 1)

    def test_sync_issue_updates_mutable_fields(self):
        issue, created = sync_issue(self.project, SAMPLE_ISSUE_PAYLOAD_1)
        self.assertTrue(created)

        # Update payload (title changed, issue closed)
        updated_payload = {
            'id': 100001,
            'number': 42,
            'title': 'Fix authentication state race condition (RESOLVED)',
            'state': 'closed',
            'labels': [{'name': 'bug', 'color': 'd73a4a'}],
        }

        updated_issue, created_again = sync_issue(self.project, updated_payload)
        self.assertFalse(created_again)
        self.assertEqual(Issue.objects.count(), 1)

        issue.refresh_from_db()
        self.assertEqual(issue.title, 'Fix authentication state race condition (RESOLVED)')
        self.assertEqual(issue.status, 'closed')

    def test_sync_issue_preserves_operator_customized_fields(self):
        # Initial creation
        issue, created = sync_issue(self.project, SAMPLE_ISSUE_PAYLOAD_1)
        self.assertTrue(created)

        # Operator customizes points, difficulty, category, is_featured
        issue.points = 200
        issue.difficulty = 'advanced'
        issue.category = 'security'
        issue.is_featured = True
        issue.save()

        # Resync from GitHub with new title and closed status
        updated_payload = {
            'id': 100001,
            'number': 42,
            'title': 'Updated Title From GitHub',
            'state': 'closed',
            'labels': [{'name': 'bug', 'color': 'd73a4a'}],
        }
        synced_issue, created_again = sync_issue(self.project, updated_payload)
        self.assertFalse(created_again)

        issue.refresh_from_db()
        # GitHub fields updated
        self.assertEqual(issue.title, 'Updated Title From GitHub')
        self.assertEqual(issue.status, 'closed')
        # Operator customizations strictly preserved
        self.assertEqual(issue.points, 200)
        self.assertEqual(issue.difficulty, 'advanced')
        self.assertEqual(issue.category, 'security')
        self.assertTrue(issue.is_featured)

    def test_sync_issue_parses_and_persists_created_at(self):
        payload_with_timestamp = {
            'id': 100099,
            'number': 99,
            'title': 'Issue with specific creation timestamp',
            'state': 'open',
            'created_at': '2026-08-15T14:30:00Z',
        }
        issue, created = sync_issue(self.project, payload_with_timestamp)
        self.assertTrue(created)
        self.assertEqual(issue.created_at.year, 2026)
        self.assertEqual(issue.created_at.month, 8)
        self.assertEqual(issue.created_at.day, 15)
        self.assertEqual(issue.created_at.hour, 14)
        self.assertEqual(issue.created_at.minute, 30)

    def test_sync_issue_extracts_drive_metadata_from_labels_and_body(self):
        drive_payload = {
            'id': 5348687301,
            'number': 1500,
            'title': '[CR-1500] Implement Secure Code Execution Sandbox and Query Sanitization Engine in OpenAI_Syntax_Generator Part 7',
            'state': 'open',
            'labels': [
                {'id': 12041774571, 'name': 'hackit-commitrush', 'color': 'C2E0C6'},
                {'id': 12041779341, 'name': 'type:security', 'color': 'D93F0B'},
                {'id': 12062788192, 'name': 'difficulty:master', 'color': 'B60205'},
            ],
            'body': '**Type:** security\r\n\r\n**Difficulty:** Master\r\n\r\n**Suggested Points:** 50\r\n\r\n**Area:** AI Security & Isolation (`src.py`)\r\n\r\n**Project:** OpenAI_Syntax_Generator',
        }
        issue, created = sync_issue(self.project, drive_payload)
        self.assertTrue(created)
        self.assertEqual(issue.github_issue_id, 5348687301)
        self.assertEqual(issue.number, 1500)
        self.assertEqual(issue.difficulty, 'master')
        self.assertEqual(issue.category, 'security')
        self.assertEqual(issue.points, 50)
        self.assertEqual(issue.labels.count(), 3)

    def test_sync_issue_updates_points_when_github_metadata_changes(self):
        """Verify that updating an existing issue with new points/difficulty on GitHub updates DB points."""
        issue, created = sync_issue(self.project, SAMPLE_ISSUE_PAYLOAD_1)
        self.assertTrue(created)
        self.assertEqual(issue.points, 50)

        # Update payload with explicit difficulty and points from GitHub
        updated_payload = {
            'id': 100001,
            'number': 42,
            'title': '[CR-42] Refactored Title',
            'state': 'open',
            'labels': [{'name': 'difficulty:medium'}, {'name': 'type:security'}],
            'body': '**Difficulty:** Medium\r\n\r\n**Suggested Points:** 20',
        }
        updated_issue, created_again = sync_issue(self.project, updated_payload)
        self.assertFalse(created_again)

        issue.refresh_from_db()
        self.assertEqual(issue.points, 20)
        self.assertEqual(issue.difficulty, 'medium')
        self.assertEqual(issue.category, 'security')

    def test_sync_issue_extracts_various_points_and_difficulty_formats(self):
        """Verify points extraction from various label and markdown body variations."""
        from core.github_sync import extract_issue_metadata

        # Format A: **Points:** 20
        res_a = extract_issue_metadata({'body': '**Points:** 20', 'labels': []})
        self.assertEqual(res_a['points'], 20)
        self.assertEqual(res_a['difficulty'], 'medium')

        # Format B: Points in label (points: 30)
        res_b = extract_issue_metadata({'body': '', 'labels': [{'name': 'points: 30'}]})
        self.assertEqual(res_b['points'], 30)
        self.assertEqual(res_b['difficulty'], 'hard')

        # Format C: Standalone difficulty label (easy -> 10)
        res_c = extract_issue_metadata({'body': '', 'labels': [{'name': 'easy'}]})
        self.assertEqual(res_c['points'], 10)
        self.assertEqual(res_c['difficulty'], 'easy')

        # Format D: Difficulty Beginner -> 5
        res_d = extract_issue_metadata({'body': '**Difficulty:** Beginner', 'labels': []})
        self.assertEqual(res_d['points'], 5)
        self.assertEqual(res_d['difficulty'], 'beginner')

    def test_sync_issue_matches_and_deduplicates_by_project_and_number(self):
        """Verify that an issue with a placeholder github_issue_id gets updated rather than duplicated."""
        # Create issue with placeholder github_issue_id (e.g. from seed data)
        seed_issue = Issue.objects.create(
            project=self.project,
            github_issue_id=701,
            number=101,
            title='Old Demo Title',
            points=50,
            difficulty='beginner',
        )

        # Real GitHub payload has new github_issue_id 5327318709
        github_payload = {
            'id': 5327318709,
            'number': 101,
            'title': '[CR-101] Real Title From GitHub',
            'state': 'open',
            'labels': [{'name': 'difficulty:medium'}],
            'body': '**Suggested Points:** 20',
        }
        synced_issue, created = sync_issue(self.project, github_payload)
        self.assertFalse(created)
        self.assertEqual(synced_issue.id, seed_issue.id)
        self.assertEqual(synced_issue.github_issue_id, 5327318709)
        self.assertEqual(synced_issue.points, 20)
        self.assertEqual(synced_issue.difficulty, 'medium')
        self.assertEqual(Issue.objects.filter(project=self.project, number=101).count(), 1)

    # ================= M2-T3 Label Synchronization Tests =================

    def test_sync_issue_associates_labels_and_creates_m2m(self):
        issue, created = sync_issue(self.project, SAMPLE_ISSUE_PAYLOAD_1)
        self.assertTrue(created)

        labels = list(issue.labels.all().order_by('name'))
        self.assertEqual(len(labels), 2)
        self.assertEqual(labels[0].name, 'bug')
        self.assertEqual(labels[0].color, 'd73a4a')
        self.assertEqual(labels[1].name, 'security')
        self.assertEqual(labels[1].color, 'b60205')
        self.assertEqual(IssueLabel.objects.count(), 2)

    def test_sync_issue_updates_labels_removes_old_label_association(self):
        # Initial sync: 'bug' and 'security'
        issue, created = sync_issue(self.project, SAMPLE_ISSUE_PAYLOAD_1)
        self.assertTrue(created)
        self.assertEqual(issue.labels.count(), 2)

        # Update payload: replace 'security' with 'backend'
        updated_payload = {
            'id': 100001,
            'number': 42,
            'title': 'Fix authentication state race condition',
            'state': 'open',
            'labels': [
                {'name': 'bug', 'color': 'd73a4a'},
                {'name': 'backend', 'color': '0052cc'},
            ],
        }

        updated_issue, created_again = sync_issue(self.project, updated_payload)
        self.assertFalse(created_again)

        issue.refresh_from_db()
        label_names = set(issue.labels.values_list('name', flat=True))
        self.assertEqual(label_names, {'bug', 'backend'})

        # 'security' IssueLabel record MUST STILL EXIST in DB (not deleted)
        self.assertTrue(IssueLabel.objects.filter(name='security').exists())
        self.assertEqual(IssueLabel.objects.count(), 3)  # bug, security, backend

    def test_sync_issue_shared_labels_across_multiple_issues(self):
        # Issue 1 has 'bug' and 'security'
        issue1, _ = sync_issue(self.project, SAMPLE_ISSUE_PAYLOAD_1)
        # Issue 2 has 'enhancement' and 'bug'
        issue2, _ = sync_issue(self.project, SAMPLE_ISSUE_PAYLOAD_2)

        # Global IssueLabel count: bug, security, enhancement = 3
        self.assertEqual(IssueLabel.objects.count(), 3)

        # Both issues reference the exact same 'bug' label record
        bug_label = IssueLabel.objects.get(name='bug')
        self.assertIn(bug_label, issue1.labels.all())
        self.assertIn(bug_label, issue2.labels.all())

        # When Issue 1 removes 'bug', Issue 2 still retains 'bug'
        issue1_no_bug_payload = {
            'id': 100001,
            'number': 42,
            'title': 'Fix authentication state race condition',
            'state': 'open',
            'labels': [{'name': 'security', 'color': 'b60205'}],
        }
        sync_issue(self.project, issue1_no_bug_payload)

        self.assertNotIn(bug_label, issue1.labels.all())
        self.assertIn(bug_label, issue2.labels.all())
        self.assertTrue(IssueLabel.objects.filter(name='bug').exists())

    def test_sync_issue_empty_labels_list_clears_associations(self):
        issue, _ = sync_issue(self.project, SAMPLE_ISSUE_PAYLOAD_1)
        self.assertEqual(issue.labels.count(), 2)

        cleared_payload = {
            'id': 100001,
            'number': 42,
            'title': 'Fix authentication state race condition',
            'state': 'open',
            'labels': [],
        }
        sync_issue(self.project, cleared_payload)

        issue.refresh_from_db()
        self.assertEqual(issue.labels.count(), 0)
        # Database IssueLabels remain cached
        self.assertEqual(IssueLabel.objects.count(), 2)

    def test_sync_issue_omitted_labels_key_preserves_associations(self):
        issue, _ = sync_issue(self.project, SAMPLE_ISSUE_PAYLOAD_1)
        self.assertEqual(issue.labels.count(), 2)

        payload_without_labels_key = {
            'id': 100001,
            'number': 42,
            'title': 'Title changed without sending labels',
            'state': 'open',
        }
        sync_issue(self.project, payload_without_labels_key)

        issue.refresh_from_db()
        self.assertEqual(issue.title, 'Title changed without sending labels')
        self.assertEqual(issue.labels.count(), 2)


class SyncIssuesForProjectTestCase(TestCase):
    def setUp(self):
        self.project = Project.objects.create(
            github_repo_id=12345678,
            owner='hackit',
            name='awesome-project',
            full_name='hackit/awesome-project',
        )

    def test_sync_issues_for_project_bulk_counts_and_filters_prs(self):
        # Pre-create issue 100001 to test update counting
        sync_issue(self.project, SAMPLE_ISSUE_PAYLOAD_1)
        self.assertEqual(Issue.objects.count(), 1)

        payloads = [
            SAMPLE_ISSUE_PAYLOAD_1,  # existing -> updated
            SAMPLE_ISSUE_PAYLOAD_2,  # new -> created
            SAMPLE_PR_PAYLOAD,       # pull request -> ignored
        ]

        created_count, updated_count = sync_issues_for_project(self.project, payloads)

        self.assertEqual(created_count, 1)
        self.assertEqual(updated_count, 1)
        self.assertEqual(Issue.objects.count(), 2)


class SyncRepositoryAndIssuesTestCase(TestCase):
    @patch('core.github_sync.GitHubClient.get_repository')
    @patch('core.github_sync.GitHubClient.get_issues')
    def test_sync_repository_and_issues_default_full_sync(self, mock_get_issues, mock_get_repo):
        mock_get_repo.return_value = SAMPLE_REPO_PAYLOAD
        mock_get_issues.return_value = [SAMPLE_ISSUE_PAYLOAD_1, SAMPLE_ISSUE_PAYLOAD_2]

        client = GitHubClient(token='test')
        project, repo_created, issues_created, issues_updated = sync_repository_and_issues(
            'hackit/awesome-project',
            client=client,
            sync_issues_flag=True,
        )

        self.assertTrue(repo_created)
        self.assertEqual(issues_created, 2)
        self.assertEqual(issues_updated, 0)
        self.assertEqual(Project.objects.count(), 1)
        self.assertEqual(Issue.objects.count(), 2)
        self.assertEqual(IssueLabel.objects.count(), 3)  # bug, security, enhancement
        mock_get_repo.assert_called_once_with('hackit', 'awesome-project')
        mock_get_issues.assert_called_once_with('hackit', 'awesome-project', state='all')

    @patch('core.github_sync.GitHubClient.get_repository')
    @patch('core.github_sync.GitHubClient.get_issues')
    def test_sync_repository_and_issues_no_issues_flag(self, mock_get_issues, mock_get_repo):
        mock_get_repo.return_value = SAMPLE_REPO_PAYLOAD

        client = GitHubClient(token='test')
        project, repo_created, issues_created, issues_updated = sync_repository_and_issues(
            'hackit/awesome-project',
            client=client,
            sync_issues_flag=False,
        )

        self.assertTrue(repo_created)
        self.assertEqual(issues_created, 0)
        self.assertEqual(issues_updated, 0)
        self.assertEqual(Project.objects.count(), 1)
        self.assertEqual(Issue.objects.count(), 0)
        mock_get_issues.assert_not_called()


@override_settings(GITHUB_API_TOKEN='ghp_SECRET_TOKEN_99999')
class SyncGithubManagementCommandTestCase(TestCase):
    @patch('core.github_sync.GitHubClient.get_repository')
    @patch('core.github_sync.GitHubClient.get_issues')
    def test_command_successful_sync_single_repo_with_issues_and_labels(self, mock_get_issues, mock_get_repo):
        mock_get_repo.return_value = SAMPLE_REPO_PAYLOAD
        mock_get_issues.return_value = [SAMPLE_ISSUE_PAYLOAD_1, SAMPLE_ISSUE_PAYLOAD_2]

        out = StringIO()
        err = StringIO()
        call_command('sync_github', '--repo', 'hackit/awesome-project', stdout=out, stderr=err)

        output = out.getvalue()
        self.assertIn("Successfully created Project 'hackit/awesome-project'", output)
        self.assertIn("Issues synced: 2 created, 0 updated.", output)
        self.assertIn("Sync complete. Repositories: 1 (1 created, 0 updated), Issues: 2 (2 created, 0 updated), Failed: 0.", output)
        self.assertEqual(Project.objects.count(), 1)
        self.assertEqual(Issue.objects.count(), 2)
        self.assertEqual(IssueLabel.objects.count(), 3)
        self.assertNotIn('ghp_SECRET_TOKEN_99999', output)

    @patch('core.github_sync.GitHubClient.get_repository')
    @patch('core.github_sync.GitHubClient.get_issues')
    def test_command_successful_resync_reports_updated(self, mock_get_issues, mock_get_repo):
        mock_get_repo.return_value = SAMPLE_REPO_PAYLOAD
        mock_get_issues.return_value = [SAMPLE_ISSUE_PAYLOAD_1]

        # First run creates
        call_command('sync_github', '--repo', 'hackit/awesome-project')

        # Second run updates
        out = StringIO()
        call_command('sync_github', '--repo', 'hackit/awesome-project', stdout=out)

        output = out.getvalue()
        self.assertIn("Successfully updated Project 'hackit/awesome-project'", output)
        self.assertIn("Issues synced: 0 created, 1 updated.", output)
        self.assertIn("Sync complete. Repositories: 1 (0 created, 1 updated), Issues: 1 (0 created, 1 updated), Failed: 0.", output)
        self.assertEqual(Project.objects.count(), 1)
        self.assertEqual(Issue.objects.count(), 1)

    @patch('core.github_sync.GitHubClient.get_repository')
    @patch('core.github_sync.GitHubClient.get_issues')
    def test_command_no_issues_flag(self, mock_get_issues, mock_get_repo):
        mock_get_repo.return_value = SAMPLE_REPO_PAYLOAD

        out = StringIO()
        call_command('sync_github', '--repo', 'hackit/awesome-project', '--no-issues', stdout=out)

        output = out.getvalue()
        self.assertIn("Successfully created Project 'hackit/awesome-project'", output)
        self.assertIn("Sync complete. Repositories: 1 (1 created, 0 updated), Issues: 0 (0 created, 0 updated), Failed: 0.", output)
        self.assertEqual(Project.objects.count(), 1)
        self.assertEqual(Issue.objects.count(), 0)
        mock_get_issues.assert_not_called()

    @patch('core.github_sync.GitHubClient.get_repository')
    @patch('core.github_sync.GitHubClient.get_issues')
    def test_command_multiple_repos(self, mock_get_issues, mock_get_repo):
        payload2 = dict(SAMPLE_REPO_PAYLOAD, id=23456789, name='project2', full_name='hackit/project2')

        def repo_side_effect(owner, repo):
            if repo == 'awesome-project':
                return SAMPLE_REPO_PAYLOAD
            elif repo == 'project2':
                return payload2
            raise GitHubResourceNotFoundError("Not found")

        def issues_side_effect(owner, repo, state='all'):
            if repo == 'awesome-project':
                return [SAMPLE_ISSUE_PAYLOAD_1]
            elif repo == 'project2':
                return [SAMPLE_ISSUE_PAYLOAD_2]
            return []

        mock_get_repo.side_effect = repo_side_effect
        mock_get_issues.side_effect = issues_side_effect

        out = StringIO()
        call_command(
            'sync_github',
            '--repo', 'hackit/awesome-project',
            '--repo', 'hackit/project2',
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("created Project 'hackit/awesome-project'", output)
        self.assertIn("created Project 'hackit/project2'", output)
        self.assertIn("Repositories: 2 (2 created, 0 updated), Issues: 2 (2 created, 0 updated), Failed: 0.", output)
        self.assertEqual(Project.objects.count(), 2)
        self.assertEqual(Issue.objects.count(), 2)

    def test_command_missing_arguments_raises_error(self):
        with self.assertRaises(CommandError) as ctx:
            call_command('sync_github')
        self.assertIn("At least one repository must be specified", str(ctx.exception))

    def test_command_invalid_repo_format_raises_error(self):
        out = StringIO()
        err = StringIO()
        with self.assertRaises(CommandError) as ctx:
            call_command('sync_github', '--repo', 'invalid_format', stdout=out, stderr=err)
        self.assertIn("Synchronization failed for 1 repository", str(ctx.exception))
        self.assertIn("Expected format: 'owner/name'", err.getvalue())

    @patch('core.github_sync.GitHubClient.get_repository')
    def test_command_handles_not_found_cleanly(self, mock_get_repo):
        mock_get_repo.side_effect = GitHubResourceNotFoundError("Repository 'hackit/not-found' was not found on GitHub (HTTP 404).")

        out = StringIO()
        err = StringIO()
        with self.assertRaises(CommandError) as ctx:
            call_command('sync_github', '--repo', 'hackit/not-found', stdout=out, stderr=err)

        self.assertIn("Synchronization failed for 1 repository", str(ctx.exception))
        self.assertIn("not found on GitHub", err.getvalue())
        self.assertNotIn('ghp_SECRET_TOKEN_99999', err.getvalue())

    @patch('core.github_sync.GitHubClient.get_repository')
    def test_command_handles_network_timeout_cleanly(self, mock_get_repo):
        mock_get_repo.side_effect = GitHubNetworkError("GitHub API request timed out after 10s.")

        out = StringIO()
        err = StringIO()
        with self.assertRaises(CommandError) as ctx:
            call_command('sync_github', '--repo', 'hackit/timeout-repo', stdout=out, stderr=err)

        self.assertIn("Synchronization failed for 1 repository", str(ctx.exception))
        self.assertIn("Network error", err.getvalue())
        self.assertNotIn('ghp_SECRET_TOKEN_99999', err.getvalue())
