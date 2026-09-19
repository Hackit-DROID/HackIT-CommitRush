import json
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from core.models import (
    AuditLog,
    Contribution,
    EventConfig,
    Issue,
    Participant,
    PointTransaction,
    Project,
    PullRequest,
)

User = get_user_model()


class AdminAPISecurityTestCase(TestCase):
    """
    Authoritative test suite verifying server-side authorization, authentication,
    strict input validation, state mutation integrity, and audit logging for the
    internal administrator API layer.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # 1. Administrator / Staff User
        self.admin_user = User.objects.create_user(
            username='admin_staff',
            email='admin@commitrush.io',
            password='secure_admin_password_123',
            is_staff=True,
            is_superuser=False,
        )

        # 2. Regular Authenticated Non-Admin Participant User
        self.participant_user = User.objects.create_user(
            username='regular_participant',
            email='participant@commitrush.io',
            password='participant_password_123',
            is_staff=False,
            is_superuser=False,
        )
        self.participant = Participant.objects.create(
            user=self.participant_user,
            github_id=987654,
            github_username='regular_participant',
            avatar_url='https://avatars.githubusercontent.com/u/987654',
            total_points=200,
            merged_count=2,
            is_suspended=False,
        )

        # 3. Another participant for moderation tests
        self.target_user = User.objects.create_user(
            username='target_participant',
            email='target@commitrush.io',
            password='target_password_123',
            is_staff=False,
        )
        self.target_participant = Participant.objects.create(
            user=self.target_user,
            github_id=112233,
            github_username='target_participant',
            avatar_url=None,
            total_points=100,
            merged_count=1,
            is_suspended=False,
        )

        # 4. Project & Issue
        self.project = Project.objects.create(
            github_repo_id=1354659372,
            owner='Hackit-DROID',
            name='Open-Source-Contribution-Drive',
            full_name='Hackit-DROID/Open-Source-Contribution-Drive',
            language='Python',
            is_enabled=True,
        )
        self.issue = Issue.objects.create(
            github_issue_id=456789,
            project=self.project,
            number=42,
            title='Sample contribution issue',
            points=50,
            difficulty='beginner',
            category='backend',
            status='open',
            is_featured=False,
        )

        # 5. Base EventConfig
        self.config = EventConfig.get_solo()
        self.config.merge_concurrency = 5
        self.config.merge_paused = False
        self.config.validation_paused = False
        self.config.submissions_paused = False
        self.config.leaderboard_frozen = False
        self.config.event_status = 'active'
        self.config.save()

    def tearDown(self):
        cache.clear()

    # =========================================================================
    # 1. System Controls & Circuit Breakers (/api/v1/admin/controls/)
    # =========================================================================

    def test_controls_get_unauthenticated_returns_401(self):
        response = self.client.get('/api/v1/admin/controls/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_controls_get_non_admin_returns_403(self):
        self.client.force_authenticate(user=self.participant_user)
        response = self.client.get('/api/v1/admin/controls/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_controls_get_admin_returns_200(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/api/v1/admin/controls/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['event_status'], 'active')
        self.assertEqual(response.data['merge_concurrency'], 5)
        self.assertFalse(response.data['merge_paused'])
        self.assertFalse(response.data['leaderboard_frozen'])

    def test_controls_patch_non_admin_returns_403(self):
        self.client.force_authenticate(user=self.participant_user)
        response = self.client.patch(
            '/api/v1/admin/controls/',
            {'merge_paused': True},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.config.refresh_from_db()
        self.assertFalse(self.config.merge_paused)

    def test_controls_patch_invalid_payload_returns_400(self):
        self.client.force_authenticate(user=self.admin_user)
        # Concurrency out of bounds
        response = self.client.patch(
            '/api/v1/admin/controls/',
            {'merge_concurrency': 0},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('merge_concurrency', response.data)

        # Invalid event status
        response = self.client.patch(
            '/api/v1/admin/controls/',
            {'event_status': 'non_existent_status'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('event_status', response.data)

    def test_controls_patch_valid_updates_state_and_logs_audit(self):
        self.client.force_authenticate(user=self.admin_user)
        payload = {
            'merge_paused': True,
            'leaderboard_frozen': True,
            'merge_concurrency': 12,
            'event_status': 'paused',
            'reason': 'Emergency investigation of merge worker latency',
        }
        response = self.client.patch('/api/v1/admin/controls/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['merge_paused'])
        self.assertTrue(response.data['leaderboard_frozen'])
        self.assertEqual(response.data['merge_concurrency'], 12)
        self.assertEqual(response.data['event_status'], 'paused')

        # Verify DB mutation
        self.config.refresh_from_db()
        self.assertTrue(self.config.merge_paused)
        self.assertTrue(self.config.leaderboard_frozen)
        self.assertEqual(self.config.merge_concurrency, 12)
        self.assertEqual(self.config.event_status, 'paused')

        # Verify AuditLog creation
        audit_entry = AuditLog.objects.filter(
            actor=self.admin_user,
            action='admin_update_system_controls',
            target_type='EventConfig',
        ).latest('created_at')
        self.assertIsNotNone(audit_entry)
        self.assertEqual(audit_entry.details['reason'], 'Emergency investigation of merge worker latency')
        self.assertTrue(audit_entry.details['updated']['merge_paused'])
        self.assertEqual(audit_entry.details['updated']['merge_concurrency'], 12)

    # =========================================================================
    # 2. Operational Metrics (/api/v1/admin/metrics/)
    # =========================================================================

    def test_metrics_unauthenticated_returns_401(self):
        response = self.client.get('/api/v1/admin/metrics/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_metrics_non_admin_returns_403(self):
        self.client.force_authenticate(user=self.participant_user)
        response = self.client.get('/api/v1/admin/metrics/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_metrics_admin_returns_200(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/api/v1/admin/metrics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('event_status', response.data)
        self.assertIn('system_status', response.data)
        self.assertIn('queues', response.data)
        self.assertIn('semaphore', response.data)
        self.assertEqual(response.data['semaphore']['configured_concurrency'], 5)

    def test_old_public_ops_metrics_removed(self):
        # /ops/metrics/ and /api/v1/ops/metrics/ are completely removed from the URL tree
        response_root = self.client.get('/ops/metrics/')
        self.assertEqual(response_root.status_code, status.HTTP_404_NOT_FOUND)
        response_api = self.client.get('/api/v1/ops/metrics/')
        self.assertEqual(response_api.status_code, status.HTTP_404_NOT_FOUND)

    # =========================================================================
    # 3. GitHub Sync Trigger (/api/v1/admin/github/sync/)
    # =========================================================================

    def test_github_sync_unauthenticated_returns_401(self):
        response = self.client.post('/api/v1/admin/github/sync/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_github_sync_non_admin_returns_403(self):
        self.client.force_authenticate(user=self.participant_user)
        response = self.client.post('/api/v1/admin/github/sync/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_github_sync_invalid_repo_format_returns_400(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            '/api/v1/admin/github/sync/',
            {'repo': 'invalid-repo-format-no-slash'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('repo', response.data)

    @patch('core.api_views.sync_repository_and_issues')
    def test_github_sync_admin_synchronous_success(self, mock_sync):
        mock_sync.return_value = (self.project, False, 2, 1)

        self.client.force_authenticate(user=self.admin_user)
        payload = {
            'repo': 'Hackit-DROID/Open-Source-Contribution-Drive',
            'sync_issues': True,
            'async_mode': False,
            'reason': 'Manual sync for newly added issue #43',
        }
        response = self.client.post('/api/v1/admin/github/sync/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'completed')
        self.assertEqual(response.data['issues_created'], 2)
        self.assertEqual(response.data['issues_updated'], 1)

        # Verify audit log
        audit = AuditLog.objects.filter(
            actor=self.admin_user,
            action='admin_github_sync_completed',
        ).latest('created_at')
        self.assertEqual(audit.details['issues_created'], 2)
        self.assertEqual(audit.details['reason'], 'Manual sync for newly added issue #43')

    @patch('core.api_views.sync_repository_and_issues')
    def test_github_sync_debounce_prevents_stampede(self, mock_sync):
        # Pre-seed lock in cache simulating recent sync
        lock_key = 'commitrush:lock:admin_sync:Hackit-DROID/Open-Source-Contribution-Drive'
        cache.set(lock_key, 999, timeout=30)

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            '/api/v1/admin/github/sync/',
            {'repo': 'Hackit-DROID/Open-Source-Contribution-Drive'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data['status'], 'conflict')
        mock_sync.assert_not_called()

    # =========================================================================
    # 4. Issue Management (/api/v1/admin/issues/, /api/v1/admin/issues/<pk>/)
    # =========================================================================

    def test_admin_issue_list_unauthenticated_returns_401(self):
        response = self.client.get('/api/v1/admin/issues/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_issue_list_non_admin_returns_403(self):
        self.client.force_authenticate(user=self.participant_user)
        response = self.client.get('/api/v1/admin/issues/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_issue_list_admin_returns_200(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/api/v1/admin/issues/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.issue.id)

    def test_admin_issue_detail_get_admin_returns_200(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(f'/api/v1/admin/issues/{self.issue.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['number'], 42)
        self.assertEqual(response.data['points'], 50)

    def test_admin_issue_patch_non_admin_returns_403(self):
        self.client.force_authenticate(user=self.participant_user)
        response = self.client.patch(
            f'/api/v1/admin/issues/{self.issue.id}/',
            {'points': 200},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.points, 50)

    def test_admin_issue_patch_disallows_mass_assignment_of_immutable_fields(self):
        self.client.force_authenticate(user=self.admin_user)
        # Attempting to overwrite immutable GitHub identifiers
        payload = {
            'github_issue_id': 9999999,
            'number': 999,
            'project': 999,
        }
        response = self.client.patch(
            f'/api/v1/admin/issues/{self.issue.id}/',
            payload,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.github_issue_id, 456789)
        self.assertEqual(self.issue.number, 42)

    def test_admin_issue_patch_valid_update_and_audit_logging(self):
        self.client.force_authenticate(user=self.admin_user)
        payload = {
            'points': 150,
            'difficulty': 'advanced',
            'category': 'frontend',
            'is_featured': True,
            'status': 'open',
            'reason': 'Adjusted difficulty and points based on issue scope reassessment',
        }
        response = self.client.patch(
            f'/api/v1/admin/issues/{self.issue.id}/',
            payload,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['points'], 150)
        self.assertEqual(response.data['difficulty'], 'advanced')
        self.assertTrue(response.data['is_featured'])

        # Check DB
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.points, 150)
        self.assertEqual(self.issue.difficulty, 'advanced')
        self.assertEqual(self.issue.category, 'frontend')
        self.assertTrue(self.issue.is_featured)

        # Verify AuditLog
        audit = AuditLog.objects.filter(
            actor=self.admin_user,
            action='admin_update_issue_metadata',
            target_type='Issue',
            target_id=str(self.issue.id),
        ).latest('created_at')
        self.assertEqual(audit.details['previous']['points'], 50)
        self.assertEqual(audit.details['updated']['points'], 150)
        self.assertEqual(audit.details['reason'], 'Adjusted difficulty and points based on issue scope reassessment')

    # =========================================================================
    # 5. Participant Moderation (/api/v1/admin/participants/<pk>/suspend/)
    # =========================================================================

    def test_participant_suspend_unauthenticated_returns_401(self):
        response = self.client.post(
            f'/api/v1/admin/participants/{self.target_participant.id}/suspend/',
            {'is_suspended': True, 'reason': 'Test'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_participant_suspend_non_admin_returns_403(self):
        self.client.force_authenticate(user=self.participant_user)
        response = self.client.post(
            f'/api/v1/admin/participants/{self.target_participant.id}/suspend/',
            {'is_suspended': True, 'reason': 'Malicious behavior'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.target_participant.refresh_from_db()
        self.assertFalse(self.target_participant.is_suspended)

    def test_participant_suspend_requires_reason(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            f'/api/v1/admin/participants/{self.target_participant.id}/suspend/',
            {'is_suspended': True, 'reason': '  '},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('reason', response.data)

    def test_participant_suspend_and_reinstate_success(self):
        self.client.force_authenticate(user=self.admin_user)

        # 1. Suspend
        suspend_response = self.client.post(
            f'/api/v1/admin/participants/{self.target_participant.id}/suspend/',
            {'is_suspended': True, 'reason': 'Automated PR spamming detected'},
            format='json',
        )
        self.assertEqual(suspend_response.status_code, status.HTTP_200_OK)
        self.assertTrue(suspend_response.data['is_suspended'])
        self.target_participant.refresh_from_db()
        self.assertTrue(self.target_participant.is_suspended)

        # AuditLog for suspend
        audit_suspend = AuditLog.objects.filter(
            actor=self.admin_user,
            action='admin_suspend_participant',
            target_id=str(self.target_participant.id),
        ).latest('created_at')
        self.assertEqual(audit_suspend.details['reason'], 'Automated PR spamming detected')

        # 2. Reinstate
        reinstate_response = self.client.post(
            f'/api/v1/admin/participants/{self.target_participant.id}/suspend/',
            {'is_suspended': False, 'reason': 'Appeal approved by organizers'},
            format='json',
        )
        self.assertEqual(reinstate_response.status_code, status.HTTP_200_OK)
        self.assertFalse(reinstate_response.data['is_suspended'])
        self.target_participant.refresh_from_db()
        self.assertFalse(self.target_participant.is_suspended)

        # AuditLog for reinstate
        audit_reinstate = AuditLog.objects.filter(
            actor=self.admin_user,
            action='admin_reinstate_participant',
            target_id=str(self.target_participant.id),
        ).latest('created_at')
        self.assertEqual(audit_reinstate.details['reason'], 'Appeal approved by organizers')

    def test_participant_detail_get_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(f'/api/v1/admin/participants/{self.target_participant.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['github_username'], 'target_participant')
        self.assertEqual(response.data['total_points'], 100)

    # =========================================================================
    # 6. Manual Point Adjustment (/api/v1/admin/points/adjust/)
    # =========================================================================

    def test_point_adjustment_unauthenticated_returns_401(self):
        response = self.client.post(
            '/api/v1/admin/points/adjust/',
            {'participant_id': self.target_participant.id, 'points': 50, 'reason': 'Bonus'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_point_adjustment_non_admin_returns_403(self):
        self.client.force_authenticate(user=self.participant_user)
        response = self.client.post(
            '/api/v1/admin/points/adjust/',
            {'participant_id': self.target_participant.id, 'points': 50, 'reason': 'Bonus'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_point_adjustment_negative_balance_prevention_returns_400(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            '/api/v1/admin/points/adjust/',
            {
                'participant_id': self.target_participant.id,
                'points': -200,  # Current balance is 100, would result in -100
                'reason': 'Over-deduction attempt',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.target_participant.refresh_from_db()
        self.assertEqual(self.target_participant.total_points, 100)

    def test_point_adjustment_valid_success(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            '/api/v1/admin/points/adjust/',
            {
                'participant_id': self.target_participant.id,
                'points': 75,
                'reason': 'Special prize awarded for excellent documentation PR',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['new_points'], 175)
        self.target_participant.refresh_from_db()
        self.assertEqual(self.target_participant.total_points, 175)

        # Ledger check
        pt = PointTransaction.objects.get(id=response.data['transaction_id'])
        self.assertEqual(pt.status, 'ADMIN_ADJUST')
        self.assertEqual(pt.points, 75)

        # Audit check
        audit = AuditLog.objects.filter(
            actor=self.admin_user,
            action='admin_point_adjustment',
        ).latest('created_at')
        self.assertEqual(audit.details['new_points'], 175)

    # =========================================================================
    # 7. Audit Log Inspection (/api/v1/admin/audit-logs/)
    # =========================================================================

    def test_audit_logs_unauthenticated_returns_401(self):
        response = self.client.get('/api/v1/admin/audit-logs/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_audit_logs_non_admin_returns_403(self):
        self.client.force_authenticate(user=self.participant_user)
        response = self.client.get('/api/v1/admin/audit-logs/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_audit_logs_admin_returns_200(self):
        # Create a test audit log
        AuditLog.objects.create(
            actor=self.admin_user,
            action='test_audit_action',
            target_type='System',
            target_id='1',
            details={'message': 'audit test'},
        )
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/api/v1/admin/audit-logs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['action'], 'test_audit_action')

    # =========================================================================
    # 8. Data Security, Isolation & Information Leakage Prevention
    # =========================================================================

    def test_public_profile_does_not_leak_sensitive_data(self):
        """Public profile exposes safe aggregates only; no emails, internal flags, or tokens."""
        response = self.client.get(f'/api/v1/profile/{self.participant.github_username}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('email', response.data)
        self.assertNotIn('user_id', response.data)
        self.assertNotIn('is_staff', response.data)
        self.assertNotIn('is_superuser', response.data)
        self.assertNotIn('token', response.data)
        self.assertIn('github_username', response.data)
        self.assertIn('total_points', response.data)
        self.assertIn('rank', response.data)

    def test_participant_cannot_access_other_participant_contribution_detail(self):
        """Participant A cannot view Contribution owned by Participant B."""
        pr = PullRequest.objects.create(
            github_pr_id=990011,
            repo=self.project,
            number=99,
            author_github_id=self.target_participant.github_id,
            author_participant=self.target_participant,
        )
        target_contrib = Contribution.objects.create(
            participant=self.target_participant,
            issue=self.issue,
            pull_request=pr,
            status='UNDER_REVIEW',
        )

        # Authenticate as regular participant (not owner, not staff)
        self.client.force_authenticate(user=self.participant_user)
        response = self.client.get(f'/api/v1/contributions/{target_contrib.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Staff can view
        self.client.force_authenticate(user=self.admin_user)
        response_staff = self.client.get(f'/api/v1/contributions/{target_contrib.id}/')
        self.assertEqual(response_staff.status_code, status.HTTP_200_OK)

    def test_all_admin_endpoints_reject_regular_participant_with_403(self):
        """Matrix test ensuring no admin endpoint is reachable by non-admin participants."""
        self.client.force_authenticate(user=self.participant_user)
        admin_routes = [
            ('GET', '/api/v1/admin/controls/'),
            ('PATCH', '/api/v1/admin/controls/'),
            ('GET', '/api/v1/admin/metrics/'),
            ('POST', '/api/v1/admin/github/sync/'),
            ('GET', '/api/v1/admin/issues/'),
            ('GET', f'/api/v1/admin/issues/{self.issue.id}/'),
            ('PATCH', f'/api/v1/admin/issues/{self.issue.id}/'),
            ('GET', f'/api/v1/admin/participants/{self.target_participant.id}/'),
            ('POST', f'/api/v1/admin/participants/{self.target_participant.id}/suspend/'),
            ('POST', '/api/v1/admin/points/adjust/'),
            ('GET', '/api/v1/admin/audit-logs/'),
        ]

        for method, url in admin_routes:
            if method == 'GET':
                resp = self.client.get(url)
            elif method == 'PATCH':
                resp = self.client.patch(url, {}, format='json')
            elif method == 'POST':
                resp = self.client.post(url, {}, format='json')
            self.assertEqual(
                resp.status_code,
                status.HTTP_403_FORBIDDEN,
                f"Expected 403 Forbidden for participant on {method} {url}, got {resp.status_code}",
            )

    def test_client_supplied_roles_cannot_grant_admin_privileges(self):
        """Forged client headers or body fields cannot grant administrative privileges."""
        self.client.force_authenticate(user=self.participant_user)
        # Attempt header forgery
        resp = self.client.get(
            '/api/v1/admin/controls/',
            HTTP_X_ROLE='admin',
            HTTP_IS_STAFF='true',
            HTTP_IS_SUPERUSER='1',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # Attempt body role parameter tampering
        resp_patch = self.client.patch(
            '/api/v1/admin/controls/',
            {'is_staff': True, 'is_superuser': True, 'emergency_pause': True},
            format='json',
            HTTP_X_ADMIN='true',
        )
        self.assertEqual(resp_patch.status_code, status.HTTP_403_FORBIDDEN)

    def test_client_supplied_user_id_cannot_impersonate_in_dashboard(self):
        """Client-supplied user IDs or participant IDs cannot impersonate another user."""
        self.client.force_authenticate(user=self.participant_user)
        # Attempt to impersonate target participant via query parameters
        resp = self.client.get(
            f'/api/v1/dashboard/?user_id={self.target_user.id}&participant_id={self.target_participant.id}'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Verify returned data is STRICTLY the authenticated participant's data
        self.assertEqual(resp.data['participant']['github_username'], self.participant.github_username)
        self.assertNotEqual(resp.data['participant']['github_username'], self.target_participant.github_username)

    def test_logout_invalidates_administrative_access(self):
        """Logging out immediately revokes administrative API access."""
        from django.test import Client as DjangoClient
        session_client = DjangoClient()
        # Log in as admin
        session_client.force_login(self.admin_user)
        resp_admin = session_client.get('/api/v1/admin/controls/')
        self.assertEqual(resp_admin.status_code, status.HTTP_200_OK)

        # Log out
        resp_logout = session_client.post('/auth/logout/')
        self.assertEqual(resp_logout.status_code, status.HTTP_200_OK)

        # Subsequent request must be rejected with 401
        resp_after = session_client.get('/api/v1/admin/controls/')
        self.assertEqual(resp_after.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_expired_or_invalid_session_rejected_with_401(self):
        """An invalid or expired session cookie is rejected with 401 Unauthorized."""
        from django.test import Client as DjangoClient
        session_client = DjangoClient()
        session_client.cookies['sessionid'] = 'corrupted-or-expired-session-id'
        resp = session_client.get('/api/v1/admin/controls/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

