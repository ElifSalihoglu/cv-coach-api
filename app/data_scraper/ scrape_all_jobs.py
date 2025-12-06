import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import csv
import json
import os
import time
from pathlib import Path

from job_scraper import scrape_job_details




CSV_PATH = "job_data.csv"  # Your CSV file with job listings
OUTPUT_DIR = Path("job_details")
OUTPUT_DIR.mkdir(exist_ok=True)

JSONL_PATH = "job_details.jsonl"


def extract_job_id(url: str) -> str:
    """
    Extracts a unique job ID from an Indeed URL.
    Example: https://de.indeed.com/viewjob?jk=12345 → "12345"
    """
    if "jk=" in url:
        return url.split("jk=")[-1].split("&")[0]
    return str(hash(url))[-8:]


def load_urls_from_csv(path: str):
    """Reads job URLs from CSV file (expects the 4th column to be the URL)."""
    urls = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            if len(row) >= 4:
                urls.append(row[3])
    return urls


def append_to_jsonl(data: dict, jsonl_path: str):
    """Appends a dictionary as a JSON line into a .jsonl file."""
    with open(jsonl_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")


def main():
    urls = load_urls_from_csv(CSV_PATH)
    print(f"Loaded {len(urls)} job URLs from CSV.")

    for url in urls:
        job_id = extract_job_id(url)
        json_path = OUTPUT_DIR / f"{job_id}.json"

        # Skip already scraped jobs
        if json_path.exists():
            print(f"Skipping (already exists): {url}")
            continue

        print(f"\n🔎 Scraping job: {url}")
        try:
            data = scrape_job_details(url)
        except Exception as e:
            print(f"❌ Error scraping {url}: {e}")
            continue

        # Save individual JSON file
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # Append to JSONL
        append_to_jsonl(data, JSONL_PATH)

        print(f"✔ Saved job details → {json_path}")
        time.sleep(1)  # polite delay


if __name__ == "__main__":
    main()
