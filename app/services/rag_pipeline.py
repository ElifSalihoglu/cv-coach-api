from __future__ import annotations

import csv
import os
from functools import lru_cache
from typing import List

from ..models.schemas import JobListing



# Compute the absolute path to the CSV file relative to this file.
DATA_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "data_scraper",
        "job_data.csv",
    )
)


@lru_cache(maxsize=1)
def load_job_listings() -> List[JobListing]:
    """
    Load job listings from the local CSV file into memory.

    The result is cached so the CSV file is only read once per process.
    Returns an empty list if the file does not exist.
    """

    listings: List[JobListing] = []

    if not os.path.exists(DATA_PATH):
        # Fail gracefully if the CSV is missing; the RAG step will simply
        # have no job listings to work with.
        return listings

    with open(DATA_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            # Safely read each column from the CSV row and strip whitespace.
            title = (row.get("Job Title") or "").strip()
            company_name = (row.get("Company Name") or "").strip()
            location = (row.get("Location") or "").strip()
            url = (row.get("Job URL") or "").strip()

            # Skip rows that do not contain at least a title.
            if not title:
                continue

            listings.append(
                JobListing(
                    title=title,
                    company_name=company_name,
                    location=location,
                    url=url,
                )
            )

    return listings
def search_job_listings_by_title(query: str) -> list[JobListing]:
    """
    Return all job listings whose title contains the given query string.
    Case-insensitive substring search.

    Example:
        query = "AI Engineer"
        -> returns all titles that contain "ai engineer" (case insensitive)
    """

    if not query:
        return []

    query_lower = query.lower()
    listings = load_job_listings()
    results: list[JobListing] = []

    for job in listings:
        if query_lower in job.title.lower():
            results.append(job)

    return results

