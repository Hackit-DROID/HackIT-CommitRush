import datetime
import logging
from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.utils import timezone

from core.models import (
    Contribution,
    EventConfig,
    Participant,
    PointTransaction,
    PullRequest,
)

logger = logging.getLogger(__name__)

STATS_CACHE_KEY = 'commitrush:stats:aggregate'
STATS_CACHE_TTL = 60  # 60 seconds per PRD §16, §20


def get_cached_event_stats() -> dict | None:
    """Retrieve aggregate stats from cache."""
    try:
        return cache.get(STATS_CACHE_KEY)
    except Exception as e:
        logger.warning("Cache backend error retrieving event stats (%s); falling back to database", e)
        return None


def set_cached_event_stats(data: dict, ttl: int = STATS_CACHE_TTL) -> bool:
    """Store calculated aggregate stats in cache."""
    try:
        cache.set(STATS_CACHE_KEY, data, ttl)
        return True
    except Exception as e:
        logger.warning("Cache backend error setting event stats (%s)", e)
        return False


def invalidate_event_stats_cache() -> None:
    """Invalidate cached event stats."""
    try:
        cache.delete(STATS_CACHE_KEY)
    except Exception as e:
        logger.warning("Cache backend error invalidating event stats (%s)", e)


def calculate_event_stats() -> dict:
    """
    Perform authoritative database aggregation across Participant, PullRequest,
    Contribution, PointTransaction, and EventConfig models.
    Executes exactly 4 optimized SQL queries without loading full tables into memory.
    """
    now = timezone.now()
    one_hour_ago = now - datetime.timedelta(hours=1)

    # 1. Participant metrics
    participant_aggs = Participant.objects.aggregate(
        total=Count('id'),
        active=Count('id', filter=Q(is_suspended=False)),
    )
    total_participants = participant_aggs['total'] or 0
    active_participants = participant_aggs['active'] or 0

    # 2. PullRequest metrics
    total_prs = PullRequest.objects.count()

    # 3. Contribution metrics by status & recent rates
    contribution_aggs = Contribution.objects.aggregate(
        total=Count('id'),
        pending=Count('id', filter=Q(status='PENDING')),
        queued=Count('id', filter=Q(status='QUEUED')),
        under_review=Count('id', filter=Q(status='UNDER_REVIEW')),
        approved=Count('id', filter=Q(status='APPROVED')),
        merging=Count('id', filter=Q(status='MERGING')),
        merged=Count('id', filter=Q(status='MERGED')),
        rejected=Count('id', filter=Q(status='REJECTED')),
        flagged=Count('id', filter=Q(status='FLAGGED')),
        retry=Count('id', filter=Q(status='RETRY')),
        merges_past_hour=Count('id', filter=Q(status='MERGED', merged_at__gte=one_hour_ago)),
    )

    total_contributions = contribution_aggs['total'] or 0
    merged_contributions = contribution_aggs['merged'] or 0
    merges_past_hour = contribution_aggs['merges_past_hour'] or 0

    by_status = {
        'PENDING': contribution_aggs['pending'] or 0,
        'QUEUED': contribution_aggs['queued'] or 0,
        'UNDER_REVIEW': contribution_aggs['under_review'] or 0,
        'APPROVED': contribution_aggs['approved'] or 0,
        'MERGING': contribution_aggs['merging'] or 0,
        'MERGED': merged_contributions,
        'REJECTED': contribution_aggs['rejected'] or 0,
        'FLAGGED': contribution_aggs['flagged'] or 0,
        'RETRY': contribution_aggs['retry'] or 0,
    }

    # 4. Point transactions aggregation
    point_aggs = PointTransaction.objects.filter(status='AWARDED').aggregate(
        total_points=Sum('points'),
        points_past_hour=Sum('points', filter=Q(created_at__gte=one_hour_ago)),
    )
    total_points = point_aggs['total_points'] or 0
    points_past_hour = point_aggs['points_past_hour'] or 0

    # 5. Event config runtime status
    config = EventConfig.get_solo()

    return {
        'event_status': config.event_status,
        'system_status': {
            'merge_paused': config.merge_paused,
            'validation_paused': config.validation_paused,
            'submissions_paused': config.submissions_paused,
            'leaderboard_frozen': config.leaderboard_frozen,
        },
        'participants': {
            'total': total_participants,
            'active': active_participants,
        },
        'pull_requests': {
            'total': total_prs,
            'merged': merged_contributions,
        },
        'contributions': {
            'total': total_contributions,
            'by_status': by_status,
        },
        'points': {
            'total_awarded': total_points,
            'points_past_hour': points_past_hour,
        },
        'rates': {
            'merges_past_hour': merges_past_hour,
            'points_past_hour': points_past_hour,
        },
        'updated_at': now.isoformat(),
    }


def fetch_event_stats(force_refresh: bool = False) -> dict:
    """
    Fetch event stats from cache if available; otherwise compute fresh from PostgreSQL
    and cache the result.
    """
    if not force_refresh:
        cached = get_cached_event_stats()
        if cached is not None:
            return cached

    stats = calculate_event_stats()
    set_cached_event_stats(stats, ttl=STATS_CACHE_TTL)
    return stats
