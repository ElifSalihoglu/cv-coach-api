from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import time

driver = webdriver.Chrome()

title = "AI Engineer"  # + yerine boşluk kullan, URL’de yine encode edilir
city = "Berlin"
country = "Germany"

driver.get(f'https://de.indeed.com/jobs?q={title}&l={city}%2C+{country}')

# Sayfadaki job card'ların yüklenmesini bekle
wait = WebDriverWait(driver, 10)
wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.job_seen_beacon")))

job_cards = driver.find_elements(By.CSS_SELECTOR, "div.job_seen_beacon")
print("Found job cards:", len(job_cards))
with open("/Users/elifsalihoglu/Desktop/tarot_backend/llm-rag-cv-coach/app/data_scraper/job_data.csv", "w", encoding="utf-8") as f:
    f.write("Job Title,Company Name,Location,Job URL\n")    
    for card in job_cards:
        print('------------------')
        # Başlık
        try:
            job_title_el = card.find_element(By.CSS_SELECTOR, "h2.jobTitle span")
            job_title = job_title_el.text
        except:
            job_title = "N/A"

        # Şirket adı
        try:
            company_el = card.find_element(By.CSS_SELECTOR, '[data-testid="company-name"]')
            company_name = company_el.text
        except:
            company_name = "N/A"

        # Lokasyon
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

        print(f'Job Title: {job_title}')
        print(f'Company Name: {company_name}')
        print(f'Location: {company_location}')
        print(f'Job URL: {job_url}')

        f.write(f'"{job_title}","{company_name}","{company_location}","{job_url}"\n')

    input("Press Enter to exit...")
    driver.quit()
