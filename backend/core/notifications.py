import json
import logging
import os
import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

DEFAULT_COOLDOWN_SECONDS = 1800  # 30 minutes


class AlertSeverity:
    INFO = 'INFO'
    WARNING = 'WARNING'
    ERROR = 'ERROR'
    CRITICAL = 'CRITICAL'


class NotificationManager:
    """
    Clean notification and alerting abstraction for CommitRush.
    Features:
    - Multi-channel delivery: logger, AuditLog, Webhook (Slack/Discord/Telegram/generic), Email.
    - Alert deduplication and cooldown: does not spam administrators on repeated failures.
    - State tracking: sends an alert on failure, and a recovery notification when resolved.
    - Secret safety: never logs or leaks tokens or credentials.
    """

    @classmethod
    def _get_cache_key(cls, alert_key: str) -> str:
        return f"commitrush:alert:state:{alert_key}"

    @classmethod
    def send_alert(
        cls,
        subject: str = '',
        message: str = '',
        level: str = 'ERROR',
        alert_key: str = '',
        metadata: dict | None = None,
        cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
        title: str = '',
        severity: str = '',
        context: dict | None = None,
    ) -> bool:
        """
        Sends an alert notification with deduplication/cooldown.
        Returns True if alert was dispatched, False if suppressed by cooldown.
        """
        subject = title or subject
        level = (severity or level or 'ERROR').upper()
        meta = context or metadata or {}
        alert_identifier = alert_key or subject.lower().replace(' ', '_')
        cache_key = cls._get_cache_key(alert_identifier)

        now_ts = timezone.now().timestamp()

        # Check existing alert state in cache
        try:
            alert_state = cache.get(cache_key)
        except Exception as e:
            logger.warning("Cache access error in NotificationManager: %s", e)
            alert_state = None

        if alert_state and (now_ts - alert_state.get('last_sent', 0)) < cooldown_seconds:
            logger.info("Alert '%s' suppressed by cooldown (sent %ds ago)", alert_identifier, int(now_ts - alert_state['last_sent']))
            return False

        # Mark alert as active in cache
        new_state = {
            'is_active': True,
            'first_triggered': alert_state.get('first_triggered', now_ts) if alert_state else now_ts,
            'last_sent': now_ts,
            'subject': subject,
            'level': level,
        }
        try:
            cache.set(cache_key, new_state, timeout=cooldown_seconds * 3)
        except Exception as e:
            logger.warning("Cache set error in NotificationManager: %s", e)

        # Dispatch alert through channels
        cls._dispatch(
            subject=f"🚨 {subject}",
            message=message,
            level=level,
            metadata=meta,
        )
        return True

    @classmethod
    def resolve_alert(
        cls,
        subject: str = '',
        message: str = '',
        alert_key: str = '',
        metadata: dict | None = None,
        title: str = '',
        resolution_message: str = '',
        context: dict | None = None,
    ) -> bool:
        """
        Sends a recovery notification if an alert was previously active.
        Returns True if recovery notification was dispatched, False otherwise.
        """
        subject = title or subject
        message = resolution_message or message
        meta = context or metadata or {}
        cache_key = cls._get_cache_key(alert_key)
        try:
            alert_state = cache.get(cache_key)
        except Exception:
            alert_state = None

        if not alert_state or not alert_state.get('is_active'):
            # No prior active alert to resolve
            return False

        # Clear active state
        try:
            cache.delete(cache_key)
        except Exception:
            pass

        cls._dispatch(
            subject=f"🟢 [RESOLVED] {subject}",
            message=message,
            level='INFO',
            metadata=metadata or {},
        )
        return True

    @classmethod
    def _dispatch(cls, subject: str, message: str, level: str, metadata: dict):
        """
        Dispatches to logger, audit log, webhook, and email.
        """
        # 1. Structured logging
        log_msg = f"[ALERT - {level}] {subject}\n{message}"
        if level == 'CRITICAL':
            logger.critical(log_msg)
        elif level == 'WARNING':
            logger.warning(log_msg)
        elif level == 'INFO':
            logger.info(log_msg)
        else:
            logger.error(log_msg)

        # 2. AuditLog record in PostgreSQL
        try:
            from core.models import AuditLog
            AuditLog.objects.create(
                actor=None,
                action='pipeline_alert',
                target_type='System',
                target_id=subject[:255],
                details={
                    'subject': subject,
                    'message': message,
                    'level': level,
                    'metadata': metadata,
                },
            )
        except Exception as e:
            logger.warning("Failed to record AuditLog alert: %s", e)

        # 3. Webhook delivery (e.g. Slack/Discord/custom webhook)
        webhook_url = os.environ.get('ALERT_WEBHOOK_URL', getattr(settings, 'ALERT_WEBHOOK_URL', ''))
        if webhook_url:
            try:
                payload = {
                    'text': f"*{subject}*\n```{message}```",
                    'subject': subject,
                    'message': message,
                    'level': level,
                    'metadata': metadata,
                    'timestamp': timezone.now().isoformat(),
                }
                requests.post(webhook_url, json=payload, timeout=5)
            except Exception as e:
                logger.warning("Failed to send webhook alert to %s: %s", webhook_url[:20], e)

        # 4. Email delivery (if ADMIN_EMAIL configured)
        admin_email = os.environ.get('ADMIN_EMAIL', getattr(settings, 'ADMIN_EMAIL', ''))
        if admin_email:
            try:
                from django.core.mail import send_mail
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@commitrush.hackit.org'),
                    recipient_list=[admin_email],
                    fail_silently=True,
                )
            except Exception as e:
                logger.warning("Failed to send email alert: %s", e)
