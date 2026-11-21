import openai
from fastapi.testclient import TestClient

from app.api.v1.routes_cv import get_cv_coach
from app.main import app
from app.services.cv_coach import OpenAICVCoach
from app.services.openai_setup import create_openai_client, get_openai_model


def test_create_openai_client_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert create_openai_client() is None


def test_create_openai_client_sets_timeout_and_retries(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")

    client = create_openai_client()

    assert isinstance(client, openai.AsyncOpenAI)
    assert client.timeout == 30.0
    assert client.max_retries == 2


def test_get_openai_model_has_valid_default(monkeypatch):
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    assert get_openai_model() == "gpt-4.1-mini"


def test_get_cv_coach_builds_openai_coach_when_key_is_set(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    get_cv_coach.cache_clear()
    try:
        assert isinstance(get_cv_coach(), OpenAICVCoach)
    finally:
        get_cv_coach.cache_clear()


def test_optimize_returns_503_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_cv_coach.cache_clear()
    payload = {
        "job_title": "AI Engineer",
        "job_description": "Build and maintain Python APIs.",
        "current_bullets": ["Built a Python API for internal reporting."],
    }
    try:
        with TestClient(app) as client:
            response = client.post("/v1/cv/optimize", json=payload)
    finally:
        get_cv_coach.cache_clear()

    assert response.status_code == 503
