import logging
from datetime import timedelta
from django.conf import settings
from django.db import models
from django.utils import timezone

from core.github_sync import (
    GitHubClient,
    GitHubRateLimitError,
    GitHubSyncError,
    sync_issues_for_project,
)
from core.models import Project, WebhookEvent
from core.webhook_processing import handle_pull_request_event

logger = logging.getLogger(__name__)


def has_recent_webhook_activity(project: Project, window_minutes: int) -> bool:
    """
    Check if a repository has received or processed any WebhookEvent within the given time window.
    Considers both unprocessed webhooks (processed_at=None) and recently processed webhooks.
    """
    cutoff = timezone.now() - timedelta(minutes=window_minutes)
    return WebhookEvent.objects.filter(
        models.Q(processed_at__gte=cutoff) | models.Q(processed_at__isnull=True),
        models.Q(payload__repository__id=project.github_repo_id)
        | models.Q(payload__repository__full_name__iexact=project.full_name),
    ).exists()


def reconcile_repository(project: Project, client: GitHubClient | None = None) -> dict:
    """
    Reconcile a single tracked repository against GitHub REST API (PRD §13.4, plan.md M4-T5).
    - Fetches all issues (open and closed) and synchronizes them into Issue/IssueLabel models.
    - Fetches all pull requests and feeds them through handle_pull_request_event for idempotent
      PullRequest caching and Contribution matching/transitions.
    
    Returns a dictionary summarizing the reconciliation outcome.
    """
    if not project or not project.is_enabled:
        logger.info("Skipping reconciliation for disabled or non-existent project: %s", project)
        return {'status': 'skipped', 'reason': 'Project is disabled or not found'}

    if client is None:
        client = GitHubClient()

    owner = project.owner
    repo = project.name

    logger.info("Starting reconciliation for repository %s", project.full_name)

    # 1. Reconcile Issues
    issues_data = client.get_issues(owner, repo, state='all')
    issues_created, issues_updated = sync_issues_for_project(project, issues_data)

    # 2. Reconcile Pull Requests
    prs_data = client.get_pull_requests(owner, repo, state='all')
    pr_stats = {
        'total_prs': len(prs_data),
        'contribution_created': 0,
        'contribution_updated': 0,
        'pr_merged': 0,
        'pr_rejected': 0,
        'pr_cached': 0,
        'submissions_paused': 0,
        'synchronized': 0,
        'other': 0,
    }

    for pr_item in prs_data:
        # Determine appropriate synthetic webhook action based on PR state
        if pr_item.get('merged_at') or pr_item.get('merged'):
            action = 'closed'
        elif (pr_item.get('state') or '').lower() == 'closed':
            action = 'closed'
        else:
            action = 'opened'

        synthetic_payload = {
            'action': action,
            'pull_request': pr_item,
            'repository': {
                'id': project.github_repo_id,
                'full_name': project.full_name,
                'name': project.name,
                'owner': {'login': project.owner},
            },
        }

        res = handle_pull_request_event(synthetic_payload)
        status_key = res.get('status', 'other')
        if status_key in pr_stats:
            pr_stats[status_key] += 1
        else:
            pr_stats['other'] += 1

    logger.info(
        "Completed reconciliation for %s: %d issues created, %d issues updated, %d PRs reconciled",
        project.full_name,
        issues_created,
        issues_updated,
        len(prs_data),
    )

    return {
        'status': 'success',
        'project_id': project.id,
        'full_name': project.full_name,
        'issues_created': issues_created,
        'issues_updated': issues_updated,
        'prs_reconciled': len(prs_data),
        'pr_stats': pr_stats,
    }


def reconcile_recent_repositories(
    window_minutes: int | None = None,
    client: GitHubClient | None = None,
) -> dict:
    """
    Scheduled Celery beat task every N minutes (configurable, e.g. 15).
    Pulls recent PR/issue activity per tracked repo via REST API for repos with
    NO recent webhook activity in the window (PRD §13.4, plan.md M4-T5).
    """
    if window_minutes is None:
        window_minutes = getattr(settings, 'RECONCILIATION_RECENT_WINDOW_MINUTES', 15)

    if client is None:
        client = GitHubClient()

    enabled_projects = list(Project.objects.filter(is_enabled=True).order_by('id'))
    reconciled = []
    skipped = []
    errors = []

    logger.info(
        "Running 15-minute reconciliation across %d enabled project(s) with window=%d min",
        len(enabled_projects),
        window_minutes,
    )

    for proj in enabled_projects:
        if has_recent_webhook_activity(proj, window_minutes):
            logger.info("Skipping reconciliation for %s: active webhook activity within %d min", proj.full_name, window_minutes)
            skipped.append({'project_id': proj.id, 'full_name': proj.full_name, 'reason': 'recent_webhook_activity'})
            continue

        try:
            res = reconcile_repository(proj, client=client)
            reconciled.append(res)
        except GitHubRateLimitError:
            # Re-raise rate limit error to allow Celery task to back off and requeue
            raise
        except Exception as e:
            logger.exception("Error during reconciliation for %s", proj.full_name)
            errors.append({'project_id': proj.id, 'full_name': proj.full_name, 'error': str(e)})

    return {
        'status': 'completed',
        'window_minutes': window_minutes,
        'total_projects': len(enabled_projects),
        'reconciled_count': len(reconciled),
        'skipped_count': len(skipped),
        'error_count': len(errors),
        'reconciled': reconciled,
        'skipped': skipped,
        'errors': errors,
    }


def reconcile_all_repositories_nightly(client: GitHubClient | None = None) -> dict:
    """
    Scheduled nightly full-repo reconciliation across all tracked repositories (PRD §13.4, plan.md M4-T5).
    Slower, comprehensive safety net for missed webhooks regardless of recent webhook timestamps.
    """
    if client is None:
        client = GitHubClient()

    enabled_projects = list(Project.objects.filter(is_enabled=True).order_by('id'))
    reconciled = []
    errors = []

    logger.info("Running nightly full-repo reconciliation across %d enabled project(s)", len(enabled_projects))

    for proj in enabled_projects:
        try:
            res = reconcile_repository(proj, client=client)
            reconciled.append(res)
        except GitHubRateLimitError:
            # Re-raise rate limit error to allow Celery task to back off and requeue
            raise
        except Exception as e:
            logger.exception("Error during nightly reconciliation for %s", proj.full_name)
            errors.append({'project_id': proj.id, 'full_name': proj.full_name, 'error': str(e)})

    return {
        'status': 'completed',
        'mode': 'nightly_full',
        'total_projects': len(enabled_projects),
        'reconciled_count': len(reconciled),
        'error_count': len(errors),
        'reconciled': reconciled,
        'errors': errors,
    }
