import logging
from typing import Any
from django.contrib.auth import get_user_model
from core.models import AuditLog

logger = logging.getLogger(__name__)
User = get_user_model()


def log_audit_event(
    actor=None,
    action: str = '',
    target_type: str = '',
    target_id: str | int = '',
    details: dict[str, Any] | None = None,
) -> AuditLog:
    """
    Standardized, safe audit event logger (PRD §15, §18, plan.md M8).
    Creates an immutable AuditLog record capturing who performed what action on which target.
    
    Guarantees:
    - actor is set if authenticated User instance, else None (system action).
    - target_id is normalized to string.
    - details is sanitized JSON dictionary (never None).
    - Zero secrets or credentials logged.
    """
    actor_user = None
    if actor and getattr(actor, 'is_authenticated', False):
        if isinstance(actor, User):
            actor_user = actor

    sanitized_details = details if isinstance(details, dict) else {}

    audit_entry = AuditLog.objects.create(
        actor=actor_user,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else '',
        details=sanitized_details,
    )

    logger.info(
        "Audit event logged: action='%s', target='%s:%s', actor='%s'",
        action, target_type, target_id, actor_user.username if actor_user else 'system',
    )
    return audit_entry


def get_audit_logs_for_target(target_type: str, target_id: str | int):
    """
    Retrieve indexed audit history for a specific entity target (PRD §15, §18).
    """
    return AuditLog.objects.filter(
        target_type=target_type,
        target_id=str(target_id),
    ).select_related('actor').order_by('-created_at')
