"""The General agent: analyses any occupation that no specialist agent claims."""
from app.careers.agents.general.gates import DRAFT_GATES, REQUIREMENT_GATES
from app.careers.agents.general.model_input import general_input
from app.careers.agents.general.prompt import GENERAL_SYSTEM_PROMPT
from app.careers.agents.general.rules import GENERAL_LEXICON, offers_choice
from app.careers.core.agent import CareerAgent
from app.careers.core.profile import DomainProfile
from app.careers.core.state import AgentCard

GENERAL_PROFILE = DomainProfile(
    id="general",
    system_prompt=GENERAL_SYSTEM_PROMPT,
    build_input=general_input,
    offers_choice=offers_choice,
    requirement_gates=REQUIREMENT_GATES,
    draft_gates=DRAFT_GATES,
    lexicon=GENERAL_LEXICON,
)

GENERAL_CARD = AgentCard(
    id="general",
    domain="General career",
    description="Any occupation without a dedicated agent: care, education, sales, administration, "
                "hospitality, trades, public service and fields not yet covered.",
    # no routing cues by design: the orchestrator picks it when no specialist clearly fits
)

GENERAL_AGENT = CareerAgent(GENERAL_CARD, GENERAL_PROFILE)
