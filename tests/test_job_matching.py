from app.models.schemas import SearchResultJob
from app.services.job_matching import job_key, match_jobs

AI_JOB = SearchResultJob(
    title="AI Engineer",
    company="Acme GmbH",
    location="Berlin",
    url="https://de.indeed.com/rc/clk?jk=aaa111&fccid=x&vjs=3",
)
DATA_JOB = SearchResultJob(
    title="Data Scientist",
    company="Beta AG",
    location="München",
    url="https://de.indeed.com/pagead/clk?mo=r&jk=bbb222&xpse=y",
)

AI_DETAIL = {
    "url": "https://de.indeed.com/viewjob?jk=aaa111",
    "full_description": "Build RAG systems with Python.",
}
DATA_DETAIL = {
    "url": "https://de.indeed.com/viewjob?jk=bbb222&from=serp",
    "full_description": "Train forecasting models with SQL.",
}


def test_two_listings_get_their_own_descriptions_even_if_details_are_reordered():
    matched = match_jobs([AI_JOB, DATA_JOB], [DATA_DETAIL, AI_DETAIL])

    assert [m.company for m in matched] == ["Acme GmbH", "Beta AG"]
    assert matched[0].job_description == "Build RAG systems with Python."
    assert matched[1].job_description == "Train forecasting models with SQL."
    assert all(m.status == "ready" for m in matched)
    assert matched[0].source_url == AI_JOB.url


def test_missing_detail_is_reported_and_other_jobs_still_match():
    matched = match_jobs([AI_JOB, DATA_JOB], [DATA_DETAIL])

    assert matched[0].status == "missing_description"
    assert matched[0].job_description == ""
    assert matched[1].status == "ready"


def test_blank_description_counts_as_missing():
    blank = {**AI_DETAIL, "full_description": "   "}

    matched = match_jobs([AI_JOB], [blank])

    assert matched[0].status == "missing_description"


def test_duplicate_search_results_are_returned_once():
    dup = AI_JOB.model_copy(update={"url": "https://de.indeed.com/viewjob?jk=aaa111"})

    matched = match_jobs([AI_JOB, dup], [AI_DETAIL])

    assert len(matched) == 1


def test_job_key_ignores_tracking_params_for_non_indeed_boards():
    a = "https://www.stepstone.de/stellenangebote--ML-Engineer--123-inline.html?rltr=1"
    b = "https://stepstone.de/stellenangebote--ML-Engineer--123-inline.html/"

    assert job_key(a) == job_key(b)
