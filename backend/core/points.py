import logging
from core.models import Contribution
from core.scoring.engine import ScoringEngine

logger = logging.getLogger(__name__)



def award_points_for_contribution(contribution_or_id: Contribution | int) -> dict:
    """
    Atomically award points for a confirmed MERGED Contribution (PRD §14, §15, Deliverable 1).
    Delegates to the central authoritative ScoringEngine pipeline.
    """
    return ScoringEngine.award_points_for_contribution(contribution_or_id)

