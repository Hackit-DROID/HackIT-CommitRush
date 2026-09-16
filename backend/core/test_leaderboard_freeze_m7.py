from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import (
    Contribution,
    EventConfig,
    Issue,
    Participant,
    PointTransaction,
    Project,
    PullRequest,
)
from core.points import award_points_for_contribution

User = get_user_model()


class LeaderboardFreezeTests(TestCase):
    """
    Unit and integration tests for M7-T2: Leaderboard Freeze (PRD §8.6, §12.6, §18, Plan M7-T2).
    Verifies:
    1. leaderboard_frozen = false: reflects live standings.
    2. leaderboard_frozen = true: locks public leaderboard view.
    3. While frozen, background point awards and DB updates continue normally in Postgres,
       but public leaderboard continues showing frozen standings.
    4. Multiple leaderboard requests while frozen return identical consistent snapshot.
    5. Disable freeze: live standings resume with accumulated point changes.
    6. Freeze/unfreeze cache invalidation lifecycle.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.config = EventConfig.get_solo()
        self.config.leaderboard_frozen = False
        self.config.save()

        self.user1 = User.objects.create_user(username='frozen_alice', password='password123')
        self.participant1 = Participant.objects.create(
            user=self.user1,
            github_id=901,
            github_username='frozen_alice',
            total_points=200,
            merged_count=2,
        )

        self.user2 = User.objects.create_user(username='frozen_bob', password='password123')
        self.participant2 = Participant.objects.create(
            user=self.user2,
            github_id=902,
            github_username='frozen_bob',
            total_points=100,
            merged_count=1,
        )

        self.project = Project.objects.create(
            github_repo_id=7701,
            owner='hackit',
            name='freeze-repo',
            full_name='hackit/freeze-repo',
            is_enabled=True,
        )
        self.issue = Issue.objects.create(
            github_issue_id=7702,
            project=self.project,
            number=1,
            title='Freeze Issue',
            points=150,
            status='open',
        )

        # Initial contribution for Bob
        pr_bob_initial = PullRequest.objects.create(
            github_pr_id=7700,
            repo=self.project,
            number=1,
            author_github_id=self.participant2.github_id,
            author_participant=self.participant2,
            merged=True,
        )
        Contribution.objects.create(
            participant=self.participant2,
            issue=self.issue,
            pull_request=pr_bob_initial,
            status='MERGED',
        )

    def tearDown(self):
        cache.clear()

    def test_freeze_lifecycle_and_live_point_award_isolation(self):
        url = reverse('leaderboard')

        # 1. Initially unfrozen: Alice is Rank 1 (200 pts), Bob is Rank 2 (100 pts)
        res1 = self.client.get(url)
        self.assertEqual(res1.status_code, 200)
        d1 = res1.json()
        self.assertFalse(d1['is_frozen'])
        self.assertEqual(d1['results'][0]['github_username'], 'frozen_alice')
        self.assertEqual(d1['results'][0]['total_points'], 200)
        self.assertEqual(d1['results'][1]['github_username'], 'frozen_bob')
        self.assertEqual(d1['results'][1]['total_points'], 100)

        # 2. Enable leaderboard freeze
        self.config.leaderboard_frozen = True
        self.config.save()

        # Prime the frozen snapshot
        res_frozen1 = self.client.get(url)
        self.assertEqual(res_frozen1.status_code, 200)
        d_frozen1 = res_frozen1.json()
        self.assertTrue(d_frozen1['is_frozen'])
        self.assertEqual(d_frozen1['results'][0]['github_username'], 'frozen_alice')
        self.assertEqual(d_frozen1['results'][0]['total_points'], 200)

        # 3. While frozen, Bob gets a PR merged and earns 150 points (100 + 150 = 250 > Alice 200)
        pr = PullRequest.objects.create(
            github_pr_id=7703,
            repo=self.project,
            number=10,
            author_github_id=self.participant2.github_id,
            author_participant=self.participant2,
            merged=True,
        )
        c = Contribution.objects.create(
            participant=self.participant2,
            issue=self.issue,
            pull_request=pr,
            status='MERGED',
        )
        award_res = award_points_for_contribution(c.id)
        self.assertEqual(award_res['status'], 'AWARDED')

        # Verify underlying PostgreSQL state is updated
        self.participant2.refresh_from_db()
        self.assertEqual(self.participant2.total_points, 250)
        self.assertEqual(self.participant2.merged_count, 2)

        # 4. Public leaderboard view MUST STILL show frozen standings (Alice Rank 1 at 200, Bob Rank 2 at 100)
        res_frozen2 = self.client.get(url)
        self.assertEqual(res_frozen2.status_code, 200)
        d_frozen2 = res_frozen2.json()
        self.assertTrue(d_frozen2['is_frozen'])
        self.assertEqual(d_frozen2['results'][0]['github_username'], 'frozen_alice')
        self.assertEqual(d_frozen2['results'][0]['rank'], 1)
        self.assertEqual(d_frozen2['results'][0]['total_points'], 200)
        self.assertEqual(d_frozen2['results'][1]['github_username'], 'frozen_bob')
        self.assertEqual(d_frozen2['results'][1]['rank'], 2)
        self.assertEqual(d_frozen2['results'][1]['total_points'], 100)

        # 5. Multiple requests while frozen return the exact same consistent standings
        res_frozen3 = self.client.get(url)
        self.assertEqual(res_frozen3.json()['results'], d_frozen2['results'])

        # 6. Disable freeze (unfreeze event)
        self.config.leaderboard_frozen = False
        self.config.save()

        # 7. Public leaderboard resumes live standings: Bob is now Rank 1 (250 pts), Alice is Rank 2 (200 pts)
        res_live = self.client.get(url)
        self.assertEqual(res_live.status_code, 200)
        d_live = res_live.json()
        self.assertFalse(d_live['is_frozen'])
        self.assertEqual(d_live['results'][0]['github_username'], 'frozen_bob')
        self.assertEqual(d_live['results'][0]['rank'], 1)
        self.assertEqual(d_live['results'][0]['total_points'], 250)
        self.assertEqual(d_live['results'][1]['github_username'], 'frozen_alice')
        self.assertEqual(d_live['results'][1]['rank'], 2)
        self.assertEqual(d_live['results'][1]['total_points'], 200)

    def test_freeze_with_authenticated_user_me_field(self):
        # Authenticate as Bob (initially Rank 2)
        self.client.force_authenticate(user=self.user2)

        # Freeze the leaderboard
        self.config.leaderboard_frozen = True
        self.config.save()

        url = reverse('leaderboard')
        res = self.client.get(url, {'include_me': 'true'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['is_frozen'])
        self.assertIsNotNone(data['me'])
        self.assertEqual(data['me']['github_username'], 'frozen_bob')
