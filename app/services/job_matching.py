from typing import Iterable
from urllib.parse import parse_qs, urlsplit

from app.models.schemas import MatchedJob, SearchResultJob


def job_key(url: str) -> str:
    """
    Stable identity for a job posting URL, so a search-result link and the
    detail-page link of the same job compare equal.

    - Indeed: the `jk` query parameter (viewjob, rc/clk and pagead links all carry it).
    - Other boards (e.g. StepStone): host + path, without query/fragment/www.
    """
    parts = urlsplit((url or "").strip())
    host = (parts.hostname or "").lower().removeprefix("www.")

    if host.endswith("indeed.com"):
        jk = parse_qs(parts.query).get("jk", [""])[0]
        if jk:
            return f"indeed:{jk}"

    return f"{host}{parts.path.rstrip('/')}"


def match_jobs(
    search_results: Iterable[SearchResultJob],
    details: Iterable[dict],
) -> list[MatchedJob]:
    """
    Join search results with scraped job details by URL key.

    Order follows the search results. Duplicate search results (same key) are
    kept once. A result with no detail, or an empty description, is returned
    with status "missing_description" instead of being dropped.
    """
    descriptions: dict[str, str] = {}
    for detail in details:
        text = (detail.get("full_description") or "").strip()
        if text:
            descriptions.setdefault(job_key(detail.get("url", "")), text)

    matched: list[MatchedJob] = []
    seen: set[str] = set()
    for result in search_results:
        key = job_key(result.url)
        if key in seen:
            continue
        seen.add(key)

        description = descriptions.get(key, "")
        matched.append(
            MatchedJob(
                title=result.title,
                company=result.company,
                location=result.location,
                source_url=result.url,
                job_description=description,
                status="ready" if description else "missing_description",
            )
        )
    return matched
