from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from app.models.cv_document import CVParseResponse, ParsedCV
from app.prompts.cv_templates import PARSE_CV_SYSTEM_PROMPT
from app.services.cv_parsing import assign_ids, check_against_text

T = TypeVar("T", bound=BaseModel)


class CVCoach(Protocol):
    async def parse(self, cv_text: str) -> CVParseResponse:
        ...


class ContentGenerator(Protocol):
    async def generate(
        self, system_prompt: str, user_content: dict[str, Any], output_model: type[T]
    ) -> T:
        ...


class OpenAICVCoach:
    def __init__(self, llm_client: ContentGenerator) -> None:
        self._llm = llm_client

    async def parse(self, cv_text: str) -> CVParseResponse:
        """One model call per uploaded CV. The user reviews the result."""
        parsed = await self._llm.generate(
            system_prompt=PARSE_CV_SYSTEM_PROMPT,
            user_content={"cv_text": cv_text},
            output_model=ParsedCV,
        )
        cv = assign_ids(parsed)
        return CVParseResponse(cv=cv, warnings=check_against_text(cv, cv_text))
