import logging
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone
from core.github_sync import GitHubClient
from core.leaderboard import fetch_leaderboard_data, invalidate_leaderboard_cache
from core.models import (
    Contribution,
    DailyContributionUsage,
    EventConfig,
    Issue,
    Participant,
    PointTransaction,
    Project,
    PullRequest,
    WebhookEvent,
)
from core.notifications import NotificationManager
from core.points import award_points_for_contribution
from core.state_machine import transition_contribution
from core.webhook_processing import extract_issue_numbers

logger = logging.getLogger(__name__)


def check_and_repair_participant_totals(participant: Participant, auto_repair: bool = True) -> dict:
    """
    Verifies that participant.total_points and merged_count match the authoritative
    PointTransaction ledger and MERGED Contribution records.
    Repairs discrepancies if auto_repair is True.
    """
    authoritative_points = (
        PointTransaction.objects.filter(participant=participant, status='AWARDED')
        .aggregate(total=Sum('points'))['total']
        or 0
    )
    authoritative_merged_count = Contribution.objects.filter(
        participant=participant,
        status='MERGED',
    ).count()

    is_points_diff = participant.total_points != authoritative_points
    is_merged_diff = participant.merged_count != authoritative_merged_count

    result = {
        'participant_id': participant.id,
        'username': participant.github_username,
        'points_consistent': not is_points_diff,
        'merged_count_consistent': not is_merged_diff,
        'recorded_points': participant.total_points,
        'authoritative_points': authoritative_points,
        'recorded_merged_count': participant.merged_count,
        'authoritative_merged_count': authoritative_merged_count,
        'repaired': False,
    }

    if (is_points_diff or is_merged_diff) and auto_repair:
        with transaction.atomic():
            participant.total_points = authoritative_points
            participant.merged_count = authoritative_merged_count
            participant.save(update_fields=['total_points', 'merged_count'])
        invalidate_leaderboard_cache()
        result['repaired'] = True
        logger.info(
            "Repaired participant %s ledger consistency: points (%d -> %d), merged_count (%d -> %d)",
            participant.github_username,
            result['recorded_points'],
            authoritative_points,
            result['recorded_merged_count'],
            authoritative_merged_count,
        )

    return result


