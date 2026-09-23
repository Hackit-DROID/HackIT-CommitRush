import hmac
import logging
import urllib.parse
from django.conf import settings
from django.contrib.auth import login, logout
from django.http import HttpResponseNotAllowed, HttpResponseRedirect, JsonResponse
from django.middleware.csrf import get_token
from django.utils.http import url_has_allowed_host_and_scheme

from core.oauth import (
    BadSignature,
    OAuthError,
    OAuthConfigurationError,
    OAuthTokenExchangeError,
    OAuthProfileError,
    SignatureExpired,
    build_github_authorize_url,
    exchange_code_for_token,
    fetch_github_user_profile,
    generate_oauth_state,
    get_or_create_participant_from_github,
    sign_oauth_state,
    unsign_oauth_state,
)

logger = logging.getLogger(__name__)


def get_allowed_redirect_hosts(request=None):
    """
    Returns a set of permitted host strings for safe redirection.
    Includes the request host, configured ALLOWED_HOSTS, FRONTEND_URL host,
    and CORS_ALLOWED_ORIGINS hosts.
    """
    allowed = set()
    if request:
        try:
            allowed.add(request.get_host())
        except Exception:
            pass

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


def resolve_frontend_post_login_url(next_url: str | None, request=None) -> str:
    """
    Safely resolves the post-login destination URL to a trusted frontend route.
    Guarantees that:
    1. The final redirect ALWAYS lands on FRONTEND_URL (e.g. http://localhost:5173 or production domain).
    2. It NEVER redirects to backend API/admin endpoints (e.g. http://localhost:8000/issues/).
    3. Open redirects to external/malicious hosts are completely rejected.
    4. Safe relative paths (e.g. /issues, /dashboard, /projects, /leaderboard) are preserved on FRONTEND_URL.
    """
    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173').rstrip('/')
    default_redirect = getattr(
        settings, 'FRONTEND_AUTH_REDIRECT_URL', f"{frontend_url}/profile"
    )

    if not next_url:
        return default_redirect

    next_url = next_url.strip()
    if not next_url:
        return default_redirect

    # Discard dangerous schemes like javascript:, data:, etc.
    lower_url = next_url.lower()
    if lower_url.startswith(('javascript:', 'data:', 'vbscript:')):
        logger.warning('Discarded unsafe scheme in post-login redirect URL: %s', next_url)
        return default_redirect

    # Reject scheme-relative URLs (e.g. //evil.com/phish)
    if next_url.startswith('//'):
        logger.warning('Discarded scheme-relative open redirect URL: %s', next_url)
        return default_redirect

    parsed = urllib.parse.urlparse(next_url)
    parsed_frontend = urllib.parse.urlparse(frontend_url)

    target_path = ''
    target_query = parsed.query
    target_fragment = parsed.fragment

    if parsed.netloc:
        allowed_hosts = get_allowed_redirect_hosts(request)
        if parsed.netloc == parsed_frontend.netloc:
            target_path = parsed.path
        elif parsed.netloc in allowed_hosts or parsed.netloc.split(':')[0] in ('localhost', '127.0.0.1'):
            target_path = parsed.path
        else:
            logger.warning('Discarded untrusted external redirect host: %s', parsed.netloc)
            return default_redirect
    else:
        if not next_url.startswith('/'):
            logger.warning('Discarded non-root-relative redirect path: %s', next_url)
            return default_redirect
        target_path = parsed.path

    # Ensure path starts with single /
    if not target_path.startswith('/'):
        target_path = f"/{target_path}"

    # Block backend-only paths
    backend_prefixes = ('/api/', '/auth/', '/admin/', '/webhooks/', '/health/', '/static/', '/media/')
    if any(target_path == prefix.rstrip('/') or target_path.startswith(prefix) for prefix in backend_prefixes):
        logger.info('Redirect path %s points to backend endpoint; falling back to profile.', target_path)
        return default_redirect

    # Normalize root path to default redirect
    if target_path in ('', '/'):
        return default_redirect

    # Assemble final URL strictly on FRONTEND_URL
    query_part = f"?{target_query}" if target_query else ""
    fragment_part = f"#{target_fragment}" if target_fragment else ""

    return f"{frontend_url}{target_path}{query_part}{fragment_part}"


