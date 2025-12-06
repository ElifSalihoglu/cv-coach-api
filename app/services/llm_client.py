from typing import Any, Dict
import json
from .openai_setup import openai_client, OPENAI_MODEL


class LLMClient:
    """
    Thin wrapper around a language model provider.
    Replace `generate_json` with actual OpenAI / Azure / others.
    """

    def __init__(self) -> None:
        # place for API keys, model names, etc.
        self.model_name = "gpt-4.1-mini"

    async def generate_json(self, system_prompt: str, user_content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calls OpenAI API to generate optimized bullets, summary, and LinkedIn headline.
        """
        job_description = user_content.get("job_description", "")
        current_bullets = user_content.get("current_bullets", [])
        retrieved_examples = user_content.get("retrieved_examples", [])

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_content)}
        ]
        response = await openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        content = response.choices[0].message.content
        return json.loads(content)
