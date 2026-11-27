import asyncio
import json
import logging
from types import SimpleNamespace

import httpx
import openai
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_llm_client
from app.logging_utils import log_event
from app.main import app
from app.models.cv_document import ParsedCV
from app.services.llm_client import LLMClient, LLMError

SECRET_CV = "ZXQ-UNIQUE-CV-PHRASE built a secret rocket guidance system"
FAKE_REQUEST = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")

MODEL_OUTPUT = {
    "name": "ZXQ-UNIQUE-MODEL-OUTPUT name",
    "summary": "ZXQ-UNIQUE-MODEL-OUTPUT summary",
}


class FakeCompletions:
    def __init__(self, content=None, refusal=None, error=None, usage=None, finish_reason=None, served_model=None):
        self.content, self.refusal, self.error, self.usage = content, refusal, error, usage
        self.finish_reason, self.served_model = finish_reason, served_model

    async def create(self, **kwargs):
        if self.error is not None:
            raise self.error
        message = SimpleNamespace(content=self.content, refusal=self.refusal)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message, finish_reason=self.finish_reason)],
            usage=self.usage,
            model=self.served_model,
        )


def fake_openai(**kwargs):
    return SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions(**kwargs)))


def good_openai():
    return fake_openai(
        content=json.dumps(MODEL_OUTPUT),
        usage=SimpleNamespace(prompt_tokens=321, completion_tokens=45),
    )


def app_records(caplog):
    return [r for r in caplog.records if r.name.startswith("app")]


def by_event(caplog, event):
    return [r for r in app_records(caplog) if r.event == event]


# ---------------------------------------------------------- LLM client


def _run_llm(**kwargs):
    client = LLMClient(fake_openai(**kwargs), model="gpt-test")
    return asyncio.run(client.generate("system prompt", {"cv": SECRET_CV}, ParsedCV))


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"error": openai.APITimeoutError(request=FAKE_REQUEST)}, "llm_timeout"),
        ({"error": openai.APIConnectionError(request=FAKE_REQUEST)}, "llm_unavailable"),
        ({"content": "not json ZXQ-UNIQUE-MODEL-OUTPUT"}, "llm_invalid_output"),
        ({"content": None, "refusal": "no ZXQ-UNIQUE-MODEL-OUTPUT"}, "llm_refusal"),
        ({"content": ""}, "llm_empty_output"),
    ],
    ids=["timeout", "unavailable", "invalid-output", "refusal", "empty"],
)
def test_llm_failures_get_distinct_reason_codes_and_are_logged_once(caplog, kwargs, reason):
    caplog.set_level(logging.INFO, logger="app")

    with pytest.raises(LLMError):
        _run_llm(**kwargs)

    lines = by_event(caplog, "llm_call")
    assert len(lines) == 1
    assert lines[0].levelno == logging.WARNING
    message = lines[0].getMessage()
    assert "model=gpt-test" in message and "outcome=failed" in message
    assert f"reason={reason}" in message and "duration_ms=" in message
    assert "ZXQ-UNIQUE" not in caplog.text


def test_llm_call_logs_start_and_enriched_result_without_content(caplog):
    caplog.set_level(logging.INFO, logger="app")
    client = LLMClient(
        fake_openai(
            content=json.dumps(MODEL_OUTPUT),
            usage=SimpleNamespace(prompt_tokens=412, completion_tokens=96),
            finish_reason="stop",
            served_model="gpt-test-2026-01-01",
        ),
        model="gpt-test",
    )

    asyncio.run(client.generate("system prompt", {"cv": SECRET_CV}, ParsedCV))

    start = by_event(caplog, "llm_call_start")[0].getMessage()
    assert "model=gpt-test" in start and "temperature=0.3" in start
    assert "input_chars=" in start
    done = by_event(caplog, "llm_call")[0].getMessage()
    for expected in (
        "outcome=ok",
        "tokens_in=412",
        "tokens_out=96",
        "finish_reason=stop",
        "served_model=gpt-test-2026-01-01",
    ):
        assert expected in done
    assert "ZXQ-UNIQUE" not in caplog.text


def test_truncated_answer_shows_finish_reason_length(caplog):
    caplog.set_level(logging.INFO, logger="app")

    with pytest.raises(LLMError):
        _run_llm(content='{"name": "cut off', finish_reason="length")

    message = by_event(caplog, "llm_call")[0].getMessage()
    assert "reason=llm_invalid_output" in message and "finish_reason=length" in message


def test_llm_success_without_usage_logs_no_token_fields(caplog):
    caplog.set_level(logging.INFO, logger="app")

    _run_llm(content=json.dumps(MODEL_OUTPUT))

    message = by_event(caplog, "llm_call")[0].getMessage()
    assert "outcome=ok" in message and "tokens_in" not in message


def test_the_parse_endpoint_logs_the_llm_call_under_the_request_id_without_content(caplog, monkeypatch):
    caplog.set_level(logging.INFO, logger="app")
    llm = LLMClient(good_openai(), model="gpt-test")
    monkeypatch.setitem(app.dependency_overrides, get_llm_client, lambda: llm)

    with TestClient(app) as client:
        response = client.post("/v1/cv/parse", json={"cv_text": SECRET_CV})

    assert response.status_code == 200
    llm = by_event(caplog, "llm_call")[0]
    assert llm.request_id == response.headers["X-Request-ID"]
    assert "tokens_in=321" in llm.getMessage()
    end = by_event(caplog, "request_end")[0].getMessage()
    assert "status=200" in end and "duration_ms=" in end
    assert not [r for r in app_records(caplog) if r.levelno >= logging.ERROR]
    assert SECRET_CV not in caplog.text and "ZXQ-UNIQUE-MODEL-OUTPUT" not in caplog.text


# ---------------------------------------------------------- helper


def test_log_event_redacts_free_text_values(caplog):
    caplog.set_level(logging.INFO, logger="app")

    log_event(
        logging.getLogger("app.test"),
        logging.INFO,
        "probe",
        safe="gpt-4.1-mini",
        free_text="my secret cv text",
        url="https://a.b/c?jk=1",
        count=3,
        none_value=None,
    )

    message = caplog.records[-1].getMessage()
    assert "safe=gpt-4.1-mini" in message and "count=3" in message
    assert "free_text=<redacted>" in message and "url=<redacted>" in message
    assert "none_value" not in message
    assert "secret" not in message