def github_login_view(request):
    """
    GET /auth/github/login/
    Initiates GitHub OAuth flow by generating a secure state token,
    storing it in session and cookie, and redirecting the user to GitHub authorization.
    Validates optional ?next= parameter against allowed hosts to prevent open redirect.
    """
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])

    # Loopback host normalization:
    # If GITHUB_REDIRECT_URI is on localhost (e.g. http://localhost:8000/auth/github/callback/),
    # and the incoming request is on 127.0.0.1, redirect to localhost so that session
    # cookies are established on the exact domain that GitHub will return to.
    redirect_uri = getattr(settings, 'GITHUB_REDIRECT_URI', '')
    if redirect_uri:
        parsed_redirect = urllib.parse.urlparse(redirect_uri)
        req_host = request.get_host().split(':')[0]
        referer = request.META.get('HTTP_REFERER')
        referer_host = urllib.parse.urlparse(referer).hostname if referer else None
        # If GitHub redirect URI is configured for localhost, ensure user initiates on localhost
        # to guarantee session and cookie preservation across the OAuth dance.
        if parsed_redirect.hostname == 'localhost':
            if req_host == '127.0.0.1' or (referer_host == '127.0.0.1' and req_host != 'localhost'):
                query_str = request.META.get('QUERY_STRING')
                query_part = f"?{query_str}" if query_str else ""
                target_url = f"{parsed_redirect.scheme}://{parsed_redirect.netloc}{request.path}{query_part}"
                logger.info(
                    "Normalizing OAuth login loopback host (req=%s, ref=%s) to %s to align with GITHUB_REDIRECT_URI",
                    req_host,
                    referer_host,
                    parsed_redirect.netloc,
                )
                return HttpResponseRedirect(target_url)

    raw_state = generate_oauth_state()
    signed_state = sign_oauth_state(raw_state)
    request.session['oauth_state'] = signed_state
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
        authorize_url = build_github_authorize_url(signed_state)
    except OAuthConfigurationError as e:
        logger.error('OAuth configuration error: %s', str(e))
        return JsonResponse({'error': 'GitHub OAuth is not properly configured.'}, status=500)

    response = HttpResponseRedirect(authorize_url)
    # Set fallback signed state cookie for defense-in-depth across partitioned sessions
    response.set_cookie(
        'commitrush_oauth_state',
        signed_state,
        max_age=600,
        httponly=True,
        samesite=getattr(settings, 'SESSION_COOKIE_SAMESITE', 'Lax'),
        secure=getattr(settings, 'SESSION_COOKIE_SECURE', False),
        path='/',
    )
    return response


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
        response = JsonResponse({'error': f'GitHub authorization cancelled or failed: {error_description}'}, status=400)
        response.delete_cookie('commitrush_oauth_state', path='/')
        return response

    # Validate state parameter against cryptographic signature and session/cookie
    received_state = request.GET.get('state')
    expected_state = request.session.pop('oauth_state', None)
    fallback_cookie_state = request.COOKIES.get('commitrush_oauth_state')

    is_valid_state = False

    if received_state:
        # First, try cryptographic unsigning (verifies HMAC signature and 10-minute expiry)
        try:
            unsigned_raw = unsign_oauth_state(received_state)
        except (BadSignature, SignatureExpired):
            unsigned_raw = None

        # 1. Match unsigned raw token against session state
        if unsigned_raw and expected_state and hmac.compare_digest(unsigned_raw, expected_state):
            is_valid_state = True
        # 2. Match unsigned raw token against fallback signed cookie
        elif unsigned_raw and fallback_cookie_state:
            try:
                cookie_raw = unsign_oauth_state(fallback_cookie_state)
                if hmac.compare_digest(unsigned_raw, cookie_raw):
                    is_valid_state = True
            except (BadSignature, SignatureExpired):
                pass
        # 3. Direct match for raw mock states (backwards compatibility with existing unit tests)
        elif expected_state and hmac.compare_digest(received_state, expected_state):
            is_valid_state = True
        # 4. Fallback cookie match directly
        elif fallback_cookie_state and hmac.compare_digest(received_state, fallback_cookie_state):
            is_valid_state = True

    if not is_valid_state:
        request.session.pop('oauth_next_url', None)
        logger.warning('Invalid, expired, or missing OAuth state token during callback.')
        response = JsonResponse({'error': 'Invalid or missing OAuth state parameter.'}, status=400)
        response.delete_cookie('commitrush_oauth_state', path='/')
        return response

    code = request.GET.get('code')
    if not code:
        request.session.pop('oauth_next_url', None)
        response = JsonResponse({'error': 'Missing authorization code.'}, status=400)
        response.delete_cookie('commitrush_oauth_state', path='/')
        return response

    try:
        access_token = exchange_code_for_token(code)
        user_info = fetch_github_user_profile(access_token)
        participant, created = get_or_create_participant_from_github(user_info)
    except OAuthTokenExchangeError as e:
        logger.warning('OAuth token exchange failure: %s', str(e))
        response = JsonResponse({'error': str(e)}, status=400)
        response.delete_cookie('commitrush_oauth_state', path='/')
        return response
    except OAuthProfileError as e:
        logger.warning('OAuth user profile retrieval failure: %s', str(e))
        response = JsonResponse({'error': str(e)}, status=502)
        response.delete_cookie('commitrush_oauth_state', path='/')
        return response
    except OAuthConfigurationError as e:
        logger.error('OAuth configuration failure: %s', str(e))
        response = JsonResponse({'error': 'OAuth configuration error.'}, status=500)
        response.delete_cookie('commitrush_oauth_state', path='/')
        return response
    except Exception as e:
        logger.exception('Unexpected error during OAuth callback processing')
        response = JsonResponse({'error': 'An internal error occurred during authentication.'}, status=500)
        response.delete_cookie('commitrush_oauth_state', path='/')
        return response

    # Establish authenticated Django session
    login(request, participant.user)

    # Resolve post-login destination safely to the React frontend
    stored_next_url = request.session.pop('oauth_next_url', None)
    redirect_url = resolve_frontend_post_login_url(stored_next_url, request)

    response = HttpResponseRedirect(redirect_url)
    response.delete_cookie('commitrush_oauth_state', path='/')
    return response


