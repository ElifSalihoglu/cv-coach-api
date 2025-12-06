from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import time


def safe_text(element):
    """Returns the text of a selenium element safely."""
    try:
        return element.text.strip()
    except:
        return ""


def safe_find(driver, selector, by=By.CSS_SELECTOR, multiple=False):
    """
    Helper to safely find elements.
    Returns [] for multiple mode, "" for single mode if not found.
    """
    try:
        if multiple:
            return driver.find_elements(by, selector)
        return driver.find_element(by, selector)
    except:
        return [] if multiple else None


def scrape_job_details(url: str) -> dict:
    """Scrapes structured job information from an Indeed job posting page."""

    driver = webdriver.Chrome()
    wait = WebDriverWait(driver, 10)

    driver.get(url)
    time.sleep(2)

    # -------- TITLE --------
    title_el = safe_find(driver, "h1.jobsearch-JobInfoHeader-title")
    title = safe_text(title_el)

    # -------- COMPANY --------
    company_el = safe_find(driver, '[data-testid="jobsearch-CompanyInfoContainer"]')
    company = safe_text(company_el)

    # -------- LOCATION --------
    loc_el = safe_find(driver, '[data-testid="jobsearch-JobInfoHeader-companyLocation"]')
    location = safe_text(loc_el)

    # -------- SKILLS --------
    skills_section = safe_find(
        driver, 'div[aria-label="Fähigkeiten"] ul li span', multiple=True
    )
    skills = [safe_text(s) for s in skills_section]

    # -------- LANGUAGES --------
    lang_section = safe_find(
        driver, 'div[aria-label="Sprachen"] ul li span', multiple=True
    )
    languages = [safe_text(s) for s in lang_section]

    # -------- SALARY --------
    salary_el = safe_find(driver, 'div[aria-label="Gehalt"] span')
    salary = safe_text(salary_el)

    # -------- EMPLOYMENT TYPE --------
    emp_el = safe_find(driver, 'div[aria-label="Anstellungsart"] span')
    employment_type = safe_text(emp_el)

    # -------- BENEFITS --------
    benefit_items = safe_find(driver, '#benefits ul li', multiple=True)
    benefits = [safe_text(b) for b in benefit_items]

    # -------- FULL JOB DESCRIPTION --------
    desc_el = safe_find(driver, '#jobDescriptionText')
    full_description = safe_text(desc_el)

    job_data = {
        "url": url,
        "title": title,
        "company": company,
        "location": location,
        "skills": skills,
        "languages": languages,
        "salary": salary,
        "employment_type": employment_type,
        "benefits": benefits,
        "full_description": full_description,
    }

    driver.quit()
    return job_data


if __name__ == "__main__":
    test_url = input("Paste Indeed job URL: ")
    data = scrape_job_details(test_url)
    print("\n===== SCRAPED JOB DATA =====")
    for k, v in data.items():
        print(k, ":", v)
