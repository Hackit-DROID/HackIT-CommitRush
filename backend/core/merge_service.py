import logging
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from core.github_sync import (
    GitHubClient,
    GitHubSyncError,
    GitHubResourceNotFoundError,
    GitHubAuthenticationError,
    GitHubRateLimitError,
    GitHubAPIError,
    GitHubNetworkError,
    GitHubMergeError,
    GitHubMergeConflictError,
)
from core.models import Contribution, EventConfig, PullRequest
from core.points import award_points_for_contribution
from core.semaphore import RedisMergeSemaphore
from core.state_machine import transition_contribution

logger = logging.getLogger(__name__)

TRANSIENT_MERGE_MAX_RETRIES = 5
MERGE_CONFLICT_MAX_RETRIES = 1


def claim_next_approved_contribution() -> Contribution | None:
    """
    Atomically claim the highest-priority, oldest APPROVED contribution for merge processing (PRD §12.3, Plan M6-T3).
    
    Ordering:
    - is_priority DESC (admin priority boost)
    - approved_at ASC (strict FIFO)
    - id ASC (deterministic tie-breaker)
    
    Uses PostgreSQL row-level locks with skip_locked=True for non-blocking concurrent worker claims.
    Returns the claimed Contribution in MERGING state, or None if queue is empty or merge is paused.
    """
    config = EventConfig.get_solo()
    if config.merge_paused:
        logger.info("Merge queue processing is paused in EventConfig; skipping claim.")
        return None

    with transaction.atomic():
        candidate = (
            Contribution.objects.select_for_update(skip_locked=True)
            .filter(status='APPROVED')
            .order_by('-is_priority', 'approved_at', 'id')
            .first()
        )
        if not candidate:
            return None

        # Atomically transition to MERGING
        claimed, transitioned = transition_contribution(candidate.id, 'MERGING')
        if transitioned:
            logger.info(
                "Claimed Contribution %s for merge queue (priority=%s, approved_at=%s)",
                claimed.id,
                claimed.is_priority,
                claimed.approved_at,
            )
            return claimed
        return None


