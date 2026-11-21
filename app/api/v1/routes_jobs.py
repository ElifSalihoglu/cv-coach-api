from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.routes_cv import get_cv_coach
from app.models.schemas import JobOptimizationResult
from app.services.cv_coach import CVCoach
from app.services.job_search_flow import DetailFn, SearchFn, search_and_optimize

router = APIRouter(prefix="/v1/jobs")


class JobSearchOptimizeRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Role to search for.")
    city: str = Field("Berlin", min_length=1)
    country: str = Field("Germany", min_length=1)
    cv_bullets: list[str] = Field(..., min_length=1, description="Original CV bullets.")
    limit: int = Field(5, ge=1, le=10, description="Max jobs to process.")


class JobSearchOptimizeResponse(BaseModel):
    results: list[JobOptimizationResult]


def get_scrapers() -> tuple[SearchFn, DetailFn]:
    """Selenium is imported lazily so the API starts (and tests run) without it."""
    from app.data_scraper.job_scraper import scrape_job_details
    from app.data_scraper.scraper import scrape_indeed_jobs

    return scrape_indeed_jobs, scrape_job_details


@router.post("/optimize", response_model=JobSearchOptimizeResponse)
async def optimize_for_search(
    request: JobSearchOptimizeRequest,
    coach: Annotated[CVCoach | None, Depends(get_cv_coach)],
    scrapers: Annotated[tuple[SearchFn, DetailFn], Depends(get_scrapers)],
) -> JobSearchOptimizeResponse:
    if coach is None:
        raise HTTPException(status_code=503, detail="CV coach is unavailable.")

    search, fetch_detail = scrapers
    try:
        results = await search_and_optimize(
            search=search,
            fetch_detail=fetch_detail,
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
