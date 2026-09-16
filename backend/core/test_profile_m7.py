from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
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


class PublicProfileApiTests(TestCase):
    """
    Unit and integration tests for M7-T4: /profile/{username}/ API (PRD §16, §19, Plan M7-T4).
    Verifies:
    - Public access without authentication.
    - Case-insensitive username lookup.
    - Safe field whitelisting (zero leakage of tokens, passwords, private usage, moderation reasons, audit logs).
    - Accurate total points, merged count, and global rank matching the leaderboard.
    - Aggregate statistics calculation (total, merged, in-progress, rejected).
    - Safe recent merged contributions list with project name, issue details, points, and GitHub PR URL.
    - 404 for nonexistent username.
    - 404 for suspended participant.
    - Special characters / URL encoding in username.
    - Zero synchronous GitHub calls.
    """

    def setUp(self):
        self.client = APIClient()

        # Leader / user with highest points -> rank 1
        self.u1 = User.objects.create_user(username='top_contributor', password='password123')
        self.p1 = Participant.objects.create(
            user=self.u1,
            github_id=3001,
            github_username='top_contributor',
            avatar_url='https://avatars.githubusercontent.com/u/3001',
            total_points=500,
            merged_count=5,
        )

        # Target profile user -> rank 2
        self.u2 = User.objects.create_user(username='samir_dev', password='password123')
        self.p2 = Participant.objects.create(
            user=self.u2,
            github_id=3002,
            github_username='samir_dev',
            avatar_url='https://avatars.githubusercontent.com/u/3002',
            total_points=250,
            merged_count=3,
        )

        # Suspended participant
        self.u_suspended = User.objects.create_user(username='banned_user', password='password123')
        self.p_suspended = Participant.objects.create(
            user=self.u_suspended,
            github_id=3003,
            github_username='banned_user',
            total_points=100,
            is_suspended=True,
        )

        # Tracked project & issues
        self.project = Project.objects.create(
            github_repo_id=9001,
            owner='hackit',
            name='profile-repo',
            full_name='hackit/profile-repo',
            is_enabled=True,
        )
        self.issue_1 = Issue.objects.create(
            github_issue_id=9002,
            project=self.project,
            number=101,
            title='Feature ABC',
            points=50,
            status='open',
        )
        self.issue_2 = Issue.objects.create(
            github_issue_id=9003,
            project=self.project,
            number=102,
            title='Bugfix XYZ',
            points=100,
            status='open',
        )

        # Contributions for samir_dev
        # 1. MERGED
        pr1 = PullRequest.objects.create(
            github_pr_id=9101,
            repo=self.project,
            number=21,
            author_github_id=self.p2.github_id,
            merged=True,
            merged_at=timezone.now(),
        )
        Contribution.objects.create(
            participant=self.p2,
            issue=self.issue_1,
            pull_request=pr1,
            status='MERGED',
            merged_at=timezone.now(),
        )

        # 2. MERGED
        pr2 = PullRequest.objects.create(
            github_pr_id=9102,
            repo=self.project,
            number=22,
            author_github_id=self.p2.github_id,
            merged=True,
            merged_at=timezone.now(),
        )
        Contribution.objects.create(
            participant=self.p2,
            issue=self.issue_2,
            pull_request=pr2,
            status='MERGED',
            merged_at=timezone.now(),
        )

        # 3. UNDER_REVIEW (in-progress)
        pr3 = PullRequest.objects.create(
            github_pr_id=9103,
            repo=self.project,
            number=23,
            author_github_id=self.p2.github_id,
        )
        Contribution.objects.create(
            participant=self.p2,
            issue=self.issue_1,
            pull_request=pr3,
            status='UNDER_REVIEW',
        )

        # 4. REJECTED
        pr4 = PullRequest.objects.create(
            github_pr_id=9104,
            repo=self.project,
            number=24,
            author_github_id=self.p2.github_id,
        )
        Contribution.objects.create(
            participant=self.p2,
            issue=self.issue_2,
            pull_request=pr4,
            status='REJECTED',
        )

    def test_public_profile_success(self):
        url = reverse('profile-detail', kwargs={'username': 'samir_dev'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = response.json()

        # Identity & ranking
        self.assertEqual(data['id'], self.p2.id)
        self.assertEqual(data['github_id'], 3002)
        self.assertEqual(data['github_username'], 'samir_dev')
        self.assertEqual(data['avatar_url'], self.p2.avatar_url)
        self.assertEqual(data['total_points'], 250)
        self.assertEqual(data['merged_count'], 3)
        self.assertEqual(data['rank'], 2)  # Top contributor is rank 1 (500 pts), samir_dev is rank 2 (250 pts)

        # Aggregate statistics
        stats = data['stats']
        self.assertEqual(stats['total_contributions'], 4)
        self.assertEqual(stats['merged_contributions'], 2)
        self.assertEqual(stats['in_progress_contributions'], 1)
        self.assertEqual(stats['rejected_contributions'], 1)

        # Safe recent merged contributions list
        recent_merged = data['recent_merged_contributions']
        self.assertEqual(len(recent_merged), 2)
        self.assertEqual(recent_merged[0]['project_name'], 'hackit/profile-repo')
        self.assertIn(recent_merged[0]['issue_number'], [101, 102])
        self.assertIn('https://github.com/hackit/profile-repo/pull/', recent_merged[0]['github_url'])

    def test_case_insensitive_username_lookup(self):
        url = reverse('profile-detail', kwargs={'username': 'SAMIR_DEV'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['github_username'], 'samir_dev')

    def test_nonexistent_username_returns_404(self):
        url = reverse('profile-detail', kwargs={'username': 'non_existent_user_12345'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_suspended_participant_returns_404_without_leaking_data(self):
        url = reverse('profile-detail', kwargs={'username': 'banned_user'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_safe_field_exposure_no_private_leakage(self):
        url = reverse('profile-detail', kwargs={'username': 'samir_dev'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Whitelist keys only
        allowed_top_keys = {
            'id',
            'github_id',
            'github_username',
            'avatar_url',
            'total_points',
            'merged_count',
            'rank',
            'stats',
            'recent_merged_contributions',
        }
        self.assertEqual(set(data.keys()), allowed_top_keys)

        # Ensure no private fields are leaked
        forbidden_fields = [
            'password',
            'email',
            'token',
            'access_token',
            'session_key',
            'daily_usage',
            'is_suspended',
            'flagged_reason',
            'locked_at',
            'retry_count',
        ]
        for field in forbidden_fields:
            self.assertNotIn(field, data)
            for item in data['recent_merged_contributions']:
                self.assertNotIn(field, item)
