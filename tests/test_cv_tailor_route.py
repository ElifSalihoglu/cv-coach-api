"""POST /v1/cv/tailor: one model call for one job; the CV facts stay untouched."""
import pytest
from fastapi.testclient import TestClient

from app.api.v1.routes_cv import get_cv_coach
from app.main import app
from app.models.cv_document import StructuredCV, TailoredCVResult
from app.services.llm_client import LLMOutputError, LLMTimeoutError, LLMUnavailableError

CV = {
    "name": "Elçin Yıldız", "summary": "Original summary.", "skills": ["Python"],
    "experiences": [{"id": "exp1", "employer": "Acme", "title": "Engineer",
                     "bullets": [{"id": "exp1.b1", "text": "Built a billing API."}]}],
}


class FakeCoach:
    def __init__(self, error: Exception | None = None):
        self.calls: list[tuple[str, str, str]] = []
        self.error = error

    async def tailor(self, cv: StructuredCV, job_title: str, job_description: str):
        self.calls.append((cv.name, job_title, job_description))
        if self.error:
            raise self.error
        return TailoredCVResult(
            cv=cv.model_copy(update={"summary": f"Tailored for {job_title}."}),
            warnings=["exp1.b1: rewrite reverted (new numbers 40)"],
        )


def _post(monkeypatch, coach, **overrides):
    monkeypatch.setitem(app.dependency_overrides, get_cv_coach, lambda: coach)
    body = {"cv": CV, "job_title": "AI Engineer", "job_description": "Build agents.", **overrides}
    with TestClient(app) as client:
        return client.post("/v1/cv/tailor", json=body)


def test_tailors_once_and_returns_cv_and_warnings(monkeypatch):
    coach = FakeCoach()
    response = _post(monkeypatch, coach)

    assert response.status_code == 200
    body = response.json()
    assert body["cv"]["summary"] == "Tailored for AI Engineer."
    assert body["cv"]["name"] == "Elçin Yıldız"
    assert body["warnings"] == ["Bullet 1 at Acme: rewrite reverted (new numbers 40)"]
    assert body["changes"] == [{
        "kind": "summary", "id": "summary", "where": "Summary",
        "before": "Original summary.", "after": "Tailored for AI Engineer.", "detail": "",
    }]
    assert coach.calls == [("Elçin Yıldız", "AI Engineer", "Build agents.")]


def test_without_an_api_key_it_is_503(monkeypatch):
    response = _post(monkeypatch, None)
    assert response.status_code == 503


@pytest.mark.parametrize("error,status", [
    (LLMTimeoutError("slow"), 504),
    (LLMUnavailableError("down"), 503),
    (LLMOutputError("bad"), 502),
])
def test_model_failures_map_to_http_errors(monkeypatch, error, status):
    assert _post(monkeypatch, FakeCoach(error)).status_code == status


@pytest.mark.parametrize("overrides", [
    {"job_title": ""}, {"job_description": ""}, {"job_description": "x" * 20_001},
])
def test_invalid_body_is_422_and_never_calls_the_model(monkeypatch, overrides):
    coach = FakeCoach()
    assert _post(monkeypatch, coach, **overrides).status_code == 422
    assert coach.calls == []
