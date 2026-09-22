import datetime
from io import StringIO
import urllib.parse
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.middleware.csrf import _get_new_csrf_string, _mask_cipher_secret
from django.test import Client, TestCase, override_settings

from core.bootstrap import bootstrap_event_config
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


class EventConfigSingletonTestCase(TestCase):
    def test_canonical_defaults_on_bootstrap(self):
        config = EventConfig.get_solo()
        self.assertEqual(config.pk, 1)
        self.assertEqual(config.merge_concurrency, 5)
        self.assertEqual(config.max_contributions_per_day, 5)
        self.assertEqual(config.max_points_per_day, 500)
        self.assertFalse(config.merge_paused)
        self.assertFalse(config.validation_paused)
        self.assertFalse(config.submissions_paused)
        self.assertFalse(config.leaderboard_frozen)
        self.assertEqual(config.event_status, 'pending')

    def test_singleton_save_enforces_pk_1(self):
        config = EventConfig(
            merge_concurrency=10,
            max_contributions_per_day=8,
            max_points_per_day=800,
            event_status='active',
        )
        config.save()
        self.assertEqual(config.pk, 1)
        self.assertEqual(EventConfig.objects.count(), 1)

        # Another instance saved still targets pk=1 and overwrites/updates
        config2 = EventConfig(
            merge_concurrency=3,
            event_status='paused',
        )
        config2.save()
        self.assertEqual(config2.pk, 1)
        self.assertEqual(EventConfig.objects.count(), 1)
        self.assertEqual(EventConfig.objects.get(pk=1).merge_concurrency, 3)
        self.assertEqual(EventConfig.objects.get(pk=1).event_status, 'paused')

    def test_singleton_delete_prevented(self):
        config = EventConfig.get_solo()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                config.delete()
        self.assertEqual(EventConfig.objects.count(), 1)

    def test_queryset_delete_prevented(self):
        EventConfig.get_solo()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                EventConfig.objects.all().delete()
        self.assertEqual(EventConfig.objects.count(), 1)

    def test_get_solo_and_load_methods_are_idempotent_and_preserve_edits(self):
        config = EventConfig.get_solo()
        config.event_status = 'active'
        config.merge_concurrency = 12
        config.save()

        # Calling get_solo again returns the existing record with updated values
        loaded_solo = EventConfig.get_solo()
        self.assertEqual(loaded_solo.pk, 1)
        self.assertEqual(loaded_solo.event_status, 'active')
        self.assertEqual(loaded_solo.merge_concurrency, 12)

        # Calling load alias returns identical instance
        loaded_alias = EventConfig.load()
        self.assertEqual(loaded_alias.pk, 1)
        self.assertEqual(loaded_alias.event_status, 'active')
        self.assertEqual(loaded_alias.merge_concurrency, 12)

    def test_bootstrap_utility_function(self):
        config = bootstrap_event_config()
        self.assertIsNotNone(config)
        self.assertEqual(config.pk, 1)
        self.assertEqual(EventConfig.objects.count(), 1)

    def test_bootstrap_management_command(self):
        out = StringIO()
        call_command('bootstrap_eventconfig', stdout=out)
        output = out.getvalue()
        self.assertIn("EventConfig singleton initialized successfully", output)
        self.assertIn("ID: 1", output)


