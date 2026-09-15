import logging
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


def health_view(request):
    """
    GET /health/
    Health check endpoint for load balancers, Gunicorn, and uptime monitoring (PRD §23, §21.1).
    Checks database connectivity and returns 200 (healthy) or 503 (unhealthy/unavailable).
    """
    if request.method not in ['GET', 'HEAD']:
        return HttpResponseNotAllowed(['GET', 'HEAD'])

    db_ok = check_database()

    if db_ok:
        response_data = {
            'status': 'healthy',
            'database': 'connected',
        }
        return JsonResponse(response_data, status=200)
    else:
        response_data = {
            'status': 'unhealthy',
            'database': 'unavailable',
        }
        return JsonResponse(response_data, status=503)
