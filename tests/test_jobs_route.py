from fastapi.testclient import TestClient

from app.api.v1.routes_cv import get_cv_coach
from app.api.v1.routes_jobs import get_scrapers
from app.main import app
from app.models.schemas import CVOptimizeResponse
from app.services.cv_text import extract_bullets

CV_BULLETS = ["Built ML pipelines using Python and FastAPI."]

SEARCH_RESULTS = [
    {"title": "RAG Engineer", "company": "Acme", "location": "Berlin",
     "url": "https://de.indeed.com/rc/clk?jk=aaa&fccid=x"},
    {"title": "Vision Engineer", "company": "Beta", "location": "Berlin",
     "url": "https://de.indeed.com/rc/clk?jk=bbb&fccid=y"},
    {"title": "Broken card", "company": "N/A", "location": "N/A", "url": "N/A"},
]
DETAILS = {
    "https://de.indeed.com/rc/clk?jk=aaa&fccid=x": {
        "url": "https://de.indeed.com/viewjob?jk=aaa",
        "full_description": "Build RAG systems.",
    },
    "https://de.indeed.com/rc/clk?jk=bbb&fccid=y": {
        "url": "https://de.indeed.com/viewjob?jk=bbb",
        "full_description": "Train vision models.",
    },
}


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


def _post(monkeypatch, coach, details=DETAILS, **overrides):
    def fetch_detail(url):
        value = details[url]
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setitem(app.dependency_overrides, get_cv_coach, lambda: coach)
    monkeypatch.setitem(
        app.dependency_overrides,
        get_scrapers,
        lambda: (lambda q, c, k: SEARCH_RESULTS, fetch_detail),
    )
    payload = {"query": "AI Engineer", "cv_bullets": CV_BULLETS, **overrides}
    with TestClient(app) as client:
        return client.post("/v1/jobs/optimize", json=payload)


def test_search_returns_one_separate_result_per_job_in_order(monkeypatch):
    coach = RecordingCoach()

    response = _post(monkeypatch, coach)

    assert response.status_code == 200
    results = response.json()["results"]
    assert [r["job"]["company"] for r in results] == ["Acme", "Beta"]
    assert [r["status"] for r in results] == ["optimized", "optimized"]
    assert results[0]["job"]["source_url"].endswith("jk=aaa&fccid=x")
    assert results[0]["optimization"]["improved_bullets"] == ["for RAG Engineer"]
    assert results[1]["optimization"]["improved_bullets"] == ["for Vision Engineer"]
    assert [r.job_description for r in coach.requests] == [
        "Build RAG systems.",
        "Train vision models.",
    ]
    assert all(r.current_bullets == CV_BULLETS for r in coach.requests)


def test_detail_fetch_failure_marks_only_that_job_missing(monkeypatch):
    details = {**DETAILS}
    first_url = SEARCH_RESULTS[0]["url"]
    details[first_url] = RuntimeError("page blocked")
    coach = RecordingCoach()

    response = _post(monkeypatch, coach, details=details)

    results = response.json()["results"]
    assert [r["status"] for r in results] == ["missing_description", "optimized"]
    assert [r.job_title for r in coach.requests] == ["Vision Engineer"]


def test_limit_caps_number_of_processed_jobs(monkeypatch):
    response = _post(monkeypatch, RecordingCoach(), limit=1)

    assert len(response.json()["results"]) == 1


def test_search_failure_returns_502(monkeypatch):
    def failing_search(q, c, k):
        raise RuntimeError("chrome crashed")

    monkeypatch.setitem(app.dependency_overrides, get_cv_coach, lambda: RecordingCoach())
    monkeypatch.setitem(
        app.dependency_overrides, get_scrapers, lambda: (failing_search, lambda u: {})
    )

    with TestClient(app) as client:
        response = client.post(
            "/v1/jobs/optimize", json={"query": "AI", "cv_bullets": CV_BULLETS}
        )

    assert response.status_code == 502


def test_extract_bullets_strips_markers_and_drops_short_lines():
    text = "Jane Doe\nEXPERIENCE\n• Built ML pipelines using Python and FastAPI.\n- Reduced latency by 30% across services.\n2021-2023\n"

    assert extract_bullets(text) == [
        "Built ML pipelines using Python and FastAPI.",
        "Reduced latency by 30% across services.",
    ]
