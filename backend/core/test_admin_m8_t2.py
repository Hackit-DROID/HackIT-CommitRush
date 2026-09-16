from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, Client
from django.urls import reverse

from core.models import (
    AuditLog,
    Contribution,
    DailyContributionUsage,
    Issue,
    Participant,
    PointTransaction,
    Project,
    PullRequest,
)

User = get_user_model()


class AdminM8T2ContributionTests(TestCase):
    """
    Test suite for M8-T2: Contribution Django Admin customizations, state machine actions,
    force-merge idempotency, and audit trail generation (PRD §18, plan.md M8-T2).
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
        self.staff_user.user_permissions.set(Permission.objects.all())

        self.participant_user = User.objects.create_user(
            username='dev_bob',
            email='bob@example.com',
            password='BobPassword123!',
        )
        self.participant = Participant.objects.create(
            user=self.participant_user,
            github_id=333444,
            github_username='dev_bob',
            total_points=0,
            merged_count=0,
            is_suspended=False,
        )

        self.project = Project.objects.create(
            github_repo_id=123123,
            owner='hackit-org',
            name='analytics-engine',
            full_name='hackit-org/analytics-engine',
            language='Python',
            is_enabled=True,
        )

        self.issue = Issue.objects.create(
            github_issue_id=456456,
            project=self.project,
            number=10,
            title='Optimize aggregation queries',
            points=150,
            difficulty='advanced',
            category='database',
            status='open',
        )

        self.pr = PullRequest.objects.create(
            github_pr_id=789789,
            repo=self.project,
            number=101,
            author_github_id=333444,
            author_participant=self.participant,
            merged=False,
        )

        self.client = Client()

    @patch('core.admin.validate_contribution_task.delay')
    def test_retry_action_transitions_and_enqueues_validation(self, mock_validate_task):
        """Admin retry action transitions RETRY contribution to UNDER_REVIEW, enqueues validation, and logs audit."""
        self.client.force_login(self.staff_user)

        contrib = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=self.pr,
            status='RETRY',
            retry_count=1,
        )

        post_data = {
            'action': 'retry_contributions',
            '_selected_action': [str(contrib.id)],
        }
        resp = self.client.post(reverse('admin:core_contribution_changelist'), post_data, follow=True)
        self.assertEqual(resp.status_code, 200)

        contrib.refresh_from_db()
        self.assertEqual(contrib.status, 'UNDER_REVIEW')
        mock_validate_task.assert_called_once_with(contrib.id)

        audit = AuditLog.objects.filter(
            action='admin_retry_contribution',
            target_type='Contribution',
            target_id=str(contrib.id),
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.actor, self.staff_user)

    def test_flag_action_transitions_to_flagged_with_audit(self):
        """Admin flag action transitions active contribution to FLAGGED with audit."""
        self.client.force_login(self.staff_user)

        contrib = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=self.pr,
            status='UNDER_REVIEW',
        )

        post_data = {
            'action': 'flag_contributions',
            '_selected_action': [str(contrib.id)],
        }
        resp = self.client.post(reverse('admin:core_contribution_changelist'), post_data, follow=True)
        self.assertEqual(resp.status_code, 200)

        contrib.refresh_from_db()
        self.assertEqual(contrib.status, 'FLAGGED')

        audit = AuditLog.objects.filter(
            action='admin_flag_contribution',
            target_type='Contribution',
            target_id=str(contrib.id),
        ).first()
        self.assertIsNotNone(audit)

    def test_reject_action_transitions_to_rejected_with_audit(self):
        """Admin reject action transitions non-terminal contribution to REJECTED with audit."""
        self.client.force_login(self.staff_user)

        contrib = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=self.pr,
            status='APPROVED',
        )

        post_data = {
            'action': 'reject_contributions',
            '_selected_action': [str(contrib.id)],
        }
        resp = self.client.post(reverse('admin:core_contribution_changelist'), post_data, follow=True)
        self.assertEqual(resp.status_code, 200)

        contrib.refresh_from_db()
        self.assertEqual(contrib.status, 'REJECTED')

        audit = AuditLog.objects.filter(
            action='admin_reject_contribution',
            target_type='Contribution',
            target_id=str(contrib.id),
        ).first()
        self.assertIsNotNone(audit)

    def test_manually_approve_action_transitions_flagged_to_approved(self):
        """Admin manual approve override transitions FLAGGED contribution to APPROVED with audit."""
        self.client.force_login(self.staff_user)

        contrib = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=self.pr,
            status='FLAGGED',
            flagged_reason='Held for suspicious diff review',
        )

        post_data = {
            'action': 'manually_approve_contributions',
            '_selected_action': [str(contrib.id)],
        }
        resp = self.client.post(reverse('admin:core_contribution_changelist'), post_data, follow=True)
        self.assertEqual(resp.status_code, 200)

        contrib.refresh_from_db()
        self.assertEqual(contrib.status, 'APPROVED')
        self.assertIsNotNone(contrib.approved_at)

        audit = AuditLog.objects.filter(
            action='admin_approve_contribution',
            target_type='Contribution',
            target_id=str(contrib.id),
        ).first()
        self.assertIsNotNone(audit)

    def test_force_merge_action_transitions_to_merged_awards_points_idempotently(self):
        """Force merge transitions to MERGED, awards points safely, and avoids duplicate points on retry."""
        self.client.force_login(self.staff_user)

        contrib = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=self.pr,
            status='APPROVED',
        )

        post_data = {
            'action': 'force_merge_contributions',
            '_selected_action': [str(contrib.id)],
        }

        # First force merge
        resp = self.client.post(reverse('admin:core_contribution_changelist'), post_data, follow=True)
        self.assertEqual(resp.status_code, 200)

        contrib.refresh_from_db()
        self.assertEqual(contrib.status, 'MERGED')
        self.assertIsNotNone(contrib.merged_at)

        self.participant.refresh_from_db()
        self.assertEqual(self.participant.total_points, 150)
        self.assertEqual(self.participant.merged_count, 1)

        # Verify PointTransaction
        pt = PointTransaction.objects.filter(contribution=contrib, status='AWARDED').first()
        self.assertIsNotNone(pt)
        self.assertEqual(pt.points, 150)

        audit = AuditLog.objects.filter(
            action='admin_force_merge',
            target_type='Contribution',
            target_id=str(contrib.id),
        ).first()
        self.assertIsNotNone(audit)

        # Second force merge attempt (must be idempotent: no double awarding)
        resp2 = self.client.post(reverse('admin:core_contribution_changelist'), post_data, follow=True)
        self.assertEqual(resp2.status_code, 200)

        self.participant.refresh_from_db()
        self.assertEqual(self.participant.total_points, 150)  # Still 150, not 300!
        self.assertEqual(self.participant.merged_count, 1)

        pt_count = PointTransaction.objects.filter(contribution=contrib, status='AWARDED').count()
        self.assertEqual(pt_count, 1)

    def test_contribution_change_form_renders_audit_trail(self):
        """Admin change form displays contribution audit history."""
        self.client.force_login(self.staff_user)

        contrib = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=self.pr,
            status='APPROVED',
        )

        AuditLog.objects.create(
            actor=self.staff_user,
            action='admin_approve_contribution',
            target_type='Contribution',
            target_id=str(contrib.id),
            details={'reason': 'Manual verification passed'},
        )

        resp = self.client.get(reverse('admin:core_contribution_change', args=[contrib.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'admin_approve_contribution')
        self.assertContains(resp, 'staffuser')
        self.assertContains(resp, 'Manual verification passed')
