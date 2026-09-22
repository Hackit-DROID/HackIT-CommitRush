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
    ScoringBreakdown,
)
from core.scoring.classifier import classify_contribution
from core.scoring.constants import (
    DAILY_POINTS_CAP,
    DIFFICULTY_POINTS,
    get_difficulty_points,
    get_event_today,
)
from core.scoring.farming import detect_farming_signals

logger = logging.getLogger(__name__)


class ScoringEngine:
    """
    Central authoritative scoring service for CommitRush (PRD §14, §15, Deliverable 1).
    Enforces the single canonical pipeline:
    PR (Contribution)
     ↓
    Validation Check
     ↓
    Contribution Classification
     ↓
    Base Point Calculation
     ↓
    Category Multiplier Application
     ↓
    Per-PR Maximum Point Cap
     ↓
    Farming Detection Heuristics
     ↓
    Daily Limits (Contributions Count & Points Cap - 120 points IST)
     ↓
    Final Awarded Points Resolution
     ↓
    Atomic Transaction Ledger (PointTransaction + ScoringBreakdown)
     ↓
    Leaderboard Cache Invalidation
    """

    @classmethod
    def calculate_scoring_plan(
        cls,
        contribution: Contribution,
        participant: Participant,
        config: EventConfig,
        daily_usage: DailyContributionUsage,
    ) -> dict:
        """
        Pure deterministic calculation stage of the scoring pipeline.
        Calculates category, multiplier, raw points, caps, and farming signals
        without performing database mutations.
        """
        # Step 2: Contribution classification
        category_key, category_label = classify_contribution(contribution)

        # Step 3: Base point calculation
        issue = getattr(contribution, 'issue', None)
        if issue and getattr(issue, 'difficulty', None):
            base_points = get_difficulty_points(issue.difficulty, getattr(issue, 'points', 10) or 10)
        elif issue and getattr(issue, 'points', None) is not None and issue.points > 0:
            base_points = issue.points
        else:
            base_points = 10

        # Step 4: Multiplier application
        multiplier = config.get_category_multiplier(category_key)

        # Step 5: Calculated points
        calculated_points = int(round(base_points * multiplier))

        # Step 6: Per-PR cap
        per_pr_cap = config.per_pr_max_points
        if per_pr_cap is not None and per_pr_cap > 0 and calculated_points > per_pr_cap:
            points_after_pr_cap = per_pr_cap
            is_pr_capped = True
        else:
            points_after_pr_cap = calculated_points
            is_pr_capped = False

        # Step 7: Farming signals detection
        farming_signals = detect_farming_signals(
            contribution=contribution,
            participant=participant,
            base_points=base_points,
            category=category_key,
        )

        # Step 8: Daily limits & farming caps (Official Event Rule: 120 points/day in IST)
        daily_points_max = config.max_points_per_day or DAILY_POINTS_CAP
        daily_contribs_max = config.max_contributions_per_day
        daily_points_before = daily_usage.points_count
        daily_allowance_remaining = max(0, daily_points_max - daily_points_before)

        # Check daily contribution count cap
        is_under_contrib_cap = (daily_usage.contributions_count + 1) <= daily_contribs_max

        cap_applied = 'Not reached'
        if is_pr_capped:
            cap_applied = 'Per-PR cap'

        if not is_under_contrib_cap:
            # Daily contribution count cap exceeded
            final_awarded_points = 0
            cap_applied = 'Daily contribution limit'
            status = 'DEFERRED'
            reason = f"Daily limit exceeded: daily contributions cap ({daily_usage.contributions_count}/{daily_contribs_max})"
        elif daily_allowance_remaining <= 0:
            # Daily points cap completely exhausted
            final_awarded_points = 0
            cap_applied = 'Daily limit'
            status = 'DEFERRED'
            reason = f"DAILY LIMIT REACHED: Participant already reached the {daily_points_max}-point daily limit for today ({daily_points_before}/{daily_points_max})"
        elif points_after_pr_cap > daily_allowance_remaining:
            # Points exceed remaining daily allowance
            if config.allow_partial_daily_points:
                final_awarded_points = daily_allowance_remaining
                cap_applied = 'Daily limit'
                status = 'AWARDED'
                repo_name = getattr(getattr(contribution, 'pull_request', None), 'repo', None)
                pr_num = getattr(getattr(contribution, 'pull_request', None), 'number', contribution.id)
                issue_num = getattr(issue, 'number', '')
                reason = f"Merged PR #{pr_num} on {repo_name} for Issue #{issue_num} (capped by daily limit)"
            else:
                final_awarded_points = 0
                cap_applied = 'Daily limit'
                status = 'DEFERRED'
                reason = f"NOT COUNTED - DAILY LIMIT: Adding {points_after_pr_cap} points would exceed today's {daily_points_max}-point daily limit ({daily_points_before}/{daily_points_max})"
        else:
            # Under all caps
            final_awarded_points = points_after_pr_cap
            status = 'AWARDED'
            repo_name = getattr(getattr(contribution, 'pull_request', None), 'repo', None)
            pr_num = getattr(getattr(contribution, 'pull_request', None), 'number', contribution.id)
            issue_num = getattr(issue, 'number', '')
            reason = f"Merged PR #{pr_num} on {repo_name} for Issue #{issue_num}"

        return {
            'status': status,
            'base_points': base_points,
            'category': category_key,
            'category_label': category_label,
            'multiplier': multiplier,
            'calculated_points': calculated_points,
            'per_pr_cap': per_pr_cap,
            'points_after_pr_cap': points_after_pr_cap,
            'daily_points_cap': daily_points_max,
            'daily_points_before': daily_points_before,
            'daily_allowance_remaining': daily_allowance_remaining,
            'cap_applied': cap_applied,
            'final_awarded_points': final_awarded_points,
            'farming_signals': farming_signals,
            'reason': reason,
        }

    @classmethod
    def award_points_for_contribution(cls, contribution_or_id: Contribution | int) -> dict:
        """
        Atomically award points for a confirmed MERGED Contribution through the scoring pipeline.
        Guarantees:
        - Row-level lock concurrency safety.
        - Exactly-once award idempotency.
        - Suspended participant gating.
        - Auditable ScoringBreakdown recording.
        - Immutable PointTransaction ledger entry.
        - Total points and merged_count synchronization.
        - Leaderboard cache invalidation.
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

            # Idempotency check: exactly-once award in ledger
            existing_awarded = PointTransaction.objects.filter(
                contribution=contribution,
                status='AWARDED',
            ).first()
            if existing_awarded:
                logger.info(
                    "Contribution %s already has awarded points (%s pts, txn %s); skipping.",
                    contrib_id,
                    existing_awarded.points,
                    existing_awarded.id,
                )
                return {
                    'status': 'ALREADY_AWARDED',
                    'points': existing_awarded.points,
                    'transaction_id': existing_awarded.id,
                }

            participant = Participant.objects.select_for_update().get(id=contribution.participant_id)
            config = EventConfig.get_solo()
            today = get_event_today()

            # Merged status check: only merged PRs can award points
            if contribution.pull_request and not contribution.pull_request.merged:
                logger.warning(
                    "PullRequest %s is not merged; cannot award points for Contribution %s",
                    contribution.pull_request_id,
                    contrib_id,
                )
                return {
                    'status': 'DEFERRED',
                    'points': 0,
                    'reason': 'PR is not merged. Only merged pull requests award competition points.',
                }

            # Branch check: PR must target designated event branch (normally main)
            designated_branch = config.target_branch or 'main'
            pr_branch = getattr(contribution.pull_request, 'base_branch', 'main') or 'main'
            if pr_branch != designated_branch:
                logger.warning(
                    "PullRequest %s targets '%s' instead of designated branch '%s'",
                    contribution.pull_request_id,
                    pr_branch,
                    designated_branch,
                )
                return {
                    'status': 'DEFERRED',
                    'points': 0,
                    'reason': f"PR does not target designated event branch '{designated_branch}'.",
                }

            # Anti-exploit: Single CommitRush issue must not award points more than once across the event
            if contribution.issue:
                prior_issue_award = PointTransaction.objects.filter(
                    contribution__issue=contribution.issue,
                    status='AWARDED',
                ).exclude(contribution=contribution).first()
                if prior_issue_award:
                    logger.info(
                        "Issue %s was already awarded points in txn %s; deferring points for Contribution %s",
                        contribution.issue_id,
                        prior_issue_award.id,
                        contrib_id,
                    )
                    pt = PointTransaction.objects.create(
                        contribution=contribution,
                        participant=participant,
                        points=0,
                        status='DEFERRED',
                        reason=f"Duplicate issue scoring prevented: Issue #{getattr(contribution.issue, 'number', '')} has already awarded points.",
                    )
                    category_key, category_label = classify_contribution(contribution)
                    base_points = getattr(contribution.issue, 'points', 10) or 10
                    breakdown, _ = ScoringBreakdown.objects.update_or_create(
                        contribution=contribution,
                        defaults={
                            'point_transaction': pt,
                            'base_points': base_points,
                            'category': category_key,
                            'category_label': category_label,
                            'multiplier': 1.0,
                            'calculated_points': base_points,
                            'per_pr_cap': config.per_pr_max_points,
                            'points_after_pr_cap': base_points,
                            'daily_points_cap': config.max_points_per_day,
                            'daily_points_before': 0,
                            'daily_allowance_remaining': 0,
                            'cap_applied': 'Duplicate issue',
                            'final_awarded_points': 0,
                            'farming_signals': {'duplicate_issue': True},
                        },
                    )
                    return {
                        'status': 'DEFERRED',
                        'points': 0,
                        'reason': f"Duplicate issue scoring prevented: Issue #{getattr(contribution.issue, 'number', '')} has already awarded points.",
                        'transaction_id': pt.id,
                        'breakdown_id': breakdown.id,
                    }

            # Suspended participant gating
            if participant.is_suspended:
                logger.warning(
                    "Participant %s is suspended; deferring points for Contribution %s",
                    participant.github_username,
                    contrib_id,
                )
                pt = PointTransaction.objects.create(
                    contribution=contribution,
                    participant=participant,
                    points=0,
                    status='DEFERRED',
                    reason=f"Participant {participant.github_username} is suspended from competition.",
                )
                # Also create ScoringBreakdown for auditability
                category_key, category_label = classify_contribution(contribution)
                base_points = (
                    getattr(contribution.issue, 'points', 10)
                    if contribution.issue and contribution.issue.points is not None and contribution.issue.points > 0
                    else 10
                )
                ScoringBreakdown.objects.update_or_create(
                    contribution=contribution,
                    defaults={
                        'point_transaction': pt,
                        'base_points': base_points,
                        'category': category_key,
                        'category_label': category_label,
                        'multiplier': 1.0,
                        'calculated_points': base_points,
                        'per_pr_cap': config.per_pr_max_points,
                        'points_after_pr_cap': base_points,
                        'daily_points_cap': config.max_points_per_day,
                        'daily_points_before': 0,
                        'daily_allowance_remaining': 0,
                        'cap_applied': 'Participant suspended',
                        'final_awarded_points': 0,
                        'farming_signals': {'suspended': True},
                    },
                )
                return {
                    'status': 'DEFERRED',
                    'points': 0,
                    'reason': 'Participant is suspended.',
                    'transaction_id': pt.id,
                }

            # Row lock on DailyContributionUsage for (participant, date in IST)
            daily_usage, _ = DailyContributionUsage.objects.select_for_update().get_or_create(
                participant=participant,
                date=today,
                defaults={'contributions_count': 0, 'points_count': 0},
            )

            # Evaluate scoring plan
            plan = cls.calculate_scoring_plan(
                contribution=contribution,
                participant=participant,
                config=config,
                daily_usage=daily_usage,
            )

            final_pts = plan['final_awarded_points']
            txn_status = plan['status']
            txn_reason = plan['reason']

            # Record PointTransaction ledger entry
            try:
                with transaction.atomic():
                    pt = PointTransaction.objects.create(
                        contribution=contribution,
                        participant=participant,
                        points=final_pts,
                        status=txn_status,
                        reason=txn_reason,
                    )
            except IntegrityError:
                # Race condition safety: already awarded
                existing = PointTransaction.objects.filter(contribution=contribution, status='AWARDED').first()
                return {
                    'status': 'ALREADY_AWARDED',
                    'points': existing.points if existing else final_pts,
                    'transaction_id': existing.id if existing else None,
                }

            # Record or update auditable ScoringBreakdown
            breakdown, _ = ScoringBreakdown.objects.update_or_create(
                contribution=contribution,
                defaults={
                    'point_transaction': pt,
                    'base_points': plan['base_points'],
                    'category': plan['category'],
                    'category_label': plan['category_label'],
                    'multiplier': plan['multiplier'],
                    'calculated_points': plan['calculated_points'],
                    'per_pr_cap': plan['per_pr_cap'],
                    'points_after_pr_cap': plan['points_after_pr_cap'],
                    'daily_points_cap': plan['daily_points_cap'],
                    'daily_points_before': plan['daily_points_before'],
                    'daily_allowance_remaining': plan['daily_allowance_remaining'],
                    'cap_applied': plan['cap_applied'],
                    'final_awarded_points': final_pts,
                    'farming_signals': plan['farming_signals'],
                },
            )

            if txn_status == 'AWARDED':
                # Update daily usage counters
                daily_usage.contributions_count += 1
                daily_usage.points_count += final_pts
                daily_usage.save(update_fields=['contributions_count', 'points_count'])

                # Update participant total points and merged count
                participant.total_points += final_pts
                participant.merged_count = participant.contributions.filter(status='MERGED').count()
                participant.save(update_fields=['total_points', 'merged_count'])

                # Invalidate cached leaderboard pages
                invalidate_leaderboard_cache()

                logger.info(
                    "Awarded %d points to %s for Contribution %s (%s, %sx, cap=%s, txn %d)",
                    final_pts,
                    participant.github_username,
                    contrib_id,
                    plan['category_label'],
                    plan['multiplier'],
                    plan['cap_applied'],
                    pt.id,
                )
            else:
                # Deferred: update sub_status if daily limit reached
                if plan.get('cap_applied') == 'Daily limit':
                    contribution.sub_status = 'DAILY_LIMIT_REACHED'
                    contribution.flagged_reason = plan.get('reason', 'DAILY LIMIT REACHED')
                    contribution.save(update_fields=['sub_status', 'flagged_reason'])
                # update merged count since contribution is still MERGED
                participant.merged_count = participant.contributions.filter(status='MERGED').count()
                participant.save(update_fields=['merged_count'])
                invalidate_leaderboard_cache()

                logger.info(
                    "Deferred points for Contribution %s (Participant %s): %s",
                    contrib_id,
                    participant.github_username,
                    txn_reason,
                )

            return {
                'status': txn_status,
                'points': final_pts,
                'base_points': plan['base_points'],
                'category': plan['category'],
                'category_label': plan['category_label'],
                'multiplier': plan['multiplier'],
                'calculated_points': plan['calculated_points'],
                'per_pr_cap': plan['per_pr_cap'],
                'cap_applied': plan['cap_applied'],
                'farming_signals': plan['farming_signals'],
                'transaction_id': pt.id,
                'breakdown_id': breakdown.id,
                'reason': txn_reason,
            }
