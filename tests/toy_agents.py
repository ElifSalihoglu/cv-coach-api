"""
Test-only specialists. `specialist` builds a REAL one (card + profile, run by the shared engine), so
tests that use it exercise the real AgentEngine with a fake model. `broken` is a failure injection.
"""
from typing import Any

from app.careers.core.base_agent import SpecialistAgent
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


def specialist(
    agent_id: str, domain: str, *cues: str, prompt: str | None = None, gates: tuple[Gate, ...] = ()
) -> SpecialistAgent:
    profile = DomainProfile(
        id=agent_id,
        system_prompt=prompt or f"You are the {domain} test coach.",
        build_input=toy_input,
        offers_choice=lambda description: False,
        requirement_gates=gates,
    )
    return SpecialistAgent(AgentCard(agent_id, domain, f"{domain} test agent", routing_cues=tuple(cues)), profile)


class Broken:
    """A specialist whose own code fails (not the model): the General agent must answer instead."""

    def __init__(self, agent_id: str, domain: str, *cues: str) -> None:
        self.card = AgentCard(agent_id, domain, f"{domain} broken agent", routing_cues=tuple(cues))

    async def analyze(self, case, llm):
        raise RuntimeError("bug in the agent")
