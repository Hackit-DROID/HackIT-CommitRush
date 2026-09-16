from datetime import timedelta
import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from celery.exceptions import Retry
from core.github_sync import (
    GitHubAPIError,
    GitHubClient,
    GitHubRateLimitError,
)
from core.models import (
    Contribution,
    EventConfig,
    Issue,
    IssueLabel,
    Participant,
    Project,
    PullRequest,
    WebhookEvent,
)
from core.reconciliation import (
    has_recent_webhook_activity,
    reconcile_all_repositories_nightly,
    reconcile_recent_repositories,
    reconcile_repository,
)
from core.tasks import (
    process_webhook_event_task,
    reconcile_all_repositories_nightly_task,
    reconcile_recent_repositories_task,
)
from core.webhook_processing import extract_issue_numbers, process_webhook_event

User = get_user_model()
TEST_WEBHOOK_SECRET = 'super_secret_webhook_key_12345'


def generate_hub_signature(payload_bytes: bytes, secret: str = TEST_WEBHOOK_SECRET) -> str:
    """Helper to generate standard GitHub sha256 HMAC signature header."""
    digest = hmac.new(secret.encode('utf-8'), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


@override_settings(GITHUB_WEBHOOK_SECRET=TEST_WEBHOOK_SECRET)
class WebhookReceiverTestCase(TestCase):
    """
    Test suite for M4-T1 (Webhook receiver) and M4-T2 (Delivery deduplication).
    Verifies HMAC verification, fast receipt, delivery deduplication, and error handling.
    """

    def setUp(self):
        self.client = APIClient()
        self.proj = Project.objects.create(
            github_repo_id=101,
            owner='hackit',
            name='awesome-core',
            full_name='hackit/awesome-core',
            is_enabled=True,
        )

    def test_m4_t1_valid_signature_accepted_and_persisted(self):
        """Valid HMAC signature returns HTTP 200, stores WebhookEvent, and enqueues task."""
        payload = {
            'action': 'opened',
            'pull_request': {'id': 901, 'number': 1, 'title': 'Add feature'},
            'repository': {'id': 101, 'full_name': 'hackit/awesome-core'},
        }
        body = json.dumps(payload).encode('utf-8')
        sig = generate_hub_signature(body)
        delivery_id = 'deliv-001-uuid-1234'

        with patch('core.tasks.process_webhook_event_task.delay') as mock_delay:
            response = self.client.post(
                '/webhooks/github/',
                data=body,
                content_type='application/json',
                HTTP_X_HUB_SIGNATURE_256=sig,
                HTTP_X_GITHUB_DELIVERY=delivery_id,
                HTTP_X_GITHUB_EVENT='pull_request',
            )

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['status'], 'ok')
            self.assertEqual(data['delivery_id'], delivery_id)

            # Assert WebhookEvent is persisted in DB
            event = WebhookEvent.objects.get(delivery_id=delivery_id)
            self.assertEqual(event.event_type, 'pull_request')
            self.assertEqual(event.payload['action'], 'opened')
            self.assertIsNone(event.processed_at)

            # Assert task enqueued
            mock_delay.assert_called_once_with(event.id)

    def test_m4_t1_versioned_api_endpoint_parity(self):
        """Both /webhooks/github/ and /api/v1/webhooks/github/ behave identically."""
        payload = {'zen': 'Mind your words'}
        body = json.dumps(payload).encode('utf-8')
        sig = generate_hub_signature(body)

        with patch('core.tasks.process_webhook_event_task.delay'):
            response = self.client.post(
                '/api/v1/webhooks/github/',
                data=body,
                content_type='application/json',
                HTTP_X_HUB_SIGNATURE_256=sig,
                HTTP_X_GITHUB_DELIVERY='deliv-v1-parity',
                HTTP_X_GITHUB_EVENT='ping',
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['status'], 'ok')
            self.assertTrue(WebhookEvent.objects.filter(delivery_id='deliv-v1-parity').exists())

    def test_m4_t1_missing_signature_header_returns_401(self):
        """Missing X-Hub-Signature-256 header returns HTTP 401 Unauthorized."""
        body = json.dumps({'zen': 'test'}).encode('utf-8')
        response = self.client.post(
            '/webhooks/github/',
            data=body,
            content_type='application/json',
            HTTP_X_GITHUB_DELIVERY='deliv-no-sig',
            HTTP_X_GITHUB_EVENT='ping',
        )
        self.assertEqual(response.status_code, 401)
        self.assertFalse(WebhookEvent.objects.filter(delivery_id='deliv-no-sig').exists())

    def test_m4_t1_invalid_signature_digest_returns_401(self):
        """Mismatched/invalid HMAC signature returns HTTP 401."""
        body = json.dumps({'zen': 'test'}).encode('utf-8')
        bad_sig = generate_hub_signature(body, secret='wrong_secret_key')

        response = self.client.post(
            '/webhooks/github/',
            data=body,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=bad_sig,
            HTTP_X_GITHUB_DELIVERY='deliv-bad-sig',
            HTTP_X_GITHUB_EVENT='ping',
        )
        self.assertEqual(response.status_code, 401)
        self.assertFalse(WebhookEvent.objects.filter(delivery_id='deliv-bad-sig').exists())

    def test_m4_t1_malformed_signature_format_returns_401(self):
        """Signature missing 'sha256=' prefix returns HTTP 401."""
        body = json.dumps({'zen': 'test'}).encode('utf-8')
        response = self.client.post(
            '/webhooks/github/',
            data=body,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256='invalid_sig_without_prefix',
            HTTP_X_GITHUB_DELIVERY='deliv-malformed-sig',
        )
        self.assertEqual(response.status_code, 401)

    @override_settings(GITHUB_WEBHOOK_SECRET='')
    def test_m4_t1_missing_configured_secret_returns_401(self):
        """If GITHUB_WEBHOOK_SECRET is empty/unconfigured, all webhooks are safely rejected with 401."""
        body = json.dumps({'zen': 'test'}).encode('utf-8')
        sig = generate_hub_signature(body, secret='any_key')
        response = self.client.post(
            '/webhooks/github/',
            data=body,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=sig,
            HTTP_X_GITHUB_DELIVERY='deliv-no-secret',
        )
        self.assertEqual(response.status_code, 401)

    def test_m4_t1_missing_delivery_header_returns_400(self):
        """Missing X-GitHub-Delivery header returns HTTP 400."""
        body = json.dumps({'zen': 'test'}).encode('utf-8')
        sig = generate_hub_signature(body)
        response = self.client.post(
            '/webhooks/github/',
            data=body,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=sig,
        )
        self.assertEqual(response.status_code, 400)

    def test_m4_t1_malformed_json_body_returns_400(self):
        """Invalid JSON in request body returns HTTP 400."""
        body = b'NOT A VALID JSON'
        sig = generate_hub_signature(body)
        response = self.client.post(
            '/webhooks/github/',
            data=body,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=sig,
            HTTP_X_GITHUB_DELIVERY='deliv-invalid-json',
        )
        self.assertEqual(response.status_code, 400)

    def test_m4_t1_non_post_methods_rejected_405(self):
        """GET/PUT/DELETE requests to webhook receiver return HTTP 405 Method Not Allowed."""
        for method in ['get', 'put', 'delete', 'patch']:
            with self.subTest(method=method):
                caller = getattr(self.client, method)
                response = caller('/webhooks/github/')
                self.assertEqual(response.status_code, 405)

    @patch('urllib.request.urlopen')
    @patch('http.client.HTTPConnection')
    @patch('http.client.HTTPSConnection')
    def test_m4_t1_fast_ack_zero_synchronous_network_calls(self, mock_https, mock_http, mock_urlopen):
        """
        Non-negotiable invariant:
        Webhook HTTP receiver executes zero outbound HTTP/HTTPS network calls and acks immediately.
        """
        mock_urlopen.side_effect = AssertionError("Webhook HTTP receiver must NEVER make urllib network calls!")
        mock_http.side_effect = AssertionError("Webhook HTTP receiver must NEVER make HTTP calls!")
        mock_https.side_effect = AssertionError("Webhook HTTP receiver must NEVER make HTTPS calls!")

        payload = {'action': 'opened', 'zen': 'test'}
        body = json.dumps(payload).encode('utf-8')
        sig = generate_hub_signature(body)

        with patch('core.tasks.process_webhook_event_task.delay') as mock_delay:
            response = self.client.post(
                '/webhooks/github/',
                data=body,
                content_type='application/json',
                HTTP_X_HUB_SIGNATURE_256=sig,
                HTTP_X_GITHUB_DELIVERY='deliv-zero-network',
                HTTP_X_GITHUB_EVENT='ping',
            )
            self.assertEqual(response.status_code, 200)
            mock_delay.assert_called_once()

    # =========================================================================
    # M4-T2: Delivery Deduplication Tests
    # =========================================================================

    def test_m4_t2_duplicate_delivery_returns_200_no_op(self):
        """
        PRD §13.2 & §16:
        Duplicate X-GitHub-Delivery returns HTTP 200 no-op, does not duplicate WebhookEvent,
        and does not enqueue duplicate processing.
        """
        delivery_id = 'deliv-dedup-unique-999'
        payload = {'zen': 'duplicate test'}
        body = json.dumps(payload).encode('utf-8')
        sig = generate_hub_signature(body)

        with patch('core.tasks.process_webhook_event_task.delay') as mock_delay:
            # 1. First delivery -> 200 ok
            res1 = self.client.post(
                '/webhooks/github/',
                data=body,
                content_type='application/json',
                HTTP_X_HUB_SIGNATURE_256=sig,
                HTTP_X_GITHUB_DELIVERY=delivery_id,
                HTTP_X_GITHUB_EVENT='ping',
            )
            self.assertEqual(res1.status_code, 200)
            self.assertEqual(res1.json()['status'], 'ok')
            self.assertEqual(mock_delay.call_count, 1)
            self.assertEqual(WebhookEvent.objects.filter(delivery_id=delivery_id).count(), 1)

            # 2. Duplicate delivery -> 200 duplicate
            res2 = self.client.post(
                '/webhooks/github/',
                data=body,
                content_type='application/json',
                HTTP_X_HUB_SIGNATURE_256=sig,
                HTTP_X_GITHUB_DELIVERY=delivery_id,
                HTTP_X_GITHUB_EVENT='ping',
            )
            self.assertEqual(res2.status_code, 200)
            self.assertEqual(res2.json()['status'], 'duplicate')
            # No additional task enqueued
            self.assertEqual(mock_delay.call_count, 1)
            self.assertEqual(WebhookEvent.objects.filter(delivery_id=delivery_id).count(), 1)

    @patch('core.models.WebhookEvent.objects.create')
    def test_m4_t2_concurrent_delivery_race_condition_caught(self, mock_create):
        """Simulated IntegrityError on concurrent insert is caught and returned as duplicate 200."""
        mock_create.side_effect = IntegrityError("duplicate key value violates unique constraint")

        body = json.dumps({'zen': 'race test'}).encode('utf-8')
        sig = generate_hub_signature(body)

        response = self.client.post(
            '/webhooks/github/',
            data=body,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=sig,
            HTTP_X_GITHUB_DELIVERY='deliv-race-condition',
            HTTP_X_GITHUB_EVENT='ping',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'duplicate')


