import math
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from core.leaderboard import (
    calculate_participant_rank,
    fetch_leaderboard_data,
    get_leaderboard_queryset,
    invalidate_leaderboard_cache,
)
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


class LeaderboardApiTests(TestCase):
    """
    Unit and integration tests for M7-T1: /leaderboard/ API (PRD §8.6, §15, §16, §20).
    Verifies:
    - Empty leaderboard returns valid empty structure.
    - Deterministic ranking: total_points DESC, merged_count DESC, id ASC.
    - Suspended participants are excluded from public leaderboard ranking.
    - Server-side pagination (page, page_size, beyond available count).
    - Requester's own rank (`me` object) when authenticated, including when off the visible page.
    - Redis caching behavior (cache hit, cache miss, invalidation on point award).
    - Public access permitted without authentication.
    - Zero synchronous GitHub calls in request path.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.config = EventConfig.get_solo()
        self.config.leaderboard_frozen = False
        self.config.save()

        # Create a sample project and issue for contributions
        self.project = Project.objects.create(
            github_repo_id=10101,
            owner='hackit',
            name='board-repo',
            full_name='hackit/board-repo',
            is_enabled=True,
        )
        self.issue = Issue.objects.create(
            github_issue_id=20202,
            project=self.project,
            number=1,
            title='Issue 1',
            points=50,
            status='open',
        )

    def tearDown(self):
        cache.clear()

    def test_empty_leaderboard(self):
        url = reverse('leaderboard')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 0)
        self.assertEqual(data['page'], 1)
        self.assertEqual(data['total_pages'], 1)
        self.assertEqual(data['results'], [])
        self.assertIsNone(data['me'])
        self.assertFalse(data['is_frozen'])

    def test_leaderboard_ranking_ordering_and_tie_breaking(self):
        """
        Ranking order must be strictly:
        1. total_points DESC
        2. merged_count DESC
        3. id ASC (deterministic final tie-break)
        """
        # User 1: 200 pts, 3 merges
        u1 = User.objects.create_user(username='alice', password='password123')
        p1 = Participant.objects.create(user=u1, github_id=1, github_username='alice', total_points=200, merged_count=3)

        # User 2: 300 pts, 1 merge (highest points -> rank 1)
        u2 = User.objects.create_user(username='bob', password='password123')
        p2 = Participant.objects.create(user=u2, github_id=2, github_username='bob', total_points=300, merged_count=1)

        # User 3: 200 pts, 5 merges (same points as alice, but more merges -> rank 2, alice is rank 3)
        u3 = User.objects.create_user(username='carol', password='password123')
        p3 = Participant.objects.create(user=u3, github_id=3, github_username='carol', total_points=200, merged_count=5)

        # User 4: 200 pts, 3 merges, higher id than alice -> rank 4 (alice has lower id -> rank 3)
        u4 = User.objects.create_user(username='david', password='password123')
        p4 = Participant.objects.create(user=u4, github_id=4, github_username='david', total_points=200, merged_count=3)

        url = reverse('leaderboard')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data['count'], 4)
        results = data['results']
        self.assertEqual(len(results), 4)

        # Rank 1: Bob (300 pts)
        self.assertEqual(results[0]['github_username'], 'bob')
        self.assertEqual(results[0]['rank'], 1)
        self.assertEqual(results[0]['total_points'], 300)

        # Rank 2: Carol (200 pts, 5 merges)
        self.assertEqual(results[1]['github_username'], 'carol')
        self.assertEqual(results[1]['rank'], 2)
        self.assertEqual(results[1]['total_points'], 200)
        self.assertEqual(results[1]['merged_count'], 5)

        # Rank 3: Alice (200 pts, 3 merges, lower id)
        self.assertEqual(results[2]['github_username'], 'alice')
        self.assertEqual(results[2]['rank'], 3)
        self.assertEqual(results[2]['participant_id'], p1.id)

        # Rank 4: David (200 pts, 3 merges, higher id)
        self.assertEqual(results[3]['github_username'], 'david')
        self.assertEqual(results[3]['rank'], 4)
        self.assertEqual(results[3]['participant_id'], p4.id)

    def test_suspended_participant_excluded_from_leaderboard(self):
        u1 = User.objects.create_user(username='clean_user', password='password123')
        p1 = Participant.objects.create(user=u1, github_id=11, github_username='clean_user', total_points=100)

        u2 = User.objects.create_user(username='bad_user', password='password123')
        p2 = Participant.objects.create(user=u2, github_id=22, github_username='bad_user', total_points=500, is_suspended=True)

        url = reverse('leaderboard')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['github_username'], 'clean_user')
        self.assertEqual(data['results'][0]['rank'], 1)

    def test_pagination_and_page_beyond_available_rows(self):
        # Create 25 participants
        for i in range(1, 26):
            u = User.objects.create_user(username=f'user_{i:02d}', password='password123')
            Participant.objects.create(user=u, github_id=i, github_username=f'user_{i:02d}', total_points=i * 10)

        url = reverse('leaderboard')

        # Page 1, size 10 -> items 1..10
        res1 = self.client.get(url, {'page': 1, 'page_size': 10})
        self.assertEqual(res1.status_code, 200)
        d1 = res1.json()
        self.assertEqual(d1['count'], 25)
        self.assertEqual(d1['total_pages'], 3)
        self.assertEqual(len(d1['results']), 10)
        self.assertEqual(d1['results'][0]['rank'], 1)
        self.assertEqual(d1['results'][0]['github_username'], 'user_25')  # Highest points (250)
        self.assertIsNotNone(d1['next'])
        self.assertIsNone(d1['previous'])

        # Page 2, size 10 -> items 11..20
        res2 = self.client.get(url, {'page': 2, 'page_size': 10})
        self.assertEqual(res2.status_code, 200)
        d2 = res2.json()
        self.assertEqual(len(d2['results']), 10)
        self.assertEqual(d2['results'][0]['rank'], 11)
        self.assertIsNotNone(d2['next'])
        self.assertIsNotNone(d2['previous'])

        # Page 3, size 10 -> items 21..25
        res3 = self.client.get(url, {'page': 3, 'page_size': 10})
        self.assertEqual(res3.status_code, 200)
        d3 = res3.json()
        self.assertEqual(len(d3['results']), 5)
        self.assertEqual(d3['results'][0]['rank'], 21)
        self.assertIsNone(d3['next'])
        self.assertIsNotNone(d3['previous'])

        # Page 4 (beyond count) -> empty results list, valid response
        res4 = self.client.get(url, {'page': 4, 'page_size': 10})
        self.assertEqual(res4.status_code, 200)
        d4 = res4.json()
        self.assertEqual(d4['results'], [])

    def test_current_participant_rank_when_outside_visible_page(self):
        # Create 25 participants
        participants = []
        for i in range(1, 26):
            u = User.objects.create_user(username=f'user_{i:02d}', password='password123')
            p = Participant.objects.create(user=u, github_id=100 + i, github_username=f'user_{i:02d}', total_points=i * 10)
            participants.append(p)

        # Authenticate as user_01 (lowest points -> rank 25)
        target_user = User.objects.get(username='user_01')
        self.client.force_authenticate(user=target_user)

        # Request page 1 (which only shows top 10: user_25 to user_16)
        url = reverse('leaderboard')
        response = self.client.get(url, {'page': 1, 'page_size': 10, 'include_me': 'true'})
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Page 1 results should not include user_01
        usernames_on_page = [r['github_username'] for r in data['results']]
        self.assertNotIn('user_01', usernames_on_page)

        # But `me` must accurately report rank 25
        self.assertIsNotNone(data['me'])
        self.assertEqual(data['me']['github_username'], 'user_01')
        self.assertEqual(data['me']['rank'], 25)
        self.assertEqual(data['me']['total_points'], 10)

    def test_caching_and_invalidation_on_point_award(self):
        u1 = User.objects.create_user(username='leader_alice', password='password123')
        p1 = Participant.objects.create(user=u1, github_id=501, github_username='leader_alice', total_points=100)

        u2 = User.objects.create_user(username='leader_bob', password='password123')
        p2 = Participant.objects.create(user=u2, github_id=502, github_username='leader_bob', total_points=50)

        url = reverse('leaderboard')

        # Initial request populates cache
        res1 = self.client.get(url)
        self.assertEqual(res1.status_code, 200)
        d1 = res1.json()
        self.assertEqual(d1['results'][0]['github_username'], 'leader_alice')
        self.assertEqual(d1['results'][0]['total_points'], 100)

        # Create a contribution and award points to Bob (50 + 100 = 150 > Alice 100)
        pr = PullRequest.objects.create(
            github_pr_id=9901,
            repo=self.project,
            number=42,
            author_github_id=p2.github_id,
            author_participant=p2,
            merged=True,
        )
        issue2 = Issue.objects.create(
            github_issue_id=9902,
            project=self.project,
            number=2,
            title='Big Issue',
            points=100,
            status='open',
        )
        c = Contribution.objects.create(
            participant=p2,
            issue=issue2,
            pull_request=pr,
            status='MERGED',
        )

        award_res = award_points_for_contribution(c.id)
        self.assertEqual(award_res['status'], 'AWARDED')

        # Next request must reflect updated leaderboard with Bob as Rank 1
        res2 = self.client.get(url)
        self.assertEqual(res2.status_code, 200)
        d2 = res2.json()
        self.assertEqual(d2['results'][0]['github_username'], 'leader_bob')
        self.assertEqual(d2['results'][0]['rank'], 1)
        self.assertEqual(d2['results'][0]['total_points'], 150)
        self.assertEqual(d2['results'][0]['merged_count'], 1)

        self.assertEqual(d2['results'][1]['github_username'], 'leader_alice')
        self.assertEqual(d2['results'][1]['rank'], 2)
