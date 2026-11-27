"""
CareerAgent: the one agent implementation. The IT agent and the General agent are both instances,
differing only in their card and their `DomainProfile`. Execution is the shared `AgentEngine`'s.
An agent is built once and holds nothing per request.
"""
from app.careers.core.engine import DEFAULT_ENGINE, AgentEngine
from app.careers.core.profile import DomainProfile
from app.careers.core.state import AgentCard, CareerCase
from app.models.coaching import CoachResult
from app.services.llm_client import ContentGenerator


class CareerAgent:
    def __init__(self, card: AgentCard, profile: DomainProfile, engine: AgentEngine = DEFAULT_ENGINE) -> None:
        self.card = card
        self.profile = profile
        self._engine = engine

    async def analyze(self, case: CareerCase, llm: ContentGenerator) -> CoachResult:
        return await self._engine.run(self.profile, case, llm)
