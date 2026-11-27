from pydantic import BaseModel, Field


class SearchResultJob(BaseModel):
    """One card from a job-board search result page (no full description yet)."""

    title: str
    company: str
    location: str
    url: str


class MatchedJob(BaseModel):
    """
    A search result joined with its scraped detail page.
    status is "ready" when a non-empty full description was found,
    otherwise "missing_description" so the UI can show it and move on.
    """

    title: str
    company: str
    location: str
    source_url: str
    job_description: str = ""
    status: str = Field(..., pattern="^(ready|missing_description)$")
