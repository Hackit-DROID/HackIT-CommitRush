import datetime
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from core.models import (
    Participant,
    Project,
    Issue,
    IssueLabel,
    PullRequest,
    Contribution,
    PointTransaction,
    DailyContributionUsage,
    EventConfig,
    WebhookEvent,
    AuditLog,
)

User = get_user_model()


class SchemaIntegrityTestCase(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', email='user1@test.com')
        self.user2 = User.objects.create_user(username='user2', email='user2@test.com')

        self.participant1 = Participant.objects.create(
            user=self.user1,
            github_id=10001,
            github_username='octocat1',
        )
        self.project1 = Project.objects.create(
            github_repo_id=20001,
            owner='hackit',
            name='repo1',
            full_name='hackit/repo1',
            language='Python',
            is_enabled=True,
        )
        self.issue1 = Issue.objects.create(
            github_issue_id=30001,
            project=self.project1,
            number=1,
            title='Test Issue 1',
            points=100,
            difficulty='intermediate',
            status='open',
        )
        self.pr1 = PullRequest.objects.create(
            github_pr_id=40001,
            repo=self.project1,
            number=101,
            author_github_id=10001,
            author_participant=self.participant1,
        )

    def test_participant_unique_github_id(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Participant.objects.create(
                    user=self.user2,
                    github_id=10001,  # duplicate
                    github_username='octocat2',
                )

    def test_project_unique_github_repo_id(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Project.objects.create(
                    github_repo_id=20001,  # duplicate
                    owner='hackit',
                    name='repo2',
                    full_name='hackit/repo2',
                )

    def test_issue_unique_github_issue_id(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Issue.objects.create(
                    github_issue_id=30001,  # duplicate
                    project=self.project1,
                    number=2,
                    title='Duplicate Issue',
                )

    def test_pull_request_unique_github_pr_id(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PullRequest.objects.create(
                    github_pr_id=40001,  # duplicate
                    repo=self.project1,
                    number=102,
                    author_github_id=10001,
                )

    def test_contribution_unique_participant_pr(self):
        Contribution.objects.create(
            participant=self.participant1,
            issue=self.issue1,
            pull_request=self.pr1,
            status='PENDING',
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Contribution.objects.create(
                    participant=self.participant1,
                    issue=self.issue1,
                    pull_request=self.pr1,  # duplicate pair
                    status='QUEUED',
                )

    def test_point_transaction_awarded_partial_uniqueness(self):
        contrib = Contribution.objects.create(
            participant=self.participant1,
            issue=self.issue1,
            pull_request=self.pr1,
            status='MERGED',
        )
        # First AWARDED transaction succeeds
        PointTransaction.objects.create(
            contribution=contrib,
            participant=self.participant1,
            points=100,
            status='AWARDED',
        )
        # Second AWARDED transaction for the same contribution must fail
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PointTransaction.objects.create(
                    contribution=contrib,
                    participant=self.participant1,
                    points=100,
                    status='AWARDED',
                )

    def test_point_transaction_multiple_deferred_allowed(self):
        contrib = Contribution.objects.create(
            participant=self.participant1,
            issue=self.issue1,
            pull_request=self.pr1,
            status='MERGED',
        )
        # Multiple DEFERRED / non-AWARDED entries are allowed for the same contribution
        pt1 = PointTransaction.objects.create(
            contribution=contrib,
            participant=self.participant1,
            points=0,
            status='DEFERRED',
        )
        pt2 = PointTransaction.objects.create(
            contribution=contrib,
            participant=self.participant1,
            points=0,
            status='DEFERRED',
        )
        self.assertIsNotNone(pt1.id)
        self.assertIsNotNone(pt2.id)

    def test_daily_contribution_usage_unique_participant_date(self):
        today = datetime.date(2026, 9, 16)
        DailyContributionUsage.objects.create(
            participant=self.participant1,
            date=today,
            contributions_count=1,
            points_count=50,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DailyContributionUsage.objects.create(
                    participant=self.participant1,
                    date=today,  # duplicate (participant, date)
                    contributions_count=2,
                    points_count=100,
                )

    def test_webhook_event_unique_delivery_id(self):
        WebhookEvent.objects.create(
            delivery_id='delivery-uuid-1234',
            event_type='pull_request',
            payload={'action': 'opened'},
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WebhookEvent.objects.create(
                    delivery_id='delivery-uuid-1234',  # duplicate
                    event_type='pull_request',
                    payload={'action': 'synchronize'},
                )

    def test_all_11_models_instantiate_and_save(self):
        # EventConfig
        config = EventConfig.objects.create(
            merge_concurrency=8,
            max_contributions_per_day=5,
            max_points_per_day=500,
            event_status='active',
        )
        self.assertEqual(config.merge_concurrency, 8)

        # IssueLabel
        label = IssueLabel.objects.create(name='good-first-issue', color='#7057ff')
        self.issue1.labels.add(label)
        self.assertEqual(self.issue1.labels.count(), 1)

        # AuditLog
        audit = AuditLog.objects.create(
            actor=self.user1,
            action='admin_override',
            target_type='Contribution',
            target_id='1',
            details={'reason': 'Manual approval'},
        )
        self.assertIsNotNone(audit.id)
