"""The Human resources career agent: recruiting, talent, compensation, employee relations and people analytics."""

from app.careers.agents.hr.gates import DRAFT_GATES, REQUIREMENT_GATES
from app.careers.agents.hr.model_input import hr_input
from app.careers.agents.hr.prompt import HR_SYSTEM_PROMPT
from app.careers.agents.hr.rules import HR_LEXICON, offers_choice
from app.careers.core.agent import CareerAgent
from app.careers.core.profile import DomainProfile
from app.careers.core.state import AgentCard

HR_PROFILE = DomainProfile(
    id="hr",
    system_prompt=HR_SYSTEM_PROMPT,
    build_input=hr_input,
    offers_choice=offers_choice,
    requirement_gates=REQUIREMENT_GATES,
    draft_gates=DRAFT_GATES,
    lexicon=HR_LEXICON,
)

HR_CARD = AgentCard(
    id="hr",
    domain="Human resources",
    description="Recruiting, talent and learning, compensation and benefits, employee relations, HR operations "
    "and people analytics roles.",
    routing_cues=(
        "recruiter",
        "talent acquisition",
        "hr manager",
        "hr analyst",
        "hr business partner",
        "people analytics",
    ),
)

HR_AGENT = CareerAgent(HR_CARD, HR_PROFILE)

__all__ = ["HR_AGENT", "HR_CARD", "HR_PROFILE"]
