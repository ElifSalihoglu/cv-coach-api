import asyncio

from app.models.schemas import CVOptimizeResponse, MatchedJob
from app.services.job_optimization import optimize_for_jobs

CV_BULLETS = [
    "Built ML pipelines using Python and FastAPI.",
    "Reduced model inference latency by 30%.",
]


def _job(title, company, description, status="ready"):
    return MatchedJob(
        title=title,
        company=company,
        location="Berlin",
        source_url=f"https://de.indeed.com/viewjob?jk={company.lower()}",
        job_description=description,
        status=status,
    )


def _response_for(title):
    return CVOptimizeResponse(
        improved_bullets=[f"Tailored bullet for {title}"],
        summary=f"Summary for {title}",
        linkedin_headline=f"Headline for {title}",
    )


class FakeCoach:
    """Records requests; fails for job titles listed in fail_for."""

    def __init__(self, fail_for=()):
        self.requests = []
        self.fail_for = set(fail_for)

    async def optimize(self, request):
        self.requests.append(request)
        if request.job_title in self.fail_for:
            raise RuntimeError("model unavailable")
        return _response_for(request.job_title)


def test_two_ready_jobs_get_separate_calls_with_original_cv():
    rag = _job("RAG Engineer", "Acme", "Build RAG systems.")
    cv = _job("Computer Vision Engineer", "Beta", "Train vision models.")
    coach = FakeCoach()

    results = asyncio.run(optimize_for_jobs(coach, [rag, cv], CV_BULLETS))

    assert len(coach.requests) == 2
    assert [r.job_title for r in coach.requests] == [
        "RAG Engineer",
        "Computer Vision Engineer",
    ]
    assert [r.job_description for r in coach.requests] == [
        "Build RAG systems.",
        "Train vision models.",
    ]
    assert all(r.current_bullets == CV_BULLETS for r in coach.requests)

    assert [r.job.company for r in results] == ["Acme", "Beta"]
    assert all(r.status == "optimized" for r in results)
    assert results[0].optimization == _response_for("RAG Engineer")
    assert results[1].optimization == _response_for("Computer Vision Engineer")


def test_partial_failure_keeps_order_and_skips_missing_description():
    first = _job("RAG Engineer", "Acme", "Build RAG systems.")
    missing = _job("Data Engineer", "Gamma", "", status="missing_description")
    third = _job("Computer Vision Engineer", "Beta", "Train vision models.")
    coach = FakeCoach(fail_for={"RAG Engineer"})

    results = asyncio.run(optimize_for_jobs(coach, [first, missing, third], CV_BULLETS))

    assert [r.status for r in results] == ["failed", "missing_description", "optimized"]
    assert [r.job.company for r in results] == ["Acme", "Gamma", "Beta"]

    assert "model unavailable" in results[0].error
    assert results[0].optimization is None
    assert results[1].optimization is None
    assert results[2].optimization == _response_for("Computer Vision Engineer")

    # optimize is never called for the job without a description
    assert [r.job_title for r in coach.requests] == [
        "RAG Engineer",
        "Computer Vision Engineer",
    ]
    assert coach.requests[1].current_bullets == CV_BULLETS
