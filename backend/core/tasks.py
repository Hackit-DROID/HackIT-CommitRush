import logging
import time
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from core.github_sync import (
    GitHubClient,
    GitHubSyncError,
    GitHubResourceNotFoundError,
    GitHubAuthenticationError,
    GitHubRateLimitError,
    GitHubAPIError,
    GitHubNetworkError,
    GitHubDataError,
    parse_repo_identifier,
    sync_repository_and_issues,
)

logger = logging.getLogger(__name__)

LOW_QUOTA_SAFETY_THRESHOLD = 0.10  # 10% safety threshold per PRD §13.6
TRANSIENT_MAX_RETRIES = 5


@shared_task(
    bind=True,
    name='core.tasks.sync_repository_task',
    queue='sync',
    max_retries=TRANSIENT_MAX_RETRIES,
)
def sync_repository_task(
    self,
    repo_identifier: str,
    sync_issues: bool = True,
    rate_limit_retries: int = 0,
) -> dict:
    """
    Celery task to synchronize repository metadata and issues from GitHub REST API.
    Routed to the low-priority 'sync' queue (PRD §10.1, §13.6, plan.md M2-T4).
    
    Rate Limit Policy (PRD §13.6, M2-T4):
    - When HTTP 403 (rate limited), HTTP 429, or remaining quota < 10% is detected,
      the task deprioritizes/requeues itself using Retry-After or X-RateLimit-Reset timestamp.
    - Rate limit retries do NOT count against the normal transient retry budget.
    
    Transient Failure Policy:
    - 5xx server errors, timeouts, and network connection drops use bounded exponential backoff
      with a maximum of 5 attempts.
    
    Permanent Failure Policy:
    - 401 authentication failures, 404 missing repositories, malformed response data,
      and invalid repository identifiers are NOT retried.
    """
    try:
        owner, repo = parse_repo_identifier(repo_identifier)
    except ValueError as e:
        logger.error("Permanent validation error in sync_repository_task: %s", str(e))
        return {
            'status': 'failed',
            'error': str(e),
            'repo': repo_identifier,
            'permanent': True,
        }

    client = GitHubClient()

    try:
        project, repo_created, issues_created, issues_updated = sync_repository_and_issues(
            f"{owner}/{repo}",
            client=client,
            sync_issues_flag=sync_issues,
        )
        return {
            'status': 'success',
            'repo': f"{owner}/{repo}",
            'project_id': project.id,
            'repo_created': repo_created,
            'issues_created': issues_created,
            'issues_updated': issues_updated,
        }

    except GitHubRateLimitError as e:
        # Rate limit handling: calculate delay from Retry-After or reset timestamp
        logger.warning(
            "GitHub rate limit / low quota for %s/%s (remaining: %s, limit: %s, reset: %s, retry_after: %s)",
            owner, repo, e.remaining, e.limit, e.reset_timestamp, e.retry_after,
        )
        delay = 60
        if e.retry_after is not None and e.retry_after > 0:
            delay = e.retry_after
        elif e.reset_timestamp is not None:
            now = int(time.time())
            delay = max(e.reset_timestamp - now, 10)

        # Requeue with countdown without incrementing the transient failure budget
        raise self.retry(
            exc=e,
            countdown=delay,
            max_retries=None,
            kwargs={
                'repo_identifier': repo_identifier,
                'sync_issues': sync_issues,
                'rate_limit_retries': rate_limit_retries + 1,
            },
        )

    except (GitHubNetworkError, GitHubAPIError) as e:
        # Transient failure: exponential backoff bounded to TRANSIENT_MAX_RETRIES
        transient_retries = self.request.retries
        if transient_retries >= TRANSIENT_MAX_RETRIES:
            logger.error(
                "Max retries (%d) exceeded for transient failure syncing %s/%s: %s",
                TRANSIENT_MAX_RETRIES, owner, repo, str(e),
            )
            raise

        countdown = 2 ** transient_retries
        logger.warning(
            "Transient failure syncing %s/%s (attempt %d/%d). Retrying in %ds: %s",
            owner, repo, transient_retries + 1, TRANSIENT_MAX_RETRIES, countdown, str(e),
        )
        raise self.retry(
            exc=e,
            countdown=countdown,
            max_retries=TRANSIENT_MAX_RETRIES,
        )

    except (GitHubResourceNotFoundError, GitHubAuthenticationError, GitHubDataError) as e:
        # Permanent failure: do not retry
        logger.error("Permanent GitHub error syncing %s/%s: %s", owner, repo, str(e))
        return {
            'status': 'failed',
            'error': str(e),
            'repo': f"{owner}/{repo}",
            'permanent': True,
        }

    except Exception as e:
        logger.exception("Unexpected error in sync_repository_task for %s/%s", owner, repo)
        raise


