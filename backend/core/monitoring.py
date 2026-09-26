import logging
import time
from datetime import timedelta
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from core.github_sync import GitHubClient
from core.models import (
    Contribution,
    DailyContributionUsage,
    EventConfig,
    Participant,
    PointTransaction,
    Project,
    PullRequest,
    WebhookEvent,
)
from core.notifications import NotificationManager

logger = logging.getLogger(__name__)

WORKER_HEARTBEAT_KEY = 'commitrush:heartbeat:worker'
BEAT_HEARTBEAT_KEY = 'commitrush:heartbeat:beat'
LAST_RECONCILIATION_KEY = 'commitrush:monitoring:last_reconciliation'
LAST_PR_SYNC_KEY = 'commitrush:monitoring:last_pr_sync'

HEARTBEAT_TTL_SECONDS = 300  # 5 minutes threshold for worker/beat staleness


def record_worker_heartbeat(worker_name: str = 'celery_worker'):
    """Called by Celery worker to record active health."""
    try:
        cache.set(WORKER_HEARTBEAT_KEY, {
            'worker': worker_name,
            'timestamp': timezone.now().isoformat(),
            'time_ts': time.time(),
        }, timeout=HEARTBEAT_TTL_SECONDS * 2)
    except Exception as e:
        logger.warning("Failed to record worker heartbeat: %s", e)


def record_beat_heartbeat():
    """Called by Celery Beat to record active scheduling health."""
    try:
        cache.set(BEAT_HEARTBEAT_KEY, {
            'timestamp': timezone.now().isoformat(),
            'time_ts': time.time(),
        }, timeout=HEARTBEAT_TTL_SECONDS * 2)
    except Exception as e:
        logger.warning("Failed to record beat heartbeat: %s", e)


def record_reconciliation_event(project_name: str, prs_count: int, issues_count: int):
    """Called when reconciliation completes successfully."""
    try:
        cache.set(LAST_RECONCILIATION_KEY, {
            'timestamp': timezone.now().isoformat(),
            'time_ts': time.time(),
            'project': project_name,
            'prs_count': prs_count,
            'issues_count': issues_count,
        }, timeout=86400)
    except Exception as e:
        logger.warning("Failed to record reconciliation event: %s", e)


def record_pr_sync_event(pr_number: int, repo_full_name: str, status: str):
    """Called when a PR is synchronized."""
    try:
        cache.set(LAST_PR_SYNC_KEY, {
            'timestamp': timezone.now().isoformat(),
            'time_ts': time.time(),
            'pr_number': pr_number,
            'repo': repo_full_name,
            'status': status,
        }, timeout=86400)
    except Exception as e:
        logger.warning("Failed to record PR sync event: %s", e)


