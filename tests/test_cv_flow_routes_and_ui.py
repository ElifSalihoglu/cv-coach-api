from pathlib import Path

from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from app.api.v1.routes_cv import get_cv_coach
from app.api.v1.routes_jobs import get_job_search
from app.main import app
from app.models.cv_document import CVParseResponse, TailoredCVResult
from app.services.cv_parsing import assign_ids
from tests.test_tailored_cv_pdf import CV_TEXT, PARSED

UI_FILE = str(Path(__file__).resolve().parents[1] / "app" / "ui" / "app.py")

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


def test_review_form_shows_extra_sections_and_confirm_keeps_them():
    cv = assign_ids(PARSED).model_dump()
    at = AppTest.from_file(UI_FILE, default_timeout=30)
    at.session_state["parsed"] = {"cv": cv, "warnings": [], "version": 1}
    at.run()

    assert not at.exception
    values = [w.value for w in at.text_input] + [w.value for w in at.text_area]
    for fact in ("Veri Kalitesi Paneli", "Google Cloud", "İngilizce - C1, Almanca - B1"):
        assert fact in values
    assert any("Bitirme tezi" in v for v in values)  # thesis under education
    assert any("Python ve SQL ile geliştirildi." in v for v in values)  # project text

    # One prominent confirm button, the last element of the review form.
    confirm = [b for b in at.get("button")
               if b.proto.label == "Confirm CV and continue to job search"]
    assert len(confirm) == 1 and confirm[0].proto.type == "primary"
    form_buttons = [b for b in at.get("button") if b.proto.form_id]
    assert form_buttons == confirm

    confirm[0].click()
    at.run()

    confirmed = at.session_state["confirmed_cv"]
    assert confirmed["projects"] == cv["projects"]
    assert confirmed["certifications"] == cv["certifications"]
    assert confirmed["languages"] == cv["languages"]
    assert confirmed["education"] == cv["education"]


def test_ui_results_show_preview_and_download_without_new_requests(monkeypatch):
    """Rendering the results card (and re-rendering it) makes no API call."""
    import requests

    def no_network(*args, **kwargs):
        raise AssertionError("the UI must not call the API when showing results")

    monkeypatch.setattr(requests, "post", no_network)
    cv = assign_ids(PARSED).model_dump()
    results = [{
        "job": {"title": "Data Engineer", "company": "Gamma", "location": "Berlin",
                "source_url": "https://example.com/a", "job_description": "d",
                "status": "ready"},
        "status": "optimized", "error": None, "optimization": None,
        "tailored_cv": cv, "tailoring_warnings": [],
    }]

    at = AppTest.from_file(UI_FILE, default_timeout=30)
    at.session_state["job_results"] = results
    at.run()
    at.run()  # a second run stands in for downloading again

    assert not at.exception
    assert any("Acme Teknoloji" in md.value for md in at.markdown)
    downloads = at.get("download_button")
    assert len(downloads) == 1
