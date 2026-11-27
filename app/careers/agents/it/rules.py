"""
Rules that only make sense for IT postings and CVs. They stay in the IT agent on purpose:
another field has other generic conditions, other words that fit anything, and another
meaning for "design".
"""
import re

from app.careers.core.claims import stem
from app.careers.core.evidence import fold
from app.models.cv_document import StructuredCV

_WORDS = re.compile(r"\w+", re.UNICODE)

# ---- does the posting ask the applicant to pick a track?

_CHOICE_WORDS = re.compile(
    r"\b(tracks?|streams?|paths?|choose|pick|select|either|one of (the|our|these|four|three|two|five))\b",
    re.IGNORECASE,
)


def offers_choice(job_description: str) -> bool:
    """The posting asks the applicant to pick a track or role (we can tell from its words)."""
    return bool(_CHOICE_WORDS.search(job_description or ""))


# ---- conditions that are true of any engineer

_GENERIC_REQUIREMENT = re.compile(
    r"\b\d+\s*\+?\s*years?\b|\bcommunication\b|\bownership\b|\bteam\s?(player|work)\b"
    r"|\bcollaborat\w*|\bproblem[- ]solving\b",
    re.IGNORECASE,
)


def is_generic(quote: str) -> bool:
    """Years of experience, communication, ownership...: true of any engineer, a weak target."""
    return bool(_GENERIC_REQUIREMENT.search(quote))


# ---- "designing X" needs a CV line that says the candidate designed something of that kind

_DESIGN = re.compile(r"\b(design(?:ed|s|ing)?|architect(?:ed|s|ing)?)\b", re.IGNORECASE)
_FILLER = {"and", "the", "for", "with", "into", "from", "that", "this", "their", "our", "your", "using", "used", "of", "to", "in", "on", "a", "an"}

# Words that fit almost anything: sharing "internal tools" must not make "designing internal
# REST APIs" look supported by "Designed internal tools for operations".
_GENERIC_OBJECT = {
    "tool", "tools", "system", "systems", "service", "services", "solution", "solutions",
    "platform", "platforms", "application", "applications", "feature", "features",
    "process", "processes", "internal", "new", "various", "several", "scalable", "robust",
}


def _design_objects(text: str) -> list[set[str]]:
    """For each 'design ...' / 'architect ...' phrase, the words of what was designed."""
    found = []
    for m in _DESIGN.finditer(text):
        clause = re.split(r"[.;:\n]", text[m.end():], maxsplit=1)[0]
        # What was designed ends where who or what it was for begins ("... for the operations team").
        clause = re.split(r"\b(?:for|to|with|between|across|at|in|on|by|within|using|so)\b", clause, maxsplit=1)[0]
        words = [w for w in _WORDS.findall(fold(clause))
                 if w not in _FILLER and w not in _GENERIC_OBJECT and len(w) > 2][:5]
        found.append({stem(w) for w in words})
    return found


def unsupported_design_claims(text: str, cv: StructuredCV) -> list[str]:
    """
    "Designing REST APIs" needs a CV line that says the candidate designed something of
    that kind. A technology in the skills list, or integration work, is not design work.
    Returns the offending phrases (empty when every design claim has such a line).
    """
    source = " . ".join([cv.summary, *(b.text for e in cv.experiences for b in e.bullets),
                         *(p.description for p in cv.projects)])
    have = set().union(*_design_objects(source), set())
    flagged = []
    for m, objects in zip(_DESIGN.finditer(text), _design_objects(text)):
        if objects and not objects & have:
            flagged.append(text[m.start(): m.end() + 80].split(".")[0].strip())
    return flagged
