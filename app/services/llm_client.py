import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol, Sequence, TypeVar

import openai
from pydantic import BaseModel, ValidationError

from app.logging_utils import log_event

logger = logging.getLogger("app.llm")

TEMPERATURE = 0.3

T = TypeVar("T", bound=BaseModel)
R = TypeVar("R")


@dataclass(frozen=True)
class ToolSpec:
    """A tool the model may call. Delegation tools take no arguments: calling one is the decision."""

    name: str
    description: str


@dataclass(frozen=True)
class ToolStep:
    """One finished tool call: the model called `name` and `result` (a short JSON summary) came back."""

    name: str
    call_id: str
    result: str


class ContentGenerator(Protocol):
    """What the agents need from a model client; `LLMClient` is the real one, tests pass fakes."""

    async def generate(self, system_prompt: str, user_content: dict[str, Any], output_model: type[T]) -> T: ...

    async def choose_tool(
        self,
        system_prompt: str,
        user_content: dict[str, Any],
        tools: Sequence[ToolSpec],
        steps: Sequence[ToolStep] = (),
    ) -> str | None:
        """The name of the next tool the model calls, or None when it is done. `steps` are the calls so far."""
        ...


class LLMError(Exception):
    """Base class for errors the service layer should handle."""

    # Safe, stable code for logs. Never put exception text in logs: it can
    # contain model output or user data.
    reason_code = "llm_error"


class LLMTimeoutError(LLMError):
    """The provider did not answer in time."""

    reason_code = "llm_timeout"


class LLMUnavailableError(LLMError):
    """The provider is unreachable, rate limited or failing on its side."""

    reason_code = "llm_unavailable"


class LLMOutputError(LLMError):
    """The provider answered, but the answer cannot be used."""

    reason_code = "llm_invalid_output"

    def __init__(self, message: str, reason_code: str | None = None) -> None:
        super().__init__(message)
        if reason_code is not None:
            self.reason_code = reason_code


class LLMClient:
    """
    Thin wrapper around the OpenAI chat completions API.

    The OpenAI client is passed in instead of imported, so tests can use a
    fake client and importing this module never requires an API key.
    """

    def __init__(self, openai_client: Any, model: str) -> None:
        self._client = openai_client
        self._model = model

    async def generate(
        self,
        system_prompt: str,
        user_content: dict[str, Any],
        output_model: type[T],
    ) -> T:
        # ensure_ascii=False keeps Turkish characters as they are in the prompt.
        user_message = json.dumps(user_content, ensure_ascii=False)
        return await self._logged(
            len(system_prompt) + len(user_message),
            lambda details: self._generate(system_prompt, user_message, details, output_model),
        )

    async def choose_tool(
        self,
        system_prompt: str,
        user_content: dict[str, Any],
        tools: Sequence[ToolSpec],
        steps: Sequence[ToolStep] = (),
    ) -> str | None:
        user_message = json.dumps(user_content, ensure_ascii=False)
        return await self._logged(
            len(system_prompt) + len(user_message) + sum(len(s.result) for s in steps),
            lambda details: self._choose_tool(system_prompt, user_message, tools, steps, details),
        )

    async def _logged(self, input_chars: int, call: Callable[[dict[str, object]], Awaitable[R]]) -> R:
        started = time.perf_counter()
        # Sizes and settings only, never the prompt or the content itself.
        log_event(
            logger,
            logging.INFO,
            "llm_call_start",
            model=self._model,
            temperature=TEMPERATURE,
            input_chars=input_chars,
        )
        details: dict[str, object] = {}
        try:
            result = await call(details)
        except LLMError as exc:
            # The single place where an LLM failure is logged.
            log_event(
                logger,
                logging.WARNING,
                "llm_call",
                model=self._model,
                outcome="failed",
                reason=exc.reason_code,
                duration_ms=round((time.perf_counter() - started) * 1000),
                **details,
            )
            raise
        log_event(
            logger,
            logging.INFO,
            "llm_call",
            model=self._model,
            outcome="ok",
            duration_ms=round((time.perf_counter() - started) * 1000),
            **details,
        )
        return result

    async def _create(self, details: dict[str, object], **request: Any) -> Any:
        """The provider call: errors mapped to ours, usage and finish reason noted for the log."""
        try:
            response = await self._client.chat.completions.create(model=self._model, temperature=TEMPERATURE, **request)
        # APITimeoutError is a subclass of APIConnectionError, so it must come first.
        except openai.APITimeoutError as exc:
            raise LLMTimeoutError("The language model did not respond in time.") from exc
        except (
            openai.RateLimitError,
            openai.APIConnectionError,
            openai.InternalServerError,
        ) as exc:
            raise LLMUnavailableError("The language model is currently unavailable.") from exc

        usage = getattr(response, "usage", None)
        for key, attr in (("tokens_in", "prompt_tokens"), ("tokens_out", "completion_tokens")):
            value = getattr(usage, attr, None)
            if isinstance(value, int):
                details[key] = value
        choice = response.choices[0]
        # "length" means the answer was cut off, a common cause of invalid output.
        finish_reason = getattr(choice, "finish_reason", None)
        if isinstance(finish_reason, str):
            details["finish_reason"] = finish_reason
        served_model = getattr(response, "model", None)
        if isinstance(served_model, str):
            details["served_model"] = served_model
        return choice.message

    async def _choose_tool(
        self,
        system_prompt: str,
        user_message: str,
        tools: Sequence[ToolSpec],
        steps: Sequence[ToolStep],
        details: dict[str, object],
    ) -> str | None:
        history: list[dict[str, Any]] = []
        for step in steps:  # each finished call goes back as an assistant tool call and its tool message
            call = {"id": step.call_id, "type": "function", "function": {"name": step.name, "arguments": "{}"}}
            history.append({"role": "assistant", "content": None, "tool_calls": [call]})
            history.append({"role": "tool", "tool_call_id": step.call_id, "content": step.result})
        message = await self._create(
            details,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
                *history,
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
                    },
                }
                for t in tools
            ],
            tool_choice="auto",
            parallel_tool_calls=False,
        )
        if getattr(message, "refusal", None):
            raise LLMOutputError(f"The language model refused: {message.refusal}", "llm_refusal")
        calls = getattr(message, "tool_calls", None) or []
        return calls[0].function.name if calls else None

    async def _generate(
        self,
        system_prompt: str,
        user_message: str,
        details: dict[str, object],
        output_model: type[T],
    ) -> T:
        message = await self._create(
            details,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
        )
        if getattr(message, "refusal", None):
            raise LLMOutputError(f"The language model refused: {message.refusal}", "llm_refusal")
        if not message.content:
            raise LLMOutputError("The language model returned an empty answer.", "llm_empty_output")

        try:
            return output_model.model_validate_json(message.content)
        except ValidationError as exc:
            raise LLMOutputError("The language model returned invalid content.") from exc