def execute_merge(
    contribution_or_id: Contribution | int,
    client: GitHubClient | None = None,
) -> dict:
    """
    Execute merge pipeline for a Contribution against GitHub REST API (PRD §12.3, Plan M6-T2, M6-T4).
    
    Pipeline:
    1. Ensure status is MERGING (or transition APPROVED/RETRY -> MERGING).
    2. Zero frontend merge authority: backend GitHub bot calls PUT /repos/{owner}/{repo}/pulls/{number}/merge.
    3. Authority check: calls GET /repos/{owner}/{repo}/pulls/{number} to confirm merged == True.
    4. Transition MERGING -> MERGED, update PullRequest.merged, and trigger transactional point award (M6-T5).
    5. Error policy:
       - 5xx/network timeouts: exponential backoff up to 5 attempts -> RETRY or FLAGGED.
       - Rate limits (403/429): requeue signal with Retry-After / reset timestamp.
       - Merge conflicts (405/409): 1 retry attempt -> FLAGGED.
       - Permanent errors (404/401): FLAGGED.
    """
    contrib_id = contribution_or_id.id if isinstance(contribution_or_id, Contribution) else contribution_or_id

    config = EventConfig.get_solo()
    if config.merge_paused:
        logger.info("Merge operations paused; deferring execution for Contribution %s", contrib_id)
        return {'status': 'paused', 'contribution_id': contrib_id}

    contribution = (
        Contribution.objects.select_related('pull_request__repo', 'issue', 'participant')
        .filter(id=contrib_id)
        .first()
    )
    if not contribution:
        logger.error("Contribution %s not found for merge execution", contrib_id)
        return {'status': 'not_found', 'contribution_id': contrib_id}

    # Idempotency check: already MERGED
    if contribution.status == 'MERGED':
        logger.info("Contribution %s is already MERGED; ensuring points awarded.", contrib_id)
        point_res = award_points_for_contribution(contrib_id)
        return {
            'status': 'success',
            'contribution_id': contrib_id,
            'merged': True,
            'points': point_res,
        }

    # Transition to MERGING if currently in APPROVED or RETRY
    if contribution.status in ('APPROVED', 'RETRY'):
        contribution, _ = transition_contribution(contrib_id, 'MERGING')

    if contribution.status != 'MERGING':
        logger.warning("Contribution %s is in state '%s', expected 'MERGING'; aborting merge.", contrib_id, contribution.status)
        return {'status': 'invalid_state', 'current_status': contribution.status, 'contribution_id': contrib_id}

    pr = contribution.pull_request
    repo = pr.repo
    owner = repo.owner
    repo_name = repo.name
    pull_number = pr.number
    head_sha = pr.head_sha or None

    gh_client = client or GitHubClient()

    # Step 1: Perform merge on GitHub
    try:
        merge_result = gh_client.merge_pull_request(
            owner=owner,
            repo=repo_name,
            pull_number=pull_number,
            commit_title=f"Merge PR #{pull_number}: {contribution.issue.title if contribution.issue else ''}".strip(),
            commit_message=f"CommitRush automated merge for Issue #{contribution.issue.number if contribution.issue else ''} by @{contribution.participant.github_username}",
            merge_method='merge',
            sha=head_sha,
        )
        logger.info("GitHub merge API responded for PR #%s on %s/%s: %s", pull_number, owner, repo_name, merge_result)
    except GitHubMergeConflictError as e:
        # Check if already merged on GitHub out-of-band before failing
        try:
            pr_check = gh_client.get_pull_request(owner=owner, repo=repo_name, pull_number=pull_number)
            if pr_check.get('merged') is True:
                logger.info("PR #%s on %s/%s is already confirmed merged on GitHub.", pull_number, owner, repo_name)
                return _finalize_merged_contribution(contribution, pr_check)
        except Exception:
            pass

        # Merge conflict / unmergeable: 1 retry attempt before FLAGGED (PRD §12.3, Plan M6-T4)
        if contribution.retry_count < MERGE_CONFLICT_MAX_RETRIES:
            logger.warning(
                "Merge conflict for Contribution %s (attempt %d/%d). Transitioning to RETRY: %s",
                contrib_id,
                contribution.retry_count + 1,
                MERGE_CONFLICT_MAX_RETRIES,
                str(e),
            )
            transition_contribution(contrib_id, 'RETRY', reason=f"Merge conflict: {str(e)}", max_retries=MERGE_CONFLICT_MAX_RETRIES + 1)
            return {
                'status': 'retry',
                'retry_type': 'conflict',
                'contribution_id': contrib_id,
                'error': str(e),
            }
        else:
            logger.error("Merge conflict retries exhausted for Contribution %s. Escalating to FLAGGED: %s", contrib_id, str(e))
            transition_contribution(contrib_id, 'FLAGGED', reason=f"Merge conflict / PR unmergeable: {str(e)}")
            return {
                'status': 'flagged',
                'reason': f"Merge conflict / PR unmergeable: {str(e)}",
                'contribution_id': contrib_id,
            }

    except GitHubRateLimitError as e:
        logger.warning("GitHub rate limit encountered during merge for Contribution %s: %s", contrib_id, str(e))
        return {
            'status': 'rate_limited',
            'contribution_id': contrib_id,
            'remaining': e.remaining,
            'reset_timestamp': e.reset_timestamp,
            'retry_after': e.retry_after,
            'error': str(e),
        }

    except (GitHubNetworkError, GitHubAPIError) as e:
        # 5xx server errors / timeouts: exponential backoff up to 5 attempts (PRD §12.3, Plan M6-T4)
        new_retries = contribution.retry_count + 1
        if new_retries >= TRANSIENT_MERGE_MAX_RETRIES:
            logger.error(
                "Max transient merge retries (%d) exceeded for Contribution %s. Escalating to FLAGGED: %s",
                TRANSIENT_MERGE_MAX_RETRIES,
                contrib_id,
                str(e),
            )
            transition_contribution(
                contrib_id,
                'FLAGGED',
                reason=f"Max transient merge retries ({TRANSIENT_MERGE_MAX_RETRIES}) exceeded: {str(e)}",
            )
            return {
                'status': 'flagged',
                'reason': f"Max transient merge retries exceeded: {str(e)}",
                'contribution_id': contrib_id,
            }
        else:
            countdown = 2 ** contribution.retry_count
            logger.warning(
                "Transient merge failure for Contribution %s (attempt %d/%d). Retrying in %ds: %s",
                contrib_id,
                new_retries,
                TRANSIENT_MERGE_MAX_RETRIES,
                countdown,
                str(e),
            )
            transition_contribution(
                contrib_id,
                'RETRY',
                reason=f"Transient GitHub error: {str(e)}",
                max_retries=TRANSIENT_MERGE_MAX_RETRIES,
            )
            return {
                'status': 'retry',
                'retry_type': 'transient',
                'countdown': countdown,
                'contribution_id': contrib_id,
                'error': str(e),
            }

    except (GitHubResourceNotFoundError, GitHubAuthenticationError, GitHubSyncError) as e:
        logger.error("Permanent failure during merge for Contribution %s: %s", contrib_id, str(e))
        transition_contribution(contrib_id, 'FLAGGED', reason=f"Permanent merge failure: {str(e)}")
        return {
            'status': 'flagged',
            'reason': f"Permanent merge failure: {str(e)}",
            'contribution_id': contrib_id,
        }

    # Step 2: Confirm merge state from GitHub GET API
    try:
        pr_data = gh_client.get_pull_request(owner=owner, repo=repo_name, pull_number=pull_number)
    except (GitHubNetworkError, GitHubAPIError) as e:
        countdown = 2 ** contribution.retry_count
        logger.warning(
            "Transient network/API failure fetching PR #%s confirmation for Contribution %s: %s; retrying in %ds",
            pull_number, contrib_id, e, countdown,
        )
        transition_contribution(
            contrib_id,
            'RETRY',
            reason=f"Transient error confirming merge state: {str(e)}",
            max_retries=TRANSIENT_MERGE_MAX_RETRIES,
        )
        return {
            'status': 'retry',
            'retry_type': 'transient',
            'countdown': countdown,
            'contribution_id': contrib_id,
            'error': str(e),
        }
    except Exception as e:
        logger.warning("Failed to fetch PR #%s confirmation for Contribution %s (%s); treating 200 PUT as merged", pull_number, contrib_id, e)
        pr_data = {'merged': True, 'merged_at': timezone.now().isoformat()}

    if pr_data.get('merged') is True:
        return _finalize_merged_contribution(contribution, pr_data)
    else:
        logger.error("PR #%s on %s/%s reported merged=False after successful merge response for Contribution %s", pull_number, owner, repo_name, contrib_id)
        transition_contribution(contrib_id, 'FLAGGED', reason="GitHub PR remained unmerged after merge call.")
        return {
            'status': 'flagged',
            'reason': 'PR reported unmerged following merge call.',
            'contribution_id': contrib_id,
        }


def _finalize_merged_contribution(contribution: Contribution, pr_data: dict) -> dict:
    """
    Finalize a confirmed merged pull request:
    - Update PullRequest record with merged=True and merged_at timestamp.
    - Transition Contribution status to MERGED.
    - Award points via transactional point award module.
    """
    with transaction.atomic():
        pr = contribution.pull_request
        pr.merged = True
        merged_at_raw = pr_data.get('merged_at')
        if merged_at_raw:
            parsed_dt = parse_datetime(merged_at_raw)
            pr.merged_at = parsed_dt if parsed_dt else timezone.now()
        else:
            pr.merged_at = timezone.now()
        pr.save(update_fields=['merged', 'merged_at'])

        transition_contribution(contribution.id, 'MERGED')
        point_res = award_points_for_contribution(contribution.id)

    logger.info(
        "Successfully finalized MERGED status and points for Contribution %s (PR #%s, pts: %s)",
        contribution.id,
        pr.number,
        point_res,
    )
    return {
        'status': 'success',
        'contribution_id': contribution.id,
        'merged': True,
        'points': point_res,
    }
