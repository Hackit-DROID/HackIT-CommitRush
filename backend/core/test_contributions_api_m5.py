from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import (
    Contribution,
    Issue,
    Participant,
    Project,
    PullRequest,
)

User = get_user_model()


class ContributionsApiM5TestCase(TestCase):
    """
    Unit & Integration test suite for M5-T4: Contribution Status REST APIs.
    Tests /contributions/mine/ and /contributions/{id}/ for authentication,
    object-level authorization, filtering, pagination, response payload shape,
    and zero-network invariant.
    """

    def setUp(self):
        self.client = APIClient()

        # Users and participants
        self.user_alice = User.objects.create_user(username='alice', email='alice@example.com')
        self.participant_alice = Participant.objects.create(
            user=self.user_alice,
            github_id=10001,
            github_username='alice',
            avatar_url='https://github.com/alice.png',
        )

        self.user_bob = User.objects.create_user(username='bob', email='bob@example.com')
        self.participant_bob = Participant.objects.create(
            user=self.user_bob,
            github_id=10002,
            github_username='bob',
            avatar_url='https://github.com/bob.png',
        )

        self.admin_user = User.objects.create_user(
            username='admin_boss',
            email='admin@example.com',
            is_staff=True,
        )

        # Projects and issues
        self.project = Project.objects.create(
            github_repo_id=5001,
            owner='hackit',
            name='commitrush-core',
            full_name='hackit/commitrush-core',
            language='Python',
            is_enabled=True,
        )

        self.issue_1 = Issue.objects.create(
            github_issue_id=6001,
            project=self.project,
            number=10,
            title='Implement API endpoint for contributions',
            points=100,
            difficulty='intermediate',
            category='backend',
            status='open',
        )
        self.issue_2 = Issue.objects.create(
            github_issue_id=6002,
            project=self.project,
            number=20,
            title='Build user status dashboard',
            points=50,
            difficulty='beginner',
            category='frontend',
            status='open',
        )

        # Alice's PR & Contribution
        self.pr_alice = PullRequest.objects.create(
            github_pr_id=7001,
            repo=self.project,
            number=101,
            author_github_id=self.participant_alice.github_id,
            author_participant=self.participant_alice,
            head_sha='sha_alice_123',
        )
        self.contrib_alice = Contribution.objects.create(
            participant=self.participant_alice,
            issue=self.issue_1,
            pull_request=self.pr_alice,
            status='APPROVED',
            approved_at=timezone.now(),
        )

        # Bob's PR & Contribution
        self.pr_bob = PullRequest.objects.create(
            github_pr_id=7002,
            repo=self.project,
            number=102,
            author_github_id=self.participant_bob.github_id,
            author_participant=self.participant_bob,
            head_sha='sha_bob_456',
        )
        self.contrib_bob = Contribution.objects.create(
            participant=self.participant_bob,
            issue=self.issue_2,
            pull_request=self.pr_bob,
            status='UNDER_REVIEW',
            sub_status='VALIDATING',
        )

    # =========================================================================
    # GET /api/v1/contributions/mine/
    # =========================================================================

    def test_my_contributions_unauthenticated_rejected(self):
        response = self.client.get('/api/v1/contributions/mine/')
        self.assertIn(response.status_code, [401, 403])

    def test_my_contributions_authenticated_returns_only_own_contributions(self):
        self.client.force_authenticate(user=self.user_alice)
        response = self.client.get('/api/v1/contributions/mine/')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(len(data['results']), 1)

        item = data['results'][0]
        self.assertEqual(item['id'], self.contrib_alice.id)
        self.assertEqual(item['status'], 'APPROVED')
        self.assertEqual(item['participant']['github_username'], 'alice')
        self.assertEqual(item['issue']['title'], 'Implement API endpoint for contributions')
        self.assertEqual(item['pull_request']['number'], 101)

    def test_my_contributions_filter_by_status(self):
        self.client.force_authenticate(user=self.user_alice)

        # Filter for matching status
        response = self.client.get('/api/v1/contributions/mine/?status=APPROVED')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)

        # Filter for non-matching status
        response = self.client.get('/api/v1/contributions/mine/?status=MERGED')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 0)

    # =========================================================================
    # GET /api/v1/contributions/{id}/
    # =========================================================================

    def test_contribution_detail_unauthenticated_rejected(self):
        response = self.client.get(f'/api/v1/contributions/{self.contrib_alice.id}/')
        self.assertIn(response.status_code, [401, 403])

    def test_contribution_detail_owner_can_access(self):
        self.client.force_authenticate(user=self.user_alice)
        response = self.client.get(f'/api/v1/contributions/{self.contrib_alice.id}/')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['id'], self.contrib_alice.id)
        self.assertEqual(data['status'], 'APPROVED')
        self.assertEqual(data['sub_status'], '')
        self.assertEqual(data['participant']['github_username'], 'alice')
        self.assertEqual(data['issue']['points'], 100)
        self.assertEqual(data['pull_request']['head_sha'], 'sha_alice_123')
        self.assertIn('github.com/hackit/commitrush-core/pull/101', data['pull_request']['github_url'])
        self.assertIn('github.com/hackit/commitrush-core/issues/10', data['issue']['github_url'])

    def test_contribution_detail_admin_can_access_any(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(f'/api/v1/contributions/{self.contrib_alice.id}/')
        self.assertEqual(response.status_code, 200)

        response_bob = self.client.get(f'/api/v1/contributions/{self.contrib_bob.id}/')
        self.assertEqual(response_bob.status_code, 200)

    def test_contribution_detail_non_owner_forbidden(self):
        # Bob tries to access Alice's contribution
        self.client.force_authenticate(user=self.user_bob)
        response = self.client.get(f'/api/v1/contributions/{self.contrib_alice.id}/')
        self.assertEqual(response.status_code, 403)

    def test_contribution_detail_not_found(self):
        self.client.force_authenticate(user=self.user_alice)
        response = self.client.get('/api/v1/contributions/999999/')
        self.assertEqual(response.status_code, 404)

    def test_zero_network_calls_on_contribution_endpoints(self):
        self.client.force_authenticate(user=self.user_alice)

        with patch('urllib.request.urlopen') as mock_urlopen, patch('requests.get') as mock_get:
            res1 = self.client.get('/api/v1/contributions/mine/')
            self.assertEqual(res1.status_code, 200)

            res2 = self.client.get(f'/api/v1/contributions/{self.contrib_alice.id}/')
            self.assertEqual(res2.status_code, 200)

            mock_urlopen.assert_not_called()
            mock_get.assert_not_called()
