"""
CommitRush Scoring Constants and Timezone Utilities.
Authoritative source for event scoring rules, difficulty values, and IST timezone handling.
"""

import zoneinfo
from datetime import date, datetime
from django.utils import timezone

# Official Event Timezone (PRD / Event Rule: Asia/Kolkata, resets at 00:00 IST)
EVENT_TIMEZONE_NAME = 'Asia/Kolkata'
EVENT_TIMEZONE = zoneinfo.ZoneInfo(EVENT_TIMEZONE_NAME)

# Event Daily Points Cap
DAILY_POINTS_CAP = 120

# Authoritative Difficulty to Points Mapping (PRD / Event Rule)
# Beginner = 5, Easy = 10, Medium = 20, Hard = 30, Master = 50
DIFFICULTY_POINTS = {
    'beginner': 5,
    'easy': 10,
    'medium': 20,
    'intermediate': 20,
    'hard': 30,
    'advanced': 30,
    'master': 50,
    'expert': 50,
}

# Designated Event Target Branch
DEFAULT_TARGET_BRANCH = 'main'


def get_event_now() -> datetime:
    """
    Returns the current timezone-aware datetime converted to Asia/Kolkata (IST).
    """
    return timezone.now().astimezone(EVENT_TIMEZONE)


def get_event_today() -> date:
    """
    Returns the current calendar date in Asia/Kolkata (IST).
    The daily counter resets at 00:00 IST every day.
    """
    return get_event_now().date()


def get_difficulty_points(difficulty: str | None, default: int = 10) -> int:
    """
    Resolves the point value for a given difficulty string.
    """
    if not difficulty:
        return default
    return DIFFICULTY_POINTS.get(difficulty.strip().lower(), default)