@shared_task(
    bind=True,
    name='core.tasks.process_webhook_event_task',
    queue='webhooks',
    max_retries=3,
)
def process_webhook_event_task(self, webhook_event_id: int) -> dict:
    """
    Celery task to asynchronously process inbound GitHub webhook events.
    Routed to the high-priority 'webhooks' queue (PRD §10.1, §12.1, §13.3, plan.md M4-T3).
    Idempotently handles pull_request and issues events.
    """
    from core.models import WebhookEvent
    from core.webhook_processing import process_webhook_event

    webhook_event = WebhookEvent.objects.filter(id=webhook_event_id).first()
    if not webhook_event:
        logger.warning("WebhookEvent %s not found for processing", webhook_event_id)
        return {'status': 'not_found', 'webhook_event_id': webhook_event_id}

    try:
        result = process_webhook_event(webhook_event)
        return {
            'status': 'success',
            'delivery_id': webhook_event.delivery_id,
            'result': result,
        }
    except Exception as e:
        logger.exception("Error processing webhook event %s (delivery_id=%s)", webhook_event_id, webhook_event.delivery_id)
        retries = self.request.retries
        if retries < 3:
            raise self.retry(exc=e, countdown=2 ** retries, max_retries=3)
        return {
            'status': 'failed',
            'delivery_id': webhook_event.delivery_id,
            'error': str(e),
        }


@shared_task(
    bind=True,
    name='core.tasks.reconcile_recent_repositories_task',
    queue='sync',
    max_retries=TRANSIENT_MAX_RETRIES,
)
def reconcile_recent_repositories_task(
    self,
    window_minutes: int | None = None,
    rate_limit_retries: int = 0,
) -> dict:
    """
    Scheduled Celery beat task to reconcile repositories with no recent webhook activity.
    Runs every N minutes (default 15). Routed to low-priority 'sync' queue.
    Rate-limit aware per PRD §13.6 and plan.md M4-T5.
    """
    from core.reconciliation import reconcile_recent_repositories

    client = GitHubClient()
    try:
        return reconcile_recent_repositories(window_minutes=window_minutes, client=client)
    except GitHubRateLimitError as e:
        logger.warning(
            "GitHub rate limit reached in reconcile_recent_repositories_task (remaining: %s, reset: %s, retry_after: %s)",
            e.remaining, e.reset_timestamp, e.retry_after,
        )
        delay = 60
        if e.retry_after is not None and e.retry_after > 0:
            delay = e.retry_after
        elif e.reset_timestamp is not None:
            now = int(time.time())
            delay = max(e.reset_timestamp - now, 10)

        raise self.retry(
            exc=e,
            countdown=delay,
            max_retries=None,
            kwargs={
                'window_minutes': window_minutes,
                'rate_limit_retries': rate_limit_retries + 1,
            },
        )
    except (GitHubNetworkError, GitHubAPIError) as e:
        transient_retries = self.request.retries
        if transient_retries >= TRANSIENT_MAX_RETRIES:
            logger.error(
                "Max retries (%d) exceeded in reconcile_recent_repositories_task: %s",
                TRANSIENT_MAX_RETRIES, str(e),
            )
            raise
        countdown = 2 ** transient_retries
        logger.warning(
            "Transient failure in reconcile_recent_repositories_task (attempt %d/%d). Retrying in %ds: %s",
            transient_retries + 1, TRANSIENT_MAX_RETRIES, countdown, str(e),
        )
        raise self.retry(
            exc=e,
            countdown=countdown,
            max_retries=TRANSIENT_MAX_RETRIES,
        )
    except Exception as e:
        logger.exception("Unexpected error in reconcile_recent_repositories_task")
        raise


