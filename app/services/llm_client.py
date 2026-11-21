import json
from typing import Any

import openai
from pydantic import ValidationError

from app.models.schemas import GeneratedCVContent


class LLMError(Exception):
    """Base class for errors the service layer should handle."""


class LLMTimeoutError(LLMError):
    """The provider did not answer in time."""


class LLMUnavailableError(LLMError):
    """The provider is unreachable, rate limited or failing on its side."""


class LLMOutputError(LLMError):
    """The provider answered, but the answer cannot be used."""


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
        self, system_prompt: str, user_content: dict[str, Any]
    ) -> GeneratedCVContent:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_content)},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            )
        # APITimeoutError is a subclass of APIConnectionError, so it must come first.
        except openai.APITimeoutError as exc:
            raise LLMTimeoutError("The language model did not respond in time.") from exc
        except (
            openai.RateLimitError,
            openai.APIConnectionError,
            openai.InternalServerError,
        ) as exc:
            raise LLMUnavailableError("The language model is currently unavailable.") from exc

        message = response.choices[0].message
        if getattr(message, "refusal", None):
            raise LLMOutputError(f"The language model refused: {message.refusal}")
        if not message.content:
            raise LLMOutputError("The language model returned an empty answer.")

        try:
            return GeneratedCVContent.model_validate_json(message.content)
        except ValidationError as exc:
            raise LLMOutputError("The language model returned invalid content.") from exc
