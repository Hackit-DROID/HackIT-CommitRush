import logging
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.leaderboard import invalidate_leaderboard_cache
from core.models import (
    Contribution,
    DailyContributionUsage,
    EventConfig,
    Participant,
    PointTransaction,
)

logger = logging.getLogger(__name__)


def award_points_for_contribution(contribution_or_id: Contribution | int) -> dict:
    """
    Atomically award points for a confirmed MERGED Contribution (PRD §14, §15, Plan M6-T5).
    Enforces:
    - Exactly-once point awards per contribution (idempotency via unique database constraint).
    - Daily contribution credit and points caps from EventConfig via row-level locks (select_for_update).
    - Immutable ledger recording in PointTransaction (AWARDED or DEFERRED).
    - Suspended participant gating.
    
    Returns a dict with transaction status, points, and transaction ID.
    """
    contrib_id = contribution_or_id.id if isinstance(contribution_or_id, Contribution) else contribution_or_id

    with transaction.atomic():
        try:
            contribution = (
                Contribution.objects.select_for_update()
                .select_related('participant', 'issue', 'pull_request__repo')
                .get(id=contrib_id)
            )
        except Contribution.DoesNotExist:
            logger.error("Contribution %s does not exist for point award", contrib_id)
            return {'status': 'NOT_FOUND', 'points': 0, 'error': f"Contribution {contrib_id} not found."}

        # Idempotency check: exactly-once award
        existing_awarded = PointTransaction.objects.filter(
            contribution=contribution,
            status='AWARDED',
        ).first()
        if existing_awarded:
            logger.info("Contribution %s already has awarded points (%s pts, txn %s); skipping.", contrib_id, existing_awarded.points, existing_awarded.id)
            return {
                'status': 'ALREADY_AWARDED',
                'points': existing_awarded.points,
                'transaction_id': existing_awarded.id,
            }

        participant = Participant.objects.select_for_update().get(id=contribution.participant_id)
        config = EventConfig.get_solo()
        today = timezone.now().date()

        # Suspended participant check
        if participant.is_suspended:
            logger.warning("Participant %s is suspended; deferring points for Contribution %s", participant.github_username, contrib_id)
            pt = PointTransaction.objects.create(
                contribution=contribution,
                participant=participant,
                points=0,
                status='DEFERRED',
                reason=f"Participant {participant.github_username} is suspended from competition.",
            )
            return {
                'status': 'DEFERRED',
                'points': 0,
                'reason': 'Participant is suspended.',
                'transaction_id': pt.id,
            }

        # Row lock on DailyContributionUsage for (participant, date)
        daily_usage, _ = DailyContributionUsage.objects.select_for_update().get_or_create(
            participant=participant,
            date=today,
            defaults={'contributions_count': 0, 'points_count': 0},
        )

        issue_points = contribution.issue.points if contribution.issue else 50
        max_daily_contributions = config.max_contributions_per_day
        max_daily_points = config.max_points_per_day

        is_under_contrib_cap = (daily_usage.contributions_count + 1) <= max_daily_contributions
        is_under_points_cap = (daily_usage.points_count + issue_points) <= max_daily_points

        if is_under_contrib_cap and is_under_points_cap:
            # Under cap: award points
            try:
                with transaction.atomic():
                    pt = PointTransaction.objects.create(
                        contribution=contribution,
                        participant=participant,
                        points=issue_points,
                        status='AWARDED',
                        reason=(
                            f"Merged PR #{contribution.pull_request.number} on "
                            f"{contribution.pull_request.repo.full_name} for Issue #{contribution.issue.number}"
                        ),
                    )
            except IntegrityError:
                # Race condition safety: already awarded (savepoint rolled back cleanly)
                existing = PointTransaction.objects.filter(contribution=contribution, status='AWARDED').first()
                return {
                    'status': 'ALREADY_AWARDED',
                    'points': existing.points if existing else issue_points,
                    'transaction_id': existing.id if existing else None,
                }

            # Update daily usage counters
            daily_usage.contributions_count += 1
            daily_usage.points_count += issue_points
            daily_usage.save(update_fields=['contributions_count', 'points_count'])

            # Update participant total points and merged count
            participant.total_points += issue_points
            participant.merged_count = participant.contributions.filter(status='MERGED').count()
            participant.save(update_fields=['total_points', 'merged_count'])

            # Invalidate cached leaderboard pages
            invalidate_leaderboard_cache()

            logger.info(
                "Awarded %d points to %s for Contribution %s (txn %d, daily usage: %d/%d contribs, %d/%d pts)",
                issue_points,
                participant.github_username,
                contrib_id,
                pt.id,
                daily_usage.contributions_count,
                max_daily_contributions,
                daily_usage.points_count,
                max_daily_points,
            )
            return {
                'status': 'AWARDED',
                'points': issue_points,
                'transaction_id': pt.id,
            }

        else:
            # Cap exceeded: record DEFERRED transaction
            reason_parts = []
            if not is_under_contrib_cap:
                reason_parts.append(f"daily contributions cap ({daily_usage.contributions_count}/{max_daily_contributions})")
            if not is_under_points_cap:
                reason_parts.append(f"daily points cap ({daily_usage.points_count + issue_points}/{max_daily_points})")
            defer_reason = f"Daily limit exceeded: {', '.join(reason_parts)}"

            pt = PointTransaction.objects.create(
                contribution=contribution,
                participant=participant,
                points=0,
                status='DEFERRED',
                reason=defer_reason,
            )

            # Update participant merged count (since contribution is still MERGED)
            participant.merged_count = participant.contributions.filter(status='MERGED').count()
            participant.save(update_fields=['merged_count'])

            # Invalidate cached leaderboard pages
            invalidate_leaderboard_cache()

            logger.info(
                "Deferred points for Contribution %s (Participant %s): %s",
                contrib_id,
                participant.github_username,
                defer_reason,
            )
            return {
                'status': 'DEFERRED',
                'points': 0,
                'reason': defer_reason,
                'transaction_id': pt.id,
            }
