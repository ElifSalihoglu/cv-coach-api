import asyncio
import json
from types import SimpleNamespace

from app.models.schemas import GeneratedCVContent
from app.services.llm_client import LLMClient


class FakeCompletions:
    """Stands in for openai_client.chat.completions and records each call."""

    def __init__(self, content):
        self.content = content
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        message = SimpleNamespace(content=self.content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def make_fake_openai(content):
    completions = FakeCompletions(content)
    fake_openai = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return fake_openai, completions


def test_generate_returns_validated_content():
    model_output = {
        "improved_bullets": ["Automated weekly reporting with Python."],
        "summary": "Python developer focused on data automation.",
        "linkedin_headline": "AI Engineer | Python | Data Automation",
    }
    fake_openai, completions = make_fake_openai(json.dumps(model_output))
    client = LLMClient(openai_client=fake_openai, model="test-model")

    result = asyncio.run(
        client.generate(system_prompt="test prompt", user_content={"job_title": "AI Engineer"})
    )

    assert isinstance(result, GeneratedCVContent)
    assert result.improved_bullets == model_output["improved_bullets"]
    assert completions.calls[0]["model"] == "test-model"
