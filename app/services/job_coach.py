"""
LEGACY compatibility layer. New code must not import from here.

The IT coach is now the IT specialist agent (`app.careers.agents.it`) run by the shared
`AgentEngine`, and requests enter through the General agent (`app.careers.agents.general`).
This module only keeps the old names alive for the existing tests and any outside caller:

- `ITCareerCoach(llm).analyze(cv, job_title, job_description, focus)`
- `build_result`, `coach_input`, `offers_choice`, `unsupported_design_claims`
- the small helpers `_fold`, `_quote_in`, `_slug`, `_is_generic`

Production code uses `CareerCase` + the registry/General agent instead. Remove this file once
the tests that import it are moved to the new entry points.
"""
from app.careers.agents.it import IT_AGENT, IT_PROFILE
from app.careers.agents.it.model_input import coach_input
from app.careers.agents.it.rules import is_generic as _is_generic
from app.careers.agents.it.rules import offers_choice, unsupported_design_claims
from app.careers.core.evidence import fold as _fold
from app.careers.core.evidence import quote_in as _quote_in
from app.careers.core.evidence import slug as _slug
from app.careers.core.state import CareerCase
from app.models.coaching import CoachModelOutput, CoachResult
from app.models.cv_document import StructuredCV
from app.services.cv_coach import ContentGenerator

MAX_SUGGESTIONS = IT_PROFILE.limits.max_suggestions
MAX_PROMOTES = IT_PROFILE.limits.per_kind["promote"]
MAX_QUESTIONS = IT_PROFILE.limits.max_questions


class ITCareerCoach:
    """LEGACY: the IT specialist alone, without routing. Use the General agent instead."""

    def __init__(self, llm: ContentGenerator) -> None:
        self._llm = llm

    async def analyze(
        self, cv: StructuredCV, job_title: str, job_description: str, focus: str = "",
        *, domain: str = "", career_goal: str = "",
    ) -> CoachResult:
        """
        One model call; a second one only if the model invents a choice the posting never offers.
        `domain` and `career_goal` are routing hints: this coach is the IT agent alone and ignores them.
        """
        return await IT_AGENT.analyze(CareerCase(cv, job_title, job_description, focus), self._llm)


def build_result(
    cv: StructuredCV, job_description: str, output: CoachModelOutput, focus: str = ""
) -> CoachResult:
    """Our own checks on a model answer, with the IT agent's rules."""
    return IT_AGENT.build_result(cv, job_description, output, focus)


__all__ = [
    "ITCareerCoach", "build_result", "coach_input", "offers_choice", "unsupported_design_claims",
    "MAX_SUGGESTIONS", "MAX_PROMOTES", "MAX_QUESTIONS",
]
