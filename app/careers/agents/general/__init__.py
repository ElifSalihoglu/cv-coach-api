"""The General Career Agent: the entry point that delegates, and the analyst of last resort."""
from app.careers.agents.general.agent import GeneralAgent
from app.careers.agents.general.profile import GENERAL_CARD, GENERAL_PROFILE

__all__ = ["GENERAL_CARD", "GENERAL_PROFILE", "GeneralAgent"]