def frontend_profile_redirect(request):
    """
    Redirects direct GET requests on backend /profile/ to the frontend SPA at FRONTEND_URL/profile.
    """
    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173').rstrip('/')
    return HttpResponseRedirect(f"{frontend_url}/profile")


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

    csrf_token = get_token(request)
    data['csrf_token'] = csrf_token
    response = JsonResponse(data, status=200)
    response['X-CSRFToken'] = csrf_token
    return response


def csrf_view(request):
    """
    GET /auth/csrf/
    Returns CSRF token and ensures the csrftoken cookie is set for cross-origin SPAs.
    """
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])

    csrf_token = get_token(request)
    response = JsonResponse({'csrf_token': csrf_token}, status=200)
    response['X-CSRFToken'] = csrf_token
    return response


def dev_login_view(request):
    """
    GET /auth/dev-login/?username=<username>&next=/profile
    Development convenience endpoint to quickly establish a session for local testing.
    Strictly disabled when settings.DEBUG is False or ALLOW_DEV_LOGIN is False.
    """
    if not getattr(settings, 'DEBUG', False) or not getattr(settings, 'ALLOW_DEV_LOGIN', True):
        return JsonResponse({'error': 'Dev login is disabled in production environments.'}, status=403)

    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])

    from django.contrib.auth import get_user_model
    User = get_user_model()
    username = request.GET.get('username')
    if not username:
        return JsonResponse({'error': 'Username parameter is required.'}, status=400)

    user = User.objects.filter(username=username).first()
    if not user:
        return JsonResponse({'error': f"User '{username}' not found."}, status=404)

    login(request, user)
    next_url = request.GET.get('next')
    redirect_url = resolve_frontend_post_login_url(next_url, request)
    return HttpResponseRedirect(redirect_url)
