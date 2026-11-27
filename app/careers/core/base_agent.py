"""
The one standard every specialist agent follows.

Composition, not inheritance: a specialist is a card (who it is) plus a `DomainProfile` (what is
specific to its field), run by the shared `AgentEngine`. A new domain is a new profile and a
registry entry; no specialist subclasses another and none has its own way of executing.

Lifecycle: built once, holds nothing per request, `analyze` is called per request with the case
and the model client.
"""
from typing import Protocol

from app.careers.core.engine import DEFAULT_ENGINE, AgentEngine
from app.careers.core.profile import DomainProfile
from app.careers.core.state import AgentCard, CareerCase
from app.models.coaching import CoachModelOutput, CoachResult
from app.models.cv_document import StructuredCV
from app.services.cv_coach import ContentGenerator


class BaseCareerAgent(Protocol):
    """What the rest of the system may rely on. Agents hold no per-request state."""

    card: AgentCard

    async def analyze(self, case: CareerCase, llm: ContentGenerator) -> CoachResult:
        ...


class SpecialistAgent:
    """A career agent made of a card and a domain profile, executed by the shared engine."""

    def __init__(self, card: AgentCard, profile: DomainProfile, engine: AgentEngine = DEFAULT_ENGINE) -> None:
        self.card = card
        self.profile = profile
        self._engine = engine

    async def analyze(self, case: CareerCase, llm: ContentGenerator) -> CoachResult:
        return await self._engine.run(self.profile, case, llm)

    def build_result(
        self, cv: StructuredCV, job_description: str, output: CoachModelOutput, focus: str = ""
    ) -> CoachResult:
        """Our own checks alone, for a model answer someone already has (tests, evaluation)."""
        return self._engine.build_result(self.profile, cv, job_description, output, focus)