@override_settings(GITHUB_WEBHOOK_SECRET=TEST_WEBHOOK_SECRET)
class WebhookProcessingTestCase(TestCase):
    """
    Test suite for M4-T3: Webhook queue processing & event mappings.
    Covers pull_request (opened, synchronize, closed merged/unmerged) and issues (closed, labeled, edited).
    """

    def setUp(self):
        self.user = User.objects.create_user(username='octo_coder', email='octo@example.com')
        self.participant = Participant.objects.create(
            user=self.user,
            github_id=9001,
            github_username='octo_coder',
        )

        self.project = Project.objects.create(
            github_repo_id=5001,
            owner='hackit',
            name='core-api',
            full_name='hackit/core-api',
            language='Python',
            is_enabled=True,
        )

        self.label_bug = IssueLabel.objects.create(name='bug', color='d73a4a')

        self.issue1 = Issue.objects.create(
            github_issue_id=8001,
            project=self.project,
            number=42,
            title='Authentication token race condition',
            points=100,
            difficulty='intermediate',
            category='security',
            status='open',
            is_featured=True,
        )
        self.issue1.labels.add(self.label_bug)

    def test_extract_issue_numbers(self):
        """Test extraction of issue numbers from varied PR text formats."""
        self.assertEqual(extract_issue_numbers("Fixes #42"), [42])
        self.assertEqual(extract_issue_numbers("Closes #10 and resolves #20"), [10, 20])
        self.assertEqual(extract_issue_numbers("This addresses issue #99 in core"), [99])
        self.assertEqual(extract_issue_numbers("Feature work on branch fix/#15"), [15])
        self.assertEqual(extract_issue_numbers("No issue number in this text"), [])
        self.assertEqual(extract_issue_numbers(None), [])

    def test_m4_t3_pr_opened_creates_pending_contribution_for_tracked_issue(self):
        """
        PRD §13.3:
        pull_request.opened referencing a tracked issue creates PullRequest and Contribution in PENDING.
        """
        payload = {
            'action': 'opened',
            'pull_request': {
                'id': 7001,
                'number': 101,
                'title': 'Fixes #42 - resolve race condition in auth tokens',
                'body': 'This PR closes #42 cleanly with atomic locks.',
                'user': {'id': 9001, 'login': 'octo_coder'},
                'head': {'sha': 'abc123def456', 'ref': 'patch-auth-42'},
                'merged': False,
                'merged_at': None,
            },
            'repository': {
                'id': 5001,
                'full_name': 'hackit/core-api',
            },
        }

        webhook_event = WebhookEvent.objects.create(
            delivery_id='pr-opened-001',
            event_type='pull_request',
            payload=payload,
        )

        result = process_webhook_event(webhook_event)
        self.assertEqual(result['status'], 'contribution_created')

        # Verify PullRequest row created
        pr = PullRequest.objects.get(github_pr_id=7001)
        self.assertEqual(pr.repo, self.project)
        self.assertEqual(pr.number, 101)
        self.assertEqual(pr.author_participant, self.participant)
        self.assertEqual(pr.head_sha, 'abc123def456')
        self.assertFalse(pr.merged)

        # Verify Contribution row created in PENDING status
        contrib = Contribution.objects.get(pull_request=pr)
        self.assertEqual(contrib.participant, self.participant)
        self.assertEqual(contrib.issue, self.issue1)
        self.assertEqual(contrib.status, 'PENDING')

        # Verify WebhookEvent marked processed
        webhook_event.refresh_from_db()
        self.assertIsNotNone(webhook_event.processed_at)
        self.assertEqual(webhook_event.processing_error, '')

    def test_m4_t3_pr_opened_without_tracked_issue_creates_pr_no_contribution(self):
        """
        PRD §13.3:
        pull_request.opened NOT referencing any tracked issue caches the PR but does NOT create Contribution.
        """
        payload = {
            'action': 'opened',
            'pull_request': {
                'id': 7002,
                'number': 102,
                'title': 'Unrelated documentation update',
                'body': 'Fix typo in README without issue reference',
                'user': {'id': 9001, 'login': 'octo_coder'},
                'head': {'sha': 'sha-unrelated', 'ref': 'docs-typo'},
                'merged': False,
            },
            'repository': {
                'id': 5001,
                'full_name': 'hackit/core-api',
            },
        }

        webhook_event = WebhookEvent.objects.create(
            delivery_id='pr-opened-no-issue',
            event_type='pull_request',
            payload=payload,
        )

        result = process_webhook_event(webhook_event)
        self.assertEqual(result['status'], 'pr_cached')
        self.assertTrue(PullRequest.objects.filter(github_pr_id=7002).exists())
        self.assertFalse(Contribution.objects.filter(pull_request__github_pr_id=7002).exists())

    def test_m4_t3_pr_opened_unregistered_author_creates_pr_no_contribution(self):
        """
        PR opened by a GitHub user not registered on CommitRush creates PullRequest with null participant,
        and does NOT create a Contribution.
        """
        payload = {
            'action': 'opened',
            'pull_request': {
                'id': 7003,
                'number': 103,
                'title': 'Fixes #42 from unregistered user',
                'body': 'Closes #42',
                'user': {'id': 999999, 'login': 'unknown_contributor'},
                'head': {'sha': 'sha-unknown', 'ref': 'fix-42'},
                'merged': False,
            },
            'repository': {
                'id': 5001,
                'full_name': 'hackit/core-api',
            },
        }

        webhook_event = WebhookEvent.objects.create(
            delivery_id='pr-opened-unregistered',
            event_type='pull_request',
            payload=payload,
        )

        result = process_webhook_event(webhook_event)
        self.assertEqual(result['status'], 'pr_cached')
        pr = PullRequest.objects.get(github_pr_id=7003)
        self.assertIsNone(pr.author_participant)
        self.assertEqual(pr.author_github_id, 999999)
        self.assertFalse(Contribution.objects.filter(pull_request=pr).exists())

    def test_m4_t3_pr_synchronize_updates_commit_sha(self):
        """
        PRD §13.3:
        pull_request.synchronize updates PullRequest.head_sha and refreshes Contribution.
        """
        # Pre-create PR and Contribution
        pr = PullRequest.objects.create(
            github_pr_id=7004,
            repo=self.project,
            number=104,
            author_github_id=9001,
            author_participant=self.participant,
            head_sha='old_sha_111',
            merged=False,
        )
        contrib = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue1,
            pull_request=pr,
            status='PENDING',
        )

        payload = {
            'action': 'synchronize',
            'pull_request': {
                'id': 7004,
                'number': 104,
                'user': {'id': 9001, 'login': 'octo_coder'},
                'head': {'sha': 'new_sha_222', 'ref': 'patch-branch'},
                'merged': False,
            },
            'repository': {
                'id': 5001,
                'full_name': 'hackit/core-api',
            },
        }

        webhook_event = WebhookEvent.objects.create(
            delivery_id='pr-sync-001',
            event_type='pull_request',
            payload=payload,
        )

        result = process_webhook_event(webhook_event)
        self.assertEqual(result['status'], 'synchronized')
        self.assertEqual(result['head_sha'], 'new_sha_222')

        pr.refresh_from_db()
        self.assertEqual(pr.head_sha, 'new_sha_222')

    def test_m4_t3_pr_closed_merged_transitions_contribution_to_merged(self):
        """
        PRD §13.3:
        pull_request.closed with merged=True transitions Contribution to MERGED.
        """
        pr = PullRequest.objects.create(
            github_pr_id=7005,
            repo=self.project,
            number=105,
            author_github_id=9001,
            author_participant=self.participant,
            head_sha='sha_merged_123',
            merged=False,
        )
        contrib = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue1,
            pull_request=pr,
            status='UNDER_REVIEW',
        )

        payload = {
            'action': 'closed',
            'pull_request': {
                'id': 7005,
                'number': 105,
                'user': {'id': 9001, 'login': 'octo_coder'},
                'head': {'sha': 'sha_merged_123'},
                'merged': True,
                'merged_at': '2026-09-16T12:00:00Z',
            },
            'repository': {
                'id': 5001,
                'full_name': 'hackit/core-api',
            },
        }

        webhook_event = WebhookEvent.objects.create(
            delivery_id='pr-closed-merged-001',
            event_type='pull_request',
            payload=payload,
        )

        result = process_webhook_event(webhook_event)
        self.assertEqual(result['status'], 'pr_merged')

        pr.refresh_from_db()
        self.assertTrue(pr.merged)
        self.assertIsNotNone(pr.merged_at)

        contrib.refresh_from_db()
        self.assertEqual(contrib.status, 'MERGED')
        self.assertIsNotNone(contrib.merged_at)

    def test_m4_t3_pr_closed_unmerged_transitions_contribution_to_rejected(self):
        """
        PRD §13.3:
        pull_request.closed with merged=False transitions Contribution to REJECTED.
        """
        pr = PullRequest.objects.create(
            github_pr_id=7006,
            repo=self.project,
            number=106,
            author_github_id=9001,
            author_participant=self.participant,
            head_sha='sha_unmerged_123',
            merged=False,
        )
        contrib = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue1,
            pull_request=pr,
            status='UNDER_REVIEW',
        )

        payload = {
            'action': 'closed',
            'pull_request': {
                'id': 7006,
                'number': 106,
                'user': {'id': 9001, 'login': 'octo_coder'},
                'head': {'sha': 'sha_unmerged_123'},
                'merged': False,
                'merged_at': None,
            },
            'repository': {
                'id': 5001,
                'full_name': 'hackit/core-api',
            },
        }

        webhook_event = WebhookEvent.objects.create(
            delivery_id='pr-closed-unmerged-001',
            event_type='pull_request',
            payload=payload,
        )

        result = process_webhook_event(webhook_event)
        self.assertEqual(result['status'], 'pr_rejected')

        pr.refresh_from_db()
        self.assertFalse(pr.merged)

        contrib.refresh_from_db()
        self.assertEqual(contrib.status, 'REJECTED')

    def test_m4_t3_issues_closed_marks_local_issue_closed(self):
        """
        PRD §13.3:
        issues.closed marks the local Issue status closed.
        """
        self.assertEqual(self.issue1.status, 'open')

        payload = {
            'action': 'closed',
            'issue': {
                'id': 8001,
                'number': 42,
                'title': 'Authentication token race condition',
                'state': 'closed',
            },
            'repository': {
                'id': 5001,
                'full_name': 'hackit/core-api',
            },
        }

        webhook_event = WebhookEvent.objects.create(
            delivery_id='issue-closed-001',
            event_type='issues',
            payload=payload,
        )

        result = process_webhook_event(webhook_event)
        self.assertEqual(result['status'], 'issue_closed')

        self.issue1.refresh_from_db()
        self.assertEqual(self.issue1.status, 'closed')

    def test_m4_t3_issues_labeled_and_edited_updates_metadata_cache(self):
        """
        PRD §13.3:
        issues.labeled / issues.edited updates local Issue title and labels
        while preserving operator customizations.
        """
        # Set operator customizations
        self.issue1.points = 200
        self.issue1.difficulty = 'advanced'
        self.issue1.category = 'security'
        self.issue1.is_featured = True
        self.issue1.save()

        payload = {
            'action': 'labeled',
            'issue': {
                'id': 8001,
                'number': 42,
                'title': 'Authentication token race condition (UPDATED TITLE)',
                'state': 'open',
                'created_at': '2026-09-10T10:00:00Z',
                'labels': [
                    {'name': 'bug', 'color': 'd73a4a'},
                    {'name': 'backend', 'color': '008672'},
                ],
            },
            'repository': {
                'id': 5001,
                'full_name': 'hackit/core-api',
            },
        }

        webhook_event = WebhookEvent.objects.create(
            delivery_id='issue-labeled-001',
            event_type='issues',
            payload=payload,
        )

        result = process_webhook_event(webhook_event)
        self.assertEqual(result['status'], 'issue_synced')

        self.issue1.refresh_from_db()
        self.assertEqual(self.issue1.title, 'Authentication token race condition (UPDATED TITLE)')
        label_names = set(self.issue1.labels.values_list('name', flat=True))
        self.assertEqual(label_names, {'bug', 'backend'})

        # Operator customizations preserved
        self.assertEqual(self.issue1.points, 200)
        self.assertEqual(self.issue1.difficulty, 'advanced')
        self.assertEqual(self.issue1.category, 'security')
        self.assertTrue(self.issue1.is_featured)

    def test_m4_t3_process_webhook_event_task_idempotent_execution(self):
        """
        Executing process_webhook_event_task multiple times is completely idempotent.
        """
        payload = {
            'action': 'opened',
            'pull_request': {
                'id': 7099,
                'number': 199,
                'title': 'Fixes #42',
                'user': {'id': 9001, 'login': 'octo_coder'},
                'head': {'sha': 'sha-idempotency', 'ref': 'patch-1'},
                'merged': False,
            },
            'repository': {
                'id': 5001,
                'full_name': 'hackit/core-api',
            },
        }

        webhook_event = WebhookEvent.objects.create(
            delivery_id='task-idempotent-001',
            event_type='pull_request',
            payload=payload,
        )

        # First task run
        task_res1 = process_webhook_event_task(webhook_event.id)
        self.assertEqual(task_res1['status'], 'success')
        self.assertEqual(Contribution.objects.filter(pull_request__github_pr_id=7099).count(), 1)

        # Second task run with identical webhook_event
        task_res2 = process_webhook_event_task(webhook_event.id)
        self.assertEqual(task_res2['status'], 'success')
        self.assertEqual(Contribution.objects.filter(pull_request__github_pr_id=7099).count(), 1)


