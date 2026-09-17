import datetime
import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase, Client
from django.urls import reverse
from django.utils import timezone

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
from core.points import award_points_for_contribution
from core.state_machine import (
    InvalidStateTransitionError,
    UnauthorizedTransitionError,
    transition_contribution,
)
from core.webhook_processing import process_webhook_event
from core.webhook_views import verify_github_signature

User = get_user_model()


class M9T1PointAwardUnitTests(TestCase):
    """
    M9-T1: Point Award Transaction & Invariant Unit Tests (PRD §14, §15, plan.md M9-T1).
    """

    def setUp(self):
        self.config = EventConfig.get_solo()
        self.config.max_contributions_per_day = 5
        self.config.max_points_per_day = 100
        self.config.save()

        self.user = User.objects.create_user(username='unit_tester', password='pass123Word!')
        self.participant = Participant.objects.create(
            user=self.user,
            github_id=888001,
            github_username='unit_tester',
            total_points=0,
            merged_count=0,
            is_suspended=False,
        )

        self.project = Project.objects.create(
            github_repo_id=999001,
            owner='hackit-unit',
            name='unit-repo',
            full_name='hackit-unit/unit-repo',
            is_enabled=True,
        )

        self.issue_50 = Issue.objects.create(
            github_issue_id=777001,
            project=self.project,
            number=1,
            title='50 Point Issue',
            points=50,
            status='open',
        )
        self.issue_25 = Issue.objects.create(
            github_issue_id=777002,
            project=self.project,
            number=2,
            title='25 Point Issue',
            points=25,
            status='open',
        )

    def _create_merged_contribution(self, issue, pr_num):
        pr = PullRequest.objects.create(
            github_pr_id=pr_num + 50000,
            repo=self.project,
            number=pr_num,
            author_github_id=self.participant.github_id,
            author_participant=self.participant,
            merged=True,
            merged_at=timezone.now(),
        )
        return Contribution.objects.create(
            participant=self.participant,
            issue=issue,
            pull_request=pr,
            status='MERGED',
            merged_at=timezone.now(),
        )

    def test_exact_daily_point_boundary(self):
        """Participant with 50 points can receive exactly 50 more points up to max_points_per_day (100)."""
        c1 = self._create_merged_contribution(self.issue_50, 1)
        res1 = award_points_for_contribution(c1.id)
        self.assertEqual(res1['status'], 'AWARDED')
        self.assertEqual(res1['points'], 50)

        # Second 50-point contribution reaches exact boundary (50 + 50 = 100 == 100)
        c2 = self._create_merged_contribution(self.issue_50, 2)
        res2 = award_points_for_contribution(c2.id)
        self.assertEqual(res2['status'], 'AWARDED')
        self.assertEqual(res2['points'], 50)

        self.participant.refresh_from_db()
        self.assertEqual(self.participant.total_points, 100)
        self.assertEqual(self.participant.merged_count, 2)

    def test_one_above_daily_point_boundary_defers(self):
        """Participant at 100 points attempting to earn 25 more points is DEFERRED (100 + 25 > 100)."""
        c1 = self._create_merged_contribution(self.issue_50, 1)
        c2 = self._create_merged_contribution(self.issue_50, 2)
        award_points_for_contribution(c1.id)
        award_points_for_contribution(c2.id)

        # 3rd contribution exceeds point limit
        c3 = self._create_merged_contribution(self.issue_25, 3)
        res3 = award_points_for_contribution(c3.id)
        self.assertEqual(res3['status'], 'DEFERRED')
        self.assertEqual(res3['points'], 0)
        self.assertIn('Daily limit exceeded', res3['reason'])

        self.participant.refresh_from_db()
        self.assertEqual(self.participant.total_points, 100)  # Preserved

    def test_daily_contribution_count_exact_and_above_boundary(self):
        """Daily contribution count cap enforces strictly at boundary."""
        self.config.max_contributions_per_day = 2
        self.config.max_points_per_day = 1000
        self.config.save()

        c1 = self._create_merged_contribution(self.issue_25, 1)
        c2 = self._create_merged_contribution(self.issue_25, 2)
        c3 = self._create_merged_contribution(self.issue_25, 3)

        res1 = award_points_for_contribution(c1.id)
        res2 = award_points_for_contribution(c2.id)
        res3 = award_points_for_contribution(c3.id)

        self.assertEqual(res1['status'], 'AWARDED')
        self.assertEqual(res2['status'], 'AWARDED')
        self.assertEqual(res3['status'], 'DEFERRED')

        self.participant.refresh_from_db()
        self.assertEqual(self.participant.total_points, 50)

    def test_repeated_award_request_is_idempotent_no_double_points(self):
        """Multiple sequential calls to award_points_for_contribution return ALREADY_AWARDED."""
        c1 = self._create_merged_contribution(self.issue_50, 1)
        res1 = award_points_for_contribution(c1.id)
        self.assertEqual(res1['status'], 'AWARDED')

        for _ in range(3):
            res_repeat = award_points_for_contribution(c1.id)
            self.assertEqual(res_repeat['status'], 'ALREADY_AWARDED')
            self.assertEqual(res_repeat['points'], 50)

        self.participant.refresh_from_db()
        self.assertEqual(self.participant.total_points, 50)
        self.assertEqual(PointTransaction.objects.filter(contribution=c1, status='AWARDED').count(), 1)

    def test_point_transaction_uniqueness_constraint_enforced_by_db(self):
        """Database uniquely constrains AWARDED point transactions per contribution."""
        c1 = self._create_merged_contribution(self.issue_50, 1)
        PointTransaction.objects.create(
            contribution=c1,
            participant=self.participant,
            points=50,
            status='AWARDED',
        )

        with self.assertRaises(IntegrityError):
            PointTransaction.objects.create(
                contribution=c1,
                participant=self.participant,
                points=50,
                status='AWARDED',
            )

    @patch('core.points.DailyContributionUsage.objects.select_for_update')
    def test_transaction_rollback_preserves_atomic_state(self, mock_usage_select):
        """Simulated DB failure during award transaction cleanly rolls back all modifications."""
        mock_usage_select.side_effect = Exception("Simulated database deadlock")
        c1 = self._create_merged_contribution(self.issue_50, 1)

        with self.assertRaises(Exception):
            award_points_for_contribution(c1.id)

        self.participant.refresh_from_db()
        self.assertEqual(self.participant.total_points, 0)
        self.assertEqual(self.participant.merged_count, 0)
        self.assertEqual(PointTransaction.objects.filter(contribution=c1).count(), 0)