@shared_task(
    bind=True,
    name='core.tasks.reconcile_all_repositories_nightly_task',
    queue='sync',
    max_retries=TRANSIENT_MAX_RETRIES,
)
def reconcile_all_repositories_nightly_task(
    self,
    rate_limit_retries: int = 0,
) -> dict:
    """
    Scheduled Celery beat task to run full reconciliation across all tracked repositories nightly.
    Runs once daily. Routed to low-priority 'sync' queue.
    Rate-limit aware per PRD §13.6 and plan.md M4-T5.
    """
    from core.reconciliation import reconcile_all_repositories_nightly

    client = GitHubClient()
    try:
        return reconcile_all_repositories_nightly(client=client)
    except GitHubRateLimitError as e:
        logger.warning(
            "GitHub rate limit reached in reconcile_all_repositories_nightly_task (remaining: %s, reset: %s, retry_after: %s)",
            e.remaining, e.reset_timestamp, e.retry_after,
        )
        delay = 60
        if e.retry_after is not None and e.retry_after > 0:
            delay = e.retry_after
        elif e.reset_timestamp is not None:
            now = int(time.time())
            delay = max(e.reset_timestamp - now, 10)

        raise self.retry(
            exc=e,
            countdown=delay,
            max_retries=None,
            kwargs={
                'rate_limit_retries': rate_limit_retries + 1,
            },
        )
    except (GitHubNetworkError, GitHubAPIError) as e:
        transient_retries = self.request.retries
        if transient_retries >= TRANSIENT_MAX_RETRIES:
            logger.error(
                "Max retries (%d) exceeded in reconcile_all_repositories_nightly_task: %s",
                TRANSIENT_MAX_RETRIES, str(e),
            )
            raise
        countdown = 2 ** transient_retries
        logger.warning(
            "Transient failure in reconcile_all_repositories_nightly_task (attempt %d/%d). Retrying in %ds: %s",
            transient_retries + 1, TRANSIENT_MAX_RETRIES, countdown, str(e),
        )
        raise self.retry(
            exc=e,
            countdown=countdown,
            max_retries=TRANSIENT_MAX_RETRIES,
        )
    except Exception as e:
        logger.exception("Unexpected error in reconcile_all_repositories_nightly_task")
        raise


@shared_task(
    bind=True,
    name='core.tasks.validate_contribution_task',
    queue='validation',
    max_retries=3,
)
def validate_contribution_task(self, contribution_id: int) -> dict:
    """
    Celery task to execute deterministic validation on a QUEUED Contribution (PRD §11, §12.1, §22, plan.md M5-T2).
    Routed to the high-priority 'validation' queue.
    """
    from core.models import EventConfig
    from core.validation import validate_contribution

    config = EventConfig.get_solo()
    if config.validation_paused:
        logger.info("Validation pipeline paused; requeuing validate_contribution_task for Contribution %s", contribution_id)
        raise self.retry(countdown=30, max_retries=None)

    try:
        return validate_contribution(contribution_id)
    except Exception as e:
        logger.exception("Error in validate_contribution_task for Contribution %s", contribution_id)
        retries = self.request.retries
        if retries < 3:
            raise self.retry(exc=e, countdown=2 ** retries, max_retries=3)
        return {
            'status': 'failed',
            'contribution_id': contribution_id,
            'error': str(e),
        }


@shared_task(
    bind=True,
    name='core.tasks.requeue_stale_contributions_task',
    queue='sync',
    max_retries=3,
)
def requeue_stale_contributions_task(self, timeout_minutes: int | None = None) -> dict:
    """
    Periodic Celery beat task to sweep and recover crashed worker contributions (PRD §11.2, §12.4, plan.md M5-T3).
    Reverts stale UNDER_REVIEW / MERGING contributions to their prior queued state.
    """
    from core.crash_recovery import requeue_stale_contributions

    try:
        return requeue_stale_contributions(timeout_minutes=timeout_minutes)
    except Exception as e:
        logger.exception("Error in requeue_stale_contributions_task")
        raise
