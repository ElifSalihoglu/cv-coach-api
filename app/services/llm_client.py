import json
from typing import Any

from app.models.schemas import GeneratedCVContent


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
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_content)},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        content = response.choices[0].message.content
        return GeneratedCVContent.model_validate_json(content)
