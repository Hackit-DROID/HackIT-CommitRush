import time
from io import StringIO
from unittest.mock import MagicMock, patch

from celery.exceptions import Retry
from django.conf import settings
from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase, override_settings

from commitrush.celery import app as celery_app
from core.github_sync import (
    GitHubAuthenticationError,
    GitHubDataError,
    GitHubNetworkError,
    GitHubAPIError,
    GitHubRateLimitError,
    GitHubResourceNotFoundError,
    sync_issue,
    sync_label,
    sync_project,
)
from core.models import Issue, IssueLabel, Project
from core.tasks import (
    LOW_QUOTA_SAFETY_THRESHOLD,
    TRANSIENT_MAX_RETRIES,
    sync_repository_task,
)


SAMPLE_REPO_PAYLOAD = {
    'id': 77778888,
    'name': 'celery-sync-repo',
    'full_name': 'hackit/celery-sync-repo',
    'owner': {'login': 'hackit'},
    'language': 'Python',
    'description': 'Repository for Celery sync tests',
}

SAMPLE_ISSUE_PAYLOAD = {
    'id': 88889999,
    'number': 101,
    'title': 'Test Celery rate limit backoff',
    'state': 'open',
    'labels': [{'name': 'celery', 'color': '37814A'}],
}


class CeleryConfigurationTestCase(TestCase):
    def test_celery_app_initialization_and_task_registration(self):
        self.assertIsNotNone(celery_app)
        self.assertIn('core.tasks.sync_repository_task', celery_app.tasks)

    def test_celery_task_routing_to_sync_queue(self):
        task = celery_app.tasks['core.tasks.sync_repository_task']
        self.assertEqual(task.queue, 'sync')
        routes = getattr(settings, 'CELERY_TASK_ROUTES', {})
        self.assertEqual(routes.get('core.tasks.sync_repository_task'), {'queue': 'sync'})

    def test_celery_security_json_serialization_only(self):
        accept_content = getattr(settings, 'CELERY_ACCEPT_CONTENT', [])
        task_serializer = getattr(settings, 'CELERY_TASK_SERIALIZER', '')
        result_serializer = getattr(settings, 'CELERY_RESULT_SERIALIZER', '')

        self.assertEqual(accept_content, ['json'])
        self.assertEqual(task_serializer, 'json')
        self.assertEqual(result_serializer, 'json')
        self.assertNotIn('pickle', accept_content)


