import hashlib
import hmac
import json
import logging
from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.models import WebhookEvent

logger = logging.getLogger(__name__)


def verify_github_signature(request_body: bytes, signature_header: str | None, secret: str) -> bool:
    """
    Verify GitHub X-Hub-Signature-256 HMAC header using constant-time comparison (PRD §13.2, §16, §19).
    Returns True if valid, False otherwise.
    """
    if not secret or not signature_header:
        return False

    if not signature_header.startswith('sha256='):
        return False

    received_digest = signature_header[len('sha256='):].strip()
    if not received_digest:
        return False

    expected_digest = hmac.new(
        secret.encode('utf-8'),
        request_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(received_digest, expected_digest)


@csrf_exempt
@require_POST
def github_webhook_view(request):
    """
    M4-T1: POST /webhooks/github/ and /api/v1/webhooks/github/
    Inbound GitHub webhook receiver endpoint.
    
    Security & Performance Guarantees:
    - Verifies X-Hub-Signature-256 HMAC against stored secret. Missing/bad signature returns HTTP 401.
    - Idempotent delivery deduplication on X-GitHub-Delivery (M4-T2). Duplicate returns HTTP 200 no-op.
    - Fast acknowledgement target: <200ms without executing synchronous processing or GitHub network calls.
    - Persists raw payload into WebhookEvent and enqueues Celery task to the 'webhooks' queue (M4-T3).
    """
    secret = getattr(settings, 'GITHUB_WEBHOOK_SECRET', '')
    signature_header = request.headers.get('x-hub-signature-256') or request.META.get('HTTP_X_HUB_SIGNATURE_256')

    if not verify_github_signature(request.body, signature_header, secret):
        logger.warning("Rejected webhook with invalid or missing HMAC signature.")
        return HttpResponse("Invalid or missing webhook signature.", status=401)

    delivery_id = (
        request.headers.get('x-github-delivery')
        or request.META.get('HTTP_X_GITHUB_DELIVERY', '')
    ).strip()

    if not delivery_id:
        return HttpResponse("Missing X-GitHub-Delivery header.", status=400)

    event_type = (
        request.headers.get('x-github-event')
        or request.META.get('HTTP_X_GITHUB_EVENT', 'unknown')
    ).strip()

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return HttpResponse("Invalid JSON payload.", status=400)

    # Fast-path check for duplicate delivery (M4-T2)
    if WebhookEvent.objects.filter(delivery_id=delivery_id).exists():
        logger.info("Webhook duplicate delivery ignored: %s", delivery_id)
        return JsonResponse({"status": "duplicate", "delivery_id": delivery_id}, status=200)

    # Durable persistence with atomic race condition handling (M4-T1, M4-T2)
    try:
        with transaction.atomic():
            webhook_event = WebhookEvent.objects.create(
                delivery_id=delivery_id,
                event_type=event_type,
                payload=payload,
            )
    except IntegrityError:
        logger.info("Webhook duplicate delivery race caught for: %s", delivery_id)
        return JsonResponse({"status": "duplicate", "delivery_id": delivery_id}, status=200)

    # Async enqueue to high-priority 'webhooks' queue (M4-T3)
    from core.tasks import process_webhook_event_task
    process_webhook_event_task.delay(webhook_event.id)

    return JsonResponse(
        {
            "status": "ok",
            "delivery_id": delivery_id,
            "event_type": event_type,
            "webhook_event_id": webhook_event.id,
        },
        status=200,
    )
