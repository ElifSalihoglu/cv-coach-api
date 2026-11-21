import asyncio
from typing import Callable

from app.models.schemas import JobOptimizationResult, SearchResultJob
from app.services.cv_coach import CVCoach
from app.services.job_matching import match_jobs
from app.services.job_optimization import optimize_for_jobs

SearchFn = Callable[[str, str, str], list[dict]]
DetailFn = Callable[[str], dict]


async def search_and_optimize(
    *,
    search: SearchFn,
    fetch_detail: DetailFn,
    coach: CVCoach,
    query: str,
    city: str,
    country: str,
    cv_bullets: list[str],
    limit: int = 5,
) -> list[JobOptimizationResult]:
    """
    One search -> detail pages -> per-job optimization.

    `search` and `fetch_detail` are blocking (Selenium), so they run in worker
    threads. A detail page that fails to load simply has no description and
    comes back as "missing_description"; other jobs are still processed.
    A failing search itself raises, since there is nothing to show.
    """
    raw_results = await asyncio.to_thread(search, query, city, country)

    results = [
        SearchResultJob(
            title=r.get("title") or "",
            company=r.get("company") or "",
            location=r.get("location") or "",
            url=r["url"],
        )
        for r in raw_results
        if r.get("url") and r["url"] != "N/A"
    ][:limit]

    details: list[dict] = []
    for result in results:
        try:
            details.append(await asyncio.to_thread(fetch_detail, result.url))
        except Exception:
            continue

    return await optimize_for_jobs(coach, match_jobs(results, details), cv_bullets)
