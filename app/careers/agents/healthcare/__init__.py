"""The Healthcare career agent: clinical, nursing, allied health and care roles."""

from app.careers.agents.healthcare.gates import DRAFT_GATES, REQUIREMENT_GATES
from app.careers.agents.healthcare.model_input import healthcare_input
from app.careers.agents.healthcare.prompt import HEALTHCARE_SYSTEM_PROMPT
from app.careers.agents.healthcare.rules import HEALTHCARE_LEXICON, offers_choice
from app.careers.core.agent import CareerAgent
from app.careers.core.profile import DomainProfile
from app.careers.core.state import AgentCard

HEALTHCARE_PROFILE = DomainProfile(
    id="healthcare",
    system_prompt=HEALTHCARE_SYSTEM_PROMPT,
    build_input=healthcare_input,
    offers_choice=offers_choice,
    requirement_gates=REQUIREMENT_GATES,
    draft_gates=DRAFT_GATES,
    lexicon=HEALTHCARE_LEXICON,
)

HEALTHCARE_CARD = AgentCard(
    id="healthcare",
    domain="Healthcare",
    description="Clinical, nursing, medical, allied health, pharmacy, care and health administration roles.",
    routing_cues=("nurse", "doctor", "physician", "clinician", "paramedic", "pharmacist", "therapist", "caregiver"),
)

HEALTHCARE_AGENT = CareerAgent(HEALTHCARE_CARD, HEALTHCARE_PROFILE)

__all__ = ["HEALTHCARE_AGENT", "HEALTHCARE_CARD", "HEALTHCARE_PROFILE"]
