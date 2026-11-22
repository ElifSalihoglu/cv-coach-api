from urllib.parse import quote_plus

from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import time

from app.services.search_errors import (
    HumanVerificationRequired,
    SearchTimeout,
    looks_like_verification,
)

INDEED_BASE = "https://de.indeed.com"


def location_query(city: str, country: str) -> str:
    """'Berlin, Germany' when a country is given, else just the city (or 'remote')."""
    city, country = (city or "").strip(), (country or "").strip()
    return f"{city}, {country}" if city and country else city or country


def _card_text(card, selector: str) -> str:
    try:
        return card.find_element(By.CSS_SELECTOR, selector).get_attribute("textContent").strip()
    except NoSuchElementException:
        return ""


def _verification_shown(driver) -> bool:
    """Detect a human-check page. We only detect it; we never try to pass it."""
    try:
        body = driver.find_element(By.TAG_NAME, "body").text[:2000]
        return looks_like_verification(driver.title, driver.current_url, body)
    except WebDriverException:
        return False


REASON_OPEN_FAILED = "detail_open_failed"  # the job's detail pane never showed up
REASON_EMPTY = "description_empty"  # the pane opened, but had no description text


def _read_description(driver, link, job_title: str) -> tuple[str, str | None]:
    """
    Click a result card and read the full description from the results page's
    side pane. Opening /viewjob in a fresh browser redirects to Indeed's sign-in
    page, but the side pane works without an account.

    Returns (description, reason). reason is None on success, otherwise a safe
    code telling "pane could not be opened" apart from "pane opened, empty".
    """
    pane_opened = False

    def pane_shows_job(drv):
        nonlocal pane_opened
        panes = drv.find_elements(By.ID, "jobsearch-ViewjobPaneWrapper")
        if not panes or job_title[:40] not in panes[0].text:
            return False
        pane_opened = True
        desc = panes[0].find_elements(
            By.CSS_SELECTOR, ".simple-job-description-html, #jobDescriptionText"
        )
        text = desc[0].text.strip() if desc else ""
        return text or False

    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'})", link)
        link.click()
    except WebDriverException:  # stale element, click intercepted, ...
        return "", REASON_OPEN_FAILED

    try:
        return WebDriverWait(driver, 10).until(pane_shows_job), None
    except TimeoutException:
        if _verification_shown(driver):  # a check can appear in the middle of a search
            raise HumanVerificationRequired()
        return "", (REASON_EMPTY if pane_opened else REASON_OPEN_FAILED)


def scrape_indeed_jobs_with_details(
    title: str, city: str, country: str, limit: int = 5
) -> list[dict]:
    """
    One browser session: search, then read each result's full description from
    the side pane. Each dict has title, company, location, url (canonical
    /viewjob?jk=... link) and full_description ("" if it could not be read).

    For logging, each dict also has detail_duration_ms and, when the
    description is missing, detail_error (a safe reason code). Cards without a
    usable job id are returned with url "" so the caller can count them.

    Raises HumanVerificationRequired when Indeed shows a human check (the
    search stops at once and the browser is closed) and SearchTimeout when the
    results page does not load for any other reason.
    """
    driver = webdriver.Chrome()
    try:
        driver.get(
            f"{INDEED_BASE}/jobs?q={quote_plus(title)}&l={quote_plus(location_query(city, country))}"
        )
        if _verification_shown(driver):
            raise HumanVerificationRequired()
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.job_seen_beacon"))
            )
        except TimeoutException:
            if _verification_shown(driver):
                raise HumanVerificationRequired() from None
            raise SearchTimeout() from None

        jobs: list[dict] = []
        usable = 0
        for card in driver.find_elements(By.CSS_SELECTOR, "div.job_seen_beacon"):
            if usable >= limit:
                break
            try:
                link = card.find_element(By.CSS_SELECTOR, "a.jcs-JobTitle")
                job_key = link.get_attribute("data-jk")
                job_title = link.get_attribute("textContent").strip()
                company = _card_text(card, '[data-testid="company-name"]')
                location = _card_text(card, '[data-testid="text-location"]')
            except (NoSuchElementException, StaleElementReferenceException):
                job_key = None
            if not job_key:
                jobs.append(
                    {"title": "", "company": "", "location": "", "url": "",
                     "full_description": ""}
                )
                continue

            usable += 1
            detail_started = time.perf_counter()
            description, reason = _read_description(driver, link, job_title)
            job = {
                "title": job_title,
                "company": company,
                "location": location,
                "url": f"{INDEED_BASE}/viewjob?jk={job_key}",
                "full_description": description,
                "detail_duration_ms": round((time.perf_counter() - detail_started) * 1000),
            }
            if reason:
                job["detail_error"] = reason
            jobs.append(job)
        return jobs
    finally:
        # Always close the browser, also when the search stops early.
        try:
            driver.quit()
        except WebDriverException:
            pass

def scrape_indeed_jobs(title: str, city: str, country: str):
    driver = webdriver.Chrome()

    # URL'yi kullanıcı girdileriyle oluştur
    url = f'https://de.indeed.com/jobs?q={title}&l={city}%2C+{country}'
    driver.get(url)

    # Wait for job cards to load
    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.job_seen_beacon")))

    job_cards = driver.find_elements(By.CSS_SELECTOR, "div.job_seen_beacon")

    results = []

    for card in job_cards:
        # Job title
        try:
            job_title_el = card.find_element(By.CSS_SELECTOR, "h2.jobTitle span")
            job_title = job_title_el.text
        except:
            job_title = "N/A"

        # Company name
        try:
            company_el = card.find_element(By.CSS_SELECTOR, '[data-testid="company-name"]')
            company_name = company_el.text
        except:
            company_name = "N/A"

        # Location
        try:
            location_el = card.find_element(By.CSS_SELECTOR, '[data-testid="text-location"]')
            company_location = location_el.text
        except:
            company_location = "N/A"

        # URL
        try:
            link_el = card.find_element(By.CSS_SELECTOR, "a")
            job_url = link_el.get_attribute("href")
        except:
            job_url = "N/A"

        results.append({
            "title": job_title,
            "company": company_name,
            "location": company_location,
            "url": job_url
        })

    driver.quit()
    return results
