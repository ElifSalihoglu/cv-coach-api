from typing import Protocol

from app.models.cv_document import CVParseResponse, ParsedCV
from app.prompts.cv_templates import PARSE_CV_SYSTEM_PROMPT
from app.services.cv_parsing import assign_ids, check_against_text
from app.services.llm_client import ContentGenerator


class CVCoach(Protocol):
    async def parse(self, cv_text: str) -> CVParseResponse:
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
