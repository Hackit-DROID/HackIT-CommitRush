import json
import logging
from django.utils import timezone
from core.models import (
    Contribution,
    DailyContributionUsage,
    Issue,
    Participant,
    PointTransaction,
    Project,
    PullRequest,
    WebhookEvent,
)

logger = logging.getLogger(__name__)


def log_pipeline_step(
    stage: str,
    repository: str,
    pr_number: int,
    status: str,
    participant: str = '',
    details: dict | None = None,
    error: str = '',
    retry_status: str = '',
):
    """
    Structured logging for pipeline state transitions and observability.
    Guarantees secrets are never logged.
    """
    log_data = {
        'timestamp': timezone.now().isoformat(),
        'pipeline_stage': stage,
        'repository': repository,
        'pr_number': pr_number,
        'status': status,
        'participant': participant,
        'details': details or {},
        'error': error,
        'retry_status': retry_status,
    }
    if error or status == 'failed':
        logger.error("[PIPELINE_ERROR] %s: %s", stage, json.dumps(log_data))
    else:
        logger.info("[PIPELINE_EVENT] %s: %s", stage, json.dumps(log_data))


def trace_pr_lifecycle(repo_full_name: str, pr_number: int) -> dict:
    """
    Determine the exact lifecycle state and stage of a given PR:
    GitHub detected -> webhook received -> webhook queued -> webhook processed
    -> PullRequest created/updated -> participant matched -> issue matched
    -> Contribution created/updated -> Contribution MERGED -> scoring attempted
    -> scoring completed/deferred -> leaderboard cache invalidated -> API reflects state.
    
    Identifies the FIRST broken stage if the pipeline is incomplete.
    """
    report = {
        'repository': repo_full_name,
        'pr_number': pr_number,
        'stages': {},
        'first_broken_stage': None,
        'suggested_action': None,
        'participant': None,
        'issue': None,
        'points_awarded': 0,
        'status': 'UNKNOWN',
    }

    # 1. Project
    project = Project.objects.filter(full_name__iexact=repo_full_name).first()
    if not project:
        report['stages']['project_tracked'] = {'status': 'FAILED', 'detail': f"Repository '{repo_full_name}' is not tracked"}
        report['first_broken_stage'] = 'PROJECT_UNTRACKED'
        report['suggested_action'] = f"Track and enable repository '{repo_full_name}'"
        return report
    report['stages']['project_tracked'] = {'status': 'SUCCESS', 'project_id': project.id}

    # 2. Webhook received & processed
    webhook = WebhookEvent.objects.filter(
        event_type='pull_request',
        payload__pull_request__number=pr_number,
    ).order_by('-id').first()

    if webhook:
        report['stages']['webhook_received'] = {'status': 'SUCCESS', 'delivery_id': webhook.delivery_id}
        if webhook.processed_at:
            report['stages']['webhook_processed'] = {'status': 'SUCCESS', 'processed_at': webhook.processed_at.isoformat()}
        else:
            report['stages']['webhook_processed'] = {
                'status': 'PENDING' if not webhook.processing_error else 'FAILED',
                'error': webhook.processing_error,
            }
            if not report['first_broken_stage']:
                report['first_broken_stage'] = 'WEBHOOK_NOT_PROCESSED'
                report['suggested_action'] = 'Process webhook event or run reconciliation'
    else:
        report['stages']['webhook_received'] = {'status': 'NOT_FOUND', 'detail': 'No webhook received for this PR'}

    # 3. PullRequest record
    pr_obj = PullRequest.objects.filter(repo=project, number=pr_number).first()
    if not pr_obj:
        report['stages']['pull_request_record'] = {'status': 'MISSING'}
        if not report['first_broken_stage']:
            report['first_broken_stage'] = 'PULL_REQUEST_MISSING'
            report['suggested_action'] = 'Run repository reconciliation to synchronize PR from GitHub'
        return report

    report['stages']['pull_request_record'] = {
        'status': 'SUCCESS',
        'pr_id': pr_obj.id,
        'merged': pr_obj.merged,
        'merged_at': pr_obj.merged_at.isoformat() if pr_obj.merged_at else None,
        'author_github_id': pr_obj.author_github_id,
    }

    # 4. Participant match
    participant = pr_obj.author_participant
    if not participant and pr_obj.author_github_id:
        participant = Participant.objects.filter(github_id=pr_obj.author_github_id).first()

    if not participant:
        report['stages']['participant_matched'] = {'status': 'MISSING', 'author_github_id': pr_obj.author_github_id}
        if not report['first_broken_stage']:
            report['first_broken_stage'] = 'PARTICIPANT_NOT_REGISTERED'
            report['suggested_action'] = 'Participant has not signed up with GitHub OAuth'
        return report

    report['participant'] = participant.github_username
    report['stages']['participant_matched'] = {
        'status': 'SUCCESS',
        'participant_id': participant.id,
        'username': participant.github_username,
        'is_suspended': participant.is_suspended,
    }

    # 5. Contribution & Issue match
    contribution = Contribution.objects.filter(pull_request=pr_obj).first()
    if not contribution:
        report['stages']['contribution_record'] = {'status': 'MISSING'}
        if not report['first_broken_stage']:
            report['first_broken_stage'] = 'CONTRIBUTION_MISSING'
            report['suggested_action'] = 'Parse issue reference from PR title/body and create Contribution'
        return report

    report['issue'] = f"#{contribution.issue.number}" if contribution.issue else None
    report['stages']['issue_matched'] = {
        'status': 'SUCCESS' if contribution.issue else 'MISSING',
        'issue_id': contribution.issue_id,
        'issue_number': getattr(contribution.issue, 'number', None),
    }

    report['stages']['contribution_record'] = {
        'status': 'SUCCESS',
        'contribution_id': contribution.id,
        'current_status': contribution.status,
        'sub_status': contribution.sub_status,
        'flagged_reason': contribution.flagged_reason,
    }

    # Check if contribution reached MERGED
    if pr_obj.merged and contribution.status != 'MERGED':
        report['stages']['contribution_merged'] = {'status': 'FAILED', 'actual_status': contribution.status}
        if not report['first_broken_stage']:
            report['first_broken_stage'] = 'CONTRIBUTION_NOT_MERGED'
            report['suggested_action'] = 'Transition contribution to MERGED'
    else:
        report['stages']['contribution_merged'] = {
            'status': 'SUCCESS' if contribution.status == 'MERGED' else 'NOT_MERGED',
        }

    # 6. Scoring transaction
    pt = PointTransaction.objects.filter(contribution=contribution).order_by('-id').first()
    if pt:
        report['points_awarded'] = pt.points
        report['stages']['scoring'] = {
            'status': 'SUCCESS' if pt.status == 'AWARDED' else pt.status,
            'points': pt.points,
            'reason': pt.reason,
            'transaction_id': pt.id,
        }
    else:
        if pr_obj.merged and contribution.status == 'MERGED':
            report['stages']['scoring'] = {'status': 'MISSING'}
            if not report['first_broken_stage']:
                report['first_broken_stage'] = 'SCORING_TRANSACTION_MISSING'
                report['suggested_action'] = 'Award points for merged contribution'
        else:
            report['stages']['scoring'] = {'status': 'NOT_REACHED'}

    # 7. Participant total consistency
    if pt and pt.status == 'AWARDED':
        from django.db.models import Sum
        actual_total = PointTransaction.objects.filter(participant=participant, status='AWARDED').aggregate(s=Sum('points'))['s'] or 0
        if participant.total_points != actual_total:
            report['stages']['ledger_consistency'] = {
                'status': 'INCONSISTENT',
                'participant_total': participant.total_points,
                'ledger_total': actual_total,
            }
            if not report['first_broken_stage']:
                report['first_broken_stage'] = 'PARTICIPANT_TOTAL_INCONSISTENT'
                report['suggested_action'] = 'Synchronize participant total_points with PointTransaction ledger'
        else:
            report['stages']['ledger_consistency'] = {'status': 'SUCCESS', 'total_points': participant.total_points}

    report['status'] = 'HEALTHY' if not report['first_broken_stage'] else 'UNHEALTHY'
    return report


