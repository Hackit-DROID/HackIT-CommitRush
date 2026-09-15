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
    sync_repository_by_name,
)
from core.models import Project


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


@override_settings(GITHUB_API_TOKEN='ghp_SECRET_TOKEN_99999')
class SyncGithubManagementCommandTestCase(TestCase):
    @patch('core.github_sync.GitHubClient.get_repository')
    def test_command_successful_sync_single_repo(self, mock_get_repo):
        mock_get_repo.return_value = SAMPLE_REPO_PAYLOAD

        out = StringIO()
        err = StringIO()
        call_command('sync_github', '--repo', 'hackit/awesome-project', stdout=out, stderr=err)

        output = out.getvalue()
        self.assertIn("Successfully created Project 'hackit/awesome-project'", output)
        self.assertIn("Sync complete. Success: 1 (1 created, 0 updated), Failed: 0", output)
        self.assertEqual(Project.objects.count(), 1)
        self.assertNotIn('ghp_SECRET_TOKEN_99999', output)

    @patch('core.github_sync.GitHubClient.get_repository')
    def test_command_successful_resync_reports_updated(self, mock_get_repo):
        mock_get_repo.return_value = SAMPLE_REPO_PAYLOAD

        # First run creates
        call_command('sync_github', '--repo', 'hackit/awesome-project')

        # Second run updates
        out = StringIO()
        call_command('sync_github', '--repo', 'hackit/awesome-project', stdout=out)

        output = out.getvalue()
        self.assertIn("Successfully updated Project 'hackit/awesome-project'", output)
        self.assertIn("Sync complete. Success: 1 (0 created, 1 updated), Failed: 0", output)
        self.assertEqual(Project.objects.count(), 1)

    @patch('core.github_sync.GitHubClient.get_repository')
    def test_command_multiple_repos(self, mock_get_repo):
        payload2 = dict(SAMPLE_REPO_PAYLOAD, id=23456789, name='project2', full_name='hackit/project2')

        def side_effect(owner, repo):
            if repo == 'awesome-project':
                return SAMPLE_REPO_PAYLOAD
            elif repo == 'project2':
                return payload2
            raise GitHubResourceNotFoundError("Not found")

        mock_get_repo.side_effect = side_effect

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
        self.assertIn("Success: 2 (2 created, 0 updated), Failed: 0", output)
        self.assertEqual(Project.objects.count(), 2)

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
