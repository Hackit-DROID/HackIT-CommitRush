import json
import logging
import math
from django.conf import settings
from django.core.cache import cache
from django.db.models import F, Q, Window
from django.db.models.functions import RowNumber
from django.utils import timezone

from core.models import DailyContributionUsage, EventConfig, Participant
from core.scoring.constants import DAILY_POINTS_CAP, get_event_now, get_event_today


logger = logging.getLogger(__name__)

LEADERBOARD_CACHE_PREFIX = 'commitrush:leaderboard'
LEADERBOARD_FROZEN_CACHE_PREFIX = 'commitrush:leaderboard:frozen'
LEADERBOARD_CACHE_TTL = 60  # seconds (PRD §20)


def get_leaderboard_queryset():
    """
    Returns the authoritative Participant queryset ordered by:
    1. total_points DESC
    2. merged_count DESC
    3. id ASC (deterministic final tie-breaker)
    Excludes suspended participants from public rankings (PRD §8.6, §15, §18).
    Annotates row rank using the database RowNumber window function.
    """
    return (
        Participant.objects.filter(is_suspended=False)
        .annotate(
            rank=Window(
                expression=RowNumber(),
                order_by=[
                    F('total_points').desc(),
                    F('merged_count').desc(),
                    F('id').asc(),
                ]
            )
        )
        .order_by('-total_points', '-merged_count', 'id')
    )


def calculate_participant_rank(participant_id: int) -> int | None:
    """
    Calculates the exact global rank of a single participant (PRD §8.6, §16).
    Returns None if the participant is suspended or does not exist.
    Uses an indexed O(log N) count query matching the exact leaderboard ordering:
    total_points DESC, merged_count DESC, id ASC.
    """
    try:
        participant = Participant.objects.get(id=participant_id)
    except Participant.DoesNotExist:
        return None

    if participant.is_suspended:
        return None

    # Count all active participants that rank ahead of this participant
    higher_count = Participant.objects.filter(is_suspended=False).filter(
        Q(total_points__gt=participant.total_points) |
        Q(total_points=participant.total_points, merged_count__gt=participant.merged_count) |
        Q(total_points=participant.total_points, merged_count=participant.merged_count, id__lt=participant.id)
    ).count()

    return higher_count + 1


def get_cached_leaderboard_page(page: int = 1, page_size: int = 20, is_frozen: bool = False) -> dict | None:
    """
    Retrieves a cached leaderboard page dictionary from Redis cache.
    Returns None on cache miss or cache error.
    """
    prefix = LEADERBOARD_FROZEN_CACHE_PREFIX if is_frozen else LEADERBOARD_CACHE_PREFIX
    key = f"{prefix}:page_{page}_size_{page_size}"
    try:
        data = cache.get(key)
        if data:
            return data
    except Exception as e:
        logger.warning("Redis cache read error for leaderboard key %s: %s", key, e)
    return None


def set_cached_leaderboard_page(page: int, page_size: int, is_frozen: bool, data: dict, ttl: int = LEADERBOARD_CACHE_TTL):
    """
    Sets a cached leaderboard page dictionary in Redis cache.
    """
    prefix = LEADERBOARD_FROZEN_CACHE_PREFIX if is_frozen else LEADERBOARD_CACHE_PREFIX
    key = f"{prefix}:page_{page}_size_{page_size}"
    try:
        # If frozen, persist without expiry or with a long TTL (e.g. 24h)
        cache.set(key, data, timeout=ttl if not is_frozen else 86400)
    except Exception as e:
        logger.warning("Redis cache write error for leaderboard key %s: %s", key, e)