@override_settings(GITHUB_WEBHOOK_SECRET=TEST_WEBHOOK_SECRET)
class SubmissionsPausedTestCase(TestCase):
    """
    Test suite for M4-T4: Respect submissions_paused (PRD §12.6, §15, plan.md M4-T4).
    When submissions_paused is True:
    - Webhook receiver still accepts valid signature, persists WebhookEvent, returns 200.
    - Worker does NOT create or validate new Contribution records.
    - Raw events remain in WebhookEvent for future replay.
    - Other pause flags and issue caches are not disturbed.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='paused_user', password='password123')
        self.participant = Participant.objects.create(
            user=self.user,
            github_id=8801,
            github_username='paused_coder',
        )
        self.proj = Project.objects.create(
            github_repo_id=4001,
            owner='hackit',
            name='paused-repo',
            full_name='hackit/paused-repo',
            is_enabled=True,
        )
        self.issue = Issue.objects.create(
            github_issue_id=41001,
            project=self.proj,
            number=15,
            title='Core issue for paused submissions test',
            points=100,
            status='open',
        )
        self.config = EventConfig.get_solo()
        self.config.submissions_paused = True
        self.config.save(update_fields=['submissions_paused'])

    def tearDown(self):
        self.config.submissions_paused = False
        self.config.save(update_fields=['submissions_paused'])

    def test_m4_t4_webhook_receiver_accepts_and_persists_when_submissions_paused(self):
        """Webhook receiver verifies HMAC, persists WebhookEvent, and returns 200 even when paused."""
        payload = {
            'action': 'opened',
            'pull_request': {
                'id': 4801,
                'number': 1,
                'title': 'Fixes #15',
                'user': {'id': 8801, 'login': 'paused_coder'},
                'head': {'sha': 'sha-paused-1', 'ref': 'patch-1'},
                'merged': False,
            },
            'repository': {
                'id': 4001,
                'full_name': 'hackit/paused-repo',
            },
        }
        body = json.dumps(payload).encode('utf-8')
        sig = generate_hub_signature(body)
        delivery_id = 'paused-deliv-001'

        with patch('core.tasks.process_webhook_event_task.delay') as mock_delay:
            response = self.client.post(
                '/webhooks/github/',
                data=body,
                content_type='application/json',
                HTTP_X_HUB_SIGNATURE_256=sig,
                HTTP_X_GITHUB_DELIVERY=delivery_id,
                HTTP_X_GITHUB_EVENT='pull_request',
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['status'], 'ok')

            # Verify WebhookEvent stored
            event = WebhookEvent.objects.get(delivery_id=delivery_id)
            self.assertEqual(event.event_type, 'pull_request')
            self.assertIsNone(event.processed_at)
            mock_delay.assert_called_once_with(event.id)

    def test_m4_t4_worker_caches_pr_and_creates_no_contribution_when_submissions_paused(self):
        """Worker caches PullRequest metadata but does NOT create Contribution when submissions_paused=True."""
        payload = {
            'action': 'opened',
            'pull_request': {
                'id': 4802,
                'number': 2,
                'title': 'Fixes #15 - paused PR submission',
                'user': {'id': 8801, 'login': 'paused_coder'},
                'head': {'sha': 'sha-paused-2', 'ref': 'patch-2'},
                'merged': False,
            },
            'repository': {
                'id': 4001,
                'full_name': 'hackit/paused-repo',
            },
        }

        webhook_event = WebhookEvent.objects.create(
            delivery_id='paused-event-002',
            event_type='pull_request',
            payload=payload,
        )

        result = process_webhook_event(webhook_event)
        self.assertEqual(result['status'], 'submissions_paused')
        self.assertIn('reason', result)

        # Assert PullRequest model was synchronized
        pr = PullRequest.objects.filter(github_pr_id=4802).first()
        self.assertIsNotNone(pr)
        self.assertEqual(pr.number, 2)
        self.assertEqual(pr.head_sha, 'sha-paused-2')

        # Assert NO Contribution was created
        self.assertEqual(Contribution.objects.filter(pull_request=pr).count(), 0)

        # Assert WebhookEvent is cleanly marked processed with raw payload intact
        webhook_event.refresh_from_db()
        self.assertIsNotNone(webhook_event.processed_at)
        self.assertEqual(webhook_event.processing_error, '')

    def test_m4_t4_submissions_unpause_resumes_normal_contribution_creation(self):
        """When submissions_paused is turned off, new submissions create Contributions normally."""
        self.config.submissions_paused = False
        self.config.save(update_fields=['submissions_paused'])

        payload = {
            'action': 'opened',
            'pull_request': {
                'id': 4803,
                'number': 3,
                'title': 'Fixes #15 - unpaused PR submission',
                'user': {'id': 8801, 'login': 'paused_coder'},
                'head': {'sha': 'sha-unpaused-3', 'ref': 'patch-3'},
                'merged': False,
            },
            'repository': {
                'id': 4001,
                'full_name': 'hackit/paused-repo',
            },
        }

        webhook_event = WebhookEvent.objects.create(
            delivery_id='unpaused-event-003',
            event_type='pull_request',
            payload=payload,
        )

        result = process_webhook_event(webhook_event)
        self.assertEqual(result['status'], 'contribution_created')

        contrib = Contribution.objects.filter(pull_request__github_pr_id=4803).first()
        self.assertIsNotNone(contrib)
        self.assertEqual(contrib.status, 'PENDING')
        self.assertEqual(contrib.issue, self.issue)
        self.assertEqual(contrib.participant, self.participant)

    def test_m4_t4_issues_webhook_unaffected_by_submissions_paused(self):
        """Issue cache updates proceed normally even when submissions_paused=True."""
        payload = {
            'action': 'edited',
            'issue': {
                'id': 41001,
                'number': 15,
                'title': 'Updated Title while submissions paused',
                'state': 'open',
                'created_at': '2026-09-10T10:00:00Z',
            },
            'repository': {
                'id': 4001,
                'full_name': 'hackit/paused-repo',
            },
        }

        webhook_event = WebhookEvent.objects.create(
            delivery_id='paused-issue-event-004',
            event_type='issues',
            payload=payload,
        )

        result = process_webhook_event(webhook_event)
        self.assertEqual(result['status'], 'issue_synced')

        self.issue.refresh_from_db()
        self.assertEqual(self.issue.title, 'Updated Title while submissions paused')

    def test_m4_t4_submissions_paused_does_not_modify_unrelated_flags(self):
        """Toggling submissions_paused leaves merge_paused, validation_paused, and leaderboard_frozen intact."""
        self.config.merge_paused = True
        self.config.validation_paused = False
        self.config.leaderboard_frozen = True
        self.config.submissions_paused = True
        self.config.save()

        fresh = EventConfig.get_solo()
        self.assertTrue(fresh.submissions_paused)
        self.assertTrue(fresh.merge_paused)
        self.assertFalse(fresh.validation_paused)
        self.assertTrue(fresh.leaderboard_frozen)


class ReconciliationTestCase(TestCase):
    """
    Test suite for M4-T5: Reconciliation scaffold (PRD §13.4, §13.6, plan.md M4-T5).
    Verifies:
    - has_recent_webhook_activity window check
    - reconcile_repository issue and PR synchronization
    - Simulated missed PR webhook catch-up
    - 15-minute scheduled reconciliation (skipping recent webhook repos)
    - Nightly full reconciliation
    - Celery task execution, rate-limit backoff, and retry handling
    - submissions_paused respect during reconciliation
    """

    def setUp(self):
        self.user = User.objects.create_user(username='recon_user', password='password123')
        self.participant = Participant.objects.create(
            user=self.user,
            github_id=9901,
            github_username='recon_dev',
        )
        self.proj1 = Project.objects.create(
            github_repo_id=6001,
            owner='hackit',
            name='recon-repo-1',
            full_name='hackit/recon-repo-1',
            is_enabled=True,
        )
        self.proj2 = Project.objects.create(
            github_repo_id=6002,
            owner='hackit',
            name='recon-repo-2',
            full_name='hackit/recon-repo-2',
            is_enabled=True,
        )
        self.issue1 = Issue.objects.create(
            github_issue_id=61001,
            project=self.proj1,
            number=10,
            title='Tracked Issue #10 in Repo 1',
            points=100,
            status='open',
        )
        self.issue2 = Issue.objects.create(
            github_issue_id=62001,
            project=self.proj2,
            number=20,
            title='Tracked Issue #20 in Repo 2',
            points=50,
            status='open',
        )

    def test_m4_t5_has_recent_webhook_activity(self):
        """Verifies detection of recent webhook activity within window."""
        # Proj 1 has no webhooks
        self.assertFalse(has_recent_webhook_activity(self.proj1, window_minutes=15))

        # Create recent webhook for Proj 1 (processed 5 mins ago)
        WebhookEvent.objects.create(
            delivery_id='recent-wh-001',
            event_type='pull_request',
            payload={'repository': {'id': 6001, 'full_name': 'hackit/recon-repo-1'}},
            processed_at=timezone.now() - timedelta(minutes=5),
        )
        self.assertTrue(has_recent_webhook_activity(self.proj1, window_minutes=15))

        # For a 3-minute window, a 5-minute-old webhook is NOT recent
        self.assertFalse(has_recent_webhook_activity(self.proj1, window_minutes=3))

        # An unprocessed webhook (processed_at=None) is considered active
        WebhookEvent.objects.create(
            delivery_id='unprocessed-wh-002',
            event_type='issues',
            payload={'repository': {'id': 6002, 'full_name': 'hackit/recon-repo-2'}},
            processed_at=None,
        )
        self.assertTrue(has_recent_webhook_activity(self.proj2, window_minutes=15))

    def test_m4_t5_reconcile_repository_syncs_issues_and_prs(self):
        """reconcile_repository fetches issues and PRs via client and synchronizes models."""
        mock_client = MagicMock(spec=GitHubClient)
        mock_client.get_issues.return_value = [
            {
                'id': 61001,
                'number': 10,
                'title': 'Tracked Issue #10 (Updated Title)',
                'state': 'open',
                'created_at': '2026-09-10T10:00:00Z',
                'labels': [{'name': 'help wanted', 'color': '159818'}],
            },
            {
                'id': 61002,
                'number': 11,
                'title': 'Brand New Discovered Issue #11',
                'state': 'open',
                'created_at': '2026-09-11T11:00:00Z',
                'labels': [],
            },
        ]
        mock_client.get_pull_requests.return_value = [
            {
                'id': 7001,
                'number': 1,
                'title': 'Fixes #10 - PR 1',
                'state': 'open',
                'user': {'id': 9901, 'login': 'recon_dev'},
                'head': {'sha': 'sha-recon-pr-1', 'ref': 'feature-1'},
                'merged': False,
            },
            {
                'id': 7002,
                'number': 2,
                'title': 'Resolves #10 - PR 2 Merged',
                'state': 'closed',
                'user': {'id': 9901, 'login': 'recon_dev'},
                'head': {'sha': 'sha-recon-pr-2', 'ref': 'feature-2'},
                'merged': True,
                'merged_at': '2026-09-12T12:00:00Z',
            },
        ]

        result = reconcile_repository(self.proj1, client=mock_client)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['issues_created'], 1)
        self.assertEqual(result['issues_updated'], 1)
        self.assertEqual(result['prs_reconciled'], 2)

        # Verify Issue 10 updated and Issue 11 created
        self.issue1.refresh_from_db()
        self.assertEqual(self.issue1.title, 'Tracked Issue #10 (Updated Title)')
        self.assertTrue(Issue.objects.filter(project=self.proj1, number=11).exists())

        # Verify PR 1 created Contribution with PENDING
        pr1 = PullRequest.objects.get(github_pr_id=7001)
        contrib1 = Contribution.objects.get(pull_request=pr1)
        self.assertEqual(contrib1.status, 'PENDING')
        self.assertEqual(contrib1.participant, self.participant)

        # Verify PR 2 transitioned to MERGED
        pr2 = PullRequest.objects.get(github_pr_id=7002)
        contrib2 = Contribution.objects.get(pull_request=pr2)
        self.assertEqual(contrib2.status, 'MERGED')
        self.assertTrue(pr2.merged)

    def test_m4_t5_reconcile_catches_missed_webhook_event(self):
        """Simulates a missed PR webhook delivery: reconciliation recovers the contribution."""
        # Simulated scenario: Developer opened PR #5 resolving Issue #10 on GitHub, but webhook was dropped.
        self.assertEqual(Contribution.objects.count(), 0)
        self.assertEqual(PullRequest.objects.count(), 0)

        mock_client = MagicMock(spec=GitHubClient)
        mock_client.get_issues.return_value = []
        mock_client.get_pull_requests.return_value = [
            {
                'id': 7005,
                'number': 5,
                'title': 'Closes #10 (Missed Webhook Delivery)',
                'state': 'open',
                'user': {'id': 9901, 'login': 'recon_dev'},
                'head': {'sha': 'sha-missed-event', 'ref': 'patch-missed'},
                'merged': False,
            }
        ]

        result = reconcile_repository(self.proj1, client=mock_client)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['pr_stats']['contribution_created'], 1)

        # Contribution and PR are successfully recovered
        pr = PullRequest.objects.get(github_pr_id=7005)
        self.assertEqual(pr.number, 5)
        contrib = Contribution.objects.get(pull_request=pr)
        self.assertEqual(contrib.status, 'PENDING')
        self.assertEqual(contrib.issue, self.issue1)
        self.assertEqual(contrib.participant, self.participant)

    def test_m4_t5_reconcile_recent_repositories_skips_active_and_syncs_quiet(self):
        """reconcile_recent_repositories skips repos with recent webhooks and reconciles quiet repos."""
        # Proj 1 has recent webhook activity
        WebhookEvent.objects.create(
            delivery_id='recent-proj1-wh',
            event_type='pull_request',
            payload={'repository': {'id': 6001, 'full_name': 'hackit/recon-repo-1'}},
            processed_at=timezone.now() - timedelta(minutes=2),
        )

        mock_client = MagicMock(spec=GitHubClient)
        mock_client.get_issues.return_value = []
        mock_client.get_pull_requests.return_value = []

        result = reconcile_recent_repositories(window_minutes=15, client=mock_client)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['total_projects'], 2)
        self.assertEqual(result['skipped_count'], 1)
        self.assertEqual(result['reconciled_count'], 1)

        skipped_ids = [item['project_id'] for item in result['skipped']]
        reconciled_ids = [item['project_id'] for item in result['reconciled']]
        self.assertIn(self.proj1.id, skipped_ids)
        self.assertIn(self.proj2.id, reconciled_ids)

    def test_m4_t5_reconcile_all_repositories_nightly(self):
        """reconcile_all_repositories_nightly reconciles all enabled projects regardless of webhook history."""
        # Even with recent webhook activity on Proj 1
        WebhookEvent.objects.create(
            delivery_id='nightly-recent-wh',
            event_type='pull_request',
            payload={'repository': {'id': 6001, 'full_name': 'hackit/recon-repo-1'}},
            processed_at=timezone.now() - timedelta(minutes=1),
        )

        # Proj 2 is disabled
        self.proj2.is_enabled = False
        self.proj2.save(update_fields=['is_enabled'])

        mock_client = MagicMock(spec=GitHubClient)
        mock_client.get_issues.return_value = []
        mock_client.get_pull_requests.return_value = []

        result = reconcile_all_repositories_nightly(client=mock_client)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['total_projects'], 1)  # Only 1 enabled
        self.assertEqual(result['reconciled_count'], 1)
        self.assertEqual(result['reconciled'][0]['project_id'], self.proj1.id)

    def test_m4_t5_celery_reconcile_recent_repositories_task_success(self):
        """Celery task reconcile_recent_repositories_task runs to completion."""
        with patch('core.reconciliation.reconcile_recent_repositories') as mock_recon:
            mock_recon.return_value = {'status': 'completed', 'reconciled_count': 2}
            res = reconcile_recent_repositories_task(window_minutes=15)
            self.assertEqual(res['status'], 'completed')
            mock_recon.assert_called_once()

    def test_m4_t5_celery_reconcile_nightly_task_success(self):
        """Celery task reconcile_all_repositories_nightly_task runs to completion."""
        with patch('core.reconciliation.reconcile_all_repositories_nightly') as mock_recon:
            mock_recon.return_value = {'status': 'completed', 'reconciled_count': 2}
            res = reconcile_all_repositories_nightly_task()
            self.assertEqual(res['status'], 'completed')
            mock_recon.assert_called_once()

    @patch('core.reconciliation.reconcile_recent_repositories')
    @patch.object(reconcile_recent_repositories_task, 'retry')
    def test_m4_t5_celery_task_rate_limit_backoff(self, mock_retry, mock_recon):
        """Celery reconciliation task catches GitHubRateLimitError and backs off via retry."""
        mock_retry.side_effect = Retry("Simulated retry")
        mock_recon.side_effect = GitHubRateLimitError(
            "Rate limited",
            remaining=0,
            limit=5000,
            reset_timestamp=int(timezone.now().timestamp()) + 90,
            retry_after=90,
        )

        with self.assertRaises(Retry):
            reconcile_recent_repositories_task(window_minutes=15)

        mock_retry.assert_called_once()
        call_kwargs = mock_retry.call_args[1]
        self.assertEqual(call_kwargs['countdown'], 90)
        self.assertIsNone(call_kwargs['max_retries'])

    @patch('core.reconciliation.reconcile_recent_repositories')
    @patch.object(reconcile_recent_repositories_task, 'retry')
    def test_m4_t5_celery_task_transient_error_exponential_backoff(self, mock_retry, mock_recon):
        """Celery reconciliation task catches GitHubAPIError and uses exponential backoff."""
        mock_retry.side_effect = Retry("Simulated retry")
        mock_recon.side_effect = GitHubAPIError("GitHub 503 Service Unavailable")

        reconcile_recent_repositories_task.push_request(retries=0)
        try:
            with self.assertRaises(Retry):
                reconcile_recent_repositories_task(window_minutes=15)

            mock_retry.assert_called_once()
            call_kwargs = mock_retry.call_args[1]
            self.assertEqual(call_kwargs['countdown'], 1)
        finally:
            reconcile_recent_repositories_task.pop_request()

    @patch('core.reconciliation.reconcile_all_repositories_nightly')
    @patch.object(reconcile_all_repositories_nightly_task, 'retry')
    def test_m4_t5_celery_nightly_task_rate_limit_backoff(self, mock_retry, mock_recon):
        """Celery nightly task catches GitHubRateLimitError and backs off via retry."""
        mock_retry.side_effect = Retry("Simulated retry")
        mock_recon.side_effect = GitHubRateLimitError(
            "Rate limited",
            remaining=0,
            limit=5000,
            reset_timestamp=int(timezone.now().timestamp()) + 120,
            retry_after=120,
        )

        with self.assertRaises(Retry):
            reconcile_all_repositories_nightly_task()

        mock_retry.assert_called_once()
        call_kwargs = mock_retry.call_args[1]
        self.assertEqual(call_kwargs['countdown'], 120)
        self.assertIsNone(call_kwargs['max_retries'])

    @patch('core.reconciliation.reconcile_all_repositories_nightly')
    @patch.object(reconcile_all_repositories_nightly_task, 'retry')
    def test_m4_t5_celery_nightly_task_transient_error_backoff(self, mock_retry, mock_recon):
        """Celery nightly task catches GitHubAPIError and uses exponential backoff."""
        mock_retry.side_effect = Retry("Simulated retry")
        mock_recon.side_effect = GitHubAPIError("GitHub 500 Server Error")

        reconcile_all_repositories_nightly_task.push_request(retries=1)
        try:
            with self.assertRaises(Retry):
                reconcile_all_repositories_nightly_task()

            mock_retry.assert_called_once()
            call_kwargs = mock_retry.call_args[1]
            self.assertEqual(call_kwargs['countdown'], 2)
        finally:
            reconcile_all_repositories_nightly_task.pop_request()

    def test_m4_t5_reconciliation_respects_submissions_paused(self):
        """When submissions_paused=True, reconciliation caches PRs but creates NO Contribution rows."""
        config = EventConfig.get_solo()
        config.submissions_paused = True
        config.save(update_fields=['submissions_paused'])

        try:
            mock_client = MagicMock(spec=GitHubClient)
            mock_client.get_issues.return_value = []
            mock_client.get_pull_requests.return_value = [
                {
                    'id': 7090,
                    'number': 90,
                    'title': 'Fixes #10 while submissions are paused',
                    'state': 'open',
                    'user': {'id': 9901, 'login': 'recon_dev'},
                    'head': {'sha': 'sha-paused-recon', 'ref': 'patch-paused-recon'},
                    'merged': False,
                }
            ]

            result = reconcile_repository(self.proj1, client=mock_client)
            self.assertEqual(result['status'], 'success')
            self.assertEqual(result['pr_stats']['submissions_paused'], 1)

            # PullRequest is cached
            pr = PullRequest.objects.get(github_pr_id=7090)
            self.assertEqual(pr.number, 90)

            # NO Contribution was created
            self.assertEqual(Contribution.objects.filter(pull_request=pr).count(), 0)
        finally:
            config.submissions_paused = False
            config.save(update_fields=['submissions_paused'])
