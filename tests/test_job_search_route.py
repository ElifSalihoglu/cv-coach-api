"""POST /v1/jobs/search: find jobs and descriptions without any model call."""

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_llm_client
from app.api.v1.routes_jobs import get_job_search
from app.data_scraper.scraper import location_query
from app.main import app
from app.services.search_errors import HumanVerificationRequired, SearchTimeout

RESULTS = [
    {
        "title": "RAG Engineer",
        "company": "Acme",
        "location": "Berlin",
        "url": "https://de.indeed.com/viewjob?jk=aaa",
        "full_description": "Build RAG systems.",
    },
    {
        "title": "Vision Engineer",
        "company": "Beta",
        "location": "Remote",
        "url": "https://de.indeed.com/viewjob?jk=bbb",
        "full_description": "",
    },
    {"title": "Broken card", "company": "", "location": "", "url": "", "full_description": ""},
]


@pytest.fixture
def post(monkeypatch):
    def boom():
        raise AssertionError("searching must not request a model client")

    monkeypatch.setitem(app.dependency_overrides, get_llm_client, boom)

    def run(search, **payload):
        monkeypatch.setitem(app.dependency_overrides, get_job_search, lambda: search)
        body = {"query": "AI Engineer", "city": "Berlin", **payload}
        with TestClient(app) as client:
            return client.post("/v1/jobs/search", json=body)

    return run


def test_returns_jobs_in_order_with_ids_and_no_model_call(post):
    calls = []

    def search(query, city, country, limit):
        calls.append((query, city, country, limit))
        return RESULTS

    response = post(search)

    assert response.status_code == 200
    assert calls == [("AI Engineer", "Berlin", "", 5)]
    jobs = response.json()["jobs"]
    assert [j["company"] for j in jobs] == ["Acme", "Beta"]  # card without a url is dropped
    assert jobs[0]["id"] == "indeed:aaa"
    assert jobs[0]["job_description"] == "Build RAG systems."
    assert jobs[0]["status"] == "ready"
    assert jobs[1]["status"] == "missing_description"
    assert jobs[1]["job_description"] == ""


def test_limit_and_country_are_passed_to_the_search(post):
    calls = []

    def search(query, city, country, limit):
        calls.append((city, country, limit))
        return RESULTS

    post(search, city="remote", country="Germany", limit=2)
    assert calls == [("remote", "Germany", 2)]


def test_no_results_is_an_empty_list(post):
    assert post(lambda *a: []).json() == {"jobs": []}


@pytest.mark.parametrize(
    "error,status,code",
    [
        (HumanVerificationRequired(), 503, "human_verification"),
        (SearchTimeout(), 504, "search_timeout"),
        (RuntimeError("boom"), 502, "search_failed"),
    ],
)
def test_search_failures_are_reported_with_a_code(post, error, status, code):
    def failing(*args):
        raise error

    response = post(failing)
    assert response.status_code == status
    assert response.json()["detail"]["code"] == code


@pytest.mark.parametrize("payload", [{"query": ""}, {"city": ""}, {"limit": 11}])
def test_invalid_request_is_422(post, payload):
    assert post(lambda *a: [], **payload).status_code == 422


@pytest.mark.parametrize(
    "city,country,expected",
    [
        ("Berlin", "Germany", "Berlin, Germany"),
        ("Berlin", "", "Berlin"),
        ("remote", "", "remote"),
        (" Berlin ", " ", "Berlin"),
    ],
)
def test_location_query(city, country, expected):
    assert location_query(city, country) == expected


def test_a_search_that_crashes_is_a_502_with_a_code(monkeypatch):
    def failing_search(query, city, country, limit):
        raise RuntimeError("chrome crashed")

    monkeypatch.setitem(app.dependency_overrides, get_job_search, lambda: failing_search)
    with TestClient(app) as client:
        response = client.post("/v1/jobs/search", json={"query": "AI", "city": "Berlin"})

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "search_failed"


def test_a_missing_scraper_dependency_is_a_503_not_a_crash(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("app.data_scraper"):
            raise ModuleNotFoundError("No module named 'selenium'")
        return real_import(name, *args, **kwargs)

    app.dependency_overrides.pop(get_job_search, None)
    monkeypatch.setattr(builtins, "__import__", fake_import)

    with TestClient(app) as client:
        response = client.post("/v1/jobs/search", json={"query": "AI", "city": "Berlin"})

    assert response.status_code == 503
    assert "selenium" in response.json()["detail"]
