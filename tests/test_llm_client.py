import asyncio
import json
from types import SimpleNamespace

import httpx
import openai
import pytest
from pydantic import BaseModel, Field

from app.services.llm_client import (
    LLMClient,
    LLMOutputError,
    LLMTimeoutError,
    LLMUnavailableError,
    ToolSpec,
)


class Answer(BaseModel):
    """A stand-in output schema with one rule the model's answer can break."""

    bullets: list[str] = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)


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
        "bullets": ["Automated weekly reporting with Python."],
        "summary": "Python developer focused on data automation.",
    }
    fake_openai, completions = make_fake_openai(content=json.dumps(model_output))
    client = LLMClient(openai_client=fake_openai, model="test-model")

    result = asyncio.run(
        client.generate(system_prompt="test prompt", user_content={"job_title": "AI Engineer"}, output_model=Answer)
    )

    assert isinstance(result, Answer)
    assert result.bullets == model_output["bullets"]
    assert completions.calls[0]["model"] == "test-model"


def run_generate(**fake_kwargs):
    fake_openai, _ = make_fake_openai(**fake_kwargs)
    client = LLMClient(openai_client=fake_openai, model="test-model")
    return asyncio.run(client.generate(system_prompt="test prompt", user_content={}, output_model=Answer))


@pytest.mark.parametrize(
    "content",
    [
        "this is not json",
        json.dumps({"unexpected_field": [{"text": "wrong shape"}]}),
        json.dumps({"bullets": [], "summary": "x"}),
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


# ---- tool calling (the General agent's delegation decision)

TOOLS = [ToolSpec("ask_it", "Hand this posting to the IT specialist.")]


def choose(tool_calls=None, **fake_kwargs):
    fake_openai, completions = make_fake_openai(**fake_kwargs)
    original = completions.create

    async def create(**kwargs):
        response = await original(**kwargs)
        response.choices[0].message.tool_calls = tool_calls
        return response

    completions.create = create
    client = LLMClient(openai_client=fake_openai, model="test-model")
    answer = asyncio.run(client.choose_tool("prompt", {"job_title": "Engineer"}, TOOLS))
    return answer, completions


def test_choose_tool_returns_the_name_of_the_called_tool_and_sends_the_tools_without_json_mode():
    calls = [SimpleNamespace(function=SimpleNamespace(name="ask_it", arguments="{}"))]
    answer, completions = choose(tool_calls=calls)

    sent = completions.calls[0]
    assert answer == "ask_it"
    assert sent["tool_choice"] == "auto" and "response_format" not in sent
    assert sent["tools"][0]["function"]["name"] == "ask_it"
    assert sent["tools"][0]["function"]["parameters"]["properties"] == {}


def test_choose_tool_returns_none_when_the_model_answers_without_a_tool():
    assert choose(tool_calls=None, content="I will handle it myself.")[0] is None
    assert choose(tool_calls=[])[0] is None


def test_choose_tool_maps_provider_errors_and_refusals_like_generate():
    with pytest.raises(LLMTimeoutError):
        choose(error=openai.APITimeoutError(request=FAKE_REQUEST))
    with pytest.raises(LLMOutputError) as caught:
        choose(refusal="no")
    assert caught.value.reason_code == "llm_refusal"
