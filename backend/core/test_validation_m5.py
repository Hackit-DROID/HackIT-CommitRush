from django.contrib.auth import get_user_model
from django.test import TestCase
from unittest.mock import patch

from core.models import (
    Contribution,
    EventConfig,
    Issue,
    Participant,
    Project,
    PullRequest,
)
from core.tasks import validate_contribution_task
from core.validation import (
    run_deterministic_validation,
    validate_contribution,
)

User = get_user_model()


class ValidationRulesM5TestCase(TestCase):
    """
    Unit & Integration test suite for M5-T2: Validation Rules Engine.
    Tests deterministic abuse checks per PRD §22, duplicate PR handling,
    self-created issue farming detection, pause adherence, and Celery task execution.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='bob', email='bob@example.com')
        self.participant = Participant.objects.create(
            user=self.user,
            github_id=55555,
            github_username='bob',
            avatar_url='https://github.com/bob.png',
        )

        self.project = Project.objects.create(
            github_repo_id=2001,
            owner='hackit',
            name='analytics-worker',
            full_name='hackit/analytics-worker',
            language='Python',
            is_enabled=True,
        )

        self.issue = Issue.objects.create(
            github_issue_id=7001,
            project=self.project,
            number=15,
            title='Optimize database query execution',
            points=100,
            difficulty='intermediate',
            category='backend',
            status='open',
            created_by_github_id=99999,  # Legitimate issue created by someone else
        )

        self.pr = PullRequest.objects.create(
            github_pr_id=8001,
            repo=self.project,
            number=1,
            author_github_id=self.participant.github_id,
            author_participant=self.participant,
            head_sha='111222333444',
        )

        self.contribution = Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=self.pr,
            status='QUEUED',
        )

    def test_legitimate_contribution_approved(self):
        verdict, reason = run_deterministic_validation(self.contribution)
        self.assertEqual(verdict, 'APPROVED')
        self.assertEqual(reason, "")

    def test_self_created_issue_farming_detected_and_rejected(self):
        # Participant created their own issue -> PRD §22 Rule
        self.issue.created_by_github_id = self.participant.github_id
        self.issue.save()

        verdict, reason = run_deterministic_validation(self.contribution)
        self.assertEqual(verdict, 'REJECTED')
        self.assertIn("Self-created issue farming detected", reason)

    def test_disabled_issue_rejected(self):
        self.issue.status = 'disabled'
        self.issue.save()

        verdict, reason = run_deterministic_validation(self.contribution)
        self.assertEqual(verdict, 'REJECTED')
        self.assertIn("disabled", reason)

    def test_duplicate_pr_for_same_issue_flagged_when_prior_approved(self):
        # Create prior approved contribution for the same issue by same participant
        prior_pr = PullRequest.objects.create(
            github_pr_id=8002,
            repo=self.project,
            number=2,
            author_github_id=self.participant.github_id,
            author_participant=self.participant,
        )
        Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=prior_pr,
            status='APPROVED',
        )

        verdict, reason = run_deterministic_validation(self.contribution)
        self.assertEqual(verdict, 'FLAGGED')
        self.assertIn("Duplicate contribution pattern", reason)

    def test_duplicate_pr_for_same_issue_allowed_if_prior_rejected(self):
        # Create prior rejected contribution (e.g. author closed bad PR and opened a new one)
        prior_pr = PullRequest.objects.create(
            github_pr_id=8002,
            repo=self.project,
            number=2,
            author_github_id=self.participant.github_id,
            author_participant=self.participant,
        )
        Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=prior_pr,
            status='REJECTED',
        )

        verdict, reason = run_deterministic_validation(self.contribution)
        self.assertEqual(verdict, 'APPROVED')

    def test_validate_contribution_pipeline_success(self):
        result = validate_contribution(self.contribution.id)
        self.assertEqual(result['status'], 'approved')
        self.assertEqual(result['final_state'], 'APPROVED')

        self.contribution.refresh_from_db()
        self.assertEqual(self.contribution.status, 'APPROVED')
        self.assertIsNotNone(self.contribution.approved_at)

    def test_validate_contribution_respects_validation_paused(self):
        config = EventConfig.get_solo()
        config.validation_paused = True
        config.save()

        result = validate_contribution(self.contribution.id)
        self.assertEqual(result['status'], 'paused')

        self.contribution.refresh_from_db()
        # State must NOT be modified while paused
        self.assertEqual(self.contribution.status, 'QUEUED')

    def test_validate_contribution_celery_task(self):
        result = validate_contribution_task.apply(args=[self.contribution.id]).get()
        self.assertEqual(result['status'], 'approved')

        self.contribution.refresh_from_db()
        self.assertEqual(self.contribution.status, 'APPROVED')
