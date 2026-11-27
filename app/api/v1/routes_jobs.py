import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.logging_utils import log_event
from app.models.schemas import MatchedJob
from app.services.job_matching import job_key
from app.services.job_search_flow import SearchFn, search_jobs
from app.services.search_errors import HumanVerificationRequired, SearchTimeout

router = APIRouter(prefix="/v1/jobs")
logger = logging.getLogger("app.jobs")


def get_job_search() -> SearchFn:
    """Selenium is imported lazily so the API starts (and tests run) without it."""
    try:
        from app.data_scraper.scraper import scrape_indeed_jobs_with_details
    except ImportError as exc:
        log_event(
            logger, logging.ERROR, "job_search",
            outcome="error", reason="scraper_unavailable", exception=type(exc).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="Job scraping is unavailable: install selenium (pip install -r requirements.txt).",
        ) from exc

    return scrape_indeed_jobs_with_details


def _search_http_error(exc: Exception) -> HTTPException:
    """Map a failed search to an API error; different causes, different next steps."""
    if isinstance(exc, (HumanVerificationRequired, SearchTimeout)):
        status = 503 if isinstance(exc, HumanVerificationRequired) else 504
        return HTTPException(
            status_code=status,
            detail={"code": exc.reason_code, "message": exc.user_message},
        )
    if not getattr(exc, "already_logged", False):
        log_event(
            logger, logging.ERROR, "jobs_request",
            outcome="error", reason="flow_error", exception=type(exc).__name__,
        )
    return HTTPException(
        status_code=502,
        detail={
            "code": "search_failed",
            "message": f"Job search failed: {type(exc).__name__}.",
        },
    )


class JobSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Role or keyword.")
    city: str = Field(..., min_length=1, description="City, or 'remote'.")
    country: str = Field("", description="Optional; narrows the location.")
    limit: int = Field(5, ge=1, le=10, description="Max jobs to return.")


class FoundJob(MatchedJob):
    id: str = Field(..., description="Stable id for this posting.")


class JobSearchResponse(BaseModel):
    jobs: list[FoundJob]


@router.post("/search", response_model=JobSearchResponse)
async def search_only(
    request: JobSearchRequest,
    search: Annotated[SearchFn, Depends(get_job_search)],
) -> JobSearchResponse:
    """Find jobs with their descriptions. Never calls a model, needs no API key."""
    log_event(
        logger, logging.INFO, "jobs_request",
        endpoint="/v1/jobs/search", max_jobs=request.limit,
    )
    try:
        matched = await search_jobs(
            search=search, query=request.query, city=request.city,
            country=request.country, limit=request.limit,
        )
    except Exception as exc:
        raise _search_http_error(exc) from exc
    return JobSearchResponse(
        jobs=[FoundJob(id=job_key(job.source_url), **job.model_dump()) for job in matched]
    )
