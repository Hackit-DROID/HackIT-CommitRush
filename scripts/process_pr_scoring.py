"""
CommitRush Authoritative PR Scoring Engine for GitHub Actions.
Processes merged pull requests, enforces the 120-point daily limit in IST,
guarantees idempotency and duplicate issue protection, and updates leaderboard.json.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add script directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scoring_utils import (
    DAILY_POINTS_CAP,
    DEFAULT_TARGET_BRANCH,
    DIFFICULTY_POINTS,
    extract_cr_issue_numbers,
    extract_difficulty_from_text_or_labels,
    get_ist_now,
    get_ist_today_str,
    load_leaderboard,
    save_leaderboard,
)


def process_merged_pr(
    author_username: str,
    pr_number: int,
    pr_title: str,
    pr_body: str = '',
    base_branch: str = 'main',
    is_merged: bool = True,
    merged_at_iso: str | None = None,
    labels: list[str] | None = None,
    leaderboard_file: str = 'leaderboard.json',
) -> dict:
    """
    Processes a merged PR and awards points adhering strictly to the 120-point daily limit in IST.
    """
    if not is_merged:
        return {
            'status': 'REJECTED',
            'points': 0,
            'reason': 'PR is not merged. Closed/unmerged PRs do not award competition points.',
        }

    if base_branch != DEFAULT_TARGET_BRANCH:
        return {
            'status': 'REJECTED',
            'points': 0,
            'reason': f"PR targets '{base_branch}', but designated event branch is '{DEFAULT_TARGET_BRANCH}'.",
        }

    issue_nums = extract_cr_issue_numbers(pr_title, pr_body)
    if not issue_nums:
        return {
            'status': 'REJECTED',
            'points': 0,
            'reason': 'PR does not reference a valid CommitRush issue (e.g. CR-901 or #42).',
        }

    issue_num = issue_nums[0]
    difficulty = extract_difficulty_from_text_or_labels(f"{pr_title} {pr_body}", labels)
    issue_points = DIFFICULTY_POINTS.get(difficulty, 10)

    # Determine IST date of merge
    if merged_at_iso:
        try:
            # Handle ISO string (e.g. 2026-09-22T10:30:00Z)
            clean_iso = merged_at_iso.replace('Z', '+00:00')
            dt_merged = datetime.fromisoformat(clean_iso)
            today_str = get_ist_today_str(dt_merged)
        except Exception:
            today_str = get_ist_today_str()
    else:
        today_str = get_ist_today_str()

    leaderboard = load_leaderboard(leaderboard_file)
    participants = leaderboard.setdefault('participants', {})
    scored_issues = leaderboard.setdefault('scored_issues', {})
    processed_prs = leaderboard.setdefault('processed_prs', {})

    pr_key = str(pr_number)
    issue_key = str(issue_num)

    # Idempotency check 1: exactly-once PR scoring
    if pr_key in processed_prs:
        rec = processed_prs[pr_key]
        return {
            'status': 'ALREADY_PROCESSED',
            'points': rec.get('points', 0),
            'reason': f"PR #{pr_number} has already been processed with {rec.get('points', 0)} points.",
            'participant': author_username,
        }

    # Anti-exploit check 2: Single CommitRush issue must not award points more than once
    if issue_key in scored_issues:
        first_awarded = scored_issues[issue_key]
        processed_prs[pr_key] = {
            'author': author_username,
            'points': 0,
            'status': 'DEFERRED',
            'reason': f"Duplicate issue: CR-{issue_num} already awarded points in PR #{first_awarded.get('pr_number')}.",
            'date': today_str,
        }
        save_leaderboard(leaderboard, leaderboard_file)
        return {
            'status': 'DEFERRED',
            'points': 0,
            'reason': f"Duplicate issue scoring prevented: Issue CR-{issue_num} was already awarded points in PR #{first_awarded.get('pr_number')}.",
            'participant': author_username,
        }

    # Participant daily record lookup
    p_data = participants.setdefault(author_username, {
        'rank': len(participants),
        'github_username': author_username,
        'total_points': 0,
        'counted_prs': 0,
        'today_points': 0,
        'remaining_today': DAILY_POINTS_CAP,
        'daily_limit': DAILY_POINTS_CAP,
        'is_daily_limit_reached': False,
        'daily': {},
    })

    daily_map = p_data.setdefault('daily', {})
    day_entry = daily_map.setdefault(today_str, {'points': 0, 'merged_prs': 0})
    current_day_points = day_entry['points']

    # Evaluate 120-point daily limit:
    # A contribution is counted only if current_day_points + issue_points <= 120
    # No partial credits: either full difficulty score, or 0 if exceeding limit.
    if current_day_points >= DAILY_POINTS_CAP:
        awarded_points = 0
        status = 'DEFERRED'
        result_label = 'DAILY LIMIT REACHED'
        reason = f"DAILY LIMIT REACHED: Participant already reached {DAILY_POINTS_CAP} points for {today_str} IST."
    elif current_day_points + issue_points > DAILY_POINTS_CAP:
        awarded_points = 0
        status = 'DEFERRED'
        result_label = 'NOT COUNTED - DAILY LIMIT'
        reason = f"NOT COUNTED - DAILY LIMIT: Adding {issue_points} points would exceed the {DAILY_POINTS_CAP}-point daily limit ({current_day_points}/{DAILY_POINTS_CAP})."
    else:
        awarded_points = issue_points
        status = 'AWARDED'
        result_label = 'COUNTED'
        reason = f"Successfully awarded {awarded_points} points for CR-{issue_num} ({difficulty.capitalize()})."

    # Update state
    if status == 'AWARDED':
        day_entry['points'] += awarded_points
        day_entry['merged_prs'] += 1
        p_data['total_points'] += awarded_points
        p_data['counted_prs'] += 1
        # Mark issue as awarded
        scored_issues[issue_key] = {
            'author': author_username,
            'pr_number': pr_number,
            'points': awarded_points,
            'date': today_str,
        }
    else:
        # Still record merged PR in daily history, but with 0 competition points
        day_entry['merged_prs'] += 1

    # Update summary fields
    p_data['today_points'] = day_entry['points']
    p_data['remaining_today'] = max(0, DAILY_POINTS_CAP - day_entry['points'])
    p_data['is_daily_limit_reached'] = day_entry['points'] >= DAILY_POINTS_CAP

    # Record PR as processed
    processed_prs[pr_key] = {
        'author': author_username,
        'points': awarded_points,
        'status': status,
        'result_label': result_label,
        'reason': reason,
        'date': today_str,
        'issue_number': issue_num,
        'difficulty': difficulty,
    }

    # Re-calculate leaderboard ranks strictly by total_points DESC, counted_prs DESC, username ASC
    ranked = sorted(
        participants.values(),
        key=lambda p: (-p.get('total_points', 0), -p.get('counted_prs', 0), p.get('github_username', ''))
    )
    for idx, user_entry in enumerate(ranked, start=1):
        user_entry['rank'] = idx

    leaderboard['generated_at'] = get_ist_now().isoformat()
    leaderboard['date'] = today_str
    save_leaderboard(leaderboard, leaderboard_file)

    report = (
        f"### CommitRush Competition Scoring Result\n\n"
        f"| Field | Value |\n"
        f"| :--- | :--- |\n"
        f"| **Participant** | @{author_username} |\n"
        f"| **Pull Request** | #{pr_number} |\n"
        f"| **Target Branch** | `{base_branch}` |\n"
        f"| **Linked Issue** | CR-{issue_num} |\n"
        f"| **Difficulty Tier** | {difficulty.capitalize()} ({issue_points} pts) |\n"
        f"| **Scoring Status** | **{result_label}** |\n"
        f"| **Points Awarded** | **{awarded_points}** pts |\n"
        f"| **Today's Score (IST)** | {p_data['today_points']} / {DAILY_POINTS_CAP} |\n"
        f"| **Remaining Today** | {p_data['remaining_today']} pts |\n"
        f"| **Total Official Points** | **{p_data['total_points']}** pts (Rank #{p_data['rank']}) |\n\n"
        f"*{reason}*"
    )

    return {
        'status': status,
        'result_label': result_label,
        'points': awarded_points,
        'today_points': p_data['today_points'],
        'remaining_today': p_data['remaining_today'],
        'total_points': p_data['total_points'],
        'rank': p_data['rank'],
        'reason': reason,
        'formatted_report': report,
    }


def main():
    parser = argparse.ArgumentParser(description="Process merged PR and update leaderboard.")
    parser.add_argument('--author', required=True, help='GitHub username of the PR author')
    parser.add_argument('--pr-number', type=int, required=True, help='Pull request number')
    parser.add_argument('--title', required=True, help='PR title')
    parser.add_argument('--body', default='', help='PR body')
    parser.add_argument('--base-branch', default='main', help='Target base branch')
    parser.add_argument('--merged', action='store_true', default=True, help='Whether PR is merged')
    parser.add_argument('--merged-at', help='Merged timestamp ISO string')
    parser.add_argument('--labels', nargs='*', default=[], help='PR / Issue labels')
    parser.add_argument('--leaderboard-file', default='leaderboard.json', help='Path to leaderboard.json')
    parser.add_argument('--output-file', help='Optional path to write report to')

    args = parser.parse_args()
    res = process_merged_pr(
        author_username=args.author,
        pr_number=args.pr_number,
        pr_title=args.title,
        pr_body=args.body,
        base_branch=args.base_branch,
        is_merged=args.merged,
        merged_at_iso=args.merged_at,
        labels=args.labels,
        leaderboard_file=args.leaderboard_file,
    )

    print(res.get('formatted_report', res.get('reason', '')))

    if args.output_file and 'formatted_report' in res:
        Path(args.output_file).write_text(res['formatted_report'], encoding='utf-8')


if __name__ == '__main__':
    main()