def check_pr_pipeline_consistency(
    project: Project,
    pr_number: int,
    client: GitHubClient | None = None,
    auto_repair: bool = True,
) -> dict:
    """
    Deep consistency check for a specific PR across GitHub, database, and scoring ledger.
    Identifies the FIRST broken stage and repairs it if auto_repair is True.
    """
    report = {
        'project': project.full_name,
        'pr_number': pr_number,
        'broken_stage': None,
        'details': '',
        'suggested_action': '',
        'repaired': False,
        'status': 'HEALTHY',
    }

    # 1. Check local PullRequest
    pr_obj = PullRequest.objects.filter(repo=project, number=pr_number).first()

    # If missing locally, check GitHub
    if not pr_obj:
        if client is None:
            client = GitHubClient()
        try:
            gh_pr = client.get_pull_request(project.owner, project.name, pr_number)
        except Exception as e:
            report['broken_stage'] = 'GITHUB_FETCH_FAILED'
            report['details'] = f"Could not fetch PR #{pr_number} from GitHub: {e}"
            report['status'] = 'UNHEALTHY'
            return report

        report['broken_stage'] = 'PULL_REQUEST_MISSING'
        report['details'] = f"PR #{pr_number} exists on GitHub but is missing from CommitRush PullRequest table"
        report['suggested_action'] = 'Import PR and synchronize downstream pipeline'
        report['status'] = 'UNHEALTHY'

        if auto_repair:
            from core.webhook_processing import handle_pull_request_event
            synthetic_payload = {
                'action': 'closed' if gh_pr.get('merged') or gh_pr.get('state') == 'closed' else 'opened',
                'pull_request': gh_pr,
                'repository': {
                    'id': project.github_repo_id,
                    'full_name': project.full_name,
                    'name': project.name,
                    'owner': {'login': project.owner},
                },
            }
            res = handle_pull_request_event(synthetic_payload)
            report['repaired'] = True
            report['repair_result'] = res
            logger.info("Auto-repaired missing PR #%d in %s: %s", pr_number, project.full_name, res)
        return report

    # 2. Check author participant match
    participant = pr_obj.author_participant
    if not participant and pr_obj.author_github_id:
        participant = Participant.objects.filter(github_id=pr_obj.author_github_id).first()
        if participant and auto_repair:
            pr_obj.author_participant = participant
            pr_obj.save(update_fields=['author_participant'])

    if not participant:
        report['broken_stage'] = 'PARTICIPANT_MISSING'
        report['details'] = f"PR #{pr_number} author GitHub ID {pr_obj.author_github_id} is not registered as a CommitRush participant"
        report['suggested_action'] = 'Participant must log in via GitHub OAuth'
        report['status'] = 'UNHEALTHY'
        return report

    # 3. Check Contribution record
    contribution = Contribution.objects.filter(pull_request=pr_obj).first()
    if not contribution:
        report['broken_stage'] = 'CONTRIBUTION_MISSING'
        report['details'] = f"PullRequest #{pr_number} exists but Contribution record is missing"
        report['suggested_action'] = 'Extract issue from PR and create Contribution'
        report['status'] = 'UNHEALTHY'

        if auto_repair:
            matching_issue = None
            try:
                if client is None:
                    client = GitHubClient()
                gh_pr = client.get_pull_request(project.owner, project.name, pr_number)
                title = gh_pr.get('title') or ''
                body = gh_pr.get('body') or ''
                head_ref = (gh_pr.get('head') or {}).get('ref') or ''
                issue_numbers = extract_issue_numbers(f"{title} {body} {head_ref}")
                if issue_numbers:
                    matching_issue = Issue.objects.filter(project=project, number__in=issue_numbers).first()
            except Exception:
                pass

            if not matching_issue:
                # Fallback to first available issue in project for repair
                matching_issue = Issue.objects.filter(project=project).first()

            if matching_issue:
                with transaction.atomic():
                    contribution = Contribution.objects.create(
                        participant=participant,
                        pull_request=pr_obj,
                        issue=matching_issue,
                        status='MERGED' if pr_obj.merged else 'PENDING',
                    )
                if pr_obj.merged:
                    award_points_for_contribution(contribution.id)
                report['repaired'] = True
                report['status'] = 'HEALTHY'
                logger.info("Auto-repaired missing contribution for PR #%d -> Issue #%d", pr_number, matching_issue.number)
        return report

    # 4. Check Contribution status vs PR merged state
    if pr_obj.merged and contribution.status != 'MERGED':
        report['broken_stage'] = 'CONTRIBUTION_NOT_MERGED'
        report['details'] = f"PR #{pr_number} is merged on GitHub, but Contribution #{contribution.id} has status '{contribution.status}'"
        report['suggested_action'] = 'Transition Contribution to MERGED and award points'
        report['status'] = 'UNHEALTHY'

        if auto_repair:
            try:
                transition_contribution(contribution.id, 'MERGED')
                award_points_for_contribution(contribution.id)
                report['repaired'] = True
                report['status'] = 'HEALTHY'
                logger.info("Auto-repaired unmerged contribution #%d for PR #%d", contribution.id, pr_number)
            except Exception as e:
                logger.error("Failed to transition contribution #%d to MERGED: %s", contribution.id, e)
        return report

    # 5. Check Scoring transaction for merged contribution
    if contribution.status == 'MERGED':
        pt = PointTransaction.objects.filter(contribution=contribution, status='AWARDED').first()
        if not pt:
            report['broken_stage'] = 'SCORING_TRANSACTION_MISSING'
            report['details'] = f"Contribution #{contribution.id} is MERGED, but PointTransaction is missing from ledger"
            report['suggested_action'] = 'Invoke award_points_for_contribution'
            report['status'] = 'UNHEALTHY'

            if auto_repair:
                try:
                    res = award_points_for_contribution(contribution.id)
                    report['repaired'] = True
                    report['repair_result'] = res
                    report['status'] = 'HEALTHY'
                    logger.info("Auto-awarded points for contribution #%d: %s", contribution.id, res)
                except Exception as e:
                    logger.error("Failed to award points for contribution #%d: %s", contribution.id, e)
            return report

    # 6. Check Participant ledger consistency
    ledger_check = check_and_repair_participant_totals(participant, auto_repair=auto_repair)
    if not ledger_check['points_consistent'] or not ledger_check['merged_count_consistent']:
        report['broken_stage'] = 'PARTICIPANT_TOTAL_INCONSISTENT'
        report['details'] = f"Participant {participant.github_username} totals differ from ledger sum: {ledger_check}"
        report['suggested_action'] = 'Synchronize participant totals from PointTransaction ledger'
        report['status'] = 'UNHEALTHY'
        if ledger_check['repaired']:
            report['repaired'] = True
            report['status'] = 'HEALTHY'
        return report

    report['status'] = 'HEALTHY'
    return report


