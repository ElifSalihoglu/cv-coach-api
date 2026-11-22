import asyncio
import logging
import time
from typing import Callable

from app.logging_utils import log_event
from app.models.cv_document import StructuredCV
from app.models.schemas import JobOptimizationResult, MatchedJob, SearchResultJob
from app.services.cv_coach import CVCoach
from app.services.job_matching import job_key, match_jobs
from app.services.job_optimization import optimize_for_jobs

logger = logging.getLogger("app.jobs")

# (query, city, country, limit) -> dicts with title, company, location, url,
# full_description ("" when the description could not be read). Optional
# logging-only keys: detail_duration_ms (int) and detail_error (safe reason code).
SearchFn = Callable[[str, str, str, int], list[dict]]


def _ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


async def search_jobs(
    *,
    search: SearchFn,
    query: str,
    city: str,
    country: str,
    limit: int = 5,
    source: str = "indeed",
) -> list[MatchedJob]:
    """
    One search (with descriptions), joined into MatchedJobs. No model is called.

    `search` is blocking (Selenium), so it runs in a worker thread. A job whose
    description could not be read comes back as "missing_description"; other
    jobs are still returned. A failing search itself raises, since there is
    nothing to show.

    Logs (never the query, URLs or job text): the search stage and one line
    per job's detail outcome.
    """
    started = time.perf_counter()
    try:
        raw_results = await asyncio.to_thread(search, query, city, country, limit)
    except Exception as exc:
        log_event(
            logger, logging.ERROR, "job_search",
            source=source, outcome="error",
            reason=getattr(exc, "reason_code", "scraper_error"),
            exception=type(exc).__name__, duration_ms=_ms(started),
        )
        exc.already_logged = True  # tells the route not to log it a second time
        raise

    with_url = [r for r in raw_results if r.get("url")]
    selected = with_url[:limit]
    log_event(
        logger, logging.INFO, "job_search",
        source=source, outcome="ok" if selected else "empty",
        duration_ms=_ms(started),
        detail_ms=sum(int(r.get("detail_duration_ms") or 0) for r in raw_results),
        cards=len(raw_results),
        skipped_no_url=len(raw_results) - len(with_url),
        processed=len(selected),
    )

    results = [
        SearchResultJob(
            title=r.get("title") or "",
            company=r.get("company") or "",
            location=r.get("location") or "",
            url=r["url"],
        )
        for r in selected
    ]
    matched = match_jobs(results, selected)

    raw_by_key: dict[str, dict] = {}
    for raw in selected:
        raw_by_key.setdefault(job_key(raw["url"]), raw)

    for order, job in enumerate(matched, start=1):
        raw = raw_by_key.get(job_key(job.source_url), {})
        duration = raw.get("detail_duration_ms")
        if job.status == "ready":
            log_event(
                logger, logging.INFO, "job_detail",
                job=order, stage="detail", outcome="ok", duration_ms=duration,
                description_chars=len(job.job_description),
            )
        else:
            log_event(
                logger, logging.WARNING, "job_detail",
                job=order, stage="detail", outcome="failed",
                reason=raw.get("detail_error") or "description_empty",
                duration_ms=duration,
            )
    return matched


async def search_and_optimize(
    *,
    search: SearchFn,
    coach: CVCoach,
    query: str,
    city: str,
    country: str,
    cv_bullets: list[str],
    cv: StructuredCV | None = None,
    limit: int = 5,
    source: str = "indeed",
) -> list[JobOptimizationResult]:
    """One search (with descriptions) -> per-job optimization."""
    matched = await search_jobs(
        search=search, query=query, city=city, country=country,
        limit=limit, source=source,
    )
    optimized = await optimize_for_jobs(coach, matched, cv_bullets, cv)

    counts = {"optimized": 0, "missing_description": 0, "failed": 0}
    for item in optimized:
        counts[item.status] += 1
    log_event(
        logger, logging.INFO, "jobs_summary",
        total=len(optimized), **counts,
    )
    return optimized
