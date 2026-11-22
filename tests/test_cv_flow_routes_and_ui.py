from fastapi.testclient import TestClient

from app.api.v1.routes_cv import get_cv_coach
from app.api.v1.routes_jobs import get_job_search
from app.main import app
from app.models.cv_document import CVParseResponse, TailoredCVResult
from app.services.cv_parsing import assign_ids
from tests.test_tailored_cv_pdf import CV_TEXT, PARSED

SEARCH_RESULTS = [
    {"title": "Data Engineer", "company": "Gamma", "location": "Berlin",
     "url": "https://de.indeed.com/viewjob?jk=aaa",
     "full_description": "Build data pipelines."},
]


class FakeCoach:
    def __init__(self):
        self.parse_calls = 0
        self.tailor_calls = []

    async def parse(self, cv_text):
        self.parse_calls += 1
        return CVParseResponse(cv=assign_ids(PARSED), warnings=[])

    async def tailor(self, cv, job_title, job_description):
        self.tailor_calls.append((cv, job_title))
        return TailoredCVResult(cv=cv, warnings=["example warning"])


def _client(monkeypatch, coach):
    monkeypatch.setitem(app.dependency_overrides, get_cv_coach, lambda: coach)
    monkeypatch.setitem(
        app.dependency_overrides, get_job_search,
        lambda: (lambda query, city, country, limit: SEARCH_RESULTS),
    )
    return TestClient(app)


def test_parse_route_returns_structured_cv_with_ids(monkeypatch):
    coach = FakeCoach()
    with _client(monkeypatch, coach) as client:
        response = client.post("/v1/cv/parse", json={"cv_text": CV_TEXT})

    assert response.status_code == 200
    body = response.json()
    assert body["cv"]["experiences"][0]["id"] == "exp1"
    assert body["cv"]["experiences"][0]["bullets"][0]["id"] == "exp1.b1"
    assert coach.parse_calls == 1


def test_jobs_route_with_confirmed_cv_returns_tailored_cv_per_job(monkeypatch):
    coach = FakeCoach()
    cv = assign_ids(PARSED).model_dump()
    with _client(monkeypatch, coach) as client:
        response = client.post("/v1/jobs/optimize", json={"query": "AI", "cv": cv})

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["status"] == "optimized"
    assert result["optimization"] is None
    assert result["tailored_cv"]["experiences"][0]["employer"] == "Acme Teknoloji"
    assert result["tailoring_warnings"] == ["example warning"]
    assert [call[1] for call in coach.tailor_calls] == ["Data Engineer"]


def test_jobs_route_needs_either_cv_or_bullets(monkeypatch):
    with _client(monkeypatch, FakeCoach()) as client:
        response = client.post("/v1/jobs/optimize", json={"query": "AI"})

    assert response.status_code == 422
