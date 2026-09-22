import logging
import secrets
import urllib.parse
import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.db import transaction

from core.models import Participant

OAUTH_STATE_SALT = 'core.oauth.state'
OAUTH_STATE_MAX_AGE = 600  # 10 minutes

logger = logging.getLogger(__name__)
User = get_user_model()

GITHUB_AUTHORIZE_URL = 'https://github.com/login/oauth/authorize'
GITHUB_TOKEN_URL = 'https://github.com/login/oauth/access_token'
GITHUB_USER_API_URL = 'https://api.github.com/user'


class OAuthError(Exception):
    """Base exception for OAuth failures."""
    pass


class OAuthConfigurationError(OAuthError):
    """Raised when OAuth settings are missing or invalid."""
    pass


class OAuthStateError(OAuthError):
    """Raised when OAuth state verification fails."""
    pass


class OAuthTokenExchangeError(OAuthError):
    """Raised when exchanging authorization code for access token fails."""
    pass


class OAuthProfileError(OAuthError):
    """Raised when fetching GitHub user profile fails."""
    pass


def generate_oauth_state() -> str:
    """Generate a cryptographically secure URL-safe random state token."""
    return secrets.token_urlsafe(32)


def sign_oauth_state(raw_state: str) -> str:
    """
    Cryptographically sign the state token with a timestamp using settings.SECRET_KEY.
    Ensures state integrity and enables tamper-proof, time-bounded verification.
    """
    signer = TimestampSigner(salt=OAUTH_STATE_SALT)
    return signer.sign(raw_state)


def unsign_oauth_state(signed_state: str, max_age: int = OAUTH_STATE_MAX_AGE) -> str:
    """
    Verify and unsign state token, ensuring it has not expired and has not been tampered with.
    Raises BadSignature or SignatureExpired on verification failure.
    """
    signer = TimestampSigner(salt=OAUTH_STATE_SALT)
    return signer.unsign(signed_state, max_age=max_age)


def build_github_authorize_url(state: str) -> str:
    """
    Build the GitHub OAuth authorization URL with client_id, redirect_uri,
    scope, and state parameter.
    """
    client_id = getattr(settings, 'GITHUB_CLIENT_ID', '')
    if not client_id:
        raise OAuthConfigurationError('GITHUB_CLIENT_ID is not configured.')

    redirect_uri = getattr(settings, 'GITHUB_REDIRECT_URI', '')
    scope = getattr(settings, 'GITHUB_OAUTH_SCOPE', 'read:user')

    params = {
        'client_id': client_id,
        'scope': scope,
        'state': state,
    }
    if redirect_uri:
        params['redirect_uri'] = redirect_uri

    return f"{GITHUB_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def exchange_code_for_token(code: str) -> str:
    """
    Exchange the authorization code for a GitHub access token.
    Never exposes or logs client_secret or access_token.
    """
    client_id = getattr(settings, 'GITHUB_CLIENT_ID', '')
    client_secret = getattr(settings, 'GITHUB_CLIENT_SECRET', '')
    redirect_uri = getattr(settings, 'GITHUB_REDIRECT_URI', '')

    if not client_id or not client_secret:
        raise OAuthConfigurationError('GitHub OAuth credentials are not fully configured.')

    payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'code': code,
    }
    if redirect_uri:
        payload['redirect_uri'] = redirect_uri

    headers = {
        'Accept': 'application/json',
        'User-Agent': 'HackIT-CommitRush-Auth',
    }

    try:
        response = requests.post(
            GITHUB_TOKEN_URL,
            json=payload,
            headers=headers,
            timeout=10,
        )
    except requests.RequestException as e:
        logger.warning('GitHub token exchange network failure')
        raise OAuthTokenExchangeError('Failed to communicate with GitHub token endpoint.') from e

    if response.status_code != 200:
        logger.warning('GitHub token exchange returned HTTP %s', response.status_code)
        raise OAuthTokenExchangeError(f'GitHub token exchange failed with status {response.status_code}.')

    try:
        data = response.json()
    except ValueError as e:
        raise OAuthTokenExchangeError('Invalid JSON response from GitHub token endpoint.') from e

    if 'error' in data:
        error_msg = data.get('error_description', data.get('error'))
        logger.warning('GitHub token exchange error response: %s', data.get('error'))
        raise OAuthTokenExchangeError(f'GitHub OAuth error: {error_msg}')

    access_token = data.get('access_token')
    if not access_token:
        raise OAuthTokenExchangeError('No access token returned by GitHub.')

    return access_token


def fetch_github_user_profile(access_token: str) -> dict:
    """
    Fetch the authenticated user profile from GitHub API.
    """
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'HackIT-CommitRush-Auth',
    }

    try:
        response = requests.get(
            GITHUB_USER_API_URL,
            headers=headers,
            timeout=10,
        )
    except requests.RequestException as e:
        logger.warning('GitHub user API network failure')
        raise OAuthProfileError('Failed to communicate with GitHub user endpoint.') from e

    if response.status_code != 200:
        logger.warning('GitHub user API returned HTTP %s', response.status_code)
        raise OAuthProfileError(f'GitHub user API failed with status {response.status_code}.')

    try:
        user_info = response.json()
    except ValueError as e:
        raise OAuthProfileError('Invalid JSON response from GitHub user endpoint.') from e

    if 'id' not in user_info or 'login' not in user_info:
        raise OAuthProfileError('Incomplete user profile returned by GitHub API.')

    return user_info


def get_or_create_participant_from_github(user_info: dict) -> tuple[Participant, bool]:
    """
    Find or create a Participant using github_id as the immutable identity key.
    Updates mutable cached profile fields (github_username, avatar_url).
    Guarantees no duplicate participants for the same github_id.
    """
    github_id = user_info['id']
    github_username = user_info['login']
    avatar_url = user_info.get('avatar_url') or ''
    email = user_info.get('email') or ''

    with transaction.atomic():
        # Select for update if existing, to avoid race condition on concurrent logins
        participant = Participant.objects.select_for_update().filter(github_id=github_id).select_related('user').first()

        if participant:
            # Update mutable profile information
            updated_fields = []
            if participant.github_username != github_username:
                participant.github_username = github_username
                updated_fields.append('github_username')
            if avatar_url and participant.avatar_url != avatar_url:
                participant.avatar_url = avatar_url
                updated_fields.append('avatar_url')

            if updated_fields:
                participant.save(update_fields=updated_fields)

            # Keep Django user email in sync if available and empty
            user = participant.user
            if email and not user.email:
                user.email = email
                user.save(update_fields=['email'])

            return participant, False

        # Create new Django User and Participant
        # Ensure Django User username uniqueness and length boundary (max 150 chars)
        desired_username = github_username[:150]
        if User.objects.filter(username=desired_username).exists():
            base_name = f"{github_username}_{github_id}"[:140]
            desired_username = base_name
            counter = 1
            while User.objects.filter(username=desired_username).exists():
                desired_username = f"{base_name}_{counter}"[:150]
                counter += 1

        user = User.objects.create_user(
            username=desired_username,
            email=email,
        )
        user.set_unusable_password()
        user.save()

        participant = Participant.objects.create(
            user=user,
            github_id=github_id,
            github_username=github_username,
            avatar_url=avatar_url,
        )
        return participant, True
