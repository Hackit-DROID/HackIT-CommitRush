"""
CommitRush Standalone Scoring Utilities for GitHub Actions and Event Automation.
Compatible with standard Python 3.10+ without external third-party dependencies.
Timezone: Asia/Kolkata (IST), daily reset at 00:00 IST.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

EVENT_TIMEZONE = ZoneInfo('Asia/Kolkata')
DAILY_POINTS_CAP = 120
DEFAULT_TARGET_BRANCH = 'main'

DIFFICULTY_POINTS = {
    'beginner': 5,
    'easy': 10,
    'medium': 20,
    'intermediate': 20,
    'hard': 30,
    'advanced': 30,
    'master': 50,
    'expert': 50,
}

CR_ISSUE_REGEX = re.compile(r'\bCR[-_]?(\d+)\b', re.IGNORECASE)
EXPLICIT_ISSUE_REGEX = re.compile(
    r'(?:fixes|fix|closes|close|resolves|resolve|fixed|closed|resolved|ref|refs|issue|issues)\s*:?\s*(?:#|cr[-_]?)?(\d+)\b',
    re.IGNORECASE,
)
GENERIC_ISSUE_REGEX = re.compile(r'#(\d+)\b')


def get_ist_now() -> datetime:
    """Returns the current timezone-aware datetime in Asia/Kolkata (IST)."""
    return datetime.now(timezone.utc).astimezone(EVENT_TIMEZONE)


def get_ist_today_str(dt: datetime | None = None) -> str:
    """Returns the date formatted as YYYY-MM-DD in Asia/Kolkata (IST)."""
    if dt is None:
        dt = get_ist_now()
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc).astimezone(EVENT_TIMEZONE)
    else:
        dt = dt.astimezone(EVENT_TIMEZONE)
    return dt.strftime('%Y-%m-%d')


def extract_cr_issue_numbers(title: str, body: str = '', branch: str = '') -> list[int]:
    """
    Extracts referenced issue numbers prioritizing CR- tags and explicit closing keywords.
    """
    combined = f"{title or ''} {body or ''} {branch or ''}"
    numbers: list[int] = []
    seen: set[int] = set()

    for match in EXPLICIT_ISSUE_REGEX.findall(combined):
        try:
            val = int(match)
            if val > 0 and val not in seen:
                seen.add(val)
                numbers.append(val)
        except (ValueError, TypeError):
            continue

    for match in CR_ISSUE_REGEX.findall(combined):
        try:
            val = int(match)
            if val > 0 and val not in seen:
                seen.add(val)
                numbers.append(val)
        except (ValueError, TypeError):
            continue

    for match in GENERIC_ISSUE_REGEX.findall(combined):
        try:
            val = int(match)
            if val > 0 and val not in seen:
                seen.add(val)
                numbers.append(val)
        except (ValueError, TypeError):
            continue

    return numbers


def extract_difficulty_from_text_or_labels(text: str, labels: list[str] | None = None) -> str:
    """
    Extracts difficulty tier from GitHub labels (e.g. 'difficulty:easy') or PR/issue text.
    """
    if labels:
        for lbl in labels:
            clean = lbl.strip().lower()
            if clean.startswith('difficulty:'):
                return clean.split(':', 1)[1].strip()
            if clean in DIFFICULTY_POINTS:
                return clean

    match = re.search(r'\*\*Difficulty:\*\*\s*([^\n\r*]+)', text or '', re.IGNORECASE)
    if match:
        return match.group(1).strip().lower()

    match_diff = re.search(r'\b(beginner|easy|medium|hard|master)\b', text or '', re.IGNORECASE)
    if match_diff:
        return match_diff.group(1).strip().lower()

    return 'easy'


def load_leaderboard(file_path: str | Path = 'leaderboard.json') -> dict:
    """Loads existing persistent leaderboard JSON or returns a blank template."""
    p = Path(file_path)
    if p.is_file():
        try:
            with open(p, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass

    return {
        'event': 'HackIT CommitRush Open Source Contribution Drive',
        'repository': 'Hackit-DROID/Open-Source-Contribution-Drive',
        'timezone': 'Asia/Kolkata',
        'daily_limit': DAILY_POINTS_CAP,
        'participants': {},
    }


def save_leaderboard(data: dict, file_path: str | Path = 'leaderboard.json') -> None:
    """Saves persistent leaderboard JSON."""
    p = Path(file_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
