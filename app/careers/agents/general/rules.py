"""
Rules of the General Career Agent. None of them is about software: they are about what any
profession must not have invented for it, above all qualifications.
"""

import re

from app.careers.core.claims import ClaimLexicon, skill_like_terms

# ---- seniority and leadership words that must come from the CV

GENERAL_SENIORITY = re.compile(
    r"\b(senior|lead(?:er|ership)?|principal|head|manager|director|supervis\w*|chief|executive"
    r"|president|vice|foreman|superintendent"
    r"|kıdemli|lider\w*|yönetici\w*|müdür\w*|direktör\w*|başkan\w*|şef\w*|amir\w*|sorumlusu)",
    re.IGNORECASE,
)

GENERAL_LEXICON = ClaimLexicon(seniority=GENERAL_SENIORITY, skill_terms=skill_like_terms)

# ---- does the posting ask the applicant to pick a role?

_CHOICE_WORDS = re.compile(
    r"\b(choose|pick|select|either|one of (the|our|these|\w+) (positions|roles|vacancies|jobs)"
    r"|several (positions|roles|vacancies)|multiple (positions|roles|vacancies)|apply for (one|any))\b",
    re.IGNORECASE,
)


def offers_choice(job_description: str) -> bool:
    return bool(_CHOICE_WORDS.search(job_description or ""))


# ---- a condition a CV line cannot show

_YEARS = re.compile(r"\b\d+\s*\+?\s*(?:years?|yıl|yil)\b|\b(?:minimum|at least)\s+\w+\s+years?\b", re.IGNORECASE)


def is_years_requirement(quote: str) -> bool:
    """ "5+ years" is a condition a single CV line cannot show, so no card is aimed at it."""
    return bool(_YEARS.search(quote))


# ---- qualifications: named only when the CV lists them

_FAMILIES: dict[str, re.Pattern[str]] = {
    "licence": re.compile(r"\blicen[sc]\w*|\bruhsat\w*|\behliyet\w*", re.IGNORECASE),
    "certification": re.compile(r"\bcertif\w*|\bsertifika\w*|\bcertificate\w*", re.IGNORECASE),
    "registration": re.compile(r"\bregistered\b|\bregistration\b|\bkay[ıi]tl[ıi]\b", re.IGNORECASE),
    "accreditation": re.compile(r"\baccredit\w*|\bchartered\b|\bakredit\w*", re.IGNORECASE),
    "degree": re.compile(
        r"\bdegree\b|\bbachelor\w*|\bmaster['’]?s\b|\bmaster of\b|\bmsc\b|\bbsc\b|\bmba\b|\bphd\b"
        r"|\bdoctorate\b|\bdiploma\b|\blisans\w*|\bdoktora\b",
        re.IGNORECASE,
    ),
}


def unsupported_qualifications(text: str, cv_text: str) -> list[str]:
    """
    The kinds of qualification (licence, certification, registration, accreditation, degree)
    that `text` names but the CV never mentions in any form. Empty when the text only uses
    qualifications the CV lists.
    """
    return [name for name, pattern in _FAMILIES.items() if pattern.search(text) and not pattern.search(cv_text)]