def get_system_health(include_github_api: bool = True) -> dict:
    """
    Comprehensive, authoritative production health monitor.
    Checks:
    - Backend availability
    - Neon PostgreSQL connectivity
    - Upstash Redis connectivity
    - Celery worker activity
    - Celery Beat activity
    - GitHub API connectivity & rate limit
    - Webhook pipeline status
    - Reconciliation execution
    - Failed tasks / queue backlog
    - Scoring pipeline consistency
    """
    health = {
        'status': 'HEALTHY',
        'timestamp': timezone.now().isoformat(),
        'components': {},
        'metrics': {},
        'alerts': [],
    }

    # 1. Django Backend
    health['components']['backend'] = {
        'status': 'HEALTHY',
        'debug': getattr(settings, 'DEBUG', False),
    }

    # 2. Neon Database
    db_start = time.time()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            row = cursor.fetchone()
            if row and (row[0] == 1 or row == (1,)):
                db_latency = int((time.time() - db_start) * 1000)
                health['components']['neon_database'] = {
                    'status': 'HEALTHY',
                    'latency_ms': db_latency,
                }
            else:
                health['components']['neon_database'] = {
                    'status': 'UNHEALTHY',
                    'error': 'Unexpected query response',
                }
                health['status'] = 'UNHEALTHY'
    except Exception as e:
        health['components']['neon_database'] = {
            'status': 'UNHEALTHY',
            'error': str(e),
        }
        health['status'] = 'UNHEALTHY'

    # 3. Upstash Redis Cache & Broker
    redis_start = time.time()
    probe_key = '__commitrush_health_probe__'
    try:
        cache.set(probe_key, 'probe_value', timeout=10)
        val = cache.get(probe_key)
        cache.delete(probe_key)
        if val == 'probe_value':
            redis_latency = int((time.time() - redis_start) * 1000)
            health['components']['upstash_redis'] = {
                'status': 'HEALTHY',
                'latency_ms': redis_latency,
            }
        else:
            health['components']['upstash_redis'] = {
                'status': 'DEGRADED',
                'error': 'Cache read mismatch',
            }
            if health['status'] != 'UNHEALTHY':
                health['status'] = 'DEGRADED'
    except Exception as e:
        health['components']['upstash_redis'] = {
            'status': 'UNHEALTHY',
            'error': str(e),
        }
        health['status'] = 'UNHEALTHY'

    # 4. Celery Worker Heartbeat
    try:
        worker_data = cache.get(WORKER_HEARTBEAT_KEY)
        now_ts = time.time()
        if worker_data and (now_ts - worker_data.get('time_ts', 0)) < HEARTBEAT_TTL_SECONDS:
            age = int(now_ts - worker_data['time_ts'])
            health['components']['celery_worker'] = {
                'status': 'HEALTHY',
                'last_heartbeat_seconds_ago': age,
                'worker': worker_data.get('worker', 'default'),
            }
        else:
            last_seen = worker_data.get('timestamp') if worker_data else 'never'
            health['components']['celery_worker'] = {
                'status': 'DEGRADED' if worker_data else 'UNHEALTHY',
                'last_heartbeat': last_seen,
                'note': 'Worker heartbeat missing or stale (>5m)',
            }
            if health['status'] == 'HEALTHY':
                health['status'] = 'DEGRADED'
    except Exception:
        health['components']['celery_worker'] = {'status': 'UNKNOWN'}

    # 5. Celery Beat Heartbeat
    try:
        beat_data = cache.get(BEAT_HEARTBEAT_KEY)
        now_ts = time.time()
        if beat_data and (now_ts - beat_data.get('time_ts', 0)) < HEARTBEAT_TTL_SECONDS:
            age = int(now_ts - beat_data['time_ts'])
            health['components']['celery_beat'] = {
                'status': 'HEALTHY',
                'last_heartbeat_seconds_ago': age,
            }
        else:
            last_seen = beat_data.get('timestamp') if beat_data else 'never'
            health['components']['celery_beat'] = {
                'status': 'DEGRADED' if beat_data else 'UNHEALTHY',
                'last_heartbeat': last_seen,
                'note': 'Beat scheduler heartbeat missing or stale (>5m)',
            }
            if health['status'] == 'HEALTHY':
                health['status'] = 'DEGRADED'
    except Exception:
        health['components']['celery_beat'] = {'status': 'UNKNOWN'}

    # 6. GitHub API Connectivity & Rate Limit
    if include_github_api:
        try:
            client = GitHubClient(timeout=5)
            # Lightweight rate limit check
            headers = client._get_headers()
            resp = client.session.get(f"{client.base_url}/rate_limit", headers=headers, timeout=5)
            client._record_rate_limit(resp)
            rl = client.last_rate_limit
            remaining = rl.get('remaining', 0)
            limit = rl.get('limit', 0)
            is_low = client.is_low_quota(0.10)

            health['components']['github_api'] = {
                'status': 'HEALTHY' if not is_low else 'DEGRADED',
                'remaining': remaining,
                'limit': limit,
                'reset_timestamp': rl.get('reset'),
            }
            if is_low and health['status'] == 'HEALTHY':
                health['status'] = 'DEGRADED'
        except Exception as e:
            health['components']['github_api'] = {
                'status': 'DEGRADED',
                'error': str(e),
            }

    # 7. Webhook Pipeline Status
    try:
        one_hour_ago = timezone.now() - timedelta(hours=1)
        recent_webhooks = WebhookEvent.objects.filter(processed_at__gte=one_hour_ago).count()
        unprocessed_webhooks = WebhookEvent.objects.filter(processed_at__isnull=True).count()
        failed_webhooks = WebhookEvent.objects.filter(processing_error__gt='').count()

        health['components']['webhook_pipeline'] = {
            'status': 'HEALTHY' if failed_webhooks == 0 and unprocessed_webhooks < 20 else 'DEGRADED',
            'recent_processed_1h': recent_webhooks,
            'unprocessed_backlog': unprocessed_webhooks,
            'failed_count': failed_webhooks,
        }
    except Exception as e:
        health['components']['webhook_pipeline'] = {'status': 'UNKNOWN', 'error': str(e)}

    # 8. Reconciliation Status
    try:
        rec_data = cache.get(LAST_RECONCILIATION_KEY)
        now_ts = time.time()
        if rec_data:
            age_min = int((now_ts - rec_data.get('time_ts', now_ts)) / 60)
            health['components']['reconciliation'] = {
                'status': 'HEALTHY' if age_min < 30 else 'DEGRADED',
                'last_reconciliation_minutes_ago': age_min,
                'project': rec_data.get('project'),
            }
        else:
            health['components']['reconciliation'] = {
                'status': 'HEALTHY',
                'last_reconciliation': 'pending_first_run',
            }
    except Exception:
        health['components']['reconciliation'] = {'status': 'UNKNOWN'}

    # 9. Scoring & Contributions
    try:
        stuck_contribs = Contribution.objects.filter(
            status__in=['UNDER_REVIEW', 'MERGING'],
            locked_at__lt=timezone.now() - timedelta(minutes=10),
        ).count()
        flagged_contribs = Contribution.objects.filter(status='FLAGGED').count()

        health['components']['scoring_engine'] = {
            'status': 'HEALTHY' if stuck_contribs == 0 else 'DEGRADED',
            'stuck_contributions': stuck_contribs,
            'flagged_contributions': flagged_contribs,
        }
    except Exception as e:
        health['components']['scoring_engine'] = {'status': 'UNKNOWN', 'error': str(e)}

    # 10. Recent PR Activity
    pr_sync = cache.get(LAST_PR_SYNC_KEY)
    health['metrics']['last_pr_processed'] = pr_sync if pr_sync else None

    # Check for actionable alerts
    unhealthy_comps = [k for k, v in health['components'].items() if v.get('status') == 'UNHEALTHY']
    if unhealthy_comps:
        health['status'] = 'UNHEALTHY'
        NotificationManager.send_alert(
            subject=f"CommitRush Pipeline Outage: {', '.join(unhealthy_comps)}",
            message=f"System health degraded. Unhealthy components: {unhealthy_comps}\nHealth Report: {health['components']}",
            level='CRITICAL',
            alert_key='system_outage',
            metadata={'unhealthy': unhealthy_comps},
        )
    else:
        NotificationManager.resolve_alert(
            subject="CommitRush Pipeline Fully Recovered",
            message="All components (Neon, Upstash, Worker, Beat, GitHub) are reporting healthy status.",
            alert_key='system_outage',
        )

    return health


class HealthMonitor:
    """
    Subsystem health monitor interface.
    """
    @staticmethod
    def record_worker_heartbeat(worker_name: str = 'celery_worker'):
        return record_worker_heartbeat(worker_name)

    @staticmethod
    def record_beat_heartbeat():
        return record_beat_heartbeat()

    def check_system_health(self, include_consistency: bool = False) -> dict:
        health = get_system_health()
        health['overall_status'] = health['status']
        health['database'] = health['components'].get('neon_database', {})
        health['redis'] = health['components'].get('upstash_redis', {})
        health['celery_worker'] = health['components'].get('celery_worker', {})
        health['celery_beat'] = health['components'].get('celery_beat', {})
        if include_consistency:
            from core.consistency_checker import scan_system_consistency
            health['consistency'] = scan_system_consistency(auto_repair=False)
        return health

