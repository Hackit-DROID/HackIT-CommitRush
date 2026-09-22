"""
CommitRush Authoritative Issue Category Definitions.
Single source of truth for issue categories, user-facing labels, and serializer choices.
"""

ISSUE_CATEGORIES: list[tuple[str, str]] = [
    ('feature', 'Features'),
    ('test', 'Testing & QA'),
    ('bug', 'Bug Fixes'),
    ('security', 'Security'),
    ('performance', 'Performance'),
    ('docs', 'Documentation'),
    ('refactor', 'Refactoring'),
    ('validation', 'Validation'),
    ('ui', 'UI'),
    ('database', 'Database & Storage'),
    ('networking', 'Networking'),
    ('frontend', 'Frontend'),
    ('backend', 'Backend'),
    ('devops', 'DevOps / Infrastructure'),
    ('fullstack', 'Fullstack'),
    ('dx', 'Developer Experience'),
]

CATEGORY_CHOICES = ISSUE_CATEGORIES
CATEGORY_MAP = dict(ISSUE_CATEGORIES)
VALID_CATEGORY_KEYS = [k for k, _ in ISSUE_CATEGORIES]

DEFAULT_CATEGORY_MULTIPLIERS: dict[str, float] = {
    'feature': 1.5,
    'bug': 1.0,
    'docs': 0.8,
    'test': 1.2,
    'security': 1.5,
    'performance': 1.3,
    'refactor': 1.0,
    'validation': 1.0,
    'ui': 1.1,
    'database': 1.2,
    'networking': 1.2,
    'frontend': 1.1,
    'backend': 1.2,
    'devops': 1.2,
    'fullstack': 1.3,
    'dx': 1.0,
}

