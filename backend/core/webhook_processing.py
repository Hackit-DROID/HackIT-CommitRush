import logging
import re
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from core.github_sync import sync_issue
from core.models import (
    Contribution,
    EventConfig,
    Issue,
    Participant,
    Project,
    PullRequest,
    WebhookEvent,
)

logger = logging.getLogger(__name__)

ISSUE_REF_PATTERN = re.compile(r'(?:^|[\s(\[,/#])#?(\d+)\b')
EXPLICIT_ISSUE_PATTERN = re.compile(
    r'(?:fixes|fix|closes|close|resolves|resolve|fixed|closed|resolved|ref|refs|issue|issues)\s*:?\s*#?(\d+)\b',
    re.IGNORECASE,
)


def extract_issue_numbers(text: str | None) -> list[int]:
    """
    Extract issue numbers referenced in PR title, body, or branch name.
    Prioritizes explicit keywords ('fixes #42', 'closes #10', etc.) before
    generic '#42' patterns.
    Returns a deduplicated list of positive integers.
    """
    if not text:
        return []

    explicit_matches = EXPLICIT_ISSUE_PATTERN.findall(text)
    generic_matches = re.findall(r'#(\d+)\b', text)

    seen = set()
    numbers = []

    # First add explicit matches
    for m in explicit_matches:
        try:
            val = int(m)
            if val > 0 and val not in seen:
                seen.add(val)
                numbers.append(val)
        except (ValueError, TypeError):
            continue

    # Then add generic #123 matches
    for m in generic_matches:
        try:
            val = int(m)
            if val > 0 and val not in seen:
                seen.add(val)
                numbers.append(val)
        except (ValueError, TypeError):
            continue

    return numbers


