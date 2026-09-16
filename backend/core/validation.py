import logging
from django.db import transaction
from django.utils import timezone

from core.models import Contribution, EventConfig
from core.state_machine import (
    InvalidStateTransitionError,
    transition_contribution,
)

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Base exception for validation errors."""
    pass


def run_deterministic_validation(contribution: Contribution) -> tuple[str, str]:
    """
    Run deterministic abuse and validity checks per PRD §22, plan.md M5-T2:
    
    Rule 1: Self-created issue farming check (§22):
    - If Issue.created_by_github_id == Contribution.participant.github_id -> REJECT.
    
    Rule 2: Repository & Issue integrity check:
    - Issue must be active and linked to the PR's repository.
    
    Rule 3: Duplicate active/approved PR check per issue (§22):
    - Only the first qualifying contribution per issue per participant is credited.
    - If the participant already has an APPROVED, MERGING, or MERGED contribution for this issue,
      the second is FLAGGED for admin review.
    
    Explicit non-goals (PRD §5, §22):
    - NO LOC-diff / trivial-diff heuristics.
    - NO synchronous GitHub calls.
    - NO point awarding (M6 scope).
    
    Returns (verdict: 'APPROVED' | 'REJECTED' | 'FLAGGED', reason: str).
    """
    issue = contribution.issue
    participant = contribution.participant
    repo = contribution.pull_request.repo

    # Rule 1: Self-created issue farming check
    if issue.created_by_github_id is not None and issue.created_by_github_id == participant.github_id:
        reason = (
            f"Self-created issue farming detected: Issue #{issue.number} was created by "
            f"GitHub ID {issue.created_by_github_id}, matching the PR author."
        )
        return 'REJECTED', reason

    # Rule 2: Issue integrity & project consistency
    if issue.status == 'disabled':
        return 'REJECTED', f"Issue #{issue.number} is disabled."

    if issue.project_id != repo.id:
        return 'REJECTED', f"Issue #{issue.number} does not belong to repository {repo.full_name}."

    # Rule 3: Duplicate PR check for the same issue by the same participant
    prior_successful = Contribution.objects.filter(
        participant=participant,
        issue=issue,
        status__in=['APPROVED', 'MERGING', 'MERGED'],
    ).exclude(id=contribution.id).exists()

    if prior_successful:
        reason = (
            f"Duplicate contribution pattern: Participant {participant.github_username} already has "
            f"an approved or merged contribution for Issue #{issue.number}."
        )
        return 'FLAGGED', reason

    return 'APPROVED', ""


def validate_contribution(contribution_id: int) -> dict:
    """
    Validation pipeline orchestrator for a single Contribution (M5-T2):
    1. Checks emergency pause (EventConfig.validation_paused).
    2. Transitions QUEUED -> UNDER_REVIEW (sub_status='VALIDATING').
    3. Runs deterministic rules.
    4. Transitions to APPROVED, REJECTED, or FLAGGED.
    
    Returns summary dictionary.
    """
    # Check emergency pause
    config = EventConfig.get_solo()
    if config.validation_paused:
        logger.info("Validation pipeline paused (EventConfig.validation_paused=True); deferring Contribution %s", contribution_id)
        return {
            'status': 'paused',
            'contribution_id': contribution_id,
            'reason': 'Validation pipeline paused by administrator',
        }

    try:
        # Step 1: Transition QUEUED -> UNDER_REVIEW
        contribution, _ = transition_contribution(
            contribution_id,
            target_status='UNDER_REVIEW',
            sub_status='VALIDATING',
        )

        # Step 2: Run deterministic validation rules
        verdict, reason = run_deterministic_validation(contribution)

        # Step 3: Transition to target verdict state
        updated_contrib, _ = transition_contribution(
            contribution_id,
            target_status=verdict,
            reason=reason,
        )

        if verdict == 'APPROVED':
            try:
                from core.tasks import process_merge_queue_task
                process_merge_queue_task.delay()
            except Exception as e:
                logger.warning("Could not enqueue process_merge_queue_task: %s", e)

        return {
            'status': verdict.lower(),
            'contribution_id': updated_contrib.id,
            'final_state': updated_contrib.status,
            'sub_status': updated_contrib.sub_status,
            'reason': reason,
        }

    except InvalidStateTransitionError as e:
        logger.warning("Invalid transition during validation of Contribution %s: %s", contribution_id, str(e))
        return {
            'status': 'invalid_transition',
            'contribution_id': contribution_id,
            'error': str(e),
        }
    except Exception as e:
        logger.exception("Unexpected error validating Contribution %s", contribution_id)
        # Attempt to transition to RETRY
        try:
            transition_contribution(
                contribution_id,
                target_status='RETRY',
                reason=str(e),
            )
        except Exception:
            pass
        raise