def invalidate_leaderboard_cache():
    """
    Invalidates live leaderboard cache keys in Redis (PRD §20, Plan M7-T1).
    Called on point award or admin adjustment.
    Does NOT invalidate frozen snapshot keys when event is frozen.
    """
    try:
        if hasattr(cache, 'delete_pattern'):
            cache.delete_pattern(f"{LEADERBOARD_CACHE_PREFIX}:*")
        else:
            client = getattr(cache, 'client', None)
            if client and hasattr(client, 'get_client'):
                raw_client = client.get_client()
                keys = raw_client.keys(f":1:{LEADERBOARD_CACHE_PREFIX}:*") or raw_client.keys(f"{LEADERBOARD_CACHE_PREFIX}:*")
                if keys:
                    raw_client.delete(*keys)
            else:
                for p in range(1, 51):
                    for size in (10, 20, 50, 100):
                        cache.delete(f"{LEADERBOARD_CACHE_PREFIX}:page_{p}_size_{size}")
    except Exception as e:
        logger.warning("Redis cache invalidation error for leaderboard: %s", e)


def invalidate_frozen_leaderboard_cache():
    """
    Invalidates frozen leaderboard snapshot cache keys in Redis when unfreeze occurs.
    """
    try:
        if hasattr(cache, 'delete_pattern'):
            cache.delete_pattern(f"{LEADERBOARD_FROZEN_CACHE_PREFIX}:*")
        else:
            client = getattr(cache, 'client', None)
            if client and hasattr(client, 'get_client'):
                raw_client = client.get_client()
                keys = raw_client.keys(f":1:{LEADERBOARD_FROZEN_CACHE_PREFIX}:*") or raw_client.keys(f"{LEADERBOARD_FROZEN_CACHE_PREFIX}:*")
                if keys:
                    raw_client.delete(*keys)
            else:
                for p in range(1, 51):
                    for size in (10, 20, 50, 100):
                        cache.delete(f"{LEADERBOARD_FROZEN_CACHE_PREFIX}:page_{p}_size_{size}")
    except Exception as e:
        logger.warning("Redis cache invalidation error for frozen leaderboard: %s", e)


def fetch_leaderboard_data(page: int = 1, page_size: int = 20, current_participant: Participant | None = None) -> dict:
    """
    Fetches paginated leaderboard data from cache or authoritative PostgreSQL database.
    Respects EventConfig.leaderboard_frozen state (M7-T2).
    Includes the requester's own rank if requested/authenticated (M7-T1).
    """
    config = EventConfig.get_solo()
    is_frozen = bool(config.leaderboard_frozen)

    cached_page = get_cached_leaderboard_page(page=page, page_size=page_size, is_frozen=is_frozen)
    if cached_page is not None:
        count = cached_page['count']
        total_pages = cached_page['total_pages']
        results = cached_page['results']
    else:
        # Cache miss or Redis down: calculate from authoritative database
        total_count = Participant.objects.filter(is_suspended=False).count()
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
        offset = (page - 1) * page_size

        if offset >= total_count and total_count > 0:
            results = []
        else:
            qs = list(get_leaderboard_queryset()[offset : offset + page_size])
            today = get_event_today()
            participant_ids = [row.id for row in qs]
            daily_usages = {
                u.participant_id: u
                for u in DailyContributionUsage.objects.filter(participant_id__in=participant_ids, date=today)
            }
            daily_points_limit = config.max_points_per_day
            daily_contrib_limit = config.max_contributions_per_day

            results = []
            for row in qs:
                usage = daily_usages.get(row.id)
                pts_today = usage.points_count if usage else 0
                contribs_today = usage.contributions_count if usage else 0
                rem_allowance = max(0, daily_points_limit - pts_today)
                limit_hit = (pts_today >= daily_points_limit) or (contribs_today >= daily_contrib_limit)

                results.append({
                    'rank': row.rank,
                    'participant_id': row.id,
                    'github_username': row.github_username,
                    'avatar_url': row.avatar_url,
                    'total_points': row.total_points,
                    'merged_count': row.merged_count,
                    'points_today': pts_today,
                    'daily_limit': daily_points_limit,
                    'remaining_daily_allowance': rem_allowance,
                    'is_daily_limit_reached': limit_hit,
                })

        page_data = {
            'count': total_count,
            'total_pages': total_pages,
            'results': results,
        }
        set_cached_leaderboard_page(page=page, page_size=page_size, is_frozen=is_frozen, data=page_data)
        count = total_count

    # Resolve requester's own rank if participant is authenticated
    me_data = None
    if current_participant is not None:
        rank = calculate_participant_rank(current_participant.id)
        if rank is not None:
            today = get_event_today()
            me_usage = DailyContributionUsage.objects.filter(participant=current_participant, date=today).first()
            me_pts_today = me_usage.points_count if me_usage else 0
            me_contribs_today = me_usage.contributions_count if me_usage else 0
            me_daily_points_limit = config.max_points_per_day
            me_daily_contrib_limit = config.max_contributions_per_day
            me_rem = max(0, me_daily_points_limit - me_pts_today)
            me_limit_hit = (me_pts_today >= me_daily_points_limit) or (me_contribs_today >= me_daily_contrib_limit)

            me_data = {
                'rank': rank,
                'participant_id': current_participant.id,
                'github_username': current_participant.github_username,
                'avatar_url': current_participant.avatar_url,
                'total_points': current_participant.total_points,
                'merged_count': current_participant.merged_count,
                'points_today': me_pts_today,
                'daily_limit': me_daily_points_limit,
                'remaining_daily_allowance': me_rem,
                'is_daily_limit_reached': me_limit_hit,
            }

    return {
        'count': count,
        'page': page,
        'page_size': page_size,
        'total_pages': total_pages,
        'is_frozen': is_frozen,
        'results': results,
        'me': me_data,
    }


