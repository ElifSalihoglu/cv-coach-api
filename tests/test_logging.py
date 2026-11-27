import asyncio
import json
import logging
from types import SimpleNamespace

import httpx
import openai
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_llm_client
from app.api.v1.routes_jobs import get_job_search
from app.logging_utils import log_event
from app.main import app
from app.models.cv_document import ParsedCV
from app.services.llm_client import LLMClient, LLMError

SECRET_CV = "ZXQ-UNIQUE-CV-PHRASE built a secret rocket guidance system"
SECRET_QUERY = "ZXQ-UNIQUE-QUERY"
SECRET_JOB_TEXT = "ZXQ-UNIQUE-JOB-DESCRIPTION"
SECRET_COMPANY = "ZXQ-UNIQUE-COMPANY"
FAKE_REQUEST = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")

MODEL_OUTPUT = {
    "name": "ZXQ-UNIQUE-MODEL-OUTPUT name",
    "summary": "ZXQ-UNIQUE-MODEL-OUTPUT summary",
}
SECRETS = [
    SECRET_CV,
    SECRET_QUERY,
    SECRET_JOB_TEXT,
    SECRET_COMPANY,
    "ZXQ-UNIQUE-MODEL-OUTPUT",
    "jk=",
    "https://",
    "sk-test-key",
]


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


# ---------------------------------------------------------------- acceptance


def test_a_search_request_logs_one_request_id_and_one_line_per_stage(caplog, monkeypatch):
    caplog.set_level(logging.INFO, logger="app")
    search_results = [
        {
            "title": "RAG Engineer",
            "company": SECRET_COMPANY,
            "location": "Berlin",
            "url": "https://de.indeed.com/viewjob?jk=aaa",
            "full_description": SECRET_JOB_TEXT,
            "detail_duration_ms": 1200,
        },
        {
            "title": "Vision Engineer",
            "company": "Beta",
            "location": "Berlin",
            "url": "https://de.indeed.com/viewjob?jk=bbb",
            "full_description": "",
            "detail_duration_ms": 10050,
            "detail_error": "description_empty",
        },
        {"title": "", "company": "", "location": "", "url": "", "full_description": ""},
    ]
    monkeypatch.setitem(
        app.dependency_overrides,
        get_job_search,
        lambda: lambda query, city, country, limit: search_results,
    )

    with TestClient(app) as client:
        response = client.post("/v1/jobs/search", json={"query": SECRET_QUERY, "city": "Berlin", "limit": 5})

    assert response.status_code == 200
    records = app_records(caplog)

    # one request id on every line, and it is the one returned to the caller
    request_ids = {r.request_id for r in records}
    assert request_ids == {response.headers["X-Request-ID"]}
    assert "-" not in request_ids

    start = by_event(caplog, "jobs_request")[0].getMessage()
    assert "endpoint=/v1/jobs/search" in start and "max_jobs=5" in start

    search = by_event(caplog, "job_search")[0].getMessage()
    for expected in (
        "source=indeed",
        "outcome=ok",
        "cards=3",
        "skipped_no_url=1",
        "processed=2",
        "duration_ms=",
        "detail_ms=11250",
    ):
        assert expected in search

    # the problem job is distinguishable by position, stage and reason
    problems = [r for r in by_event(caplog, "job_detail") if r.levelno == logging.WARNING]
    assert len(problems) == 1
    problem = problems[0].getMessage()
    for expected in ("job=2", "stage=detail", "outcome=failed", "reason=description_empty", "duration_ms=10050"):
        assert expected in problem
    ok_detail = [r for r in by_event(caplog, "job_detail") if r.levelno == logging.INFO][0]
    assert "job=1" in ok_detail.getMessage()

    assert not by_event(caplog, "llm_call")  # searching never calls a model

    end = by_event(caplog, "request_end")[0].getMessage()
    assert "status=200" in end and "duration_ms=" in end

    # nothing sensitive was logged
    assert not [r for r in records if r.levelno >= logging.ERROR]
    for secret in SECRETS:
        assert secret not in caplog.text


# ---------------------------------------------------------- search stage


def _search_with(monkeypatch, search):
    monkeypatch.setitem(app.dependency_overrides, get_job_search, lambda: search)
    with TestClient(app) as client:
        return client.post("/v1/jobs/search", json={"query": SECRET_QUERY, "city": "Berlin"})


def test_zero_results_and_scraper_error_are_distinguishable(caplog, monkeypatch):
    caplog.set_level(logging.INFO, logger="app")

    empty = _search_with(monkeypatch, lambda q, c, k, n: [])
    empty_line = by_event(caplog, "job_search")[0]
    assert empty.status_code == 200
    assert empty_line.levelno == logging.INFO
    assert "outcome=empty" in empty_line.getMessage()
    assert "cards=0" in empty_line.getMessage()
    assert "reason=" not in empty_line.getMessage()

    caplog.clear()

    def broken(q, c, k, n):
        raise RuntimeError(f"chrome crashed while searching {SECRET_QUERY}")

    failed = _search_with(monkeypatch, broken)
    error_lines = by_event(caplog, "job_search")
    assert failed.status_code == 502
    assert len(error_lines) == 1  # not logged again by the route
    assert error_lines[0].levelno == logging.ERROR
    message = error_lines[0].getMessage()
    assert "outcome=error" in message and "reason=scraper_error" in message
    assert "exception=RuntimeError" in message
    assert SECRET_QUERY not in caplog.text
    assert "status=502" in by_event(caplog, "request_end")[0].getMessage()


def test_detail_page_not_opened_is_told_apart_from_empty_description(caplog, monkeypatch):
    caplog.set_level(logging.INFO, logger="app")
    results = [
        {
            "title": "A",
            "company": "x",
            "location": "y",
            "url": "https://de.indeed.com/viewjob?jk=a",
            "full_description": "",
            "detail_error": "detail_open_failed",
            "detail_duration_ms": 10000,
        },
        {
            "title": "B",
            "company": "x",
            "location": "y",
            "url": "https://de.indeed.com/viewjob?jk=b",
            "full_description": "",
            "detail_error": "description_empty",
            "detail_duration_ms": 10000,
        },
    ]

    _search_with(monkeypatch, lambda q, c, k, n: results)

    reasons = [r.getMessage() for r in by_event(caplog, "job_detail") if r.levelno == logging.WARNING]
    assert "job=1" in reasons[0] and "reason=detail_open_failed" in reasons[0]
    assert "job=2" in reasons[1] and "reason=description_empty" in reasons[1]


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
    assert "job=" not in llm.getMessage()
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