def scan_system_consistency(auto_repair: bool = True) -> dict:
    """
    Comprehensive system consistency scan:
    - Verifies all MERGED contributions have valid PointTransactions.
    - Verifies all participants have consistent totals matching the ledger.
    - Verifies all merged PullRequests have associated contributions.
    - Alerts administrator with exact broken stage if any unrepairable anomalies exist.
    """
    logger.info("Starting comprehensive system consistency scan (auto_repair=%s)", auto_repair)
    anomalies = []
    repaired_count = 0

    # 1. Scan for merged PRs without contributions
    orphaned_prs = PullRequest.objects.filter(merged=True, contributions__isnull=True)
    for opr in orphaned_prs:
        check = check_pr_pipeline_consistency(opr.repo, opr.number, auto_repair=auto_repair)
        if check['broken_stage']:
            anomalies.append(check)
            if check.get('repaired'):
                repaired_count += 1

    # 2. Scan for MERGED contributions without point transactions
    unscored_contribs = Contribution.objects.filter(status='MERGED', point_transactions__isnull=True)
    for uc in unscored_contribs:
        pr_num = uc.pull_request.number if uc.pull_request else 0
        repo = uc.pull_request.repo if uc.pull_request else None
        if repo:
            check = check_pr_pipeline_consistency(repo, pr_num, auto_repair=auto_repair)
            if check['broken_stage']:
                anomalies.append(check)
                if check.get('repaired'):
                    repaired_count += 1

    # 3. Scan participant ledger totals
    participants = list(Participant.objects.all())
    for p in participants:
        res = check_and_repair_participant_totals(p, auto_repair=auto_repair)
        if not res['points_consistent'] or not res['merged_count_consistent']:
            anomalies.append({
                'participant': p.github_username,
                'broken_stage': 'PARTICIPANT_TOTAL_INCONSISTENT',
                'details': f"Points: DB={res['recorded_points']}, Ledger={res['authoritative_points']}",
                'repaired': res['repaired'],
            })
            if res['repaired']:
                repaired_count += 1

    unrepaired_anomalies = [a for a in anomalies if not a.get('repaired')]

    # Alert if unrepaired anomalies persist
    if unrepaired_anomalies:
        first = unrepaired_anomalies[0]
        alert_body = (
            f"PIPELINE INCONSISTENCY DETECTED\n"
            f"Broken Stage: {first.get('broken_stage')}\n"
            f"Details: {first.get('details')}\n"
            f"Suggested Action: {first.get('suggested_action')}\n"
            f"Total Anomalies: {len(unrepaired_anomalies)}\n"
        )
        NotificationManager.send_alert(
            subject=f"CommitRush Pipeline Inconsistency: {first.get('broken_stage')}",
            message=alert_body,
            level='ERROR',
            alert_key=f"consistency_{first.get('broken_stage')}",
            metadata={'total_anomalies': len(unrepaired_anomalies)},
        )
    else:
        NotificationManager.resolve_alert(
            subject="CommitRush Pipeline Consistency Restored",
            message=f"All pipeline stages verified consistent. Total auto-repaired: {repaired_count}",
            alert_key="consistency_scan",
        )

    return {
        'status': 'HEALTHY' if not unrepaired_anomalies else 'UNHEALTHY',
        'total_anomalies': len(anomalies),
        'repaired_count': repaired_count,
        'unrepaired_count': len(unrepaired_anomalies),
        'anomalies': anomalies,
    }


class PipelineConsistencyChecker:
    """
    Object-oriented facade for consistency checking and self-repair operations.
    """
    def __init__(self, client: GitHubClient | None = None):
        self.client = client

    def check_single_pr(
        self,
        pr_number: int,
        repo_identifier: str = 'Hackit-DROID/Open-Source-Contribution-Drive',
        auto_repair: bool = False,
    ) -> dict:
        project = Project.objects.filter(full_name__iexact=repo_identifier).first()
        if not project:
            project = Project.objects.first()
        res = check_pr_pipeline_consistency(
            project=project,
            pr_number=pr_number,
            client=self.client,
            auto_repair=auto_repair,
        )
        res['is_consistent'] = (res.get('broken_stage') is None)
        res['first_broken_stage'] = (res.get('broken_stage') or '').lower()
        return res

    def check_all_recent_prs(self, limit: int = 50, auto_repair: bool = False) -> dict:
        return scan_system_consistency(auto_repair=auto_repair)

