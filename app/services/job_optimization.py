import logging
from typing import Iterable

from app.logging_utils import job_order_var, log_event
from app.models.schemas import (
    CVOptimizeRequest,
    JobOptimizationResult,
    MatchedJob,
)
from app.services.cv_coach import CVCoach
from app.services.llm_client import LLMError

logger = logging.getLogger("app.optimize")


async def optimize_for_jobs(
    coach: CVCoach,
    jobs: Iterable[MatchedJob],
    cv_bullets: list[str],
) -> list[JobOptimizationResult]:
    """
    Run one optimization per job, always from the user's original CV bullets.

    Results keep the input (search) order. Jobs without a description are not
    sent to the coach. A failure in one job is recorded on that job's result
    and does not stop the others.

    Logging: the job's 1-based position is set as context so the LLM client's
    own log line carries it. LLM failures are logged once, by the client; only
    unexpected errors are logged here.
    """
    results: list[JobOptimizationResult] = []

    for order, job in enumerate(jobs, start=1):
        if job.status != "ready":
            results.append(
                JobOptimizationResult(job=job, status="missing_description")
            )
            continue

        request = CVOptimizeRequest(
            job_title=job.title,
            job_description=job.job_description,
            current_bullets=list(cv_bullets),
        )
        token = job_order_var.set(order)
        try:
            optimization = await coach.optimize(request)
        except Exception as exc:
            if not isinstance(exc, LLMError):
                log_event(
                    logger, logging.WARNING, "optimize",
                    outcome="failed", reason="unexpected_error",
                    exception=type(exc).__name__,
                )
            results.append(
                JobOptimizationResult(
                    job=job,
                    status="failed",
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            continue
        finally:
            job_order_var.reset(token)

        results.append(
            JobOptimizationResult(
                job=job, status="optimized", optimization=optimization
            )
        )

    return results
