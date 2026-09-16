import logging
from django.db import transaction
from django.utils import timezone

from core.models import Contribution

logger = logging.getLogger(__name__)

MAX_VALIDATION_RETRIES = 3


class StateMachineError(Exception):
    """Base exception for state machine errors."""
    pass


class InvalidStateTransitionError(StateMachineError):
    """Raised when an invalid or disallowed state transition is attempted."""
    pass


class UnauthorizedTransitionError(InvalidStateTransitionError):
    """Raised when a restricted state transition is attempted by an unauthorized actor."""
    pass


# Canonical automatic transitions per PRD §11.2
ALLOWED_AUTOMATIC_TRANSITIONS: dict[str, set[str]] = {
    'PENDING': {'QUEUED', 'MERGED', 'REJECTED'},
    'QUEUED': {'UNDER_REVIEW', 'MERGED', 'REJECTED'},
    'UNDER_REVIEW': {'APPROVED', 'MERGED', 'REJECTED', 'FLAGGED', 'RETRY'},
    'RETRY': {'UNDER_REVIEW', 'MERGING', 'MERGED', 'FLAGGED', 'REJECTED'},
    'APPROVED': {'MERGING', 'MERGED', 'REJECTED'},
    'MERGING': {'MERGED', 'RETRY', 'FLAGGED', 'REJECTED'},
    'FLAGGED': {'MERGED', 'REJECTED'},
    'REJECTED': set(),
    'MERGED': set(),
}

# Manual / admin transitions per PRD §11.2
ALLOWED_MANUAL_TRANSITIONS: dict[str, set[str]] = {
    'FLAGGED': {'APPROVED', 'REJECTED'},
    'REJECTED': {'UNDER_REVIEW'},  # Admin override (rare)
    # Admin can reject any non-terminal state
    'PENDING': {'REJECTED'},
    'QUEUED': {'REJECTED'},
    'UNDER_REVIEW': {'REJECTED'},
    'APPROVED': {'REJECTED'},
    'MERGING': {'REJECTED'},
    'RETRY': {'REJECTED'},
}


def evaluate_pre_checks(contribution: Contribution) -> tuple[bool, str]:
    """
    Perform cheap pre-checks for a PENDING contribution per PRD §11.2:
    1. Repository is tracked and enabled.
    2. Issue is valid, tracked, and not disabled.
    3. Issue belongs to the repository being contributed to.
    4. Participant is registered and not suspended.
    
    Returns (passed: bool, reason: str).
    """
    repo = contribution.pull_request.repo
    if not repo or not repo.is_enabled:
        return False, "Repository is disabled or untracked."

    issue = contribution.issue
    if not issue or issue.status == 'disabled':
        return False, "Issue is disabled or untracked."

    if issue.project_id != repo.id:
        return False, "Issue does not belong to the repository of the pull request."

    participant = contribution.participant
    if not participant:
        return False, "Author is not registered as a participant."

    if participant.is_suspended:
        return False, "Participant is suspended from competition."

    return True, ""