class SyncRepositoryTaskTestCase(TestCase):
    @patch('core.tasks.sync_repository_and_issues')
    def test_task_successful_execution(self, mock_sync_repo_and_issues):
        project = Project.objects.create(
            github_repo_id=77778888,
            owner='hackit',
            name='celery-sync-repo',
            full_name='hackit/celery-sync-repo',
        )
        mock_sync_repo_and_issues.return_value = (project, True, 5, 0)

        result = sync_repository_task('hackit/celery-sync-repo')

        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['repo'], 'hackit/celery-sync-repo')
        self.assertEqual(result['project_id'], project.id)
        self.assertTrue(result['repo_created'])
        self.assertEqual(result['issues_created'], 5)
        self.assertEqual(result['issues_updated'], 0)

    def test_task_invalid_repo_identifier_permanent_failure_no_retry(self):
        invalid_identifiers = [
            '',
            'just-a-name',
            'https://github.com/hackit/repo',
            'hackit/..',
            'hackit/.',
            '../repo',
        ]
        for invalid_id in invalid_identifiers:
            with self.subTest(invalid_id=invalid_id):
                result = sync_repository_task(invalid_id)
                self.assertEqual(result['status'], 'failed')
                self.assertTrue(result['permanent'])
                self.assertIn('error', result)

    @patch('core.tasks.sync_repository_and_issues')
    def test_task_permanent_401_authentication_failure_no_retry(self, mock_sync):
        mock_sync.side_effect = GitHubAuthenticationError("HTTP 401 Authentication failed")

        result = sync_repository_task('hackit/celery-sync-repo')

        self.assertEqual(result['status'], 'failed')
        self.assertTrue(result['permanent'])
        self.assertIn("Authentication failed", result['error'])

    @patch('core.tasks.sync_repository_and_issues')
    def test_task_permanent_404_not_found_no_retry(self, mock_sync):
        mock_sync.side_effect = GitHubResourceNotFoundError("Repository not found")

        result = sync_repository_task('hackit/non-existent')

        self.assertEqual(result['status'], 'failed')
        self.assertTrue(result['permanent'])
        self.assertIn("not found", result['error'].lower())

    @patch('core.tasks.sync_repository_and_issues')
    def test_task_permanent_malformed_data_no_retry(self, mock_sync):
        mock_sync.side_effect = GitHubDataError("Malformed JSON payload")

        result = sync_repository_task('hackit/malformed-repo')

        self.assertEqual(result['status'], 'failed')
        self.assertTrue(result['permanent'])

    @patch('core.tasks.sync_repository_and_issues')
    @patch.object(sync_repository_task, 'retry')
    def test_task_rate_limit_403_requeues_with_countdown(self, mock_retry, mock_sync):
        mock_retry.side_effect = Retry("Simulated retry")
        reset_time = int(time.time()) + 120
        mock_sync.side_effect = GitHubRateLimitError(
            message="Rate limit exceeded",
            remaining=0,
            limit=5000,
            reset_timestamp=reset_time,
        )

        with self.assertRaises(Retry):
            sync_repository_task('hackit/celery-sync-repo')

        mock_retry.assert_called_once()
        _, kwargs = mock_retry.call_args
        self.assertGreaterEqual(kwargs['countdown'], 10)
        self.assertIsNone(kwargs['max_retries'])
        self.assertEqual(kwargs['kwargs']['rate_limit_retries'], 1)

    @patch('core.tasks.sync_repository_and_issues')
    @patch.object(sync_repository_task, 'retry')
    def test_task_rate_limit_retry_after_respected(self, mock_retry, mock_sync):
        mock_retry.side_effect = Retry("Simulated retry")
        mock_sync.side_effect = GitHubRateLimitError(
            message="Rate limit 429",
            remaining=0,
            limit=5000,
            retry_after=180,
        )

        with self.assertRaises(Retry):
            sync_repository_task('hackit/celery-sync-repo')

        mock_retry.assert_called_once()
        _, kwargs = mock_retry.call_args
        self.assertEqual(kwargs['countdown'], 180)
        self.assertIsNone(kwargs['max_retries'])

    @patch('core.tasks.sync_repository_and_issues')
    @patch.object(sync_repository_task, 'retry')
    def test_task_low_quota_below_10_percent_triggers_backoff(self, mock_retry, mock_sync):
        mock_retry.side_effect = Retry("Simulated retry")
        reset_time = int(time.time()) + 90
        mock_sync.side_effect = GitHubRateLimitError(
            message="GitHub API quota dropped below 10% safety threshold.",
            remaining=400,
            limit=5000,
            reset_timestamp=reset_time,
        )

        with self.assertRaises(Retry):
            sync_repository_task('hackit/celery-sync-repo')

        mock_retry.assert_called_once()
        _, kwargs = mock_retry.call_args
        self.assertGreaterEqual(kwargs['countdown'], 10)
        self.assertIsNone(kwargs['max_retries'])

    @patch('core.tasks.sync_repository_and_issues')
    @patch.object(sync_repository_task, 'retry')
    def test_task_transient_500_exponential_backoff(self, mock_retry, mock_sync):
        mock_retry.side_effect = Retry("Simulated retry")
        mock_sync.side_effect = GitHubAPIError("GitHub 500 Server Error")

        # Set task request retries = 0 -> countdown = 2^0 = 1s
        sync_repository_task.push_request(retries=0)
        try:
            with self.assertRaises(Retry):
                sync_repository_task('hackit/celery-sync-repo')

            mock_retry.assert_called_once()
            _, kwargs = mock_retry.call_args
            self.assertEqual(kwargs['countdown'], 1)
            self.assertEqual(kwargs['max_retries'], TRANSIENT_MAX_RETRIES)
        finally:
            sync_repository_task.pop_request()

    @patch('core.tasks.sync_repository_and_issues')
    @patch.object(sync_repository_task, 'retry')
    def test_task_transient_timeout_exponential_backoff(self, mock_retry, mock_sync):
        mock_retry.side_effect = Retry("Simulated retry")
        mock_sync.side_effect = GitHubNetworkError("Connection timed out")

        # Set task request retries = 2 -> countdown = 2^2 = 4s
        sync_repository_task.push_request(retries=2)
        try:
            with self.assertRaises(Retry):
                sync_repository_task('hackit/celery-sync-repo')

            mock_retry.assert_called_once()
            _, kwargs = mock_retry.call_args
            self.assertEqual(kwargs['countdown'], 4)
            self.assertEqual(kwargs['max_retries'], TRANSIENT_MAX_RETRIES)
        finally:
            sync_repository_task.pop_request()

    @patch('core.tasks.sync_repository_and_issues')
    def test_task_transient_max_retries_exceeded(self, mock_sync):
        mock_sync.side_effect = GitHubAPIError("Persistent 503 error")

        # Simulate task request with retries exhausted (retries = 5)
        sync_repository_task.push_request(retries=5)
        try:
            with self.assertRaises(GitHubAPIError):
                sync_repository_task('hackit/celery-sync-repo')
        finally:
            sync_repository_task.pop_request()

    def test_first_time_creation_race_project_convergence(self):
        # Initial creation
        project1, created1 = sync_project(SAMPLE_REPO_PAYLOAD)
        self.assertTrue(created1)

        # Simulate concurrent creation hitting IntegrityError fallback
        with patch('core.models.Project.objects.create') as mock_create:
            mock_create.side_effect = IntegrityError("Unique violation")
            project2, created2 = sync_project(SAMPLE_REPO_PAYLOAD)
            self.assertFalse(created2)
            self.assertEqual(project1.id, project2.id)
            self.assertEqual(Project.objects.count(), 1)

    def test_first_time_creation_race_label_convergence(self):
        label1, created1 = sync_label({'name': 'concurrency-label', 'color': '112233'})
        self.assertTrue(created1)

        with patch('core.models.IssueLabel.objects.create') as mock_create:
            mock_create.side_effect = IntegrityError("Unique violation")
            label2, created2 = sync_label({'name': 'concurrency-label', 'color': '112233'})
            self.assertFalse(created2)
            self.assertEqual(label1.id, label2.id)
            self.assertEqual(IssueLabel.objects.count(), 1)

    def test_first_time_creation_race_issue_convergence(self):
        project = Project.objects.create(
            github_repo_id=77778888,
            owner='hackit',
            name='celery-sync-repo',
            full_name='hackit/celery-sync-repo',
        )

        issue1, created1 = sync_issue(project, SAMPLE_ISSUE_PAYLOAD)
        self.assertTrue(created1)

        with patch('core.models.Issue.objects.create') as mock_create:
            mock_create.side_effect = IntegrityError("Unique violation")
            issue2, created2 = sync_issue(project, SAMPLE_ISSUE_PAYLOAD)
            self.assertFalse(created2)
            self.assertEqual(issue1.id, issue2.id)
            self.assertEqual(Issue.objects.count(), 1)


