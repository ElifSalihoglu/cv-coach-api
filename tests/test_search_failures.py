"""
Search failures (human verification, timeouts) and recovery.

Each failure has its own status and user-facing message.
"""
import pytest
from fastapi.testclient import TestClient

from app.api.v1.routes_jobs import get_job_search
from app.main import app
from app.services.search_errors import (
    HumanVerificationRequired,
    SearchTimeout,
    looks_like_verification,
)


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

def _client(monkeypatch, search):
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
    client = _client(monkeypatch, _raising(exc))

    response = client.post("/v1/jobs/search", json={"query": "AI", "city": "Berlin"})

    assert response.status_code == status
    detail = response.json()["detail"]
    assert detail["code"] == code
    assert "manual" not in detail["message"].lower()
    if code == "human_verification":
        assert detail["message"] == (
            "Indeed insan doğrulaması istediği için arama durdu. CV’n bu oturumda hazır."
        )
