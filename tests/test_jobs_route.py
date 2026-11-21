from fastapi.testclient import TestClient

from app.api.v1.routes_cv import get_cv_coach
from app.api.v1.routes_jobs import get_job_search
from app.main import app
from app.models.schemas import CVOptimizeResponse
from app.services.cv_text import extract_bullets

CV_BULLETS = ["Built ML pipelines using Python and FastAPI."]

SEARCH_RESULTS = [
    {"title": "RAG Engineer", "company": "Acme", "location": "Berlin",
     "url": "https://de.indeed.com/viewjob?jk=aaa",
     "full_description": "Build RAG systems."},
    {"title": "Vision Engineer", "company": "Beta", "location": "Berlin",
     "url": "https://de.indeed.com/viewjob?jk=bbb",
     "full_description": "Train vision models."},
    {"title": "Broken card", "company": "", "location": "", "url": "",
     "full_description": ""},
]


class RecordingCoach:
    def __init__(self):
        self.requests = []

    async def optimize(self, request):
        self.requests.append(request)
        return CVOptimizeResponse(
            improved_bullets=[f"for {request.job_title}"],
            summary="s",
            linkedin_headline="h",
        )


def _post(monkeypatch, coach, results=SEARCH_RESULTS, **overrides):
    calls = []

    def search(query, city, country, limit):
        calls.append((query, city, country, limit))
        return results

    monkeypatch.setitem(app.dependency_overrides, get_cv_coach, lambda: coach)
    monkeypatch.setitem(app.dependency_overrides, get_job_search, lambda: search)
    payload = {"query": "AI Engineer", "cv_bullets": CV_BULLETS, **overrides}
    with TestClient(app) as client:
        response = client.post("/v1/jobs/optimize", json=payload)
    return response, calls


def test_search_returns_one_separate_result_per_job_in_order(monkeypatch):
    coach = RecordingCoach()

    response, calls = _post(monkeypatch, coach)

    assert response.status_code == 200
    assert calls == [("AI Engineer", "Berlin", "Germany", 5)]
    results = response.json()["results"]
    assert [r["job"]["company"] for r in results] == ["Acme", "Beta"]
    assert [r["status"] for r in results] == ["optimized", "optimized"]
    assert results[0]["job"]["source_url"] == "https://de.indeed.com/viewjob?jk=aaa"
    assert results[0]["optimization"]["improved_bullets"] == ["for RAG Engineer"]
    assert results[1]["optimization"]["improved_bullets"] == ["for Vision Engineer"]
    assert [r.job_description for r in coach.requests] == [
        "Build RAG systems.",
        "Train vision models.",
    ]
    assert all(r.current_bullets == CV_BULLETS for r in coach.requests)


def test_job_without_description_is_marked_missing_and_not_optimized(monkeypatch):
    results = [{**SEARCH_RESULTS[0], "full_description": ""}, SEARCH_RESULTS[1]]
    coach = RecordingCoach()

    response, _ = _post(monkeypatch, coach, results=results)

    body = response.json()["results"]
    assert [r["status"] for r in body] == ["missing_description", "optimized"]
    assert [r.job_title for r in coach.requests] == ["Vision Engineer"]


def test_limit_caps_number_of_processed_jobs(monkeypatch):
    response, calls = _post(monkeypatch, RecordingCoach(), limit=1)

    assert len(response.json()["results"]) == 1
    assert calls[0][3] == 1


def test_search_failure_returns_502(monkeypatch):
    def failing_search(query, city, country, limit):
        raise RuntimeError("chrome crashed")

    monkeypatch.setitem(app.dependency_overrides, get_cv_coach, lambda: RecordingCoach())
    monkeypatch.setitem(app.dependency_overrides, get_job_search, lambda: failing_search)

    with TestClient(app) as client:
        response = client.post(
            "/v1/jobs/optimize", json={"query": "AI", "cv_bullets": CV_BULLETS}
        )

    assert response.status_code == 502


def test_missing_scraper_dependency_returns_503_not_crash(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("app.data_scraper"):
            raise ModuleNotFoundError("No module named 'selenium'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setitem(app.dependency_overrides, get_cv_coach, lambda: RecordingCoach())
    app.dependency_overrides.pop(get_job_search, None)
    monkeypatch.setattr(builtins, "__import__", fake_import)

    with TestClient(app) as client:
        response = client.post(
            "/v1/jobs/optimize", json={"query": "AI", "cv_bullets": CV_BULLETS}
        )

    assert response.status_code == 503
    assert "selenium" in response.json()["detail"]


def test_extract_bullets_strips_markers_and_drops_short_lines():
    text = "Jane Doe\nEXPERIENCE\n• Built ML pipelines using Python and FastAPI.\n- Reduced latency by 30% across services.\n2021-2023\n"

    assert extract_bullets(text) == [
        "Built ML pipelines using Python and FastAPI.",
        "Reduced latency by 30% across services.",
    ]
