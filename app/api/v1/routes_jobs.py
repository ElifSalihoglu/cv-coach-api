from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.routes_cv import get_cv_coach
from app.models.schemas import JobOptimizationResult
from app.services.cv_coach import CVCoach
from app.services.job_search_flow import SearchFn, search_and_optimize

router = APIRouter(prefix="/v1/jobs")


class JobSearchOptimizeRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Role to search for.")
    city: str = Field("Berlin", min_length=1)
    country: str = Field("Germany", min_length=1)
    cv_bullets: list[str] = Field(..., min_length=1, description="Original CV bullets.")
    limit: int = Field(5, ge=1, le=10, description="Max jobs to process.")


class JobSearchOptimizeResponse(BaseModel):
    results: list[JobOptimizationResult]


def get_job_search() -> SearchFn:
    """Selenium is imported lazily so the API starts (and tests run) without it."""
    try:
        from app.data_scraper.scraper import scrape_indeed_jobs_with_details
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="Job scraping is unavailable: install selenium (pip install -r requirements.txt).",
        ) from exc

    return scrape_indeed_jobs_with_details


@router.post("/optimize", response_model=JobSearchOptimizeResponse)
async def optimize_for_search(
    request: JobSearchOptimizeRequest,
    coach: Annotated[CVCoach | None, Depends(get_cv_coach)],
    search: Annotated[SearchFn, Depends(get_job_search)],
) -> JobSearchOptimizeResponse:
    if coach is None:
        raise HTTPException(status_code=503, detail="CV coach is unavailable.")

    try:
        results = await search_and_optimize(
            search=search,
            coach=coach,
            query=request.query,
            city=request.city,
            country=request.country,
            cv_bullets=request.cv_bullets,
            limit=request.limit,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Job search failed: {type(exc).__name__}"
        ) from exc

    return JobSearchOptimizeResponse(results=results)
