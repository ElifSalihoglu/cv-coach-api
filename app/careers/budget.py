"""
A per-request limit on model calls. Every call an agent makes goes through `BudgetedLLM`, so the limit
holds however many agents run: the General agent's delegation decisions, the specialists (and their one
repeat each), and the General agent answering after specialists failed. The check happens before the call,
so a refused call costs nothing. How many specialists one request may call is limited separately
(`DEFAULT_MAX_SPECIALISTS`, enforced by the orchestrator).
"""

from typing import Any, Sequence, TypeVar

from pydantic import BaseModel

from app.careers.core.state import OrchestrationError
from app.services.llm_client import ContentGenerator, ToolSpec, ToolStep

T = TypeVar("T", bound=BaseModel)

# At most two specialists (a second one only for a posting that spans two fields), so at most:
# 2 delegation decisions + 2 x 2 specialist calls (one repeat each) + 2 General calls after failures.
DEFAULT_MAX_SPECIALISTS = 2
DEFAULT_MAX_MODEL_CALLS = 8


class BudgetExceeded(OrchestrationError):
    code = "budget_exceeded"


class BudgetedLLM:
    def __init__(self, llm: ContentGenerator, max_calls: int = DEFAULT_MAX_MODEL_CALLS) -> None:
        self._llm = llm
        self.max_calls = max_calls
        self.calls = 0

    def _spend(self) -> None:
        if self.calls >= self.max_calls:
            raise BudgetExceeded(f"The limit of {self.max_calls} model calls for one request is used up.")
        self.calls += 1

    async def generate(self, system_prompt: str, user_content: dict[str, Any], output_model: type[T]) -> T:
        self._spend()
        return await self._llm.generate(
            system_prompt=system_prompt, user_content=user_content, output_model=output_model
        )

    async def choose_tool(
        self,
        system_prompt: str,
        user_content: dict[str, Any],
        tools: Sequence[ToolSpec],
        steps: Sequence[ToolStep] = (),
    ) -> str | None:
        self._spend()
        return await self._llm.choose_tool(
            system_prompt=system_prompt, user_content=user_content, tools=tools, steps=steps
        )