class ManagementCommandAsyncTestCase(TestCase):
    @patch('core.tasks.sync_repository_task.delay')
    def test_command_async_enqueues_to_celery(self, mock_task_delay):
        mock_task = MagicMock()
        mock_task.id = 'task-uuid-12345'
        mock_task_delay.return_value = mock_task

        out = StringIO()
        call_command('sync_github', '--repo', 'hackit/awesome-project', '--async', stdout=out)

        output = out.getvalue()
        self.assertIn("Enqueued sync for 'hackit/awesome-project' to Celery 'sync' queue (Task ID: task-uuid-12345)", output)
        self.assertIn("Successfully enqueued 1 repository sync task(s)", output)
        mock_task_delay.assert_called_once_with('hackit/awesome-project', sync_issues=True)

    @patch('core.tasks.sync_repository_task.delay')
    def test_command_async_with_no_issues_flag(self, mock_task_delay):
        mock_task = MagicMock()
        mock_task.id = 'task-uuid-67890'
        mock_task_delay.return_value = mock_task

        out = StringIO()
        call_command(
            'sync_github',
            '--repo', 'hackit/awesome-project',
            '--no-issues',
            '--async',
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("Enqueued sync for 'hackit/awesome-project' to Celery 'sync' queue (Task ID: task-uuid-67890)", output)
        mock_task_delay.assert_called_once_with('hackit/awesome-project', sync_issues=False)
