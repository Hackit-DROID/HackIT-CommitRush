"""
CommitRush System Bootstrap and Initialization Utilities.
"""
from core.models import EventConfig


def bootstrap_event_config() -> EventConfig:
    """
    Ensure the EventConfig singleton row exists with canonical defaults.
    Idempotent: returns existing singleton without modifying operator overrides.
    """
    return EventConfig.get_solo()
