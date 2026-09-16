from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, Client
from django.urls import reverse

from core.models import (
    AuditLog,
    EventConfig,
)

User = get_user_model()


class AdminM8T3EventConfigTests(TestCase):
    """
    Test suite for M8-T3: EventConfig Django Admin panel, singleton enforcement,
    runtime configuration updates, emergency control switches, and audit trail (PRD §18, plan.md M8-T3).
    """

    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='staffuser',
            email='staff@hackit.org',
            password='StaffPassword123!',
            is_staff=True,
        )
        self.staff_user.user_permissions.set(Permission.objects.all())

        self.config = EventConfig.get_solo()
        self.config.event_status = 'pending'
        self.config.merge_concurrency = 5
        self.config.max_contributions_per_day = 5
        self.config.max_points_per_day = 500
        self.config.submissions_paused = False
        self.config.validation_paused = False
        self.config.merge_paused = False
        self.config.leaderboard_frozen = False
        self.config.save()

        self.client = Client()

    def test_singleton_permissions_prevent_add_and_delete(self):
        """EventConfig admin disallows add when instance exists and disallows delete."""
        self.client.force_login(self.staff_user)

        # Cannot access add view
        resp_add = self.client.get(reverse('admin:core_eventconfig_add'))
        self.assertNotEqual(resp_add.status_code, 200)

        # Cannot delete
        resp_del = self.client.get(reverse('admin:core_eventconfig_delete', args=[self.config.id]))
        self.assertNotEqual(resp_del.status_code, 200)

    def test_update_runtime_limits_and_audit(self):
        """Admin form updates event limits and merge concurrency with audit logging."""
        self.client.force_login(self.staff_user)

        post_data = {
            'event_status': 'active',
            'merge_concurrency': 8,
            'max_contributions_per_day': 10,
            'max_points_per_day': 1000,
            'submissions_paused': False,
            'validation_paused': False,
            'merge_paused': False,
            'leaderboard_frozen': False,
        }
        resp = self.client.post(
            reverse('admin:core_eventconfig_change', args=[self.config.id]),
            post_data,
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)

        self.config.refresh_from_db()
        self.assertEqual(self.config.event_status, 'active')
        self.assertEqual(self.config.merge_concurrency, 8)
        self.assertEqual(self.config.max_contributions_per_day, 10)
        self.assertEqual(self.config.max_points_per_day, 1000)

        audit = AuditLog.objects.filter(
            action='event_config_updated',
            target_type='EventConfig',
            target_id='1',
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.actor, self.staff_user)
        self.assertIn('merge_concurrency', audit.details.get('changes', {}))
        self.assertEqual(audit.details['changes']['merge_concurrency']['new'], 8)

    def test_toggle_emergency_pause_controls_and_audit(self):
        """Toggling emergency pause controls updates DB immediately and records audit."""
        self.client.force_login(self.staff_user)

        post_data = {
            'event_status': 'active',
            'merge_concurrency': 5,
            'max_contributions_per_day': 5,
            'max_points_per_day': 500,
            'submissions_paused': True,
            'validation_paused': True,
            'merge_paused': True,
            'leaderboard_frozen': True,
        }
        resp = self.client.post(
            reverse('admin:core_eventconfig_change', args=[self.config.id]),
            post_data,
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)

        self.config.refresh_from_db()
        self.assertTrue(self.config.submissions_paused)
        self.assertTrue(self.config.validation_paused)
        self.assertTrue(self.config.merge_paused)
        self.assertTrue(self.config.leaderboard_frozen)
        self.assertIsNotNone(self.config.leaderboard_frozen_at)

        audit = AuditLog.objects.filter(
            action='event_config_updated',
            target_type='EventConfig',
            target_id='1',
        ).first()
        self.assertIsNotNone(audit)
        changes = audit.details.get('changes', {})
        self.assertIn('submissions_paused', changes)
        self.assertIn('validation_paused', changes)
        self.assertIn('merge_paused', changes)
        self.assertIn('leaderboard_frozen', changes)

    def test_validation_rejects_invalid_concurrency_and_negative_limits(self):
        """Form validation enforces merge_concurrency >= 1 and non-negative daily limits."""
        self.client.force_login(self.staff_user)

        # Invalid merge concurrency = 0
        post_data = {
            'event_status': 'active',
            'merge_concurrency': 0,
            'max_contributions_per_day': 5,
            'max_points_per_day': 500,
        }
        resp = self.client.post(reverse('admin:core_eventconfig_change', args=[self.config.id]), post_data)
        self.assertEqual(resp.status_code, 200)
        self.assertFormError(resp.context['adminform'].form, 'merge_concurrency', "Merge concurrency must be at least 1.")

        # Invalid negative max_points_per_day
        post_data['merge_concurrency'] = 5
        post_data['max_points_per_day'] = -100
        resp = self.client.post(reverse('admin:core_eventconfig_change', args=[self.config.id]), post_data)
        self.assertEqual(resp.status_code, 200)
        self.assertFormError(resp.context['adminform'].form, 'max_points_per_day', "Max points per day cannot be negative.")
