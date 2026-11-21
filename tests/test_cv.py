import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.v1.routes_cv import get_cv_coach
from app.models.schemas import CVOptimizeRequest, CVOptimizeResponse
from app.services.llm_client import LLMOutputError, LLMTimeoutError, LLMUnavailableError

class FakeCVCoach:
    async def optimize(self, request: CVOptimizeRequest) -> CVOptimizeResponse:
        return CVOptimizeResponse(
            improved_bullets=request.current_bullets,
            summary=f"Candidate for {request.job_title}.",
            linkedin_headline=request.job_title,
            retrieved_jobs=[],
        )

def test_health_returns_ok():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_optimize_rejects_missing_required_fields():
    with TestClient(app) as client:
        response = client.post("/v1/cv/optimize", json={})

    assert response.status_code == 422

def test_optimize_returns_cv_suggestions_for_valid_request(monkeypatch):
    monkeypatch.setitem(app.dependency_overrides, get_cv_coach, FakeCVCoach)
    payload = {
        "job_title": "AI Engineer",
        "job_description": "Build and maintain Python APIs.",
        "current_bullets": ["Built a Python API for internal reporting."],
    }

    with TestClient(app) as client:
        response = client.post("/v1/cv/optimize", json=payload)

    assert response.status_code == 200
    result = response.json()
    assert isinstance(result["improved_bullets"], list)
    assert len(result["improved_bullets"]) > 0
    assert result["summary"].strip()
    assert result["linkedin_headline"].strip()
    assert isinstance(result["retrieved_jobs"], list)

def test_optimize_returns_503_when_coach_is_unavailable(monkeypatch):
    monkeypatch.setitem(app.dependency_overrides, get_cv_coach, lambda: None)
    payload = {
        "job_title": "AI Engineer",
        "job_description": "Build and maintain Python APIs.",
        "current_bullets": ["Built a Python API for internal reporting."],
    }

    with TestClient(app) as client:
        response = client.post("/v1/cv/optimize", json=payload)

    assert response.status_code == 503
    assert response.json()["detail"] == "CV coach is unavailable."


class FailingCVCoach:
    def __init__(self, error):
        self.error = error

    async def optimize(self, request: CVOptimizeRequest) -> CVOptimizeResponse:
        raise self.error


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (LLMTimeoutError("timeout"), 504),
        (LLMUnavailableError("unavailable"), 503),
        (LLMOutputError("invalid output"), 502),
    ],
    ids=["timeout", "unavailable", "invalid-output"],
)
def test_optimize_maps_llm_errors_to_http_status(monkeypatch, error, expected_status):
    monkeypatch.setitem(
        app.dependency_overrides, get_cv_coach, lambda: FailingCVCoach(error)
    )
    payload = {
        "job_title": "AI Engineer",
        "job_description": "Build and maintain Python APIs.",
        "current_bullets": ["Built a Python API for internal reporting."],
    }

    with TestClient(app) as client:
        response = client.post("/v1/cv/optimize", json=payload)

    assert response.status_code == expected_status
    assert response.json()["detail"]
