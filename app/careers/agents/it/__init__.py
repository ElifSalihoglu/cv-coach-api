"""The IT career agent: software, data, AI and infrastructure roles."""

from app.careers.agents.it.gates import DRAFT_GATES, REQUIREMENT_GATES
from app.careers.agents.it.model_input import it_input
from app.careers.agents.it.prompt import IT_SYSTEM_PROMPT
from app.careers.agents.it.rules import offers_choice
from app.careers.core.agent import CareerAgent
from app.careers.core.profile import DomainProfile
from app.careers.core.state import AgentCard

IT_PROFILE = DomainProfile(
    id="it",
    system_prompt=IT_SYSTEM_PROMPT,
    build_input=it_input,
    offers_choice=offers_choice,
    requirement_gates=REQUIREMENT_GATES,
    draft_gates=DRAFT_GATES,
    # lexicon and limits: the shared defaults
)

IT_CARD = AgentCard(
    id="it",
    domain="Information technology",
    description="Software, data, AI/ML and infrastructure roles.",
    # What this agent itself treats as a clear sign of an IT posting, matched in the job title
    # (or target position). Short on purpose: a title that matches none goes to the general agent.
    routing_cues=(
        "software engineer",
        "software developer",
        "developer",
        "programmer",
        "devops",
        "sre",
        "site reliability",
        "backend",
        "back-end",
        "frontend",
        "front-end",
        "full stack",
        "fullstack",
        "data engineer",
        "data scientist",
        "machine learning",
        "ml engineer",
        "ai",
        "llm",
        "cloud engineer",
        "platform engineer",
        "qa engineer",
        "test automation",
        "cybersecurity",
        "security engineer",
        "mobile developer",
        "database administrator",
        "yazılım",
        "yazilim",
        "geliştirici",
        "gelistirici",
        "veri mühendisi",
        "siber güvenlik",
    ),
)

IT_AGENT = CareerAgent(IT_CARD, IT_PROFILE)

__all__ = ["IT_AGENT", "IT_CARD", "IT_PROFILE"]
