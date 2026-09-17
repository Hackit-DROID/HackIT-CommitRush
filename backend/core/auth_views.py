import hmac
import logging
import urllib.parse
from django.conf import settings
from django.contrib.auth import login, logout
from django.http import HttpResponseNotAllowed, HttpResponseRedirect, JsonResponse
from django.utils.http import url_has_allowed_host_and_scheme

from core.oauth import (
    OAuthError,
    OAuthConfigurationError,
    OAuthTokenExchangeError,
    OAuthProfileError,
    generate_oauth_state,
    build_github_authorize_url,
    exchange_code_for_token,
    fetch_github_user_profile,
    get_or_create_participant_from_github,
)

logger = logging.getLogger(__name__)


def get_allowed_redirect_hosts(request):
    """
    Returns a set of permitted host strings for safe redirection.
    Includes the request host, configured ALLOWED_HOSTS, FRONTEND_URL host,
    and CORS_ALLOWED_ORIGINS hosts.
    """
    allowed = {request.get_host()}

    # Add hosts from ALLOWED_HOSTS
    for host in getattr(settings, 'ALLOWED_HOSTS', []):
        if host and host not in ['*', '[::1]']:
            allowed.add(host)

    # Add host from FRONTEND_URL
    frontend_url = getattr(settings, 'FRONTEND_URL', '')
    if frontend_url:
        parsed = urllib.parse.urlparse(frontend_url)
        if parsed.netloc:
            allowed.add(parsed.netloc)

    # Add hosts from CORS_ALLOWED_ORIGINS
    for origin in getattr(settings, 'CORS_ALLOWED_ORIGINS', []):
        parsed = urllib.parse.urlparse(origin)
        if parsed.netloc:
            allowed.add(parsed.netloc)

    return allowed


def github_login_view(request):
    """
    GET /auth/github/login/
    Initiates GitHub OAuth flow by generating a secure state token,
    storing it in session, and redirecting the user to GitHub authorization.
    Validates optional ?next= parameter against allowed hosts to prevent open redirect.
    """
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])

    state = generate_oauth_state()
    request.session['oauth_state'] = state
    request.session.modified = True

    # Validate and store optional next URL for post-login redirect
    next_url = request.GET.get('next')
    if next_url:
        allowed_hosts = get_allowed_redirect_hosts(request)
        if url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts=allowed_hosts,
            require_https=request.is_secure(),
        ):
            request.session['oauth_next_url'] = next_url
        else:
            logger.warning('Discarded unsafe or untrusted OAuth next redirect URL: %s', next_url)
            request.session.pop('oauth_next_url', None)

    try:
        authorize_url = build_github_authorize_url(state)
    except OAuthConfigurationError as e:
        logger.error('OAuth configuration error: %s', str(e))
        return JsonResponse({'error': 'GitHub OAuth is not properly configured.'}, status=500)

    return HttpResponseRedirect(authorize_url)


