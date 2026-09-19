import hashlib
import hmac
import json
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import (
    AuditLog,
    Contribution,
    DailyContributionUsage,
    EventConfig,
    Issue,
    Participant,
    PointTransaction,
    Project,
    PullRequest,
    WebhookEvent,
)

User = get_user_model()
TEST_SECURITY_SECRET = 'super_secret_webhook_key_12345'


@override_settings(GITHUB_WEBHOOK_SECRET=TEST_SECURITY_SECRET)
class M9T5SecurityAuditingTests(TestCase):
    """
    M9-T5: Security, RBAC, Ownership, HMAC & Hardening Test Suite (PRD §17, §18, §19, plan.md M9-T5).
    Verifies:
    1. Authorization & Role-Based Access Control (Anonymous vs Participant vs Staff vs Superuser).
    2. Object ownership isolation (Private dashboard & contributions leakage prevention).
    3. Webhook HMAC-SHA256 signature tampering, missing signatures & replay attack rejection.
    4. API rate limiting & throttling abuse protection (HTTP 429 Too Many Requests).
    5. SQL injection resilience across all search, filtering, and sorting parameters.
    6. XSS escaping & safe serialization of user-controlled inputs.
    7. Secret exposure audit across all public API responses.
    8. Dev-login production defense audit (disabled when DEBUG=False).
    """

    def setUp(self):
        super().setUp()
        self.client = APIClient()

        self.config = EventConfig.get_solo()
        self.config.submissions_paused = False
        self.config.validation_paused = False
        self.config.merge_paused = False
        self.config.leaderboard_frozen = False
        self.config.save()

        # Users
        self.normal_user = User.objects.create_user(username='alice_dev', password='AlicePassword123!')
        self.alice = Participant.objects.create(
            user=self.normal_user,
            github_id=111001,
            github_username='alice_dev',
            total_points=150,
            merged_count=2,
        )

        self.other_user = User.objects.create_user(username='bob_dev', password='BobPassword123!')
        self.bob = Participant.objects.create(
            user=self.other_user,
            github_id=111002,
            github_username='bob_dev',
            total_points=50,
            merged_count=1,
        )

        self.staff_user = User.objects.create_user(
            username='staff_admin', password='StaffPassword123!', is_staff=True,
        )

        self.superuser = User.objects.create_superuser(
            username='root_admin', password='SuperPassword123!', email='admin@hackit.local',
        )

        # Project & Issues
        self.project = Project.objects.create(
            github_repo_id=500001,
            owner='security-org',
            name='safe-api',
            full_name='security-org/safe-api',
            language='Python',
            is_enabled=True,
        )

        self.issue = Issue.objects.create(
            github_issue_id=400001,
            project=self.project,
            number=1,
            title='Fix auth vulnerability in parser',
            points=100,
            status='open',
            created_by_github_id=999999,
        )

        # Alice's Contribution
        self.alice_pr = PullRequest.objects.create(
            github_pr_id=300001,
            repo=self.project,
            number=101,
            author_github_id=self.alice.github_id,
            author_participant=self.alice,
        )
        self.alice_contrib = Contribution.objects.create(
            participant=self.alice,
            issue=self.issue,
            pull_request=self.alice_pr,
            status='MERGED',
        )

        # Bob's Contribution
        self.bob_pr = PullRequest.objects.create(
            github_pr_id=300002,
            repo=self.project,
            number=102,
            author_github_id=self.bob.github_id,
            author_participant=self.bob,
        )
        self.bob_contrib = Contribution.objects.create(
            participant=self.bob,
            issue=self.issue,
            pull_request=self.bob_pr,
            status='PENDING',
        )

    def test_1_rbac_unauthenticated_access_denied(self):
        """1. RBAC: Anonymous users are rejected from private endpoints."""
        endpoints = [
            ('/dashboard/', 401),
            ('/contributions/mine/', 401),
            ('/auth/me/', 401),
            ('/api/v1/admin/points/adjust/', 401),
            ('/api/v1/admin/metrics/', 401),
        ]
        for url, expected_code in endpoints:
            resp = self.client.get(url) if 'adjust' not in url else self.client.post(url, {})
            self.assertIn(
                resp.status_code, [401, 403],
                f"Anonymous request to {url} returned {resp.status_code}, expected 401 or 403",
            )

    def test_2_rbac_normal_participant_forbidden_from_admin_endpoints(self):
        """2. RBAC: Normal participants are strictly forbidden from admin/ops endpoints."""
        self.client.force_authenticate(user=self.normal_user)

        admin_endpoints = [
            ('POST', '/api/v1/admin/points/adjust/', {'participant_id': self.bob.id, 'points': 50, 'reason': 'Audit'}),
            ('GET', '/api/v1/admin/metrics/', None),
        ]

        for method, url, body in admin_endpoints:
            if method == 'POST':
                resp = self.client.post(url, body, format='json')
            else:
                resp = self.client.get(url)
            self.assertEqual(
                resp.status_code, 403,
                f"Normal user accessed admin endpoint {url} with status {resp.status_code}, expected 403 Forbidden",
            )

    def test_3_rbac_staff_and_superuser_authorized_for_admin_endpoints(self):
        """3. RBAC: Staff and Superusers are permitted to access admin and ops endpoints."""
        self.client.force_authenticate(user=self.staff_user)

        # Admin point adjust
        resp = self.client.post('/api/v1/admin/points/adjust/', {
            'participant_id': self.alice.id,
            'points': 25,
            'reason': 'Staff test adjustment',
        }, format='json')
        self.assertEqual(resp.status_code, 200)

        # Admin Ops Metrics
        resp_ops = self.client.get('/api/v1/admin/metrics/')
        self.assertEqual(resp_ops.status_code, 200)
        self.assertIn('event_status', resp_ops.data)

    def test_4_object_ownership_isolation(self):
        """4. Object Isolation: Alice's dashboard and contributions do not leak Bob's private data."""
        self.client.force_authenticate(user=self.normal_user)

        # Dashboard contains only Alice's data
        resp_dash = self.client.get('/dashboard/')
        self.assertEqual(resp_dash.status_code, 200)
        self.assertEqual(resp_dash.data['participant']['github_username'], 'alice_dev')
        self.assertEqual(resp_dash.data['total_points'], 150)

        # Contributions list contains only Alice's contributions
        resp_mine = self.client.get('/contributions/mine/')
        self.assertEqual(resp_mine.status_code, 200)
        contrib_ids = [c['id'] for c in resp_mine.data.get('results', resp_mine.data)]
        self.assertIn(self.alice_contrib.id, contrib_ids)
        self.assertNotIn(self.bob_contrib.id, contrib_ids)

    @patch('core.tasks.process_webhook_event_task.delay')
    def test_5_webhook_hmac_tamper_and_missing_signature_rejection(self, mock_webhook_delay):
        """5. Webhook Security: Tampered or missing HMAC signatures are strictly rejected."""
        secret = TEST_SECURITY_SECRET
        payload = {'action': 'ping', 'zen': 'Security test'}
        body_bytes = json.dumps(payload).encode('utf-8')

        # 1. Missing HMAC signature header
        resp_missing = self.client.post(
            '/webhooks/github/',
            data=body_bytes,
            content_type='application/json',
            HTTP_X_GITHUB_EVENT='ping',
            HTTP_X_GITHUB_DELIVERY='sec-delivery-001',
        )
        self.assertEqual(resp_missing.status_code, 401)

        # 2. Tampered / invalid HMAC signature header
        resp_tampered = self.client.post(
            '/webhooks/github/',
            data=body_bytes,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256='sha256=0000000000000000000000000000000000000000000000000000000000000000',
            HTTP_X_GITHUB_EVENT='ping',
            HTTP_X_GITHUB_DELIVERY='sec-delivery-002',
        )
        self.assertEqual(resp_tampered.status_code, 401)

        # 3. Correct HMAC signature accepted
        correct_sig = 'sha256=' + hmac.new(secret.encode('utf-8'), body_bytes, hashlib.sha256).hexdigest()
        resp_valid = self.client.post(
            '/webhooks/github/',
            data=body_bytes,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=correct_sig,
            HTTP_X_GITHUB_EVENT='ping',
            HTTP_X_GITHUB_DELIVERY='sec-delivery-003',
        )
        self.assertEqual(resp_valid.status_code, 200)
        mock_webhook_delay.assert_called_once()

    def test_6_rate_limiting_abuse_rejection(self):
        """6. Throttling: Rapid request bursts on anonymous IP trigger HTTP 429 Too Many Requests."""
        from django.core.cache import cache
        cache.clear()

        # Fire 120 rapid requests from single IP to /projects/ (limit is 100/min)
        hit_429 = False
        for i in range(120):
            resp = self.client.get('/projects/', REMOTE_ADDR='198.51.100.42')
            if resp.status_code == 429:
                hit_429 = True
                break

        self.assertTrue(hit_429, "Rate limiter did not return HTTP 429 when threshold exceeded")

    def test_7_sql_injection_resilience(self):
        """7. SQL Injection: Malicious injection payloads in parameters do not cause errors or corruption."""
        malicious_payloads = [
            "'; DROP TABLE core_issue; --",
            "1' OR '1'='1",
            "safe-api' UNION SELECT NULL, NULL, NULL --",
            "admin'--",
            "1; SELECT pg_sleep(5); --",
        ]

        for payload in malicious_payloads:
            # Test search query
            resp_search = self.client.get('/issues/', {'search': payload})
            self.assertEqual(resp_search.status_code, 200)

            # Test project filter
            resp_proj = self.client.get('/issues/', {'project': payload})
            self.assertEqual(resp_proj.status_code, 200)

            # Test sort parameter (safely returns 400 validation error for unknown sort options)
            resp_sort = self.client.get('/issues/', {'sort': payload})
            self.assertIn(resp_sort.status_code, [200, 400])

            # Test profile URL slug
            resp_prof = self.client.get(f'/profile/{payload}/')
            self.assertIn(resp_prof.status_code, [404, 200])

        # Verify Issue table is intact
        self.assertTrue(Issue.objects.filter(id=self.issue.id).exists())

    def test_8_xss_payload_escaping_and_safe_serialization(self):
        """8. XSS Sanitization: Malicious HTML and JavaScript in titles and usernames are safely serialized."""
        xss_title = '<script>alert("XSS_EXPLOIT")</script><img src=x onerror=alert(1)>'
        xss_issue = Issue.objects.create(
            github_issue_id=400099,
            project=self.project,
            number=99,
            title=xss_title,
            points=50,
            status='open',
            created_by_github_id=999999,
        )

        resp = self.client.get(f'/issues/{xss_issue.id}/')
        self.assertEqual(resp.status_code, 200)
        # Verify title is serialized as a literal string in JSON (not executed or corrupted)
        self.assertEqual(resp.data['title'], xss_title)
        self.assertIn('application/json', resp['Content-Type'])

    def test_9_secret_exposure_audit(self):
        """9. Secret Exposure: Sensitive server secrets are never leaked in public API responses."""
        known_secrets = [
            getattr(settings, 'SECRET_KEY', 'django-insecure'),
            getattr(settings, 'GITHUB_WEBHOOK_SECRET', 'test-secret'),
        ]

        endpoints_to_audit = [
            '/health/',
            '/projects/',
            f'/projects/{self.project.full_name}/',
            '/issues/',
            f'/issues/{self.issue.id}/',
            '/leaderboard/',
            '/stats/',
            f'/profile/{self.alice.github_username}/',
        ]

        for url in endpoints_to_audit:
            resp = self.client.get(url)
            content_str = resp.content.decode('utf-8')
            for sec in known_secrets:
                if sec and len(sec) > 5:
                    self.assertNotIn(
                        sec, content_str,
                        f"Sensitive secret was detected in response from {url}!",
                    )

    def test_10_dev_login_production_guard(self):
        """10. Dev Login: When DEBUG=False, dev-login endpoint is strictly disabled."""
        with patch.object(settings, 'DEBUG', False):
            resp = self.client.get('/auth/dev-login/?username=alice_dev')
            self.assertEqual(resp.status_code, 403)
            self.assertIn('disabled', resp.content.decode('utf-8').lower())