def generate_leaderboard_json(as_of_date=None) -> dict:
    """
    Generates an authoritative, repository-friendly persistent leaderboard data structure.
    Adheres strictly to the requested event schema:
    {
      "event": "HackIT CommitRush Open Source Contribution Drive",
      "timezone": "Asia/Kolkata",
      "daily_limit": 120,
      "participants": {
        "userA": {
          "rank": 1,
          "total_points": 450,
          "counted_prs": 15,
          "today_points": 110,
          "remaining_today": 10,
          "daily": {
            "2026-09-23": {
              "points": 110,
              "merged_prs": 4
            }
          }
        }
      }
    }
    """
    config = EventConfig.get_solo()
    target_date = as_of_date or get_event_today()
    daily_cap = config.max_points_per_day or DAILY_POINTS_CAP

    qs = list(get_leaderboard_queryset())
    participant_ids = [p.id for p in qs]

    # Pre-fetch all daily usages grouped by participant
    all_usages = DailyContributionUsage.objects.filter(participant_id__in=participant_ids).order_by('date')
    usages_by_participant: dict[int, list[DailyContributionUsage]] = {}
    for u in all_usages:
        usages_by_participant.setdefault(u.participant_id, []).append(u)

    participants_map = {}
    for p in qs:
        p_usages = usages_by_participant.get(p.id, [])
        daily_map = {}
        pts_today = 0
        for u in p_usages:
            d_str = u.date.isoformat()
            daily_map[d_str] = {
                'points': u.points_count,
                'merged_prs': u.contributions_count,
            }
            if u.date == target_date:
                pts_today = u.points_count

        remaining_today = max(0, daily_cap - pts_today)

        participants_map[p.github_username] = {
            'rank': p.rank,
            'github_username': p.github_username,
            'total_points': p.total_points,
            'counted_prs': p.merged_count,
            'today_points': pts_today,
            'remaining_today': remaining_today,
            'daily_limit': daily_cap,
            'is_daily_limit_reached': pts_today >= daily_cap,
            'daily': daily_map,
        }

    return {
        'event': 'HackIT CommitRush Open Source Contribution Drive',
        'repository': 'Hackit-DROID/Open-Source-Contribution-Drive',
        'timezone': 'Asia/Kolkata',
        'generated_at': get_event_now().isoformat(),
        'date': target_date.isoformat(),
        'daily_limit': daily_cap,
        'participants': participants_map,
    }
