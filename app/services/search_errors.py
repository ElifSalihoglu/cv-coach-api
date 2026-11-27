"""
Search failures the user can act on. Kept free of Selenium so the API and the
tests can import them without a browser driver installed.
"""


class JobSearchError(Exception):
    """Base class. `reason_code` is safe to log; `user_message` is safe to show."""

    reason_code = "scraper_error"
    user_message = "The job search failed."


class HumanVerificationRequired(JobSearchError):
    """The job board asked for a human check. We stop and never try to pass it."""

    reason_code = "human_verification"
    user_message = "Indeed insan doğrulaması istediği için arama durdu. CV’n bu oturumda hazır."


class SearchTimeout(JobSearchError):
    """The results page did not load in time (and no verification was shown)."""

    reason_code = "search_timeout"
    user_message = "The job search timed out before results loaded. Please try again."


# Lower-case phrases that identify a bot/human check page. Detection only: we
# never solve, click through or work around these.
_VERIFICATION_MARKERS = (
    "additional verification required",
    "verify you are human",
    "verifying you are human",
    "are you a robot",
    "just a moment",
    "cf-challenge",
    "challenges.cloudflare.com",
    "captcha",
    "zusätzliche verifizierung",
    "bestätigen sie, dass sie ein mensch",
    "sind sie ein mensch",
    "güvenlik doğrulaması",
    "insan olduğunuzu doğrulayın",
)


def looks_like_verification(*page_parts: str) -> bool:
    """True when the page title, URL, text or HTML contains a human-check marker."""
    haystack = " ".join(part or "" for part in page_parts).casefold()
    return any(marker in haystack for marker in _VERIFICATION_MARKERS)