def handle_pull_request_event(payload: dict) -> dict:
    """
    Process inbound pull_request events per PRD §13.3, §15, §16 (M4-T3):
    - opened: create/update Contribution as PENDING only when it references a tracked Issue.
    - synchronize: update stored commit SHA and refresh contribution.
    - closed (merged=true): transition Contribution to MERGED.
    - closed (merged=false): transition Contribution to REJECTED.
    - other actions (e.g. edited, reopened): cache PR and update references.
    """
    action = (payload.get('action') or '').lower()
    pr_data = payload.get('pull_request')
    repo_data = payload.get('repository')

    if not pr_data or not repo_data:
        return {'status': 'ignored', 'reason': 'Missing pull_request or repository payload'}

    # 1. Resolve tracked project
    github_repo_id = repo_data.get('id')
    repo_full_name = repo_data.get('full_name') or ''

    project = None
    if github_repo_id is not None:
        project = Project.objects.filter(github_repo_id=github_repo_id).first()
    if not project and repo_full_name:
        project = Project.objects.filter(full_name__iexact=repo_full_name).first()

    if not project:
        logger.info("Ignoring PR webhook for untracked repository: %s (id: %s)", repo_full_name, github_repo_id)
        return {'status': 'ignored', 'reason': f"Repository '{repo_full_name}' is not tracked"}

    # 2. Extract PR metadata
    github_pr_id = pr_data.get('id')
    pr_number = pr_data.get('number')
    if github_pr_id is None or pr_number is None:
        return {'status': 'ignored', 'reason': 'Missing PR id or number'}

    user_data = pr_data.get('user') or {}
    author_github_id = user_data.get('id') or 0
    head_sha = (pr_data.get('head') or {}).get('sha') or ''
    is_merged = bool(pr_data.get('merged', False))
    raw_merged_at = pr_data.get('merged_at')
    merged_at = parse_datetime(raw_merged_at) if raw_merged_at else None

    # Resolve author participant if registered
    participant = None
    if author_github_id:
        participant = Participant.objects.filter(github_id=author_github_id).first()

    # 3. Synchronize PullRequest model
    with transaction.atomic():
        pr_obj, _ = PullRequest.objects.update_or_create(
            github_pr_id=github_pr_id,
            defaults={
                'repo': project,
                'number': pr_number,
                'author_github_id': author_github_id,
                'author_participant': participant,
                'head_sha': head_sha,
                'merged': is_merged,
                'merged_at': merged_at,
            },
        )

    # 4. Handle specific PR actions
    if action in ('opened', 'reopened'):
        title = pr_data.get('title') or ''
        body = pr_data.get('body') or ''
        head_ref = (pr_data.get('head') or {}).get('ref') or ''
        extracted_numbers = extract_issue_numbers(f"{title} {body} {head_ref}")

        matching_issue = None
        if extracted_numbers:
            matching_issue = Issue.objects.filter(
                project=project,
                number__in=extracted_numbers,
            ).order_by('id').first()

        # Respect submissions_paused (M4-T4, PRD §12.6, §15, plan.md M4-T4)
        config = EventConfig.get_solo()
        if config.submissions_paused:
            logger.info(
                "Submissions are paused (EventConfig.submissions_paused=True); skipping contribution creation for PR #%d in %s",
                pr_number,
                project.full_name,
            )
            return {
                'status': 'submissions_paused',
                'pr_id': pr_obj.id,
                'issue_id': matching_issue.id if matching_issue else None,
                'reason': 'Submissions are paused by admin configuration',
            }

        if matching_issue and participant:
            with transaction.atomic():
                contribution, created = Contribution.objects.get_or_create(
                    participant=participant,
                    pull_request=pr_obj,
                    defaults={
                        'issue': matching_issue,
                        'status': 'PENDING',
                    },
                )
                if not created and contribution.issue_id != matching_issue.id:
                    contribution.issue = matching_issue
                    contribution.save(update_fields=['issue', 'updated_at'])

            logger.info(
                "Contribution %s (%s) for PR #%d -> Issue #%d (%s)",
                contribution.id,
                'created' if created else 'updated',
                pr_number,
                matching_issue.number,
                project.full_name,
            )
            return {
                'status': 'contribution_created' if created else 'contribution_updated',
                'contribution_id': contribution.id,
                'issue_id': matching_issue.id,
                'pr_id': pr_obj.id,
            }

        return {
            'status': 'pr_cached',
            'pr_id': pr_obj.id,
            'reason': 'No tracked issue referenced or author not registered as participant',
        }

    elif action == 'synchronize':
        # Update head_sha and touch associated contributions
        with transaction.atomic():
            pr_obj.head_sha = head_sha
            pr_obj.save(update_fields=['head_sha'])

            # If contributions exist and are in active validation/pending states, touch them
            contributions = list(Contribution.objects.filter(pull_request=pr_obj))
            for contrib in contributions:
                if contrib.status in ('PENDING', 'QUEUED', 'UNDER_REVIEW', 'VALIDATING', 'RETRY'):
                    contrib.updated_at = timezone.now()
                    contrib.save(update_fields=['updated_at'])

        logger.info("Synchronized PR #%d (head_sha=%s) in %s", pr_number, head_sha, project.full_name)
        return {
            'status': 'synchronized',
            'pr_id': pr_obj.id,
            'head_sha': head_sha,
            'contributions_updated': len(contributions),
        }

    elif action == 'closed':
        with transaction.atomic():
            if is_merged:
                pr_obj.merged = True
                pr_obj.merged_at = merged_at or timezone.now()
                pr_obj.save(update_fields=['merged', 'merged_at'])

                contributions = list(Contribution.objects.filter(pull_request=pr_obj))
                if not contributions and participant:
                    # Catch-up for missed opened webhook: link matching issue if submissions not paused
                    config = EventConfig.get_solo()
                    if config.submissions_paused:
                        logger.info(
                            "Submissions are paused (EventConfig.submissions_paused=True); skipping catch-up contribution creation for PR #%d in %s",
                            pr_number,
                            project.full_name,
                        )
                    else:
                        title = pr_data.get('title') or ''
                        body = pr_data.get('body') or ''
                        head_ref = (pr_data.get('head') or {}).get('ref') or ''
                        extracted_numbers = extract_issue_numbers(f"{title} {body} {head_ref}")
                        if extracted_numbers:
                            matching_issue = Issue.objects.filter(
                                project=project,
                                number__in=extracted_numbers,
                            ).order_by('id').first()
                            if matching_issue:
                                contrib = Contribution.objects.create(
                                    participant=participant,
                                    pull_request=pr_obj,
                                    issue=matching_issue,
                                    status='PENDING',
                                )
                                contributions = [contrib]

                # Transition associated contributions to MERGED via state machine and trigger transactional point award
                from core.state_machine import transition_contribution
                for contrib in contributions:
                    try:
                        transition_contribution(contrib.id, 'MERGED')
                    except Exception as e:
                        logger.warning("Could not transition contribution %s to MERGED: %s", contrib.id, e)
                    try:
                        from core.points import award_points_for_contribution
                        award_points_for_contribution(contrib.id)
                    except Exception as e:
                        logger.exception("Error awarding points for merged contribution %s: %s", contrib.id, e)

                logger.info("PR #%d merged in %s; transitioned %d contribution(s) to MERGED", pr_number, project.full_name, len(contributions))
                return {
                    'status': 'pr_merged',
                    'pr_id': pr_obj.id,
                    'contributions_merged': len(contributions),
                }
            else:
                pr_obj.merged = False
                pr_obj.save(update_fields=['merged'])

                contributions = list(Contribution.objects.filter(pull_request=pr_obj))
                if not contributions and participant:
                    # Catch-up for missed opened webhook: link matching issue if submissions not paused
                    config = EventConfig.get_solo()
                    if config.submissions_paused:
                        logger.info(
                            "Submissions are paused (EventConfig.submissions_paused=True); skipping catch-up contribution creation for PR #%d in %s",
                            pr_number,
                            project.full_name,
                        )
                    else:
                        title = pr_data.get('title') or ''
                        body = pr_data.get('body') or ''
                        head_ref = (pr_data.get('head') or {}).get('ref') or ''
                        extracted_numbers = extract_issue_numbers(f"{title} {body} {head_ref}")
                        if extracted_numbers:
                            matching_issue = Issue.objects.filter(
                                project=project,
                                number__in=extracted_numbers,
                            ).order_by('id').first()
                            if matching_issue:
                                contrib = Contribution.objects.create(
                                    participant=participant,
                                    pull_request=pr_obj,
                                    issue=matching_issue,
                                    status='PENDING',
                                )
                                contributions = [contrib]

                # Transition associated contributions to REJECTED (closed without merge) via state machine
                from core.state_machine import transition_contribution
                for contrib in contributions:
                    if contrib.status != 'MERGED':
                        try:
                            transition_contribution(
                                contrib.id,
                                'REJECTED',
                                reason="Pull request closed on GitHub without merge.",
                            )
                        except Exception as e:
                            logger.warning("Could not transition contribution %s to REJECTED: %s", contrib.id, e)

                logger.info("PR #%d closed without merge in %s; transitioned %d contribution(s) to REJECTED", pr_number, project.full_name, len(contributions))
                return {
                    'status': 'pr_rejected',
                    'pr_id': pr_obj.id,
                    'contributions_rejected': len(contributions),
                }

    return {
        'status': 'pr_updated',
        'pr_id': pr_obj.id,
        'action': action,
    }