class M9T1StateMachineUnitTests(TestCase):
    """
    M9-T1: State Machine Transition Validity & Immutability Unit Tests (PRD §11, §12, plan.md M5-T1, M9-T1).
    """

    def setUp(self):
        self.user = User.objects.create_user(username='state_user', password='password123')
        self.participant = Participant.objects.create(
            user=self.user,
            github_id=888002,
            github_username='state_user',
        )
        self.project = Project.objects.create(
            github_repo_id=999002,
            owner='hackit-unit',
            name='state-repo',
            full_name='hackit-unit/state-repo',
            is_enabled=True,
        )
        self.issue = Issue.objects.create(
            github_issue_id=777003,
            project=self.project,
            number=1,
            title='State test issue',
            points=50,
        )
        self.pr = PullRequest.objects.create(
            github_pr_id=50099,
            repo=self.project,
            number=99,
            author_github_id=self.participant.github_id,
            author_participant=self.participant,
        )

    def _create_contrib(self, status):
        return Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=self.pr,
            status=status,
        )

    def test_canonical_pipeline_transitions_succeed(self):
        """Normal contribution progression: PENDING -> QUEUED -> UNDER_REVIEW -> APPROVED -> MERGING -> MERGED."""
        c = self._create_contrib('PENDING')

        c, _ = transition_contribution(c.id, 'QUEUED')
        self.assertEqual(c.status, 'QUEUED')

        c, _ = transition_contribution(c.id, 'UNDER_REVIEW')
        self.assertEqual(c.status, 'UNDER_REVIEW')
        self.assertIsNotNone(c.locked_at)

        c, _ = transition_contribution(c.id, 'APPROVED')
        self.assertEqual(c.status, 'APPROVED')
        self.assertIsNotNone(c.approved_at)

        c, _ = transition_contribution(c.id, 'MERGING')
        self.assertEqual(c.status, 'MERGING')

        c, _ = transition_contribution(c.id, 'MERGED')
        self.assertEqual(c.status, 'MERGED')
        self.assertIsNotNone(c.merged_at)

    def test_illegal_transitions_raise_error(self):
        """Illegal state jumps are rejected with InvalidStateTransitionError."""
        c = self._create_contrib('PENDING')
        with self.assertRaises(InvalidStateTransitionError):
            transition_contribution(c.id, 'APPROVED')

        with self.assertRaises(InvalidStateTransitionError):
            transition_contribution(c.id, 'MERGING')

    def test_terminal_states_cannot_silently_transition(self):
        """Terminal state MERGED cannot transition without admin override."""
        c = self._create_contrib('MERGED')
        with self.assertRaises(InvalidStateTransitionError):
            transition_contribution(c.id, 'PENDING')

        with self.assertRaises(InvalidStateTransitionError):
            transition_contribution(c.id, 'UNDER_REVIEW')

    def test_unauthorized_admin_transition_raises_error(self):
        """Admin override transitions require actor with staff/superuser privileges."""
        c = self._create_contrib('FLAGGED')
        staff_user = User.objects.create_user(username='admin_boss', is_staff=True)

        with self.assertRaises(UnauthorizedTransitionError):
            transition_contribution(c.id, 'APPROVED', actor=self.user)

        # With staff actor, transition succeeds
        c_approved, _ = transition_contribution(c.id, 'APPROVED', actor=staff_user)
        self.assertEqual(c_approved.status, 'APPROVED')