def transition_contribution(
    contribution_or_id: Contribution | int,
    target_status: str,
    actor=None,
    reason: str = '',
    sub_status: str | None = None,
    max_retries: int = MAX_VALIDATION_RETRIES,
) -> tuple[Contribution, bool]:
    """
    Centralized, atomic state machine transition engine for Contribution records (PRD §11, plan.md M5-T1).
    Uses PostgreSQL row-level locks (select_for_update) inside an atomic transaction.
    
    Idempotent:
    - If already in target_status with matching sub_status, returns (contribution, False) without error.
    
    Enforces:
    - Allowed transition gating.
    - Admin-only authorization on manual actions (FLAGGED -> APPROVED/REJECTED, REJECTED -> UNDER_REVIEW).
    - Sub-status management (VALIDATING is represented as UNDER_REVIEW + sub_status='VALIDATING').
    - Lock timestamp clearing and status timestamp recording.
    - Retry exhaustion escalation to FLAGGED.
    
    Returns (contribution, transitioned: bool).
    Raises InvalidStateTransitionError if transition is invalid.
    """
    target_status = target_status.upper().strip()
    contrib_id = contribution_or_id.id if isinstance(contribution_or_id, Contribution) else contribution_or_id

    is_admin = False
    if actor:
        is_admin = bool(getattr(actor, 'is_staff', False) or getattr(actor, 'is_superuser', False))

    with transaction.atomic():
        contribution = Contribution.objects.select_for_update().get(id=contrib_id)
        current_status = (contribution.status or '').upper().strip()
        current_sub_status = contribution.sub_status or ''

        # Desired sub-status defaults
        expected_sub_status = sub_status if sub_status is not None else (
            'VALIDATING' if target_status == 'UNDER_REVIEW' else ''
        )

        # Idempotency check
        if current_status == target_status and current_sub_status == expected_sub_status:
            logger.debug("Contribution %s already in state %s (sub: %s); no-op.", contrib_id, current_status, expected_sub_status)
            return contribution, False

        # Determine allowed target statuses for current state
        auto_allowed = ALLOWED_AUTOMATIC_TRANSITIONS.get(current_status, set())
        manual_allowed = ALLOWED_MANUAL_TRANSITIONS.get(current_status, set())

        is_auto_valid = target_status in auto_allowed
        is_manual_valid = target_status in manual_allowed

        if not is_auto_valid and not is_manual_valid:
            error_msg = f"Invalid state transition: Cannot transition Contribution {contrib_id} from '{current_status}' to '{target_status}'."
            logger.warning(error_msg)
            raise InvalidStateTransitionError(error_msg)

        if not is_auto_valid and is_manual_valid and not is_admin:
            error_msg = f"Unauthorized state transition: Transitioning Contribution {contrib_id} from '{current_status}' to '{target_status}' requires administrator privileges."
            logger.warning(error_msg)
            raise UnauthorizedTransitionError(error_msg)

        now = timezone.now()
        update_fields = ['status', 'sub_status', 'updated_at']

        # Apply state-specific side effects
        if target_status == 'QUEUED':
            contribution.status = 'QUEUED'
            contribution.sub_status = ''
            contribution.locked_at = None
            update_fields.append('locked_at')

        elif target_status == 'UNDER_REVIEW':
            contribution.status = 'UNDER_REVIEW'
            contribution.sub_status = expected_sub_status
            contribution.locked_at = now
            update_fields.append('locked_at')

        elif target_status == 'APPROVED':
            contribution.status = 'APPROVED'
            contribution.sub_status = ''
            contribution.locked_at = None
            contribution.approved_at = now
            update_fields.extend(['locked_at', 'approved_at'])

        elif target_status == 'REJECTED':
            contribution.status = 'REJECTED'
            contribution.sub_status = ''
            contribution.locked_at = None
            update_fields.append('locked_at')
            if reason:
                contribution.flagged_reason = reason
                update_fields.append('flagged_reason')

        elif target_status == 'FLAGGED':
            contribution.status = 'FLAGGED'
            contribution.sub_status = ''
            contribution.locked_at = None
            update_fields.append('locked_at')
            if reason:
                contribution.flagged_reason = reason
                update_fields.append('flagged_reason')

        elif target_status == 'RETRY':
            new_retry_count = contribution.retry_count + 1
            if new_retry_count >= max_retries:
                # Retries exhausted -> transition to FLAGGED per PRD §11.2
                contribution.status = 'FLAGGED'
                contribution.sub_status = ''
                contribution.locked_at = None
                contribution.retry_count = new_retry_count
                contribution.flagged_reason = f"Max validation retries ({max_retries}) exceeded: {reason}" if reason else f"Max validation retries ({max_retries}) exceeded."
                update_fields.extend(['locked_at', 'retry_count', 'flagged_reason'])
                logger.info(
                    "Contribution %s exhausted max retries (%d/%d); escalated to FLAGGED.",
                    contrib_id, new_retry_count, max_retries,
                )
            else:
                contribution.status = 'RETRY'
                contribution.sub_status = ''
                contribution.locked_at = None
                contribution.retry_count = new_retry_count
                update_fields.extend(['locked_at', 'retry_count'])
                if reason:
                    contribution.flagged_reason = reason
                    update_fields.append('flagged_reason')

        elif target_status == 'MERGING':
            contribution.status = 'MERGING'
            contribution.sub_status = ''
            contribution.locked_at = now
            update_fields.append('locked_at')

        elif target_status == 'MERGED':
            contribution.status = 'MERGED'
            contribution.sub_status = ''
            contribution.locked_at = None
            if not contribution.merged_at:
                contribution.merged_at = now
                update_fields.append('merged_at')
            update_fields.append('locked_at')

        contribution.save(update_fields=update_fields)
        logger.info(
            "Transitioned Contribution %s: %s -> %s (sub_status: '%s', reason: '%s')",
            contrib_id, current_status, contribution.status, contribution.sub_status, reason,
        )
        return contribution, True


def process_pending_contribution(contribution_or_id: Contribution | int) -> tuple[Contribution, str]:
    """
    Evaluate pre-checks on a PENDING contribution and transition to QUEUED or REJECTED.
    Returns (contribution, final_status).
    """
    contrib_id = contribution_or_id.id if isinstance(contribution_or_id, Contribution) else contribution_or_id
    contribution = Contribution.objects.select_related('pull_request__repo', 'issue', 'participant').get(id=contrib_id)

    if contribution.status != 'PENDING':
        return contribution, contribution.status

    passed, failure_reason = evaluate_pre_checks(contribution)
    if passed:
        updated, _ = transition_contribution(contribution.id, 'QUEUED')
        return updated, 'QUEUED'
    else:
        updated, _ = transition_contribution(contribution.id, 'REJECTED', reason=failure_reason)
        return updated, 'REJECTED'
