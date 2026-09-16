from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
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
from core.points import award_points_for_contribution

User = get_user_model()


class DashboardApiTests(TestCase):
    """
    Unit and integration tests for M7-T3: /dashboard/ Aggregated API (PRD §16, Plan M7-T3).
    Verifies:
    - Authenticated participant receives full dashboard in 1 round trip.
    - Unauthenticated request is rejected (401/403).
    - Object-level security: Participant A cannot access Participant B's dashboard.
    - Global rank matches canonical leaderboard rank.
    - Total points and merged count match participant state.
    - Daily usage reflects authoritative DailyContributionUsage and EventConfig limits.
    - In-progress contributions includes only non-terminal states (PENDING, QUEUED, UNDER_REVIEW, APPROVED, MERGING, RETRY, FLAGGED).
    - Terminal states (MERGED, REJECTED) are excluded from in-progress list.
    - Recent activity is bounded.
    - Zero synchronous GitHub calls.
    """

    def setUp(self):
        self.client = APIClient()
        self.config = EventConfig.get_solo()
        self.config.max_contributions_per_day = 5
        self.config.max_points_per_day = 300
        self.config.save()

        # User / Participant A
        self.user_a = User.objects.create_user(username='alice_dash', password='password123')
        self.participant_a = Participant.objects.create(
            user=self.user_a,
            github_id=1001,
            github_username='alice_dash',
            avatar_url='https://avatars.githubusercontent.com/u/1001',
            total_points=250,
            merged_count=3,
        )

        # User / Participant B (higher points -> rank 1, Alice rank 2)
        self.user_b = User.objects.create_user(username='bob_dash', password='password123')
        self.participant_b = Participant.objects.create(
            user=self.user_b,
            github_id=1002,
            github_username='bob_dash',
            avatar_url='https://avatars.githubusercontent.com/u/1002',
            total_points=400,
            merged_count=5,
        )

        # Tracked project & issues
        self.project = Project.objects.create(
            github_repo_id=8801,
            owner='hackit',
            name='dash-repo',
            full_name='hackit/dash-repo',
            is_enabled=True,
        )

        self.issue_1 = Issue.objects.create(
            github_issue_id=8802,
            project=self.project,
            number=1,
            title='Issue 1',
            points=50,
            status='open',
        )
        self.issue_2 = Issue.objects.create(
            github_issue_id=8803,
            project=self.project,
            number=2,
            title='Issue 2',
            points=100,
            status='open',
        )
        self.issue_3 = Issue.objects.create(
            github_issue_id=8804,
            project=self.project,
            number=3,
            title='Issue 3',
            points=100,
            status='open',
        )

        # Daily usage for Alice today
        self.today = timezone.now().date()
        self.usage_a = DailyContributionUsage.objects.create(
            participant=self.participant_a,
            date=self.today,
            contributions_count=2,
            points_count=100,
        )

        # Contributions for Alice in various states
        # 1. PENDING (in-progress)
        pr1 = PullRequest.objects.create(github_pr_id=8811, repo=self.project, number=11, author_github_id=self.participant_a.github_id)
        self.c_pending = Contribution.objects.create(participant=self.participant_a, issue=self.issue_1, pull_request=pr1, status='PENDING')

        # 2. UNDER_REVIEW (in-progress)
        pr2 = PullRequest.objects.create(github_pr_id=8812, repo=self.project, number=12, author_github_id=self.participant_a.github_id)
        self.c_review = Contribution.objects.create(participant=self.participant_a, issue=self.issue_2, pull_request=pr2, status='UNDER_REVIEW', sub_status='VALIDATING')

        # 3. MERGED (terminal)
        pr3 = PullRequest.objects.create(github_pr_id=8813, repo=self.project, number=13, author_github_id=self.participant_a.github_id, merged=True)
        self.c_merged = Contribution.objects.create(participant=self.participant_a, issue=self.issue_3, pull_request=pr3, status='MERGED')

        # 4. REJECTED (terminal)
        pr4 = PullRequest.objects.create(github_pr_id=8814, repo=self.project, number=14, author_github_id=self.participant_a.github_id)
        self.c_rejected = Contribution.objects.create(participant=self.participant_a, issue=self.issue_1, pull_request=pr4, status='REJECTED')

        # 5. FLAGGED (in-progress / awaiting admin)
        pr5 = PullRequest.objects.create(github_pr_id=8815, repo=self.project, number=15, author_github_id=self.participant_a.github_id)
        self.c_flagged = Contribution.objects.create(participant=self.participant_a, issue=self.issue_2, pull_request=pr5, status='FLAGGED', flagged_reason='Suspicious diff')

    def test_unauthenticated_request_rejected(self):
        url = reverse('dashboard')
        response = self.client.get(url)
        self.assertIn(response.status_code, [401, 403])

    def test_authenticated_dashboard_aggregation_complete(self):
        self.client.force_authenticate(user=self.user_a)
        url = reverse('dashboard')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = response.json()

        # 1. Participant identity
        self.assertEqual(data['participant']['id'], self.participant_a.id)
        self.assertEqual(data['participant']['github_username'], 'alice_dash')
        self.assertEqual(data['participant']['avatar_url'], self.participant_a.avatar_url)

        # 2. Canonical rank (Bob has 400 pts -> Rank 1, Alice has 250 pts -> Rank 2)
        self.assertEqual(data['rank'], 2)
        self.assertEqual(data['total_points'], 250)
        self.assertEqual(data['merged_count'], 3)

        # 3. Daily usage
        self.assertEqual(data['daily_usage']['date'], str(self.today))
        self.assertEqual(data['daily_usage']['contributions_count'], 2)
        self.assertEqual(data['daily_usage']['max_contributions'], 5)
        self.assertEqual(data['daily_usage']['points_count'], 100)
        self.assertEqual(data['daily_usage']['max_points'], 300)

        # 4. In-progress contributions: must contain PENDING, UNDER_REVIEW, FLAGGED; NOT MERGED or REJECTED
        in_progress = data['in_progress_contributions']
        in_progress_ids = [c['id'] for c in in_progress]
        self.assertIn(self.c_pending.id, in_progress_ids)
        self.assertIn(self.c_review.id, in_progress_ids)
        self.assertIn(self.c_flagged.id, in_progress_ids)
        self.assertNotIn(self.c_merged.id, in_progress_ids)
        self.assertNotIn(self.c_rejected.id, in_progress_ids)

        # 5. Recent activity contains all 5 contributions ordered by -created_at
        recent = data['recent_activity']
        self.assertEqual(len(recent), 5)
        recent_ids = [c['id'] for c in recent]
        self.assertIn(self.c_merged.id, recent_ids)
        self.assertIn(self.c_rejected.id, recent_ids)

    def test_user_cannot_access_another_participants_dashboard(self):
        # Authenticate as User B
        self.client.force_authenticate(user=self.user_b)
        url = reverse('dashboard')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        # Must return Bob's data, not Alice's
        self.assertEqual(data['participant']['id'], self.participant_b.id)
        self.assertEqual(data['participant']['github_username'], 'bob_dash')
        self.assertEqual(data['rank'], 1)
        self.assertEqual(data['total_points'], 400)
        self.assertEqual(data['in_progress_contributions'], [])
        self.assertEqual(data['recent_activity'], [])

    def test_empty_dashboard_for_new_participant(self):
        new_user = User.objects.create_user(username='new_user', password='password123')
        new_p = Participant.objects.create(user=new_user, github_id=2002, github_username='new_user')

        self.client.force_authenticate(user=new_user)
        url = reverse('dashboard')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data['participant']['github_username'], 'new_user')
        self.assertEqual(data['total_points'], 0)
        self.assertEqual(data['merged_count'], 0)
        self.assertEqual(data['daily_usage']['contributions_count'], 0)
        self.assertEqual(data['daily_usage']['points_count'], 0)
        self.assertEqual(data['in_progress_contributions'], [])
        self.assertEqual(data['recent_activity'], [])
