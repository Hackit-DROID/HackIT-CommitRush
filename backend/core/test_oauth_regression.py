import time
import urllib.parse
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.signing import TimestampSigner
from django.test import TestCase, override_settings

from core.models import Participant
from core.oauth import (
    OAUTH_STATE_SALT,
    generate_oauth_state,
    sign_oauth_state,
    unsign_oauth_state,
)

User = get_user_model()


@override_settings(
    GITHUB_CLIENT_ID='test_client_id',
    GITHUB_CLIENT_SECRET='test_client_secret',
    GITHUB_REDIRECT_URI='http://localhost:8000/auth/github/callback/',
    GITHUB_OAUTH_SCOPE='read:user',
    FRONTEND_URL='http://localhost:5173',
    FRONTEND_AUTH_REDIRECT_URL='http://localhost:5173/profile',
    ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'],
    CORS_ALLOWED_ORIGINS=['http://localhost:5173', 'http://127.0.0.1:5173'],
)
class GitHubOAuthRegressionTestCase(TestCase):
    """
    Comprehensive regression suite for GitHub OAuth flow, state generation,
    cryptographic signing, session persistence, cookie fallback, and loopback normalization.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='existing_oauth_user', email='oauth@test.com')
        self.participant = Participant.objects.create(
            user=self.user,
            github_id=99999,
            github_username='existing_oauth_user',
            avatar_url='https://avatars.githubusercontent.com/u/99999',
            total_points=100,
        )

    def test_login_redirect_generates_signed_state_and_sets_fallback_cookie(self):
        """
        Initiating login must generate a cryptographically signed state, store raw state
        in session, set fallback signed cookie, and include signed state in GitHub URL.
        """
        response = self.client.get('/auth/github/login/')
        self.assertEqual(response.status_code, 302)

        redirect_url = response.url
        self.assertTrue(redirect_url.startswith('https://github.com/login/oauth/authorize?'))

        parsed = urllib.parse.urlparse(redirect_url)
        params = urllib.parse.parse_qs(parsed.query)

        self.assertIn('state', params)
        signed_state = params['state'][0]

        # Verify state is signed and un-signable
        raw_state = unsign_oauth_state(signed_state)
        self.assertEqual(self.client.session.get('oauth_state'), signed_state)

        # Verify fallback signed cookie is set
        self.assertIn('commitrush_oauth_state', response.cookies)
        self.assertEqual(response.cookies['commitrush_oauth_state'].value, signed_state)

    def test_login_loopback_normalization_redirects_127_to_localhost(self):
        """
        When user accesses via 127.0.0.1 and GITHUB_REDIRECT_URI is on localhost,
        login view must redirect to localhost:8000 so cookies are established
        on the exact domain GitHub redirects to.
        """
        response = self.client.get('/auth/github/login/?next=/profile', HTTP_HOST='127.0.0.1:8000')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'http://localhost:8000/auth/github/login/?next=/profile')

    def test_login_loopback_normalization_inspects_referer_when_proxied(self):
        """
        When requests arrive via dev proxy where referer indicates 127.0.0.1,
        login view normalizes to localhost:8000.
        """
        response = self.client.get(
            '/auth/github/login/?next=/profile',
            HTTP_HOST='127.0.0.1:8000',
            HTTP_REFERER='http://127.0.0.1:5173/',
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('http://localhost:8000/auth/github/login/'))

    @patch('core.oauth.requests.post')
    @patch('core.oauth.requests.get')
    def test_callback_accepts_valid_signed_state_with_session(self, mock_get, mock_post):
        """
        Valid signed state matching session state succeeds and logs in user.
        """
        raw_state = generate_oauth_state()
        signed_state = sign_oauth_state(raw_state)

        session = self.client.session
        session['oauth_state'] = raw_state
        session.save()

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {'access_token': 'gho_token_valid'}
        mock_post.return_value = mock_post_resp

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = {
            'id': 99999,
            'login': 'existing_oauth_user',
            'avatar_url': 'https://avatars.githubusercontent.com/u/99999',
        }
        mock_get.return_value = mock_get_resp

        response = self.client.get(f'/auth/github/callback/?code=mock_code_123&state={signed_state}')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session.get('_auth_user_id')), self.user.id)
        # Session state popped
        self.assertNotIn('oauth_state', self.client.session)

    @patch('core.oauth.requests.post')
    @patch('core.oauth.requests.get')
    def test_callback_accepts_valid_signed_state_with_fallback_cookie_when_session_lost(self, mock_get, mock_post):
        """
        When session cookie was dropped (session has no oauth_state),
        the fallback signed cookie commitrush_oauth_state allows successful state validation.
        """
        raw_state = generate_oauth_state()
        signed_state = sign_oauth_state(raw_state)

        # Clear session completely
        self.client.session.clear()
        self.client.session.save()

        # Set fallback cookie on client
        self.client.cookies['commitrush_oauth_state'] = signed_state

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {'access_token': 'gho_token_fallback'}
        mock_post.return_value = mock_post_resp

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = {
            'id': 99999,
            'login': 'existing_oauth_user',
            'avatar_url': 'https://avatars.githubusercontent.com/u/99999',
        }
        mock_get.return_value = mock_get_resp

        response = self.client.get(f'/auth/github/callback/?code=mock_code_fallback&state={signed_state}')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session.get('_auth_user_id')), self.user.id)

    def test_callback_rejects_tampered_state(self):
        """
        Forged or tampered state token is rejected with HTTP 400.
        """
        raw_state = generate_oauth_state()
        session = self.client.session
        session['oauth_state'] = raw_state
        session.save()

        response = self.client.get('/auth/github/callback/?code=mock_code&state=tampered_forged_state')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'Invalid or missing OAuth state parameter.'})

    def test_callback_rejects_missing_state(self):
        """
        Missing state parameter in callback is rejected with HTTP 400.
        """
        raw_state = generate_oauth_state()
        session = self.client.session
        session['oauth_state'] = raw_state
        session.save()

        response = self.client.get('/auth/github/callback/?code=mock_code')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'Invalid or missing OAuth state parameter.'})

    def test_callback_rejects_unbound_state_csrf(self):
        """
        State token signed by server but generated for a different client/session
        is rejected if client session and cookie do not match (CSRF prevention).
        """
        attacker_raw_state = generate_oauth_state()
        attacker_signed_state = sign_oauth_state(attacker_raw_state)

        # Victim's session has a different state
        victim_raw_state = generate_oauth_state()
        session = self.client.session
        session['oauth_state'] = victim_raw_state
        session.save()

        # Attacker tricks victim into loading callback with attacker's signed state
        response = self.client.get(f'/auth/github/callback/?code=attacker_code&state={attacker_signed_state}')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'Invalid or missing OAuth state parameter.'})

    def test_callback_single_use_prevents_replay(self):
        """
        Once a state is consumed, reusing it immediately fails with HTTP 400.
        """
        raw_state = generate_oauth_state()
        signed_state = sign_oauth_state(raw_state)

        session = self.client.session
        session['oauth_state'] = raw_state
        session.save()

        with patch('core.oauth.requests.post') as mock_post, patch('core.oauth.requests.get') as mock_get:
            mock_post_resp = MagicMock()
            mock_post_resp.status_code = 200
            mock_post_resp.json.return_value = {'access_token': 'gho_token'}
            mock_post.return_value = mock_post_resp

            mock_get_resp = MagicMock()
            mock_get_resp.status_code = 200
            mock_get_resp.json.return_value = {'id': 99999, 'login': 'existing_oauth_user'}
            mock_get.return_value = mock_get_resp

            # First callback succeeds
            resp1 = self.client.get(f'/auth/github/callback/?code=code_1&state={signed_state}')
            self.assertEqual(resp1.status_code, 302)

            # Replay with same state fails
            resp2 = self.client.get(f'/auth/github/callback/?code=code_2&state={signed_state}')
            self.assertEqual(resp2.status_code, 400)
            self.assertEqual(resp2.json(), {'error': 'Invalid or missing OAuth state parameter.'})

    @patch('core.oauth.requests.post')
    @patch('core.oauth.requests.get')
    def test_callback_default_redirects_to_frontend_profile(self, mock_get, mock_post):
        """
        When no next parameter was supplied, callback redirects to FRONTEND_URL/profile.
        """
        raw_state = generate_oauth_state()
        signed_state = sign_oauth_state(raw_state)
        session = self.client.session
        session['oauth_state'] = signed_state
        session.save()

        mock_post.return_value = MagicMock(status_code=200, json=lambda: {'access_token': 'gho_tok'})
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {'id': 99999, 'login': 'existing_oauth_user'})

        response = self.client.get(f'/auth/github/callback/?code=code_ok&state={signed_state}')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'http://localhost:5173/profile')

    @patch('core.oauth.requests.post')
    @patch('core.oauth.requests.get')
    def test_callback_with_next_dashboard_redirects_to_frontend_dashboard(self, mock_get, mock_post):
        """
        When next=/dashboard, callback redirects to FRONTEND_URL/dashboard (not backend).
        """
        raw_state = generate_oauth_state()
        signed_state = sign_oauth_state(raw_state)
        session = self.client.session
        session['oauth_state'] = signed_state
        session['oauth_next_url'] = '/dashboard'
        session.save()

        mock_post.return_value = MagicMock(status_code=200, json=lambda: {'access_token': 'gho_tok'})
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {'id': 99999, 'login': 'existing_oauth_user'})

        response = self.client.get(f'/auth/github/callback/?code=code_ok&state={signed_state}')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'http://localhost:5173/dashboard')

    @patch('core.oauth.requests.post')
    @patch('core.oauth.requests.get')
    def test_callback_with_next_issues_redirects_to_frontend_issues_not_backend_api(self, mock_get, mock_post):
        """
        When next=/issues (or /issues/), callback redirects to http://localhost:5173/issues,
        NEVER to backend http://localhost:8000/issues/ which serves DRF browsable API.
        """
        raw_state = generate_oauth_state()
        signed_state = sign_oauth_state(raw_state)
        session = self.client.session
        session['oauth_state'] = signed_state
        session['oauth_next_url'] = '/issues'
        session.save()

        mock_post.return_value = MagicMock(status_code=200, json=lambda: {'access_token': 'gho_tok'})
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {'id': 99999, 'login': 'existing_oauth_user'})

        response = self.client.get(f'/auth/github/callback/?code=code_ok&state={signed_state}')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'http://localhost:5173/issues')
        self.assertFalse(response.url.startswith('http://localhost:8000'))

    @patch('core.oauth.requests.post')
    @patch('core.oauth.requests.get')
    def test_callback_with_backend_host_in_next_url_redirects_to_frontend_origin(self, mock_get, mock_post):
        """
        If next parameter was passed with backend host http://localhost:8000/issues/,
        the view extracts the path and redirects to FRONTEND_URL http://localhost:5173/issues/.
        """
        raw_state = generate_oauth_state()
        signed_state = sign_oauth_state(raw_state)
        session = self.client.session
        session['oauth_state'] = signed_state
        session['oauth_next_url'] = 'http://localhost:8000/issues/'
        session.save()

        mock_post.return_value = MagicMock(status_code=200, json=lambda: {'access_token': 'gho_tok'})
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {'id': 99999, 'login': 'existing_oauth_user'})

        response = self.client.get(f'/auth/github/callback/?code=code_ok&state={signed_state}')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'http://localhost:5173/issues/')

    @patch('core.oauth.requests.post')
    @patch('core.oauth.requests.get')
    def test_callback_rejects_malicious_external_next_url(self, mock_get, mock_post):
        """
        Open-redirect attempt next=https://evil.example.com/phish is rejected;
        falls back to FRONTEND_URL/profile.
        """
        raw_state = generate_oauth_state()
        signed_state = sign_oauth_state(raw_state)
        session = self.client.session
        session['oauth_state'] = signed_state
        session['oauth_next_url'] = 'https://evil.example.com/phish'
        session.save()

        mock_post.return_value = MagicMock(status_code=200, json=lambda: {'access_token': 'gho_tok'})
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {'id': 99999, 'login': 'existing_oauth_user'})

        response = self.client.get(f'/auth/github/callback/?code=code_ok&state={signed_state}')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'http://localhost:5173/profile')

    @patch('core.oauth.requests.post')
    @patch('core.oauth.requests.get')
    def test_callback_rejects_backend_api_prefix_in_next_url(self, mock_get, mock_post):
        """
        Attempts to redirect to backend endpoints like /api/v1/issues/ fall back to /profile.
        """
        raw_state = generate_oauth_state()
        signed_state = sign_oauth_state(raw_state)
        session = self.client.session
        session['oauth_state'] = signed_state
        session['oauth_next_url'] = '/api/v1/issues/'
        session.save()

        mock_post.return_value = MagicMock(status_code=200, json=lambda: {'access_token': 'gho_tok'})
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {'id': 99999, 'login': 'existing_oauth_user'})

        response = self.client.get(f'/auth/github/callback/?code=code_ok&state={signed_state}')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'http://localhost:5173/profile')

    @patch('core.oauth.requests.post')
    @patch('core.oauth.requests.get')
    def test_session_remains_valid_after_callback_redirect(self, mock_get, mock_post):
        """
        After successful callback redirect, the session remains authenticated
        and can access /auth/me/ returning the authenticated participant.
        """
        raw_state = generate_oauth_state()
        signed_state = sign_oauth_state(raw_state)
        session = self.client.session
        session['oauth_state'] = signed_state
        session.save()

        mock_post.return_value = MagicMock(status_code=200, json=lambda: {'access_token': 'gho_tok'})
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                'id': 99999,
                'login': 'existing_oauth_user',
                'avatar_url': 'https://avatars.githubusercontent.com/u/99999',
            },
        )

        response = self.client.get(f'/auth/github/callback/?code=code_ok&state={signed_state}')
        self.assertEqual(response.status_code, 302)

        # Now make request to /auth/me/ with same client session
        me_resp = self.client.get('/auth/me/')
        self.assertEqual(me_resp.status_code, 200)
        data = me_resp.json()
        self.assertTrue(data['is_authenticated'])
        self.assertEqual(data['github_username'], 'existing_oauth_user')

