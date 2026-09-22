import logging
from django.core.cache import cache
from django.db import connection
from django.http import HttpResponseNotAllowed, JsonResponse

logger = logging.getLogger(__name__)


def check_database() -> bool:
    """
    Performs a lightweight database connectivity check using 'SELECT 1;'.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            row = cursor.fetchone()
            return bool(row and (row[0] == 1 or row == (1,)))
    except Exception as e:
        logger.error("Health check database probe failed: %s", str(e))
        return False


def check_cache() -> bool:
    """
    Performs a lightweight cache connectivity check using a temporary probe key.
    Returns True if cache responds, False if cache is unavailable.
    """
    probe_key = '__health_probe__'
    try:
        cache.set(probe_key, 'ok', timeout=10)
        result = cache.get(probe_key)
        cache.delete(probe_key)
        return result == 'ok'
    except Exception as e:
        logger.warning("Health check cache probe degraded: %s", str(e))
        return False


def health_view(request):
    """
    GET /health/
    Health and readiness check endpoint for load balancers, Gunicorn, Kubernetes, and uptime monitoring (PRD §23, §21.1).
    Checks database connectivity and returns 200 (healthy) or 503 (unhealthy/unavailable).
    Reports cache readiness status ('connected' or 'degraded').
    """
    if request.method not in ['GET', 'HEAD']:
        return HttpResponseNotAllowed(['GET', 'HEAD'])

    db_ok = check_database()
    cache_ok = check_cache()

    if db_ok:
        response_data = {
            'status': 'healthy',
            'database': 'connected',
            'cache': 'connected' if cache_ok else 'degraded',
        }
        return JsonResponse(response_data, status=200)
    else:
        response_data = {
            'status': 'unhealthy',
            'database': 'unavailable',
            'cache': 'connected' if cache_ok else 'degraded',
        }
        return JsonResponse(response_data, status=503)
