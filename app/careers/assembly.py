"""What this deployment is made of. Adding a domain: one import and one `register` line here."""
from app.careers.agents.general import GeneralAgent
from app.careers.agents.it import IT_AGENT
from app.careers.registry import AgentRegistry


def build_default_registry() -> AgentRegistry:
    """The specialists. The General agent is not one of them: it owns the registry."""
    registry = AgentRegistry()
    registry.register(IT_AGENT)
    return registry


def build_default_general_agent() -> GeneralAgent:
    return GeneralAgent(build_default_registry())
