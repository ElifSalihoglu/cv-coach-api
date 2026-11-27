"""
The API-facing call shape: `analyze(cv, job_title, job_description, focus, *, domain, career_goal)`.

The route depends on this shape (the legacy `ITCareerCoach` has it too, which keeps the old route
tests working). It only builds the case and asks the General agent to handle it.
"""
from app.careers.agents.general import GeneralAgent
from app.careers.core.state import CareerCase, CoachResponse
from app.models.cv_document import StructuredCV
from app.services.cv_coach import ContentGenerator


class CoachFacade:
    def __init__(self, general: GeneralAgent, llm: ContentGenerator) -> None:
        self._general = general
        self._llm = llm

    async def analyze(
        self, cv: StructuredCV, job_title: str, job_description: str, focus: str = "",
        *, domain: str = "", career_goal: str = "",
    ) -> CoachResponse:
        case = CareerCase(cv, job_title, job_description, focus, domain_override=domain, career_goal=career_goal)
        return (await self._general.handle(case, self._llm)).response()
