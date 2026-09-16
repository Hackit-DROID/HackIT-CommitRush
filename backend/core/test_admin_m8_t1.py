from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

from core.models import (
    AuditLog,
    Issue,
    Participant,
    Project,
)

User = get_user_model()


class AdminM8T1Tests(TestCase):
    """
    Test suite for M8-T1: Participant, Project, and Issue Django Admin customizations (PRD §18, plan.md M8-T1).
    """

    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='superadmin',
            email='admin@hackit.org',
            password='AdminPassword123!',
        )
        self.staff_user = User.objects.create_user(
            username='staffuser',
            email='staff@hackit.org',
            password='StaffPassword123!',
            is_staff=True,
        )
        from django.contrib.auth.models import Permission
        self.staff_user.user_permissions.set(Permission.objects.all())
        self.normal_user = User.objects.create_user(
            username='regularuser',
            email='user@hackit.org',
            password='UserPassword123!',
        )

        self.participant_user = User.objects.create_user(
            username='dev_alice',
            email='alice@example.com',
            password='AlicePassword123!',
        )
        self.participant = Participant.objects.create(
            user=self.participant_user,
            github_id=111222,
            github_username='dev_alice',
            avatar_url='https://avatars.githubusercontent.com/u/111222',
            total_points=150,
            merged_count=2,
            is_suspended=False,
        )

        self.project = Project.objects.create(
            github_repo_id=999888,
            owner='hackit-org',
            name='core-service',
            full_name='hackit-org/core-service',
            language='Python',
            is_enabled=True,
            description='Core service repository',
        )

        self.issue = Issue.objects.create(
            github_issue_id=777666,
            project=self.project,
            number=42,
            title='Add Redis caching to stats endpoint',
            points=100,
            difficulty='intermediate',
            category='backend',
            status='open',
            is_featured=False,
        )

        self.client = Client()

    def test_unauthorized_user_cannot_access_admin(self):
        """Non-staff user cannot access participant/project/issue admin."""
        self.client.force_login(self.normal_user)
        resp = self.client.get(reverse('admin:core_participant_changelist'))
        self.assertNotEqual(resp.status_code, 200)

        resp = self.client.get(reverse('admin:core_project_changelist'))
        self.assertNotEqual(resp.status_code, 200)

        resp = self.client.get(reverse('admin:core_issue_changelist'))
        self.assertNotEqual(resp.status_code, 200)

    def test_staff_can_view_participant_changelist_and_search(self):
        """Staff user can view and search participants."""
        self.client.force_login(self.staff_user)
        resp = self.client.get(reverse('admin:core_participant_changelist') + '?q=dev_alice')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'dev_alice')
        self.assertContains(resp, '150')  # total points

    def test_participant_suspension_and_unsuspension_actions(self):
        """Admin action suspends and unsuspends participant, generating AuditLog records."""
        self.client.force_login(self.staff_user)

        # 1. Suspend
        post_data = {
            'action': 'suspend_participants',
            '_selected_action': [str(self.participant.id)],
        }
        resp = self.client.post(reverse('admin:core_participant_changelist'), post_data, follow=True)
        self.assertEqual(resp.status_code, 200)

        self.participant.refresh_from_db()
        self.assertTrue(self.participant.is_suspended)

        audit_suspend = AuditLog.objects.filter(
            action='participant_suspended',
            target_type='Participant',
            target_id=str(self.participant.id),
        ).first()
        self.assertIsNotNone(audit_suspend)
        self.assertEqual(audit_suspend.actor, self.staff_user)

        # 2. Unsuspend
        post_data['action'] = 'unsuspend_participants'
        resp = self.client.post(reverse('admin:core_participant_changelist'), post_data, follow=True)
        self.assertEqual(resp.status_code, 200)

        self.participant.refresh_from_db()
        self.assertFalse(self.participant.is_suspended)

        audit_unsuspend = AuditLog.objects.filter(
            action='participant_unsuspended',
            target_type='Participant',
            target_id=str(self.participant.id),
        ).first()
        self.assertIsNotNone(audit_unsuspend)
        self.assertEqual(audit_unsuspend.actor, self.staff_user)

    def test_project_enable_and_disable_actions(self):
        """Admin action disables and enables projects with AuditLog generation."""
        self.client.force_login(self.staff_user)

        # Disable
        post_data = {
            'action': 'disable_projects',
            '_selected_action': [str(self.project.id)],
        }
        resp = self.client.post(reverse('admin:core_project_changelist'), post_data, follow=True)
        self.assertEqual(resp.status_code, 200)

        self.project.refresh_from_db()
        self.assertFalse(self.project.is_enabled)

        audit_disable = AuditLog.objects.filter(
            action='project_disabled',
            target_type='Project',
            target_id=str(self.project.id),
        ).first()
        self.assertIsNotNone(audit_disable)
        self.assertEqual(audit_disable.actor, self.staff_user)

        # Enable
        post_data['action'] = 'enable_projects'
        resp = self.client.post(reverse('admin:core_project_changelist'), post_data, follow=True)
        self.assertEqual(resp.status_code, 200)

        self.project.refresh_from_db()
        self.assertTrue(self.project.is_enabled)

        audit_enable = AuditLog.objects.filter(
            action='project_enabled',
            target_type='Project',
            target_id=str(self.project.id),
        ).first()
        self.assertIsNotNone(audit_enable)

    @patch('core.admin.sync_repository_task.delay')
    def test_project_sync_now_enqueues_async_task_without_sync_github_calls(self, mock_sync_delay):
        """Project sync-now action enqueues Celery task asynchronously and logs audit."""
        self.client.force_login(self.staff_user)

        post_data = {
            'action': 'sync_projects_now',
            '_selected_action': [str(self.project.id)],
        }
        resp = self.client.post(reverse('admin:core_project_changelist'), post_data, follow=True)
        self.assertEqual(resp.status_code, 200)

        mock_sync_delay.assert_called_once_with('hackit-org/core-service')

        audit_sync = AuditLog.objects.filter(
            action='project_sync_triggered',
            target_type='Project',
            target_id=str(self.project.id),
        ).first()
        self.assertIsNotNone(audit_sync)
        self.assertEqual(audit_sync.actor, self.staff_user)

    def test_issue_enable_disable_and_mark_invalid_actions(self):
        """Issue actions toggle status correctly and record audit logs."""
        self.client.force_login(self.staff_user)

        # 1. Disable issue
        post_data = {
            'action': 'disable_issues',
            '_selected_action': [str(self.issue.id)],
        }
        resp = self.client.post(reverse('admin:core_issue_changelist'), post_data, follow=True)
        self.assertEqual(resp.status_code, 200)

        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, 'disabled')

        # 2. Enable issue
        post_data['action'] = 'enable_issues'
        resp = self.client.post(reverse('admin:core_issue_changelist'), post_data, follow=True)
        self.assertEqual(resp.status_code, 200)

        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, 'open')

        # 3. Mark as invalid
        post_data['action'] = 'mark_as_invalid'
        resp = self.client.post(reverse('admin:core_issue_changelist'), post_data, follow=True)
        self.assertEqual(resp.status_code, 200)

        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, 'disabled')

        audit_invalid = AuditLog.objects.filter(
            action='issue_marked_invalid',
            target_type='Issue',
            target_id=str(self.issue.id),
        ).first()
        self.assertIsNotNone(audit_invalid)

    def test_issue_feature_and_unfeature_actions(self):
        """Issue feature/unfeature actions update is_featured and log audit."""
        self.client.force_login(self.staff_user)

        # Feature
        post_data = {
            'action': 'feature_issues',
            '_selected_action': [str(self.issue.id)],
        }
        resp = self.client.post(reverse('admin:core_issue_changelist'), post_data, follow=True)
        self.assertEqual(resp.status_code, 200)

        self.issue.refresh_from_db()
        self.assertTrue(self.issue.is_featured)

        # Unfeature
        post_data['action'] = 'unfeature_issues'
        resp = self.client.post(reverse('admin:core_issue_changelist'), post_data, follow=True)
        self.assertEqual(resp.status_code, 200)

        self.issue.refresh_from_db()
        self.assertFalse(self.issue.is_featured)

    def test_issue_customization_in_admin_form_generates_audit_diff(self):
        """Saving customized points/difficulty in Issue admin form records audit diff."""
        self.client.force_login(self.staff_user)

        post_data = {
            'project': self.project.id,
            'number': self.issue.number,
            'title': self.issue.title,
            'points': 200,
            'difficulty': 'advanced',
            'category': 'security',
            'status': 'open',
            'is_featured': True,
        }
        resp = self.client.post(
            reverse('admin:core_issue_change', args=[self.issue.id]),
            post_data,
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)

        self.issue.refresh_from_db()
        self.assertEqual(self.issue.points, 200)
        self.assertEqual(self.issue.difficulty, 'advanced')
        self.assertEqual(self.issue.category, 'security')
        self.assertTrue(self.issue.is_featured)

        audit_custom = AuditLog.objects.filter(
            action='issue_customized',
            target_type='Issue',
            target_id=str(self.issue.id),
        ).first()
        self.assertIsNotNone(audit_custom)
        self.assertIn('points', audit_custom.details.get('changes', {}))
        self.assertEqual(audit_custom.details['changes']['points']['new'], 200)
