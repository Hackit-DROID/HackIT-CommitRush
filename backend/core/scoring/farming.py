from datetime import timedelta
from django.utils import timezone
from core.models import Contribution, Participant


def detect_farming_signals(
    contribution: Contribution,
    participant: Participant,
    base_points: int,
    category: str,
    now=None,
) -> dict:
    """
    Detect non-banning farming heuristics for administrative review (PRD §22, Section 7).
    Tracks:
    1. Multiple tiny documentation PRs (docs category with low base points)
    2. Repeated PRs against the same project in a short window
    3. Rapid bursts (multiple contributions within a short period)
    4. Very low-impact contributions (repeated minimal point PRs)
    5. Repeated trivial changes pattern
    
    Returns structured audit signals dictionary without applying automated user bans.
    """
    now = now or timezone.now()
    since_24h = now - timedelta(hours=24)
    since_1h = now - timedelta(minutes=60)

    signals: list[str] = []
    reasons: list[str] = []

    # Get recent merged or submitted contributions for this participant
    recent_qs = (
        Contribution.objects.filter(
            participant=participant,
            created_at__gte=since_24h,
        )
        .exclude(id=contribution.id)
        .select_related('issue', 'pull_request')
    )

    all_recent = list(recent_qs)
    total_recent_24h = len(all_recent) + 1  # including current

    # 1. Burst detection: contributions in past 60 minutes
    burst_count = sum(1 for c in all_recent if c.created_at >= since_1h) + 1
    if burst_count >= 3:
        signals.append('rapid_burst')
        reasons.append(f"{burst_count} contributions submitted within the last 60 minutes.")

    # 2. Repeated same project: PRs against the same repo in past 24 hours
    current_repo_id = getattr(getattr(contribution, 'pull_request', None), 'repo_id', None)
    same_repo_count = 1
    if current_repo_id:
        same_repo_count += sum(
            1 for c in all_recent
            if getattr(getattr(c, 'pull_request', None), 'repo_id', None) == current_repo_id
        )
    if same_repo_count >= 4:
        signals.append('repeated_same_project')
        repo_name = getattr(getattr(contribution, 'pull_request', None), 'repo', None)
        reasons.append(f"{same_repo_count} contributions submitted to the same project ({repo_name}) within 24 hours.")

    # 3. Multiple tiny documentation PRs
    is_current_doc = (category == 'docs') or ('doc' in (getattr(contribution.issue, 'category', '') or '').lower())
    docs_count = 1 if is_current_doc else 0
    for c in all_recent:
        c_cat = getattr(c.issue, 'category', '') or ''
        if 'doc' in c_cat.lower() or c_cat == 'docs':
            docs_count += 1
    if docs_count >= 3 and is_current_doc:
        signals.append('multiple_tiny_docs')
        reasons.append(f"{docs_count} documentation contributions submitted within 24 hours.")

    # 4. Very low-impact / trivial contributions
    is_current_low = base_points <= 15
    low_impact_count = 1 if is_current_low else 0
    for c in all_recent:
        c_pts = getattr(c.issue, 'points', 50) or 50
        if c_pts <= 15:
            low_impact_count += 1
    if low_impact_count >= 4 and is_current_low:
        signals.append('very_low_impact')
        reasons.append(f"{low_impact_count} very low-impact contributions (<=15 base points) within 24 hours.")

    # 5. Repeated trivial changes (frequent PRs with low points)
    if total_recent_24h >= 6 and (low_impact_count / total_recent_24h) > 0.6:
        signals.append('repeated_trivial_changes')
        reasons.append(f"{total_recent_24h} total contributions in 24 hours dominated by low-impact changes.")

    has_signals = len(signals) > 0
    if len(signals) >= 3:
        risk_level = 'HIGH'
    elif len(signals) == 2:
        risk_level = 'MEDIUM'
    elif len(signals) == 1:
        risk_level = 'LOW'
    else:
        risk_level = 'NONE'

    return {
        'has_signals': has_signals,
        'risk_level': risk_level,
        'signals': signals,
        'reasons': reasons,
        'metrics': {
            'burst_60m': burst_count,
            'same_project_24h': same_repo_count,
            'tiny_docs_24h': docs_count,
            'low_impact_24h': low_impact_count,
            'total_24h': total_recent_24h,
        },
    }
