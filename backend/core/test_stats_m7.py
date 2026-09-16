from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import (
    Contribution,
    DailyContributionUsage,
    EventConfig,
    Issue,
    Participant,
    PointTransaction,
    Project,
    PullRequest,
)
from core.stats import (
    STATS_CACHE_KEY,
    calculate_event_stats,
    fetch_event_stats,
    get_cached_event_stats,
    invalidate_event_stats_cache,
    set_cached_event_stats,
)
from core.tasks import refresh_event_stats_task

User = get_user_model()


class EventStatsM7Tests(TestCase):
    """
    Test suite for M7-T5 /stats/ API and stats aggregation/caching logic (PRD §8.6, §16, §23, Plan M7-T5).
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Reset singleton config
        self.config = EventConfig.get_solo()
        self.config.event_status = 'active'
        self.config.merge_paused = False
        self.config.validation_paused = False
        self.config.submissions_paused = False
        self.config.leaderboard_frozen = False
        self.config.save()

    def tearDown(self):
        cache.clear()

    def test_stats_empty_event(self):
        """Empty event returns zero metrics with correct structure."""
        response = self.client.get('/api/v1/stats/')
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data['event_status'], 'active')
        self.assertEqual(data['system_status'], {
            'merge_paused': False,
            'validation_paused': False,
            'submissions_paused': False,
            'leaderboard_frozen': False,
        })
        self.assertEqual(data['participants'], {'total': 0, 'active': 0})
        self.assertEqual(data['pull_requests'], {'total': 0, 'merged': 0})
        self.assertEqual(data['contributions']['total'], 0)
        for status_val in ['PENDING', 'QUEUED', 'UNDER_REVIEW', 'APPROVED', 'MERGING', 'MERGED', 'REJECTED', 'FLAGGED', 'RETRY']:
            self.assertEqual(data['contributions']['by_status'][status_val], 0)
        self.assertEqual(data['points'], {'total_awarded': 0, 'points_past_hour': 0})
        self.assertEqual(data['rates'], {'merges_past_hour': 0, 'points_past_hour': 0})
        self.assertIn('updated_at', data)

    def test_stats_aggregation_mixed_entities(self):
        """Authoritative aggregation across participants, PRs, statuses, and point transactions."""
        # 1. Participants: 2 active, 1 suspended
        u1 = User.objects.create_user(username='u1')
        p1 = Participant.objects.create(user=u1, github_id=101, github_username='user1', is_suspended=False, total_points=150)
        u2 = User.objects.create_user(username='u2')
        p2 = Participant.objects.create(user=u2, github_id=102, github_username='user2', is_suspended=False, total_points=50)
        u3 = User.objects.create_user(username='u3')
        p3 = Participant.objects.create(user=u3, github_id=103, github_username='user3', is_suspended=True, total_points=0)

        # 2. Project and Issue
        proj = Project.objects.create(github_repo_id=201, owner='org', name='repo', full_name='org/repo')
        iss1 = Issue.objects.create(github_issue_id=301, project=proj, points=100, number=1, title='Bug 1')
        iss2 = Issue.objects.create(github_issue_id=302, project=proj, points=50, number=2, title='Bug 2')
        iss3 = Issue.objects.create(github_issue_id=303, project=proj, points=25, number=3, title='Bug 3')

        # 3. Pull requests
        pr1 = PullRequest.objects.create(github_pr_id=401, repo=proj, number=10, merged=True, author_github_id=101, author_participant=p1)
        pr2 = PullRequest.objects.create(github_pr_id=402, repo=proj, number=11, merged=True, author_github_id=102, author_participant=p2)
        pr3 = PullRequest.objects.create(github_pr_id=403, repo=proj, number=12, merged=False, author_github_id=101, author_participant=p1)
        pr4 = PullRequest.objects.create(github_pr_id=404, repo=proj, number=13, merged=False, author_github_id=101, author_participant=p1)

        # 4. Contributions with various statuses
        c1 = Contribution.objects.create(participant=p1, issue=iss1, pull_request=pr1, status='MERGED', merged_at=timezone.now())
        c2 = Contribution.objects.create(participant=p2, issue=iss2, pull_request=pr2, status='MERGED', merged_at=timezone.now())
        c3 = Contribution.objects.create(participant=p1, issue=iss3, pull_request=pr3, status='UNDER_REVIEW')
        c4 = Contribution.objects.create(participant=p1, issue=iss1, pull_request=pr4, status='REJECTED')

        # 5. Point Transactions: 2 awarded, 1 deferred (zero points)
        PointTransaction.objects.create(
            participant=p1,
            contribution=c1,
            points=100,
            status='AWARDED',
            reason='Credited merged contribution',
        )
        PointTransaction.objects.create(
            participant=p2,
            contribution=c2,
            points=50,
            status='AWARDED',
            reason='Credited merged contribution',
        )
        PointTransaction.objects.create(
            participant=p1,
            contribution=c4,
            points=0,
            status='DEFERRED',
            reason='Daily limit reached',
        )

        # Query stats
        response = self.client.get('/api/v1/stats/')
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verify exact counts
        self.assertEqual(data['participants']['total'], 3)
        self.assertEqual(data['participants']['active'], 2)
        self.assertEqual(data['pull_requests']['total'], 4)
        self.assertEqual(data['pull_requests']['merged'], 2)
        self.assertEqual(data['contributions']['total'], 4)
        self.assertEqual(data['contributions']['by_status']['MERGED'], 2)
        self.assertEqual(data['contributions']['by_status']['UNDER_REVIEW'], 1)
        self.assertEqual(data['contributions']['by_status']['REJECTED'], 1)
        self.assertEqual(data['contributions']['by_status']['PENDING'], 0)
        self.assertEqual(data['points']['total_awarded'], 150)
        self.assertEqual(data['points']['points_past_hour'], 150)
        self.assertEqual(data['rates']['merges_past_hour'], 2)

    def test_stats_caching_and_invalidation(self):
        """Stats are cached in Redis/LocMem, and subsequent requests hit the cache."""
        u1 = User.objects.create_user(username='u1')
        p1 = Participant.objects.create(user=u1, github_id=101, github_username='user1', total_points=100)

        # 1. Initial request populates cache
        resp1 = self.client.get('/api/v1/stats/')
        self.assertEqual(resp1.status_code, 200)
        data1 = resp1.json()
        self.assertEqual(data1['participants']['total'], 1)

        # 2. Add another participant without invalidating cache
        u2 = User.objects.create_user(username='u2')
        Participant.objects.create(user=u2, github_id=102, github_username='user2', total_points=50)

        # Cached response should still return total 1
        resp2 = self.client.get('/api/v1/stats/')
        self.assertEqual(resp2.json()['participants']['total'], 1)

        # 3. Explicit invalidation or cache refresh task updates the data
        invalidate_event_stats_cache()
        resp3 = self.client.get('/api/v1/stats/')
        self.assertEqual(resp3.json()['participants']['total'], 2)

    def test_celery_refresh_event_stats_task(self):
        """Celery Beat task recalculates and writes fresh stats to cache."""
        u = User.objects.create_user(username='celery_user')
        Participant.objects.create(user=u, github_id=999, github_username='celery_user', total_points=300)

        result = refresh_event_stats_task.apply().get()
        self.assertEqual(result['status'], 'success')
        self.assertTrue(result['cached'])

        cached_data = get_cached_event_stats()
        self.assertIsNotNone(cached_data)
        self.assertEqual(cached_data['participants']['total'], 1)

    def test_stats_cache_backend_failure_graceful_degradation(self):
        """If cache backend fails or throws connection error, fallback to DB aggregation safely."""
        from core.api_views import EventStatsView
        with patch.object(EventStatsView, 'throttle_classes', []):
            with patch('core.stats.cache.get', side_effect=Exception("Redis connection refused")):
                with patch('core.stats.cache.set', side_effect=Exception("Redis connection refused")):
                    response = self.client.get('/api/v1/stats/')
                    self.assertEqual(response.status_code, 200)
                    data = response.json()
                    self.assertEqual(data['event_status'], 'active')
                    self.assertIn('participants', data)



    def test_zero_github_calls_in_stats_path(self):
        """Verify no GitHub API requests are made during stats queries."""
        with patch('requests.Session.get') as mock_get, patch('requests.Session.request') as mock_req:
            response = self.client.get('/api/v1/stats/')
            self.assertEqual(response.status_code, 200)
            mock_get.assert_not_called()
            mock_req.assert_not_called()


    def test_system_status_flags_in_stats(self):
        """System pause and freeze flags in EventConfig are accurately reflected in /stats/."""
        self.config.merge_paused = True
        self.config.validation_paused = True
        self.config.submissions_paused = True
        self.config.leaderboard_frozen = True
        self.config.save()
        invalidate_event_stats_cache()

        response = self.client.get('/api/v1/stats/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['system_status']['merge_paused'])
        self.assertTrue(data['system_status']['validation_paused'])
        self.assertTrue(data['system_status']['submissions_paused'])
        self.assertTrue(data['system_status']['leaderboard_frozen'])
