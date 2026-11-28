"""Rules that only make sense for finance postings and CVs."""

import re

from app.careers.agents.general.rules import GENERAL_SENIORITY, offers_choice, unsupported_qualifications
from app.careers.core.claims import ClaimLexicon, skill_like_terms, unlisted_roots

__all__ = ["FINANCE_LEXICON", "offers_choice", "unsupported_finance_scope", "unsupported_qualifications"]

FINANCE_LEXICON = ClaimLexicon(
    seniority=re.compile(GENERAL_SENIORITY.pattern + r"|\b(controller|partner|treasurer)\b", re.IGNORECASE),
    skill_terms=skill_like_terms,
)

# Regulated or high-stakes work: a draft may name it only if a CV line names it too.
_REGULATED_WORK = re.compile(
    r"\b(audit|portfolio|derivativ|hedg|underwrit|fiduciar|securitis|securitiz|regulator"
    r"|assets under management|anti-money|sanction)\w*",
    re.IGNORECASE,
)


def unsupported_finance_scope(text: str, cv_text: str) -> list[str]:
    """Regulated or high-stakes finance work the text claims that the CV never mentions."""
    return unlisted_roots(_REGULATED_WORK, text, cv_text)
