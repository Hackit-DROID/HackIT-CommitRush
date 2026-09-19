from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render


def custom_404_view(request, exception=None):
    """
    Custom 404 handler for CommitRush.
    - If the request is for an API endpoint (/api/...) or requests JSON (Accept header),
      returns a structured JSON error response.
    - If the request is from a browser (HTML), renders the styled dark cyber CommitRush 404 page
      providing links back to the frontend application and service health.
    """
    accept_header = request.headers.get('Accept', '')
    is_api_request = (
        request.path.startswith('/api/')
        or 'application/json' in accept_header
        or request.content_type == 'application/json'
    )

    if is_api_request:
        return JsonResponse(
            {
                'error': 'Not Found',
                'detail': f"The requested endpoint '{request.path}' was not found.",
                'status_code': 404,
            },
            status=404,
        )

    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173').rstrip('/')
    return render(
        request,
        '404.html',
        {
            'frontend_url': frontend_url,
            'path': request.path,
        },
        status=404,
    )
