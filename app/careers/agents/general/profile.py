"""The General agent's own analysis definition: card and profile, run by the shared engine."""
from app.careers.agents.general.gates import DRAFT_GATES, REQUIREMENT_GATES
from app.careers.agents.general.model_input import general_input
from app.careers.agents.general.prompt import GENERAL_SYSTEM_PROMPT
from app.careers.agents.general.rules import GENERAL_LEXICON, offers_choice
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
    description="Entry point of the system. Delegates to a specialist when one clearly fits; "
                "otherwise analyses any occupation itself: care, education, sales, administration, "
                "hospitality, trades, public service and fields not yet covered.",
    # no routing cues by design: it is chosen when no specialist clearly fits
)
