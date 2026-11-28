"""Rules that only make sense for hr postings and CVs."""

import re

from app.careers.agents.general.rules import GENERAL_SENIORITY, offers_choice, unsupported_qualifications
from app.careers.core.claims import ClaimLexicon, skill_like_terms, unlisted_roots

__all__ = ["HR_LEXICON", "offers_choice", "unsupported_hr_processes", "unsupported_qualifications"]

HR_LEXICON = ClaimLexicon(
    seniority=re.compile(GENERAL_SENIORITY.pattern + r"|\b(business partner|hrbp)\b", re.IGNORECASE),
    skill_terms=skill_like_terms,
)

# Sensitive people processes: a draft may name one only if a CV line names it too.
_SENSITIVE_PROCESS = re.compile(
    r"\b(disciplin|grievanc|redundanc|restructur|tribunal|dismiss|terminat|investigat|payroll"
    r"|whistleblow|collective bargain|union)\w*",
    re.IGNORECASE,
)


def unsupported_hr_processes(text: str, cv_text: str) -> list[str]:
    """Sensitive HR processes the text claims that the CV never mentions."""
    return unlisted_roots(_SENSITIVE_PROCESS, text, cv_text)