@override_settings(
    GITHUB_CLIENT_ID='test_client_id',
    GITHUB_CLIENT_SECRET='test_client_secret',
    GITHUB_REDIRECT_URI='http://localhost:8000/auth/github/callback/',
    GITHUB_OAUTH_SCOPE='read:user',
    FRONTEND_URL='http://localhost:5173',
    FRONTEND_AUTH_REDIRECT_URL='http://localhost:5173/',
    ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'],
    CORS_ALLOWED_ORIGINS=['http://localhost:5173', 'http://127.0.0.1:5173'],
)
class GitHubOAuthTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='existing_user', email='existing@test.com')
        self.participant = Participant.objects.create(
            user=self.user,
            github_id=55555,
            github_username='existing_github_user',
            avatar_url='https://avatars.githubusercontent.com/u/55555',
            total_points=250,
        )

    def test_login_redirect_generates_state_and_stores_in_session(self):
        response = self.client.get('/auth/github/login/')
        self.assertEqual(response.status_code, 302)

        redirect_url = response.url
        self.assertTrue(redirect_url.startswith('https://github.com/login/oauth/authorize?'))

        parsed = urllib.parse.urlparse(redirect_url)
        params = urllib.parse.parse_qs(parsed.query)

        self.assertEqual(params.get('client_id'), ['test_client_id'])
        self.assertEqual(params.get('scope'), ['read:user'])
        self.assertEqual(params.get('redirect_uri'), ['http://localhost:8000/auth/github/callback/'])
        self.assertIn('state', params)

        state = params['state'][0]
        self.assertEqual(self.client.session.get('oauth_state'), state)

    def test_login_preserves_valid_relative_next_url(self):
        response = self.client.get('/auth/github/login/?next=/custom-dashboard')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get('oauth_next_url'), '/custom-dashboard')

    def test_login_preserves_valid_frontend_next_url(self):
        response = self.client.get('/auth/github/login/?next=http://localhost:5173/profile')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get('oauth_next_url'), 'http://localhost:5173/profile')

    def test_login_discards_external_malicious_next_url(self):
        response = self.client.get('/auth/github/login/?next=https://attacker.com/evil')
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('oauth_next_url', self.client.session)

    def test_login_discards_malformed_unsafe_next_url(self):
        # javascript: URI scheme
        response1 = self.client.get('/auth/github/login/?next=javascript:alert(1)')
        self.assertEqual(response1.status_code, 302)
        self.assertNotIn('oauth_next_url', self.client.session)

        # scheme-relative URL pointing externally
        response2 = self.client.get('/auth/github/login/?next=//evil.com/phish')
        self.assertEqual(response2.status_code, 302)
        self.assertNotIn('oauth_next_url', self.client.session)

    @override_settings(GITHUB_CLIENT_ID='')
    def test_login_fails_cleanly_if_client_id_missing(self):
        response = self.client.get('/auth/github/login/')
        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertIn('error', data)

    @patch('core.oauth.requests.post')
    @patch('core.oauth.requests.get')
    def test_callback_success_creates_new_participant_and_logs_in(self, mock_get, mock_post):
        # Set state in session
        session = self.client.session
        session['oauth_state'] = 'valid_state_12345'
        session.save()

        # Mock token exchange response
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {
            'access_token': 'gho_new_token_abcdef',
            'token_type': 'bearer',
            'scope': 'read:user',
        }
        mock_post.return_value = mock_post_resp

        # Mock user profile response
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = {
            'id': 88888,
            'login': 'newcontributor',
            'avatar_url': 'https://avatars.githubusercontent.com/u/88888',
            'email': 'newcontrib@example.com',
        }
        mock_get.return_value = mock_get_resp

        response = self.client.get('/auth/github/callback/?code=auth_code_xyz&state=valid_state_12345')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'http://localhost:5173/')

        # Verify participant created
        participant = Participant.objects.filter(github_id=88888).first()
        self.assertIsNotNone(participant)
        self.assertEqual(participant.github_username, 'newcontributor')
        self.assertEqual(participant.avatar_url, 'https://avatars.githubusercontent.com/u/88888')
        self.assertEqual(participant.total_points, 0)
        self.assertFalse(participant.is_suspended)

        # Verify session logged in
        self.assertEqual(int(self.client.session.get('_auth_user_id')), participant.user.id)

        # Verify state cleared from session
        self.assertNotIn('oauth_state', self.client.session)

    @patch('core.oauth.requests.post')
    @patch('core.oauth.requests.get')
    def test_callback_redirects_to_validated_next_url(self, mock_get, mock_post):
        session = self.client.session
        session['oauth_state'] = 'valid_state_next'
        session['oauth_next_url'] = '/custom-dashboard'
        session.save()

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {'access_token': 'gho_token_123'}
        mock_post.return_value = mock_post_resp

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = {'id': 77777, 'login': 'nextuser'}
        mock_get.return_value = mock_get_resp

        response = self.client.get('/auth/github/callback/?code=code_next&state=valid_state_next')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'http://localhost:5173/custom-dashboard')

    @patch('core.oauth.requests.post')
    @patch('core.oauth.requests.get')
    def test_callback_falls_back_if_session_next_url_is_untrusted(self, mock_get, mock_post):
        session = self.client.session
        session['oauth_state'] = 'valid_state_tampered'
        session['oauth_next_url'] = 'https://attacker.com/evil'
        session.save()

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {'access_token': 'gho_token_123'}
        mock_post.return_value = mock_post_resp

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = {'id': 77778, 'login': 'fallbackuser'}
        mock_get.return_value = mock_get_resp

        response = self.client.get('/auth/github/callback/?code=code_next&state=valid_state_tampered')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'http://localhost:5173/')

    @patch('core.oauth.requests.post')
    @patch('core.oauth.requests.get')
    def test_callback_success_updates_existing_participant_and_does_not_duplicate(self, mock_get, mock_post):
        initial_count = Participant.objects.count()

        session = self.client.session
        session['oauth_state'] = 'state_for_existing'
        session.save()

        # Mock token exchange
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {'access_token': 'gho_existing_token'}
        mock_post.return_value = mock_post_resp

        # Mock user profile with updated username and avatar
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = {
            'id': 55555,  # Same github_id as setUp
            'login': 'renamed_github_user',
            'avatar_url': 'https://newavatar.com/u/55555',
        }
        mock_get.return_value = mock_get_resp

        response = self.client.get('/auth/github/callback/?code=code_123&state=state_for_existing')
        self.assertEqual(response.status_code, 302)

        # No duplicate created
        self.assertEqual(Participant.objects.count(), initial_count)

        # Profile updated
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.github_username, 'renamed_github_user')
        self.assertEqual(self.participant.avatar_url, 'https://newavatar.com/u/55555')
        self.assertEqual(self.participant.total_points, 250)  # Points preserved

        # User logged in
        self.assertEqual(int(self.client.session.get('_auth_user_id')), self.participant.user.id)

    def test_callback_invalid_state_rejected(self):
        session = self.client.session
        session['oauth_state'] = 'legitimate_state'
        session.save()

        response = self.client.get('/auth/github/callback/?code=valid_code&state=forged_state')
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)
        self.assertIn('state', data['error'].lower())

    def test_callback_missing_state_rejected(self):
        session = self.client.session
        session['oauth_state'] = 'legitimate_state'
        session.save()

        response = self.client.get('/auth/github/callback/?code=valid_code')
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)

    def test_callback_github_cancellation_error_handled(self):
        session = self.client.session
        session['oauth_state'] = 'some_state'
        session.save()

        response = self.client.get('/auth/github/callback/?error=access_denied&error_description=User+cancelled')
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)
        self.assertIn('cancelled', data['error'].lower())

    @patch('core.oauth.requests.post')
    def test_callback_token_exchange_error_handled(self, mock_post):
        session = self.client.session
        session['oauth_state'] = 'state_exchange_fail'
        session.save()

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {
            'error': 'bad_verification_code',
            'error_description': 'The code passed is incorrect or expired.',
        }
        mock_post.return_value = mock_post_resp

        response = self.client.get('/auth/github/callback/?code=expired_code&state=state_exchange_fail')
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)
        self.assertIn('expired', data['error'].lower())

    @patch('core.oauth.requests.post')
    @patch('core.oauth.requests.get')
    def test_callback_profile_fetch_error_handled(self, mock_get, mock_post):
        session = self.client.session
        session['oauth_state'] = 'state_profile_fail'
        session.save()

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {'access_token': 'gho_good_token'}
        mock_post.return_value = mock_post_resp

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 500
        mock_get_resp.json.return_value = {'message': 'GitHub Internal Server Error'}
        mock_get.return_value = mock_get_resp

        response = self.client.get('/auth/github/callback/?code=good_code&state=state_profile_fail')
        self.assertEqual(response.status_code, 502)
        data = response.json()
        self.assertIn('error', data)

    def test_me_unauthenticated_returns_401(self):
        response = self.client.get('/auth/me/')
        self.assertEqual(response.status_code, 401)
        data = response.json()
        self.assertIn('detail', data)

    def test_me_authenticated_participant_returns_profile(self):
        self.client.force_login(self.participant.user)
        response = self.client.get('/auth/me/')
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data['id'], self.participant.id)
        self.assertEqual(data['user_id'], self.participant.user.id)
        self.assertEqual(data['github_id'], 55555)
        self.assertEqual(data['github_username'], 'existing_github_user')
        self.assertEqual(data['avatar_url'], 'https://avatars.githubusercontent.com/u/55555')
        self.assertFalse(data['is_suspended'])
        self.assertEqual(data['total_points'], 250)
        self.assertTrue(data['is_authenticated'])

    def test_logout_get_method_rejected(self):
        self.client.force_login(self.participant.user)
        response = self.client.get('/auth/logout/')
        self.assertEqual(response.status_code, 405)

    def test_logout_post_with_csrf_succeeds_and_clears_session(self):
        # Use Client with enforce_csrf_checks=True
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.participant.user)

        # Set valid CSRF cookie and header
        secret = _get_new_csrf_string()
        token = _mask_cipher_secret(secret)
        csrf_client.cookies['csrftoken'] = secret

        # POST with CSRF header
        logout_resp = csrf_client.post('/auth/logout/', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(logout_resp.status_code, 200)
        self.assertEqual(logout_resp.json(), {'detail': 'Successfully logged out.'})

        # Verify session is unauthenticated
        me_after = csrf_client.get('/auth/me/')
        self.assertEqual(me_after.status_code, 401)

    def test_logout_post_without_csrf_rejected_when_enforced(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.participant.user)

        # POST without CSRF token header
        logout_resp = csrf_client.post('/auth/logout/')
        self.assertEqual(logout_resp.status_code, 403)

    def test_versioned_api_endpoints_work_identically(self):
        # Unauthenticated /api/v1/auth/me/
        resp_unauth = self.client.get('/api/v1/auth/me/')
        self.assertEqual(resp_unauth.status_code, 401)

        # Authenticated /api/v1/auth/me/
        self.client.force_login(self.participant.user)
        resp_auth = self.client.get('/api/v1/auth/me/')
        self.assertEqual(resp_auth.status_code, 200)
        self.assertEqual(resp_auth.json()['github_username'], 'existing_github_user')

        # GET /api/v1/auth/logout/ rejected with 405
        resp_get_logout = self.client.get('/api/v1/auth/logout/')
        self.assertEqual(resp_get_logout.status_code, 405)

        # POST /api/v1/auth/logout/ succeeds
        resp_logout = self.client.post('/api/v1/auth/logout/')
        self.assertEqual(resp_logout.status_code, 200)

        resp_me_again = self.client.get('/api/v1/auth/me/')
        self.assertEqual(resp_me_again.status_code, 401)

    def test_get_or_create_participant_handles_username_collision_gracefully(self):
        from core.oauth import get_or_create_participant_from_github
        # Pre-create users with collision names
        User.objects.create_user(username='colliding_user', email='c1@test.com')
        User.objects.create_user(username='colliding_user_77777', email='c2@test.com')

        user_info = {
            'id': 77777,
            'login': 'colliding_user',
            'avatar_url': 'https://avatars.githubusercontent.com/u/77777',
            'email': 'c3@test.com',
        }
        participant, created = get_or_create_participant_from_github(user_info)
        self.assertTrue(created)
        self.assertEqual(participant.github_id, 77777)
        self.assertEqual(participant.github_username, 'colliding_user')
        self.assertTrue(participant.user.username.startswith('colliding_user_77777_'))


class HealthCheckTestCase(TestCase):
    def test_health_endpoint_healthy(self):
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('status'), 'healthy')
        self.assertEqual(data.get('database'), 'connected')

    def test_versioned_health_endpoint_healthy(self):
        response = self.client.get('/api/v1/health/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('status'), 'healthy')
        self.assertEqual(data.get('database'), 'connected')

    def test_health_endpoint_head_method_supported(self):
        response = self.client.head('/health/')
        self.assertEqual(response.status_code, 200)

    def test_health_endpoint_unsupported_methods(self):
        for method in ['post', 'put', 'patch', 'delete']:
            client_method = getattr(self.client, method)
            response = client_method('/health/')
            self.assertEqual(response.status_code, 405)

    @patch('core.health_views.check_database')
    def test_health_endpoint_db_failure_returns_503(self, mock_check_db):
        mock_check_db.return_value = False
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertEqual(data.get('status'), 'unhealthy')
        self.assertEqual(data.get('database'), 'unavailable')

    @patch('django.db.connection.cursor')
    def test_health_check_database_probe_handles_db_exception(self, mock_cursor):
        mock_cursor.side_effect = Exception("Database connection timeout")
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertEqual(data.get('status'), 'unhealthy')
        self.assertEqual(data.get('database'), 'unavailable')
