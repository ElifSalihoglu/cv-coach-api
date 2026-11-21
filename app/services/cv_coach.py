from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from app.models.cv_document import (
    CVParseResponse,
    ParsedCV,
    StructuredCV,
    TailoredContent,
    TailoredCVResult,
)
from app.models.schemas import (
    CVOptimizeRequest,
    CVOptimizeResponse,
    GeneratedCVContent,
)
from app.prompts.cv_templates import (
    BASE_CV_SYSTEM_PROMPT,
    PARSE_CV_SYSTEM_PROMPT,
    TAILOR_CV_SYSTEM_PROMPT,
)
from app.services.cv_parsing import assign_ids, check_against_text
from app.services.cv_tailoring import build_tailored_cv, model_input

T = TypeVar("T", bound=BaseModel)


class CVCoach(Protocol):
    async def optimize(self, request: CVOptimizeRequest) -> CVOptimizeResponse:
        ...

    async def parse(self, cv_text: str) -> CVParseResponse:
        ...

    async def tailor(
        self, cv: StructuredCV, job_title: str, job_description: str
    ) -> TailoredCVResult:
        ...


class ContentGenerator(Protocol):
    async def generate(
        self,
        system_prompt: str,
        user_content: dict[str, Any],
        output_model: type[T] = GeneratedCVContent,  # type: ignore[assignment]
    ) -> T:
        ...


class OpenAICVCoach:
    """
    Combines the candidate's input with the model call and builds the
    final API response. No job listings are sent to the model yet, so
    retrieved_jobs is always empty.
    """

    def __init__(self, llm_client: ContentGenerator) -> None:
        self._llm = llm_client

    async def optimize(self, request: CVOptimizeRequest) -> CVOptimizeResponse:
        generated = await self._llm.generate(
            system_prompt=BASE_CV_SYSTEM_PROMPT,
            user_content={
                "job_title": request.job_title,
                "job_description": request.job_description,
                "current_bullets": request.current_bullets,
            },
        )
        return CVOptimizeResponse(
            improved_bullets=generated.improved_bullets,
            summary=generated.summary,
            linkedin_headline=generated.linkedin_headline,
            retrieved_jobs=[],
        )

    async def parse(self, cv_text: str) -> CVParseResponse:
        """One model call per uploaded CV. The user reviews the result."""
        parsed = await self._llm.generate(
            system_prompt=PARSE_CV_SYSTEM_PROMPT,
            user_content={"cv_text": cv_text},
            output_model=ParsedCV,
        )
        cv = assign_ids(parsed)
        return CVParseResponse(cv=cv, warnings=check_against_text(cv, cv_text))

    async def tailor(
        self, cv: StructuredCV, job_title: str, job_description: str
    ) -> TailoredCVResult:
        """One model call per job; the original `cv` is never modified."""
        content = await self._llm.generate(
            system_prompt=TAILOR_CV_SYSTEM_PROMPT,
            user_content=model_input(cv, job_title, job_description),
            output_model=TailoredContent,
        )
        return build_tailored_cv(cv, content, job_description)
