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

INDEED_BASE = "https://de.indeed.com"


def _card_text(card, selector: str) -> str:
    try:
        return card.find_element(By.CSS_SELECTOR, selector).get_attribute("textContent").strip()
    except NoSuchElementException:
        return ""


def _read_description(driver, link, job_title: str) -> str:
    """
    Click a result card and read the full description from the results page's
    side pane. Opening /viewjob in a fresh browser redirects to Indeed's sign-in
    page, but the side pane works without an account.
    Returns "" when the pane does not show this job's description in time.
    """
    driver.execute_script("arguments[0].scrollIntoView({block:'center'})", link)
    link.click()

    def pane_shows_job(drv):
        panes = drv.find_elements(By.ID, "jobsearch-ViewjobPaneWrapper")
        if not panes or job_title[:40] not in panes[0].text:
            return False
        desc = panes[0].find_elements(
            By.CSS_SELECTOR, ".simple-job-description-html, #jobDescriptionText"
        )
        text = desc[0].text.strip() if desc else ""
        return text or False

    try:
        return WebDriverWait(driver, 10).until(pane_shows_job)
    except TimeoutException:
        return ""


def scrape_indeed_jobs_with_details(
    title: str, city: str, country: str, limit: int = 5
) -> list[dict]:
    """
    One browser session: search, then read each result's full description from
    the side pane. Each dict has title, company, location, url (canonical
    /viewjob?jk=... link) and full_description ("" if it could not be read).
    """
    driver = webdriver.Chrome()
    try:
        driver.get(
            f"{INDEED_BASE}/jobs?q={quote_plus(title)}&l={quote_plus(f'{city}, {country}')}"
        )
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.job_seen_beacon"))
        )

        jobs: list[dict] = []
        for card in driver.find_elements(By.CSS_SELECTOR, "div.job_seen_beacon"):
            if len(jobs) >= limit:
                break
            try:
                link = card.find_element(By.CSS_SELECTOR, "a.jcs-JobTitle")
                job_key = link.get_attribute("data-jk")
                if not job_key:
                    continue
                job_title = link.get_attribute("textContent").strip()
                company = _card_text(card, '[data-testid="company-name"]')
                location = _card_text(card, '[data-testid="text-location"]')
                try:
                    description = _read_description(driver, link, job_title)
                except WebDriverException:  # stale element, click intercepted, ...
                    description = ""
            except (NoSuchElementException, StaleElementReferenceException):
                continue

            jobs.append(
                {
                    "title": job_title,
                    "company": company,
                    "location": location,
                    "url": f"{INDEED_BASE}/viewjob?jk={job_key}",
                    "full_description": description,
                }
            )
        return jobs
    finally:
        driver.quit()

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