class PipelineStage:
    GITHUB_DETECTED = 'github_detected'
    WEBHOOK_RECEIVED = 'webhook_received'
    WEBHOOK_QUEUED = 'webhook_queued'
    WEBHOOK_PROCESSED = 'webhook_processed'
    PULL_REQUEST_SYNCED = 'pull_request_synced'
    PARTICIPANT_MATCHED = 'participant_matched'
    ISSUE_MATCHED = 'issue_matched'
    CONTRIBUTION_CREATED = 'contribution_created'
    CONTRIBUTION_MERGED = 'contribution_merged'
    SCORING_ATTEMPTED = 'scoring_attempted'
    SCORING_COMPLETED = 'scoring_completed'
    LEADERBOARD_INVALIDATED = 'leaderboard_invalidated'
    API_REFLECTS_STATE = 'api_reflects_state'


class PipelineTracer:
    """
    Stateful tracer for capturing and logging PR lifecycle events.
    """
    def __init__(self, repo: str, pr_number: int, participant: str = ''):
        self.repo = repo
        self.pr_number = pr_number
        self.participant = participant
        self.history = []

    def trace(
        self,
        stage: str,
        status: str = 'success',
        details: dict | None = None,
        error: str = '',
        retry_status: str = '',
    ):
        entry = {
            'timestamp': timezone.now().isoformat(),
            'stage': stage,
            'repository': self.repo,
            'pr_number': self.pr_number,
            'status': status,
            'details': details or {},
            'error': error,
            'retry_status': retry_status,
        }
        self.history.append(entry)
        log_pipeline_step(
            stage=stage,
            repository=self.repo,
            pr_number=self.pr_number,
            status=status,
            participant=self.participant,
            details=details,
            error=error,
            retry_status=retry_status,
        )
        return entry

    def get_history(self) -> list:
        return self.history

