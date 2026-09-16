from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from core.models import AuditLog, Participant, PointTransaction

User = get_user_model()


class AdminPointAdjustmentAPITests(TestCase):
    """
    API test suite for M6-T6: Admin Manual Point Adjustments (POST /api/v1/admin/points/adjust/).
    Verifies:
    - Server-side staff authorization gating.
    - Positive and negative point adjustments.
    - Negative balance protection (HTTP 400 rejection).
    - Immutable PointTransaction ledger entry creation (status='ADMIN_ADJUST').
    - AuditLog trail generation with actor and diff details.
    """

    def setUp(self):
        self.client = APIClient()

        # Create staff admin user
        self.staff_user = User.objects.create_user(
            username='admin_user',
            email='admin@hackit.com',
            password='password123',
            is_staff=True,
        )

        # Create regular non-staff user & participant
        self.regular_user = User.objects.create_user(
            username='bob_user',
            email='bob@example.com',
            password='password123',
            is_staff=False,
        )
        self.participant = Participant.objects.create(
            user=self.regular_user,
            github_id=88888,
            github_username='bob',
            total_points=100,
        )

        self.url = '/api/v1/admin/points/adjust/'

    def test_anonymous_user_is_forbidden(self):
        response = self.client.post(self.url, {
            'participant_id': self.participant.id,
            'points': 50,
            'reason': 'Bonus points',
        })
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_non_staff_user_is_forbidden(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.post(self.url, {
            'participant_id': self.participant.id,
            'points': 50,
            'reason': 'Bonus points',
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_user_positive_point_adjustment(self):
        self.client.force_authenticate(user=self.staff_user)
        payload = {
            'participant_id': self.participant.id,
            'points': 75,
            'reason': 'Exceptional code quality bonus',
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['participant_id'], self.participant.id)
        self.assertEqual(data['previous_points'], 100)
        self.assertEqual(data['new_points'], 175)
        self.assertEqual(data['delta'], 75)

        # Verify participant total points updated in DB
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.total_points, 175)

        # Verify PointTransaction ledger entry
        pt = PointTransaction.objects.get(id=data['transaction_id'])
        self.assertEqual(pt.status, 'ADMIN_ADJUST')
        self.assertEqual(pt.points, 75)
        self.assertEqual(pt.reason, 'Exceptional code quality bonus')
        self.assertIsNone(pt.contribution)

        # Verify AuditLog entry
        audit = AuditLog.objects.filter(target_type='Participant', target_id=str(self.participant.id)).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.actor, self.staff_user)
        self.assertEqual(audit.action, 'admin_point_adjustment')
        self.assertEqual(audit.details['previous_points'], 100)
        self.assertEqual(audit.details['new_points'], 175)
        self.assertEqual(audit.details['delta'], 75)

    def test_staff_user_negative_point_adjustment_success(self):
        self.client.force_authenticate(user=self.staff_user)
        payload = {
            'participant_id': self.participant.id,
            'points': -40,
            'reason': 'Penalty for rule violation',
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.participant.refresh_from_db()
        self.assertEqual(self.participant.total_points, 60)

    def test_negative_balance_protection_rejected(self):
        # Current balance is 100. Deducting 150 would yield -50.
        self.client.force_authenticate(user=self.staff_user)
        payload = {
            'participant_id': self.participant.id,
            'points': -150,
            'reason': 'Huge deduction',
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('negative point balance', response.json()['error'])

        # Balance remains unmodified
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.total_points, 100)

    def test_zero_delta_rejected(self):
        self.client.force_authenticate(user=self.staff_user)
        payload = {
            'participant_id': self.participant.id,
            'points': 0,
            'reason': 'Zero points',
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nonexistent_participant_rejected(self):
        self.client.force_authenticate(user=self.staff_user)
        payload = {
            'participant_id': 999999,
            'points': 50,
            'reason': 'Bonus for unknown',
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_reason_rejected(self):
        self.client.force_authenticate(user=self.staff_user)
        payload = {
            'participant_id': self.participant.id,
            'points': 50,
            'reason': '   ',
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
