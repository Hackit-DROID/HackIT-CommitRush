"""
CommitRush Daily Limit Check for Pull Requests.
Evaluates whether a pull request would earn points or exceed the 120-point daily limit in IST.
Outputs formatted markdown summary for GitHub Actions status checks and PR comments.
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add script directory to sys.path for scoring_utils import
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
)


def evaluate_pr_daily_limit(
    author_username: str,
    pr_number: int,
    pr_title: str,
    pr_body: str = '',
    base_branch: str = 'main',
    labels: list[str] | None = None,
    leaderboard_file: str = 'leaderboard.json',
) -> dict:
    today_str = get_ist_today_str()
    leaderboard = load_leaderboard(leaderboard_file)
    participants = leaderboard.get('participants', {})
    participant_data = participants.get(author_username, {})

    daily_records = participant_data.get('daily', {})
    today_points = daily_records.get(today_str, {}).get('points', 0)

    # 1. Target branch check
    if base_branch != DEFAULT_TARGET_BRANCH:
        return {
            'participant': author_username,
            'today_points': today_points,
            'daily_limit': DAILY_POINTS_CAP,
            'pr_value': 0,
            'result': 'NOT COUNTED',
            'reason': f"PR targets '{base_branch}', but designated event branch is '{DEFAULT_TARGET_BRANCH}'.",
            'formatted_report': (
                f"### CommitRush Daily Limit\n"
                f"**Participant:** @{author_username}\n"
                f"**Today's points:** {today_points} / {DAILY_POINTS_CAP}\n"
                f"**PR value:** 0\n"
                f"**Result:** NOT COUNTED\n"
                f"**Reason:** PR targets `{base_branch}`, but designated event branch is `{DEFAULT_TARGET_BRANCH}`."
            ),
        }

    # 2. Extract issue
    issue_nums = extract_cr_issue_numbers(pr_title, pr_body)
    if not issue_nums:
        return {
            'participant': author_username,
            'today_points': today_points,
            'daily_limit': DAILY_POINTS_CAP,
            'pr_value': 0,
            'result': 'NOT COUNTED',
            'reason': "PR does not reference a valid CommitRush issue (e.g. CR-901 or #42).",
            'formatted_report': (
                f"### CommitRush Daily Limit\n"
                f"**Participant:** @{author_username}\n"
                f"**Today's points:** {today_points} / {DAILY_POINTS_CAP}\n"
                f"**PR value:** 0\n"
                f"**Result:** NOT COUNTED\n"
                f"**Reason:** PR does not reference a valid CommitRush issue (e.g. CR-901)."
            ),
        }

    issue_num = issue_nums[0]
    difficulty = extract_difficulty_from_text_or_labels(f"{pr_title} {pr_body}", labels)
    pr_value = DIFFICULTY_POINTS.get(difficulty, 10)

    # 3. Check daily points limit
    if today_points >= DAILY_POINTS_CAP:
        report = (
            f"CommitRush Daily Limit\n"
            f"Participant: @{author_username}\n"
            f"Today's points: {today_points} / {DAILY_POINTS_CAP}\n"
            f"PR value: {pr_value}\n"
            f"Result: NOT COUNTED\n"
            f"Reason: Daily limit of {DAILY_POINTS_CAP} points has already been reached for today."
        )
        return {
            'participant': author_username,
            'today_points': today_points,
            'daily_limit': DAILY_POINTS_CAP,
            'pr_value': pr_value,
            'result': 'NOT COUNTED',
            'reason': f"Daily limit of {DAILY_POINTS_CAP} points reached.",
            'formatted_report': report,
        }

    if today_points + pr_value > DAILY_POINTS_CAP:
        report = (
            f"CommitRush Daily Limit\n"
            f"Participant: @{author_username}\n"
            f"Today's points: {today_points} / {DAILY_POINTS_CAP}\n"
            f"PR value: {pr_value}\n"
            f"Result: NOT COUNTED\n"
            f"Reason: This PR would exceed today's {DAILY_POINTS_CAP}-point limit."
        )
        return {
            'participant': author_username,
            'today_points': today_points,
            'daily_limit': DAILY_POINTS_CAP,
            'pr_value': pr_value,
            'result': 'NOT COUNTED',
            'reason': f"This PR would exceed today's {DAILY_POINTS_CAP}-point limit.",
            'formatted_report': report,
        }

    new_total = today_points + pr_value
    report = (
        f"CommitRush Daily Limit\n"
        f"Participant: @{author_username}\n"
        f"Today's points: {today_points} / {DAILY_POINTS_CAP}\n"
        f"PR value: {pr_value}\n"
        f"Result: COUNTED\n"
        f"New daily total: {new_total} / {DAILY_POINTS_CAP}"
    )
    return {
        'participant': author_username,
        'today_points': today_points,
        'daily_limit': DAILY_POINTS_CAP,
        'pr_value': pr_value,
        'new_total': new_total,
        'result': 'COUNTED',
        'formatted_report': report,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate PR daily point limit.")
    parser.add_argument('--author', required=True, help='GitHub username of the PR author')
    parser.add_argument('--pr-number', type=int, default=1, help='Pull request number')
    parser.add_argument('--title', default='', help='PR title')
    parser.add_argument('--body', default='', help='PR body')
    parser.add_argument('--base-branch', default='main', help='Target base branch')
    parser.add_argument('--labels', nargs='*', default=[], help='List of issue/PR labels')
    parser.add_argument('--leaderboard-file', default='leaderboard.json', help='Path to leaderboard.json')
    parser.add_argument('--output-file', help='Optional path to write markdown report to')

    args = parser.parse_args()
    res = evaluate_pr_daily_limit(
        author_username=args.author,
        pr_number=args.pr_number,
        pr_title=args.title,
        pr_body=args.body,
        base_branch=args.base_branch,
        labels=args.labels,
        leaderboard_file=args.leaderboard_file,
    )

    print(res['formatted_report'])

    if args.output_file:
        Path(args.output_file).write_text(res['formatted_report'], encoding='utf-8')


if __name__ == '__main__':
    main()