def handle_issues_event(payload: dict) -> dict:
    """
    Process inbound issues events per PRD §13.3, §15, §16 (M4-T3):
    - closed: mark local Issue.status closed.
    - labeled / unlabeled / edited / opened / reopened: update local Issue cache.
    """
    action = (payload.get('action') or '').lower()
    issue_data = payload.get('issue')
    repo_data = payload.get('repository')

    if not issue_data or not repo_data:
        return {'status': 'ignored', 'reason': 'Missing issue or repository payload'}

    github_repo_id = repo_data.get('id')
    repo_full_name = repo_data.get('full_name') or ''

    project = None
    if github_repo_id is not None:
        project = Project.objects.filter(github_repo_id=github_repo_id).first()
    if not project and repo_full_name:
        project = Project.objects.filter(full_name__iexact=repo_full_name).first()

    if not project:
        logger.info("Ignoring issue webhook for untracked repository: %s (id: %s)", repo_full_name, github_repo_id)
        return {'status': 'ignored', 'reason': f"Repository '{repo_full_name}' is not tracked"}

    github_issue_id = issue_data.get('id')
    issue_number = issue_data.get('number')

    if action == 'closed':
        with transaction.atomic():
            issue = None
            if github_issue_id is not None:
                issue = Issue.objects.filter(github_issue_id=github_issue_id).first()
            if not issue and issue_number is not None:
                issue = Issue.objects.filter(project=project, number=issue_number).first()

            if issue:
                issue.status = 'closed'
                issue.save(update_fields=['status'])
                logger.info("Marked Issue #%d in %s as closed from webhook", issue.number, project.full_name)
                return {'status': 'issue_closed', 'issue_id': issue.id}
            else:
                # Issue not yet in DB, sync from payload as closed
                issue, _ = sync_issue(project, issue_data)
                return {'status': 'issue_synced_closed', 'issue_id': issue.id}

    elif action in ('labeled', 'unlabeled', 'edited', 'opened', 'reopened'):
        issue, created = sync_issue(project, issue_data)
        logger.info(
            "Synced Issue #%d in %s from webhook action '%s' (%s)",
            issue.number,
            project.full_name,
            action,
            'created' if created else 'updated',
        )
        return {
            'status': 'issue_synced',
            'action': action,
            'issue_id': issue.id,
            'created': created,
        }

    return {'status': 'ignored', 'action': action}


def process_webhook_event(webhook_event: WebhookEvent) -> dict:
    """
    Main entry point for async webhook processing worker.
    Idempotent execution: marks WebhookEvent as processed.
    """
    event_type = webhook_event.event_type.lower()
    payload = webhook_event.payload

    result = {'status': 'unhandled_event_type', 'event_type': event_type}

    try:
        if event_type == 'pull_request':
            result = handle_pull_request_event(payload)
        elif event_type == 'issues':
            result = handle_issues_event(payload)
        elif event_type == 'ping':
            result = {'status': 'pong', 'zen': payload.get('zen', '')}
        else:
            result = {'status': 'unhandled', 'event_type': event_type}

        webhook_event.processed_at = timezone.now()
        webhook_event.processing_error = ''
        webhook_event.save(update_fields=['processed_at', 'processing_error'])
        return result

    except Exception as e:
        logger.exception("Error processing WebhookEvent %s (type=%s)", webhook_event.delivery_id, event_type)
        webhook_event.processing_error = str(e)
        webhook_event.save(update_fields=['processing_error'])
        raise
