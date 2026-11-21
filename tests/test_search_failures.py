"""
Search failures (human verification, timeouts) and recovery.

Acceptance: after a failed Indeed search the confirmed CV is still in the
session and a new search works without uploading or parsing the CV again.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from app.api.v1.routes_cv import get_cv_coach
from app.api.v1.routes_jobs import get_job_search
from app.main import app
from app.models.cv_document import ParsedCV
from app.services.cv_coach import OpenAICVCoach
from app.services.cv_parsing import assign_ids
from app.services.search_errors import (
    HumanVerificationRequired,
    SearchTimeout,
    looks_like_verification,
)
from tests.test_tailored_cv_pdf import DATA_SUMMARY, PARSED, FakeLLM

UI_FILE = str(Path(__file__).resolve().parents[1] / "app" / "ui" / "app.py")


# ---- detection ----

@pytest.mark.parametrize("title,body", [
    ("Additional Verification Required", ""),
    ("Indeed", "Verify you are human by completing the action below."),
    ("Just a moment...", ""),
    ("Indeed", "Zusätzliche Verifizierung erforderlich"),
])
def test_verification_pages_are_recognised(title, body):
    assert looks_like_verification(title, "https://de.indeed.com/jobs?q=x", body)


def test_normal_results_page_is_not_a_verification_page():
    assert not looks_like_verification(
        "AI Engineer Jobs in Berlin | Indeed", "https://de.indeed.com/jobs?q=ai",
        "Jobs 1 - 15 of 200. Python developer, Acme GmbH, Berlin",
    )


# ---- scraper: stops and closes the browser ----

class FakeDriver:
    def __init__(self, title="Indeed", body_text="", cards=()):
        self.title = title
        self.current_url = "https://de.indeed.com/jobs"
        self._body_text = body_text
        self.quit_calls = 0
        self.visited = []

    def get(self, url):
        self.visited.append(url)

    def find_element(self, by, value):
        class Body:
            text = self._body_text
        return Body()

    def find_elements(self, by, value):
        return []

    def quit(self):
        self.quit_calls += 1


class ImmediateTimeoutWait:
    def __init__(self, driver, seconds):
        pass

    def until(self, condition):
        from selenium.common.exceptions import TimeoutException
        raise TimeoutException()


def _scrape_with(monkeypatch, driver):
    pytest.importorskip("selenium")
    from app.data_scraper import scraper

    monkeypatch.setattr(scraper.webdriver, "Chrome", lambda: driver)
    monkeypatch.setattr(scraper, "WebDriverWait", ImmediateTimeoutWait)
    return scraper.scrape_indeed_jobs_with_details("AI Engineer", "Berlin", "Germany")


def test_verification_screen_stops_the_search_and_closes_the_driver(monkeypatch):
    driver = FakeDriver(title="Additional Verification Required")

    with pytest.raises(HumanVerificationRequired):
        _scrape_with(monkeypatch, driver)

    assert driver.quit_calls == 1
    assert len(driver.visited) == 1  # no retry, no second page


def test_verification_after_a_results_timeout_is_not_reported_as_timeout(monkeypatch):
    class LateCheckDriver(FakeDriver):
        """Looks normal at first, shows the check once loading has timed out."""

        def __init__(self):
            super().__init__()
            self.checks = 0

        def find_element(self, by, value):
            self.checks += 1
            self._body_text = "Verify you are human" if self.checks > 1 else "loading"
            return super().find_element(by, value)

    driver = LateCheckDriver()
    with pytest.raises(HumanVerificationRequired):
        _scrape_with(monkeypatch, driver)
    assert driver.quit_calls == 1


def test_plain_timeout_is_its_own_error_and_closes_the_driver(monkeypatch):
    driver = FakeDriver(body_text="Some other page")

    with pytest.raises(SearchTimeout):
        _scrape_with(monkeypatch, driver)

    assert driver.quit_calls == 1


# ---- routes ----

def _client(monkeypatch, search, coach=None):
    monkeypatch.setitem(app.dependency_overrides, get_cv_coach, lambda: coach)
    monkeypatch.setitem(app.dependency_overrides, get_job_search, lambda: search)
    return TestClient(app)


def _raising(exc):
    def search(query, city, country, limit):
        raise exc
    return search


@pytest.mark.parametrize("exc,status,code", [
    (HumanVerificationRequired(), 503, "human_verification"),
    (SearchTimeout(), 504, "search_timeout"),
    (RuntimeError("chrome crashed"), 502, "search_failed"),
])
def test_each_search_failure_has_its_own_status_and_message(monkeypatch, exc, status, code):
    cv = assign_ids(PARSED).model_dump()
    client = _client(monkeypatch, _raising(exc), coach=object())

    response = client.post("/v1/jobs/optimize", json={"query": "AI", "cv": cv})

    assert response.status_code == status
    detail = response.json()["detail"]
    assert detail["code"] == code
    assert "manual" not in detail["message"].lower()
    if code == "human_verification":
        assert detail["message"] == (
            "Indeed insan doğrulaması istediği için arama durdu. CV’n bu oturumda hazır."
        )


SEARCH_RESULTS = [
    {"title": "Data Engineer", "company": "Gamma A.Ş.", "location": "Berlin",
     "url": "https://de.indeed.com/viewjob?jk=aaa",
     "full_description": "Build data pipelines with SQL and Airflow."},
]


def test_new_search_after_a_human_check_works_without_reuploading_the_cv(monkeypatch):
    import requests

    llm = FakeLLM()
    attempts = []

    def search(query, city, country, limit):
        attempts.append(query)
        if len(attempts) == 1:
            raise HumanVerificationRequired()
        return SEARCH_RESULTS

    client = _client(monkeypatch, search, OpenAICVCoach(llm))
    monkeypatch.setattr(
        requests, "post",
        lambda url, json=None, timeout=None: client.post(
            url.replace("http://localhost:8000", ""), json=json
        ),
    )

    confirmed = assign_ids(PARSED).model_dump()
    at = AppTest.from_file(UI_FILE, default_timeout=30)
    at.session_state["confirmed_cv"] = confirmed  # uploaded, parsed and confirmed once
    at.run()

    # 1) First search hits the human check.
    next(w for w in at.text_input if w.label == "Role").set_value("AI Engineer")
    next(b for b in at.button if b.label == "Search and tailor CV").click()
    at.run()

    assert not at.exception
    assert [e.value for e in at.error] == [
        "Indeed insan doğrulaması istediği için arama durdu. CV’n bu oturumda hazır."
    ]
    assert at.session_state["confirmed_cv"] == confirmed
    assert at.get("download_button") == []
    assert not any("manual" in e.label.lower() for e in at.expander)

    # 2) A new search, same session, no upload and no parse.
    next(b for b in at.button if b.label == "Search and tailor CV").click()
    at.run()

    assert not at.exception
    assert attempts == ["AI Engineer", "AI Engineer"]
    assert list(at.error) == []  # the old error is gone
    assert at.session_state["confirmed_cv"] == confirmed
    assert len(at.get("download_button")) == 1  # preview and PDF flow still works
    (item,) = at.session_state["job_results"]
    assert item["tailored_cv"]["summary"] == DATA_SUMMARY
    assert all(model is not ParsedCV for model, _ in llm.calls)
    assert len(llm.calls) == 1  # one tailoring call, no re-parse
