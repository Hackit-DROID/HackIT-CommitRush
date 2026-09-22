import re
from core.categories import CATEGORY_MAP, VALID_CATEGORY_KEYS
from core.models import Contribution

CATEGORY_FRIENDLY_LABELS: dict[str, str] = {
    'feature': 'Feature',
    'bug': 'Bug Fix',
    'docs': 'Documentation',
    'test': 'Testing & QA',
    'security': 'Security',
    'performance': 'Performance',
    'refactor': 'Refactoring',
    'validation': 'Validation',
    'ui': 'UI',
    'database': 'Database & Storage',
    'networking': 'Networking',
    'frontend': 'Frontend',
    'backend': 'Backend',
    'devops': 'DevOps / Infrastructure',
    'fullstack': 'Fullstack',
    'dx': 'Developer Experience',
}

CATEGORY_ALIASES: dict[str, str] = {
    'fix': 'bug',
    'bugfix': 'bug',
    'bugs': 'bug',
    'defect': 'bug',
    'documentation': 'docs',
    'doc': 'docs',
    'feat': 'feature',
    'enhancement': 'feature',
    'features': 'feature',
    'testing': 'test',
    'qa': 'test',
    'tests': 'test',
    'perf': 'performance',
    'optimization': 'performance',
    'sec': 'security',
    'vulnerability': 'security',
    'cleanup': 'refactor',
    'infra': 'devops',
    'ci': 'devops',
    'cd': 'devops',
    'db': 'database',
    'storage': 'database',
}

TITLE_PREFIX_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'^(feat|feature)(\(.*\))?:\s*', re.IGNORECASE), 'feature'),
    (re.compile(r'^(fix|bug|bugfix)(\(.*\))?:\s*', re.IGNORECASE), 'bug'),
    (re.compile(r'^(docs|doc)(\(.*\))?:\s*', re.IGNORECASE), 'docs'),
    (re.compile(r'^(test|tests)(\(.*\))?:\s*', re.IGNORECASE), 'test'),
    (re.compile(r'^(sec|security)(\(.*\))?:\s*', re.IGNORECASE), 'security'),
    (re.compile(r'^(perf|performance)(\(.*\))?:\s*', re.IGNORECASE), 'performance'),
    (re.compile(r'^(refactor|style)(\(.*\))?:\s*', re.IGNORECASE), 'refactor'),
    (re.compile(r'^(ci|build|devops)(\(.*\))?:\s*', re.IGNORECASE), 'devops'),
    (re.compile(r'^\[(feat|feature)\]\s*', re.IGNORECASE), 'feature'),
    (re.compile(r'^\[(fix|bug)\]\s*', re.IGNORECASE), 'bug'),
    (re.compile(r'^\[(docs|doc)\]\s*', re.IGNORECASE), 'docs'),
    (re.compile(r'^\[(test|tests)\]\s*', re.IGNORECASE), 'test'),
    (re.compile(r'^\[(sec|security)\]\s*', re.IGNORECASE), 'security'),
    (re.compile(r'^\[(perf|performance)\]\s*', re.IGNORECASE), 'performance'),
]


def normalize_category_key(raw_category: str | None) -> str | None:
    """Normalize a raw category name or alias to a canonical key in VALID_CATEGORY_KEYS."""
    if not raw_category:
        return None
    cleaned = raw_category.strip().lower()
    if cleaned in VALID_CATEGORY_KEYS:
        return cleaned
    if cleaned in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[cleaned]
    return None


def classify_contribution(contribution: Contribution) -> tuple[str, str]:
    """
    Classify a contribution into an authoritative (category_key, category_label).
    Cascade strategy:
    1. Issue.category (if set and resolvable)
    2. Issue cached labels
    3. Issue title prefix convention
    4. Fallback to ('feature', 'Feature')
    """
    issue = getattr(contribution, 'issue', None)

    # 1. Check Issue.category
    if issue and issue.category:
        norm = normalize_category_key(issue.category)
        if norm:
            label = CATEGORY_FRIENDLY_LABELS.get(norm, CATEGORY_MAP.get(norm, norm.capitalize()))
            return norm, label

    # 2. Check Issue labels
    if issue:
        try:
            labels = list(issue.labels.values_list('name', flat=True))
            for label_name in labels:
                norm = normalize_category_key(label_name)
                if norm:
                    label = CATEGORY_FRIENDLY_LABELS.get(norm, CATEGORY_MAP.get(norm, norm.capitalize()))
                    return norm, label
        except Exception:
            pass

    # 3. Check Issue title prefixes
    if issue and issue.title:
        title = issue.title.strip()
        for pattern, cat_key in TITLE_PREFIX_PATTERNS:
            if pattern.match(title):
                norm = normalize_category_key(cat_key)
                if norm:
                    label = CATEGORY_FRIENDLY_LABELS.get(norm, CATEGORY_MAP.get(norm, norm.capitalize()))
                    return norm, label

    # 4. Default fallback
    return 'feature', CATEGORY_FRIENDLY_LABELS['feature']
