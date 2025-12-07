from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import time

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
