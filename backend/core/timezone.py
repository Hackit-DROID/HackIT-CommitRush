import zoneinfo
from datetime import date
from django.conf import settings
from django.utils import timezone


def get_challenge_today() -> date:
    """
    Returns the current calendar date in the authoritative challenge timezone (PRD §14, §15).
    Defaults to Asia/Kolkata (IST), matching CommitRush operational timezone in India.
    Guarantees daily limits reset deterministically at midnight local challenge time.
    """
    tz_name = getattr(settings, 'CHALLENGE_TIMEZONE', 'Asia/Kolkata')
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz = zoneinfo.ZoneInfo('Asia/Kolkata')
    return timezone.now().astimezone(tz).date()
