"""
Test-only agents. `career_agent` builds a REAL one (card + profile, run by the shared engine), so
tests that use it exercise the real AgentEngine with a fake model. `broken_agent` fails inside the
engine, the way a bug in an agent's own code would.
"""
from dataclasses import replace
from typing import Any

from app.careers.core.agent import CareerAgent
from app.careers.core.gates import Gate
from app.careers.core.profile import DomainProfile
from app.careers.core.state import AgentCard
from app.models.cv_document import StructuredCV


def toy_input(cv: StructuredCV, job_title: str, job_description: str, focus: str) -> dict[str, Any]:
    """A deliberately different projection from IT's and General's: titles and bullet texts only."""
    return {
        "title": job_title, "posting": job_description, "focus": focus,
        "bullets": [
            {"id": b.id, "position": i, "text": b.text}
            for exp in cv.experiences for i, b in enumerate(exp.bullets, start=1)
        ],
    }


def career_agent(
    agent_id: str, domain: str, *cues: str, prompt: str | None = None, gates: tuple[Gate, ...] = ()
) -> CareerAgent:
    profile = DomainProfile(
        id=agent_id,
        system_prompt=prompt or f"You are the {domain} test coach.",
        build_input=toy_input,
        offers_choice=lambda description: False,
        requirement_gates=gates,
    )
    return CareerAgent(AgentCard(agent_id, domain, f"{domain} test agent", routing_cues=tuple(cues)), profile)


def broken_agent(agent_id: str, domain: str, *cues: str) -> CareerAgent:
    """An agent whose own code fails (not the model): the orchestrator must answer with the general agent."""

    def explode(*_):
        raise RuntimeError("bug in the agent")

    agent = career_agent(agent_id, domain, *cues)
    agent.profile = replace(agent.profile, build_input=explode)
    return agent