class M9T1WebhookValidationUnitTests(TestCase):
    """
    M9-T1: Webhook Payload & Signature Validation Unit Tests (PRD §13, plan.md M4-T1, M9-T1).
    """

    def setUp(self):
        self.secret = 'test-webhook-secret-xyz'
        self.client = Client()

    def _calc_sig(self, body_bytes):
        h = hmac.new(self.secret.encode('utf-8'), body_bytes, hashlib.sha256).hexdigest()
        return f"sha256={h}"

    def test_verify_github_signature_valid(self):
        payload = b'{"action": "opened", "number": 1}'
        sig = self._calc_sig(payload)
        self.assertTrue(verify_github_signature(payload, sig, self.secret))

    def test_verify_github_signature_invalid_and_missing(self):
        payload = b'{"action": "opened", "number": 1}'
        invalid_sig = "sha256=0000000000000000000000000000000000000000000000000000000000000000"
        self.assertFalse(verify_github_signature(payload, invalid_sig, self.secret))
        self.assertFalse(verify_github_signature(payload, None, self.secret))
        self.assertFalse(verify_github_signature(payload, "", self.secret))

    @patch('core.tasks.process_webhook_event_task.delay')
    def test_duplicate_webhook_delivery_id_is_idempotent(self, mock_task_delay):
        """Duplicate webhook deliveries return HTTP 200 without duplicate WebhookEvent creation."""
        payload = json.dumps({'action': 'opened', 'repository': {'id': 123}}).encode('utf-8')
        sig = self._calc_sig(payload)

        # First delivery
        with patch('django.conf.settings.GITHUB_WEBHOOK_SECRET', self.secret):
            resp1 = self.client.post(
                reverse('github-webhook'),
                data=payload,
                content_type='application/json',
                HTTP_X_HUB_SIGNATURE_256=sig,
                HTTP_X_GITHUB_EVENT='pull_request',
                HTTP_X_GITHUB_DELIVERY='deliv-m9-test-001',
            )
            self.assertEqual(resp1.status_code, 200)
            self.assertEqual(resp1.json()['status'], 'ok')

            # Second delivery with same delivery ID
            resp2 = self.client.post(
                reverse('github-webhook'),
                data=payload,
                content_type='application/json',
                HTTP_X_HUB_SIGNATURE_256=sig,
                HTTP_X_GITHUB_EVENT='pull_request',
                HTTP_X_GITHUB_DELIVERY='deliv-m9-test-001',
            )
            self.assertEqual(resp2.status_code, 200)
            self.assertEqual(resp2.json()['status'], 'duplicate')

        self.assertEqual(WebhookEvent.objects.filter(delivery_id='deliv-m9-test-001').count(), 1)

    def test_unsupported_webhook_events_do_not_corrupt_state(self):
        """Unsupported webhook events (e.g. star, watch) are handled gracefully without error."""
        event = WebhookEvent.objects.create(
            delivery_id='deliv-m9-star-001',
            event_type='star',
            payload={'action': 'created'},
        )
        res = process_webhook_event(event)
        self.assertEqual(res['status'], 'unhandled')


class M9T1PermissionsUnitTests(TestCase):
    """
    M9-T1: User Permissions, Roles & Object-Level Isolation Unit Tests (PRD §18, plan.md M7, M8, M9-T1).
    """

    def setUp(self):
        self.normal_user = User.objects.create_user(username='participant_bob', password='Password123!')
        self.participant = Participant.objects.create(
            user=self.normal_user,
            github_id=600001,
            github_username='participant_bob',
        )

        self.other_user = User.objects.create_user(username='participant_charlie', password='Password123!')
        self.other_participant = Participant.objects.create(
            user=self.other_user,
            github_id=600002,
            github_username='participant_charlie',
        )

        self.staff_user = User.objects.create_user(username='staff_dan', password='Password123!', is_staff=True)
        self.client = Client()

    def test_anonymous_user_blocked_from_protected_endpoints(self):
        """Anonymous requests to authenticated views return 401/403."""
        resp_dash = self.client.get(reverse('dashboard'))
        self.assertIn(resp_dash.status_code, [401, 403])

        resp_mine = self.client.get(reverse('my-contributions-list'))
        self.assertIn(resp_mine.status_code, [401, 403])

        resp_ops = self.client.get(reverse('ops-metrics'))
        self.assertIn(resp_ops.status_code, [401, 403])

    def test_non_staff_user_blocked_from_admin_and_ops_endpoints(self):
        """Normal participants cannot access Ops metrics or Admin points adjustment."""
        self.client.force_login(self.normal_user)

        resp_ops = self.client.get(reverse('ops-metrics'))
        self.assertEqual(resp_ops.status_code, 403)

        resp_adjust = self.client.post(
            reverse('admin-point-adjust'),
            data={'participant_id': self.participant.id, 'points': 50, 'reason': 'test'},
            content_type='application/json',
        )
        self.assertEqual(resp_adjust.status_code, 403)

    def test_staff_user_granted_access_to_ops_endpoints(self):
        """Staff user receives 200 OK from Ops metrics endpoint."""
        self.client.force_login(self.staff_user)

        resp_ops = self.client.get(reverse('ops-metrics'))
        self.assertEqual(resp_ops.status_code, 200)
