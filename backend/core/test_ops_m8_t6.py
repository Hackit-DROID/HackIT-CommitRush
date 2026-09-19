from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

from core.models import (
    Contribution,
    EventConfig,
    Issue,
    Participant,
    Project,
    PullRequest,
    WebhookEvent,
)

User = get_user_model()


class OpsMetricsM8T6Tests(TestCase):
    """
    Test suite for M8-T6: Backend Operator Metrics API (PRD §12.6, §18, plan.md M8-T6).
    """

    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='opsadmin',
            email='ops@hackit.org',
            password='OpsPassword123!',
            is_staff=True,
        )
        self.normal_user = User.objects.create_user(
            username='developer',
            email='dev@hackit.org',
            password='DevPassword123!',
        )

        self.config = EventConfig.get_solo()
        self.config.event_status = 'active'
        self.config.merge_concurrency = 8
        self.config.submissions_paused = False
        self.config.validation_paused = False
        self.config.merge_paused = False
        self.config.leaderboard_frozen = False
        self.config.save()

        self.participant = Participant.objects.create(
            user=self.normal_user,
            github_id=998877,
            github_username='developer',
            total_points=50,
            merged_count=1,
        )

        self.project = Project.objects.create(
            github_repo_id=112233,
            owner='hackit-org',
            name='infra-agent',
            full_name='hackit-org/infra-agent',
            language='Rust',
            is_enabled=True,
        )

        self.issue = Issue.objects.create(
            github_issue_id=445566,
            project=self.project,
            number=1,
            title='Setup health check probes',
            points=50,
        )

        self.pr = PullRequest.objects.create(
            github_pr_id=778899,
            repo=self.project,
            number=12,
            author_github_id=998877,
            author_participant=self.participant,
        )

        self.client = Client()

    def test_anonymous_and_non_staff_users_cannot_access_ops_metrics(self):
        """Public or non-staff users cannot access /ops/metrics/."""
        # Anonymous
        resp_anon = self.client.get(reverse('admin-metrics'))
        self.assertIn(resp_anon.status_code, [401, 403])

        # Non-staff authenticated
        self.client.force_login(self.normal_user)
        resp_user = self.client.get(reverse('admin-metrics'))
        self.assertEqual(resp_user.status_code, 403)

    def test_staff_user_receives_complete_ops_metrics(self):
        """Staff user receives aggregated queue depths, semaphore stats, and pause flags."""
        self.client.force_login(self.staff_user)

        # Create contributions in various states
        Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=self.pr,
            status='QUEUED',
        )

        pr2 = PullRequest.objects.create(
            github_pr_id=778800,
            repo=self.project,
            number=13,
            author_github_id=998877,
            author_participant=self.participant,
        )
        Contribution.objects.create(
            participant=self.participant,
            issue=self.issue,
            pull_request=pr2,
            status='APPROVED',
        )

        WebhookEvent.objects.create(
            delivery_id='delivery-ops-001',
            event_type='pull_request',
            payload={'action': 'opened'},
        )

        resp = self.client.get(reverse('admin-metrics'))
        self.assertEqual(resp.status_code, 200)

        data = resp.json()
        self.assertEqual(data['event_status'], 'active')

        # System status
        self.assertFalse(data['system_status']['submissions_paused'])
        self.assertFalse(data['system_status']['validation_paused'])
        self.assertFalse(data['system_status']['merge_paused'])
        self.assertFalse(data['system_status']['leaderboard_frozen'])

        # Queues
        self.assertEqual(data['queues']['validation_queued'], 1)
        self.assertEqual(data['queues']['merge_approved'], 1)
        self.assertEqual(data['queues']['webhooks_total'], 1)
        self.assertEqual(data['queues']['webhooks_unprocessed'], 1)

        # Semaphore
        self.assertEqual(data['semaphore']['configured_concurrency'], 8)

        # Oldest queued latency
        self.assertIsNotNone(data['oldest_queued_item_age_seconds'])
        self.assertGreaterEqual(data['oldest_queued_item_age_seconds'], 0)
