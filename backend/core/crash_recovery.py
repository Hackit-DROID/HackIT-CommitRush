import logging
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.models import Contribution

logger = logging.getLogger(__name__)

DEFAULT_LOCK_TIMEOUT_MINUTES = 10


def requeue_stale_contributions(
    timeout_minutes: int | None = None,
    re_enqueue: bool = True,
) -> dict:
    """
    Worker crash recovery sweep (PRD §11.2, §12.4, plan.md M5-T3).
    Identifies contributions stuck in UNDER_REVIEW or MERGING past the configured timeout window
    (due to worker crash or unhandled kill) and safely reverts them to their prior queued state:
    - UNDER_REVIEW (stale) -> QUEUED (and re-enqueues validation task)
    - MERGING (stale) -> APPROVED (prior state for merge queue)
    
    Guarantees:
    - Uses select_for_update(skip_locked=True) to prevent duplicate concurrent sweeps.
    - Terminal contributions (MERGED, REJECTED) are NEVER modified.
    - Active worker contributions (with fresh locked_at timestamps) are NOT touched.
    - Idempotent and thread-safe.
    
    Returns summary dictionary.
    """
    if timeout_minutes is None:
        timeout_minutes = int(getattr(settings, 'WORKER_LOCK_TIMEOUT_MINUTES', DEFAULT_LOCK_TIMEOUT_MINUTES))

    cutoff = timezone.now() - timedelta(minutes=timeout_minutes)
    recovered_under_review = []
    recovered_merging = []

    logger.info("Starting worker crash recovery sweep with timeout=%d minutes (cutoff=%s)", timeout_minutes, cutoff)

    # 1. Recover stale UNDER_REVIEW contributions
    stale_review_ids = list(
        Contribution.objects.filter(
            status='UNDER_REVIEW',
            locked_at__isnull=False,
            locked_at__lte=cutoff,
        ).values_list('id', flat=True)
    )

    for contrib_id in stale_review_ids:
        with transaction.atomic():
            contrib = Contribution.objects.select_for_update(skip_locked=True).filter(
                id=contrib_id,
                status='UNDER_REVIEW',
                locked_at__isnull=False,
                locked_at__lte=cutoff,
            ).first()

            if contrib:
                contrib.status = 'QUEUED'
                contrib.sub_status = ''
                contrib.locked_at = None
                contrib.save(update_fields=['status', 'sub_status', 'locked_at', 'updated_at'])

                recovered_under_review.append(contrib.id)
                logger.warning("Recovered crashed worker contribution %s: UNDER_REVIEW -> QUEUED", contrib.id)

                if re_enqueue:
                    try:
                        from core.tasks import validate_contribution_task
                        validate_contribution_task.delay(contrib.id)
                    except Exception as e:
                        logger.warning("Failed to re-enqueue validate_contribution_task for %s: %s", contrib.id, str(e))

    # 2. Recover stale MERGING contributions
    stale_merging_ids = list(
        Contribution.objects.filter(
            status='MERGING',
            locked_at__isnull=False,
            locked_at__lte=cutoff,
        ).values_list('id', flat=True)
    )

    for contrib_id in stale_merging_ids:
        with transaction.atomic():
            contrib = Contribution.objects.select_for_update(skip_locked=True).filter(
                id=contrib_id,
                status='MERGING',
                locked_at__isnull=False,
                locked_at__lte=cutoff,
            ).first()

            if contrib:
                contrib.status = 'APPROVED'
                contrib.sub_status = ''
                contrib.locked_at = None
                contrib.save(update_fields=['status', 'sub_status', 'locked_at', 'updated_at'])

                recovered_merging.append(contrib.id)
                logger.warning("Recovered crashed merge worker contribution %s: MERGING -> APPROVED", contrib.id)

    total_recovered = len(recovered_under_review) + len(recovered_merging)
    logger.info(
        "Crash recovery sweep completed: %d under_review recovered, %d merging recovered",
        len(recovered_under_review),
        len(recovered_merging),
    )

    return {
        'status': 'completed',
        'timeout_minutes': timeout_minutes,
        'cutoff': cutoff.isoformat(),
        'total_recovered': total_recovered,
        'recovered_under_review': recovered_under_review,
        'recovered_merging': recovered_merging,
    }
