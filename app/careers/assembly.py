"""What this deployment is made of. Adding a domain: one import and one `register` line here."""

from app.careers.agents.finance import FINANCE_AGENT
from app.careers.agents.general import GENERAL_AGENT
from app.careers.agents.healthcare import HEALTHCARE_AGENT
from app.careers.agents.hr import HR_AGENT
from app.careers.agents.it import IT_AGENT
from app.careers.orchestrator import CareerOrchestrator
from app.careers.registry import AgentRegistry
from app.services.llm_client import ContentGenerator


def build_default_registry() -> AgentRegistry:
    """The specialists. The general agent is not one of them."""
    registry = AgentRegistry()
    for agent in (IT_AGENT, HEALTHCARE_AGENT, HR_AGENT, FINANCE_AGENT):
        registry.register(agent)
    return registry


def build_orchestrator(llm: ContentGenerator) -> CareerOrchestrator:
    return CareerOrchestrator(build_default_registry(), GENERAL_AGENT, llm)
