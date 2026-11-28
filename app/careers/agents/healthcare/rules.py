"""Rules that only make sense for healthcare postings and CVs."""

import re

from app.careers.agents.general.rules import GENERAL_SENIORITY, offers_choice, unsupported_qualifications
from app.careers.core.claims import ClaimLexicon, skill_like_terms, unlisted_roots

__all__ = ["HEALTHCARE_LEXICON", "offers_choice", "unsupported_clinical_actions", "unsupported_qualifications"]

HEALTHCARE_LEXICON = ClaimLexicon(
    seniority=re.compile(
        GENERAL_SENIORITY.pattern + r"|\b(consultant|attending|matron|registrar|charge nurse)\b", re.IGNORECASE
    ),
    skill_terms=skill_like_terms,
)

# Clinical acts: a draft may name one only if a CV line names it too.
_CLINICAL_ACT = re.compile(
    r"\b(diagnos|prescrib|administ|triag|resuscitat|intubat|suture|surg|anaesthe|anesthe|dialys|vaccinat|cannulat|catheteri|transfus|dispens)\w*",
    re.IGNORECASE,
)


def unsupported_clinical_actions(text: str, cv_text: str) -> list[str]:
    """Clinical acts the text claims (diagnosing, prescribing, resuscitating...) that the CV never mentions."""
    return unlisted_roots(_CLINICAL_ACT, text, cv_text)
