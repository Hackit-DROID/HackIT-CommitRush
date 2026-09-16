from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.models import (
    Contribution,
    Issue,
    Participant,
    Project,
    PullRequest,
)
from core.state_machine import (
    InvalidStateTransitionError,
    UnauthorizedTransitionError,
    evaluate_pre_checks,
    process_pending_contribution,
    transition_contribution,
)

User = get_user_model()


class StateMachineM5TestCase(TestCase):
    """
    Unit & Integration test suite for M5-T1: Contribution State Machine.
    Tests every canonical transition, authorization gating, idempotency,
    sub-status management, pre-checks, and error handling.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='alice', email='alice@example.com')
        self.staff_user = User.objects.create_user(
            username='admin_user',
            email='admin@example.com',
            is_staff=True,
        )
        self.participant = Participant.objects.create(
            user=self.user,
            github_id=12345,
            github_username='alice',
            avatar_url='https://github.com/alice.png',
        )

        self.project = Project.objects.create(
            github_repo_id=1001,
            owner='hackit',
            name='core-engine',
            full_name='hackit/core-engine',
            language='Python',
            is_enabled=True,
        )

        self.issue = Issue.objects.create(
            github_issue_id=2001,
            project=self.project,
            number=42,
            title='Add state machine validator',
            points=100,
            difficulty='intermediate',
            category='backend',
            status='open',
            created_by_github_id=99999,  # Created by someone else
        )

        self.pr = PullRequest.objects.create(
            github_pr_id=3001,
            repo=self.project,
            number=10,
            author_github_id=self.participant.github_id,
            author_participant=self.participant,
            head_sha='abc123def456',
        )

        self.contribution = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=self.pr,
            status='PENDING',
        )

    def test_evaluate_pre_checks_pass(self):
        passed, reason = evaluate_pre_checks(self.contribution)
        self.assertTrue(passed)
        self.assertEqual(reason, "")

    def test_evaluate_pre_checks_disabled_repo(self):
        self.project.is_enabled = False
        self.project.save()
        passed, reason = evaluate_pre_checks(self.contribution)
        self.assertFalse(passed)
        self.assertIn("Repository is disabled", reason)

    def test_evaluate_pre_checks_disabled_issue(self):
        self.issue.status = 'disabled'
        self.issue.save()
        passed, reason = evaluate_pre_checks(self.contribution)
        self.assertFalse(passed)
        self.assertIn("Issue is disabled", reason)

    def test_evaluate_pre_checks_repo_mismatch(self):
        other_project = Project.objects.create(
            github_repo_id=1002,
            owner='hackit',
            name='other-repo',
            full_name='hackit/other-repo',
            language='Go',
            is_enabled=True,
        )
        self.issue.project = other_project
        self.issue.save()
        passed, reason = evaluate_pre_checks(self.contribution)
        self.assertFalse(passed)
        self.assertIn("does not belong to the repository", reason)

    def test_evaluate_pre_checks_suspended_participant(self):
        self.participant.is_suspended = True
        self.participant.save()
        passed, reason = evaluate_pre_checks(self.contribution)
        self.assertFalse(passed)
        self.assertIn("suspended", reason)

    def test_process_pending_contribution_success(self):
        contrib, status = process_pending_contribution(self.contribution.id)
        self.assertEqual(status, 'QUEUED')
        self.assertEqual(contrib.status, 'QUEUED')
        self.assertEqual(contrib.sub_status, '')
        self.assertIsNone(contrib.locked_at)

    def test_process_pending_contribution_failure_rejects(self):
        self.project.is_enabled = False
        self.project.save()
        contrib, status = process_pending_contribution(self.contribution.id)
        self.assertEqual(status, 'REJECTED')
        self.assertEqual(contrib.status, 'REJECTED')
        self.assertIn("Repository is disabled", contrib.flagged_reason)

    def test_transition_queued_to_under_review_and_validating(self):
        self.contribution.status = 'QUEUED'
        self.contribution.save()

        updated, transitioned = transition_contribution(
            self.contribution.id,
            target_status='UNDER_REVIEW',
            sub_status='VALIDATING',
        )
        self.assertTrue(transitioned)
        self.assertEqual(updated.status, 'UNDER_REVIEW')
        self.assertEqual(updated.sub_status, 'VALIDATING')
        self.assertIsNotNone(updated.locked_at)

    def test_transition_under_review_to_approved(self):
        self.contribution.status = 'UNDER_REVIEW'
        self.contribution.locked_at = timezone.now()
        self.contribution.save()

        updated, transitioned = transition_contribution(
            self.contribution.id,
            target_status='APPROVED',
        )
        self.assertTrue(transitioned)
        self.assertEqual(updated.status, 'APPROVED')
        self.assertEqual(updated.sub_status, '')
        self.assertIsNone(updated.locked_at)
        self.assertIsNotNone(updated.approved_at)

    def test_transition_under_review_to_rejected(self):
        self.contribution.status = 'UNDER_REVIEW'
        self.contribution.save()

        updated, transitioned = transition_contribution(
            self.contribution.id,
            target_status='REJECTED',
            reason='Violated integrity rules',
        )
        self.assertTrue(transitioned)
        self.assertEqual(updated.status, 'REJECTED')
        self.assertEqual(updated.flagged_reason, 'Violated integrity rules')
        self.assertIsNone(updated.locked_at)

    def test_transition_under_review_to_flagged(self):
        self.contribution.status = 'UNDER_REVIEW'
        self.contribution.save()

        updated, transitioned = transition_contribution(
            self.contribution.id,
            target_status='FLAGGED',
            reason='Suspicious contribution pattern detected',
        )
        self.assertTrue(transitioned)
        self.assertEqual(updated.status, 'FLAGGED')
        self.assertEqual(updated.flagged_reason, 'Suspicious contribution pattern detected')
        self.assertIsNone(updated.locked_at)

    def test_transition_retry_exhaustion_escalates_to_flagged(self):
        self.contribution.status = 'UNDER_REVIEW'
        self.contribution.retry_count = 2
        self.contribution.save()

        # 3rd retry (max_retries=3) -> must escalate to FLAGGED per PRD §11.2
        updated, transitioned = transition_contribution(
            self.contribution.id,
            target_status='RETRY',
            reason='GitHub API timeout',
            max_retries=3,
        )
        self.assertTrue(transitioned)
        self.assertEqual(updated.status, 'FLAGGED')
        self.assertEqual(updated.retry_count, 3)
        self.assertIn("Max validation retries (3) exceeded", updated.flagged_reason)

    def test_transition_retry_non_exhausted(self):
        self.contribution.status = 'UNDER_REVIEW'
        self.contribution.retry_count = 0
        self.contribution.save()

        updated, transitioned = transition_contribution(
            self.contribution.id,
            target_status='RETRY',
            reason='Transient 503 error',
            max_retries=3,
        )
        self.assertTrue(transitioned)
        self.assertEqual(updated.status, 'RETRY')
        self.assertEqual(updated.retry_count, 1)

    def test_flagged_requires_admin_to_approve_or_reject(self):
        self.contribution.status = 'FLAGGED'
        self.contribution.save()

        # Non-admin attempt -> UnauthorizedTransitionError
        with self.assertRaises(UnauthorizedTransitionError):
            transition_contribution(
                self.contribution.id,
                target_status='APPROVED',
                actor=self.user,
            )

        # Admin attempt -> Success
        updated, transitioned = transition_contribution(
            self.contribution.id,
            target_status='APPROVED',
            actor=self.staff_user,
        )
        self.assertTrue(transitioned)
        self.assertEqual(updated.status, 'APPROVED')

    def test_rejected_override_requires_admin(self):
        self.contribution.status = 'REJECTED'
        self.contribution.save()

        # Non-admin attempt -> UnauthorizedTransitionError
        with self.assertRaises(UnauthorizedTransitionError):
            transition_contribution(
                self.contribution.id,
                target_status='UNDER_REVIEW',
                actor=self.user,
            )

        # Admin attempt -> Success
        updated, transitioned = transition_contribution(
            self.contribution.id,
            target_status='UNDER_REVIEW',
            actor=self.staff_user,
        )
        self.assertTrue(transitioned)
        self.assertEqual(updated.status, 'UNDER_REVIEW')

    def test_invalid_transition_rejected(self):
        self.contribution.status = 'APPROVED'
        self.contribution.save()

        # Cannot jump from APPROVED to PENDING
        with self.assertRaises(InvalidStateTransitionError):
            transition_contribution(
                self.contribution.id,
                target_status='PENDING',
            )

    def test_idempotent_transition_noop(self):
        self.contribution.status = 'UNDER_REVIEW'
        self.contribution.sub_status = 'VALIDATING'
        self.contribution.save()

        updated, transitioned = transition_contribution(
            self.contribution.id,
            target_status='UNDER_REVIEW',
            sub_status='VALIDATING',
        )
        self.assertFalse(transitioned)
        self.assertEqual(updated.status, 'UNDER_REVIEW')
        self.assertEqual(updated.sub_status, 'VALIDATING')