def github_callback_view(request):
    """
    GET /auth/github/callback/
    Handles GitHub OAuth callback, verifies state CSRF token, exchanges code
    for access token, retrieves user profile, creates/updates Participant,
    and establishes an authenticated session.
    """
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])

    # Handle GitHub-reported error (e.g. user cancelled OAuth authorization)
    error = request.GET.get('error')
    if error:
        error_description = request.GET.get('error_description', error)
        request.session.pop('oauth_state', None)
        request.session.pop('oauth_next_url', None)
        logger.info('GitHub OAuth callback received error: %s', error_description)
        return JsonResponse({'error': f'GitHub authorization cancelled or failed: {error_description}'}, status=400)

    # Validate state parameter against session
    received_state = request.GET.get('state')
    expected_state = request.session.pop('oauth_state', None)

    if not received_state or not expected_state or not hmac.compare_digest(received_state, expected_state):
        request.session.pop('oauth_next_url', None)
        logger.warning('Invalid or missing OAuth state token during callback.')
        return JsonResponse({'error': 'Invalid or missing OAuth state parameter.'}, status=400)

    code = request.GET.get('code')
    if not code:
        request.session.pop('oauth_next_url', None)
        return JsonResponse({'error': 'Missing authorization code.'}, status=400)

    try:
        access_token = exchange_code_for_token(code)
        user_info = fetch_github_user_profile(access_token)
        participant, created = get_or_create_participant_from_github(user_info)
    except OAuthTokenExchangeError as e:
        logger.warning('OAuth token exchange failure: %s', str(e))
        return JsonResponse({'error': str(e)}, status=400)
    except OAuthProfileError as e:
        logger.warning('OAuth user profile retrieval failure: %s', str(e))
        return JsonResponse({'error': str(e)}, status=502)
    except OAuthConfigurationError as e:
        logger.error('OAuth configuration failure: %s', str(e))
        return JsonResponse({'error': 'OAuth configuration error.'}, status=500)
    except Exception as e:
        logger.exception('Unexpected error during OAuth callback processing')
        return JsonResponse({'error': 'An internal error occurred during authentication.'}, status=500)

    # Establish authenticated Django session
    login(request, participant.user)

    # Resolve post-login destination safely
    stored_next_url = request.session.pop('oauth_next_url', None)
    redirect_url = None
    if stored_next_url and url_has_allowed_host_and_scheme(
        url=stored_next_url,
        allowed_hosts=get_allowed_redirect_hosts(request),
        require_https=request.is_secure(),
    ):
        redirect_url = stored_next_url

    if not redirect_url:
        redirect_url = getattr(
            settings, 'FRONTEND_AUTH_REDIRECT_URL', 'http://localhost:5173/'
        )

    return HttpResponseRedirect(redirect_url)


def logout_view(request):
    """
    POST /auth/logout/
    Terminates the current authenticated session.
    Protected by Django CSRF middleware.
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    if request.user.is_authenticated:
        logout(request)

    return JsonResponse({'detail': 'Successfully logged out.'}, status=200)


def me_view(request):
    """
    GET /auth/me/
    Returns identity and profile information for the current session-authenticated participant.
    Returns 401 if unauthenticated.
    """
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])

    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication credentials were not provided.'}, status=401)

    participant = getattr(request.user, 'participant', None)
    if participant:
        data = {
            'id': participant.id,
            'user_id': request.user.id,
            'github_id': participant.github_id,
            'github_username': participant.github_username,
            'avatar_url': participant.avatar_url,
            'is_suspended': participant.is_suspended,
            'total_points': participant.total_points,
            'is_staff': request.user.is_staff,
            'is_authenticated': True,
        }
    else:
        data = {
            'id': None,
            'user_id': request.user.id,
            'github_id': None,
            'github_username': request.user.username,
            'avatar_url': None,
            'is_suspended': False,
            'total_points': 0,
            'is_staff': request.user.is_staff,
            'is_authenticated': True,
        }

    return JsonResponse(data, status=200)


def dev_login_view(request):
    """
    GET /auth/dev-login/?username=sarah_dev&next=/dashboard
    Development convenience endpoint to quickly establish a session for local testing.
    Strictly disabled when settings.DEBUG is False.
    """
    if not getattr(settings, 'DEBUG', False):
        return JsonResponse({'error': 'Dev login is disabled in production environments.'}, status=403)

    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])

    from django.contrib.auth import get_user_model
    User = get_user_model()
    username = request.GET.get('username', 'sarah_dev')
    user = User.objects.filter(username=username).first()
    if not user:
        user = User.objects.first()

    if user:
        login(request, user)
        next_url = request.GET.get('next', '/dashboard')
        if next_url.startswith('/'):
            frontend_base = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
            next_url = f"{frontend_base.rstrip('/')}{next_url}"
        return HttpResponseRedirect(next_url)

    return JsonResponse({'error': 'No user found to login.'}, status=404)
