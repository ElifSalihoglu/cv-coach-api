from typing import Any, Protocol

from app.models.schemas import (
    CVOptimizeRequest,
    CVOptimizeResponse,
    GeneratedCVContent,
)
from app.prompts.cv_templates import BASE_CV_SYSTEM_PROMPT


class CVCoach(Protocol):
    async def optimize(self, request: CVOptimizeRequest) -> CVOptimizeResponse:
        ...


class ContentGenerator(Protocol):
    async def generate(
        self, system_prompt: str, user_content: dict[str, Any]
    ) -> GeneratedCVContent:
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
