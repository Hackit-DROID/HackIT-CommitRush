from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, Client
from django.urls import reverse

from core.models import AuditLog

User = get_user_model()


class AdminM8T4AuditLogTests(TestCase):
    """
    Test suite for M8-T4: AuditLog Django Admin view, immutability, search, filtering,
    and access control (PRD §18, plan.md M8-T4).
    """

    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='staffuser',
            email='staff@hackit.org',
            password='StaffPassword123!',
            is_staff=True,
        )
        self.staff_user.user_permissions.set(Permission.objects.all())

        self.normal_user = User.objects.create_user(
            username='normaluser',
            email='normal@hackit.org',
            password='NormalPassword123!',
        )

        self.log1 = AuditLog.objects.create(
            actor=self.staff_user,
            action='participant_suspended',
            target_type='Participant',
            target_id='42',
            details={'reason': 'Suspicious bot activity'},
        )
        self.log2 = AuditLog.objects.create(
            actor=None,  # system
            action='webhook_processed',
            target_type='WebhookEvent',
            target_id='100',
            details={'event_type': 'pull_request'},
        )

        self.client = Client()

    def test_unauthorized_user_cannot_view_audit_logs(self):
        """Non-staff user is blocked from viewing AuditLog admin."""
        self.client.force_login(self.normal_user)
        resp = self.client.get(reverse('admin:core_auditlog_changelist'))
        self.assertNotEqual(resp.status_code, 200)

    def test_staff_can_view_audit_changelist_and_search(self):
        """Staff user can view AuditLog changelist and search by actor/action/target."""
        self.client.force_login(self.staff_user)

        # View changelist
        resp = self.client.get(reverse('admin:core_auditlog_changelist'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'participant_suspended')
        self.assertContains(resp, 'webhook_processed')
        self.assertContains(resp, 'System / Automation')

        # Search by actor
        resp_search = self.client.get(reverse('admin:core_auditlog_changelist') + '?q=staffuser')
        self.assertEqual(resp_search.status_code, 200)
        self.assertContains(resp_search, 'participant_suspended')

        # Filter by action
        resp_filter = self.client.get(reverse('admin:core_auditlog_changelist') + '?action=participant_suspended')
        self.assertEqual(resp_filter.status_code, 200)
        results = list(resp_filter.context['cl'].result_list)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].action, 'participant_suspended')

    def test_audit_log_is_strictly_immutable_in_admin(self):
        """AuditLog records cannot be added, edited, or deleted in admin."""
        self.client.force_login(self.staff_user)

        # Add is disallowed
        resp_add = self.client.get(reverse('admin:core_auditlog_add'))
        self.assertNotEqual(resp_add.status_code, 200)

        # Delete is disallowed
        resp_del = self.client.get(reverse('admin:core_auditlog_delete', args=[self.log1.id]))
        self.assertNotEqual(resp_del.status_code, 200)

    def test_audit_log_detail_view_renders_json_context(self):
        """AuditLog change/detail view renders structured JSON metadata."""
        self.client.force_login(self.staff_user)

        resp = self.client.get(reverse('admin:core_auditlog_change', args=[self.log1.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Suspicious bot activity')
        self.assertContains(resp, 'participant_suspended')
