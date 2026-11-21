import asyncio
import json
from types import SimpleNamespace

import httpx
import openai
import pytest

from app.models.schemas import GeneratedCVContent
from app.services.llm_client import (
    LLMClient,
    LLMOutputError,
    LLMTimeoutError,
    LLMUnavailableError,
)

FAKE_REQUEST = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")


class FakeCompletions:
    """Stands in for openai_client.chat.completions and records each call."""

    def __init__(self, content=None, refusal=None, error=None):
        self.content = content
        self.refusal = refusal
        self.error = error
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        message = SimpleNamespace(content=self.content, refusal=self.refusal)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def make_fake_openai(**kwargs):
    completions = FakeCompletions(**kwargs)
    fake_openai = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return fake_openai, completions


def test_generate_returns_validated_content():
    model_output = {
        "improved_bullets": ["Automated weekly reporting with Python."],
        "summary": "Python developer focused on data automation.",
        "linkedin_headline": "AI Engineer | Python | Data Automation",
    }
    fake_openai, completions = make_fake_openai(content=json.dumps(model_output))
    client = LLMClient(openai_client=fake_openai, model="test-model")

    result = asyncio.run(
        client.generate(system_prompt="test prompt", user_content={"job_title": "AI Engineer"})
    )

    assert isinstance(result, GeneratedCVContent)
    assert result.improved_bullets == model_output["improved_bullets"]
    assert completions.calls[0]["model"] == "test-model"


def run_generate(**fake_kwargs):
    fake_openai, _ = make_fake_openai(**fake_kwargs)
    client = LLMClient(openai_client=fake_openai, model="test-model")
    return asyncio.run(client.generate(system_prompt="test prompt", user_content={}))


@pytest.mark.parametrize(
    "content",
    [
        "this is not json",
        json.dumps({"optimized_bullets": [{"text": "old format"}]}),
        json.dumps({"improved_bullets": [], "summary": "x", "linkedin_headline": "y"}),
    ],
    ids=["not-json", "wrong-fields", "breaks-schema-rule"],
)
def test_generate_raises_output_error_for_invalid_content(content):
    with pytest.raises(LLMOutputError):
        run_generate(content=content)


def test_generate_raises_output_error_when_model_refuses():
    with pytest.raises(LLMOutputError):
        run_generate(content=None, refusal="I can't help with that.")


def test_generate_raises_timeout_error_on_openai_timeout():
    with pytest.raises(LLMTimeoutError):
        run_generate(error=openai.APITimeoutError(request=FAKE_REQUEST))


@pytest.mark.parametrize(
    "error",
    [
        openai.RateLimitError(
            "rate limited",
            response=httpx.Response(429, request=FAKE_REQUEST),
            body=None,
        ),
        openai.APIConnectionError(request=FAKE_REQUEST),
        openai.InternalServerError(
            "server error",
            response=httpx.Response(500, request=FAKE_REQUEST),
            body=None,
        ),
    ],
    ids=["rate-limit", "connection", "server-error"],
)
def test_generate_raises_unavailable_error_on_provider_failure(error):
    with pytest.raises(LLMUnavailableError):
        run_generate(error=error)
