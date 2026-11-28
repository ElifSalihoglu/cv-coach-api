"""The Finance career agent: accounting, audit, banking, investment, risk and financial analysis roles."""

from app.careers.agents.finance.gates import DRAFT_GATES, REQUIREMENT_GATES
from app.careers.agents.finance.model_input import finance_input
from app.careers.agents.finance.prompt import FINANCE_SYSTEM_PROMPT
from app.careers.agents.finance.rules import FINANCE_LEXICON, offers_choice
from app.careers.core.agent import CareerAgent
from app.careers.core.profile import DomainProfile
from app.careers.core.state import AgentCard

FINANCE_PROFILE = DomainProfile(
    id="finance",
    system_prompt=FINANCE_SYSTEM_PROMPT,
    build_input=finance_input,
    offers_choice=offers_choice,
    requirement_gates=REQUIREMENT_GATES,
    draft_gates=DRAFT_GATES,
    lexicon=FINANCE_LEXICON,
)

FINANCE_CARD = AgentCard(
    id="finance",
    domain="Finance",
    description="Accounting, audit, tax, treasury, banking, investment, risk, compliance and financial analysis roles.",
    routing_cues=(
        "accountant",
        "auditor",
        "financial analyst",
        "investment analyst",
        "risk analyst",
        "controller",
        "banker",
    ),
)

FINANCE_AGENT = CareerAgent(FINANCE_CARD, FINANCE_PROFILE)

__all__ = ["FINANCE_AGENT", "FINANCE_CARD", "FINANCE_PROFILE"]
