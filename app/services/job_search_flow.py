import asyncio
from typing import Callable

from app.models.schemas import JobOptimizationResult, SearchResultJob
from app.services.cv_coach import CVCoach
from app.services.job_matching import match_jobs
from app.services.job_optimization import optimize_for_jobs

# (query, city, country, limit) -> dicts with title, company, location, url,
# full_description ("" when the description could not be read)
SearchFn = Callable[[str, str, str, int], list[dict]]


async def search_and_optimize(
    *,
    search: SearchFn,
    coach: CVCoach,
    query: str,
    city: str,
    country: str,
    cv_bullets: list[str],
    limit: int = 5,
) -> list[JobOptimizationResult]:
    """
    One search (with descriptions) -> per-job optimization.

    `search` is blocking (Selenium), so it runs in a worker thread. A job whose
    description could not be read comes back as "missing_description"; other
    jobs are still processed. A failing search itself raises, since there is
    nothing to show.
    """
    raw_results = await asyncio.to_thread(search, query, city, country, limit)
    raw_results = [r for r in raw_results if r.get("url")][:limit]

    results = [
        SearchResultJob(
            title=r.get("title") or "",
            company=r.get("company") or "",
            location=r.get("location") or "",
            url=r["url"],
        )
        for r in raw_results
    ]

    return await optimize_for_jobs(coach, match_jobs(results, raw_results), cv_bullets)
