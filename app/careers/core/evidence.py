"""
Evidence checks every domain agent shares: is a quote really in the posting, does a
source id really point at a CV line, and does a CV line really support what a
suggestion says it supports. Nothing here knows about a field of work.
"""
import re

from app.careers.core.claims import GENERIC_LEXICON, ClaimLexicon, stem
from app.models.cv_document import CVBullet, CVExperience, StructuredCV
from app.services.cv_changes import normalize_text

_WORDS = re.compile(r"\w+", re.UNICODE)

SourceLine = tuple[CVExperience, CVBullet, int]  # (role, bullet, 1-based position in the role)

# Wording that overstates a "related" card; a related card never keeps it.
_OVERSTATED = re.compile(r"\bdirect(ly)?\b|\bexact(ly)?\b|\bmatches?\b", re.IGNORECASE)


def fold(text: str) -> str:
    return normalize_text(text).casefold()


def quote_in(job_folded: str, quote: str) -> bool:
    """The quote is really in the posting (spacing and case aside)."""
    cleaned = fold(quote).strip(" \"'“”‘’…")
    cleaned = cleaned.removesuffix("...").strip()
    return len(cleaned) >= 4 and cleaned in job_folded


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", fold(text)).strip("-") or "item"


def bullet_index(cv: StructuredCV) -> dict[str, SourceLine]:
    return {
        b.id: (exp, b, i)
        for exp in cv.experiences
        for i, b in enumerate(exp.bullets, start=1)
    }


def word_set(text: str) -> set[str]:
    return set(_WORDS.findall(fold(text)))


def _parts(term: str) -> list[str]:
    return [p for p in re.split(r"[^\w+#]+", term) if p]


def _root(word: str) -> str:
    """Crude word root, so "designed", "designing" and "design" (or "APIs" and "API") compare equal."""
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def meaningful(text: str) -> set[str]:
    return {_root(t) for t in word_set(text) if len(t) >= 4}


def checked_support(
    claimed: str, quote: str, source_texts: list[str], rationale: str,
    ignore: frozenset[str] = frozenset(),
    lexicon: ClaimLexicon = GENERIC_LEXICON,
) -> tuple[str, str, list[str]]:
    """
    "direct" means a CV line shows the very thing the posting names. The model's claim
    is kept only when a *supporting* line (one that shares meaningful words with the
    requirement) also contains every distinctive term of it (LLM, FastAPI, ...). So a
    technology that appears in one line (or only in the skills list) never makes another
    line count as work done with it, and general model evaluation is never presented as
    LLM evaluation. `ignore` holds words that only name the focus ("AI"), not a skill.
    A "related" card never keeps a rationale that says "directly" or "exactly".
    """
    terms = [t for t in lexicon.skill_terms(quote) if any(stem(p) not in ignore for p in _parts(t))]
    term_words = {stem(p) for t in terms for p in _parts(t)}
    quote_words = meaningful(quote) - term_words - ignore
    lines = [({stem(x) for x in word_set(text)}, meaningful(text)) for text in source_texts]
    supporting = [have for have, words in lines if not quote_words or quote_words & words]
    found = lambda t, have: all(stem(p) in have for p in _parts(t))  # noqa: E731
    direct = claimed == "direct" and any(all(found(t, have) for t in terms) for have in supporting)
    missing = [t for t in terms if not any(found(t, have) for have in supporting)] if claimed == "direct" and not direct else []
    support = "direct" if direct else "related"
    if support == "related" and (missing or _OVERSTATED.search(rationale)):
        named = f" {', '.join(sorted(missing))}" if missing else ""
        rationale = (
            f"Related experience: this line is close to the requirement but does not mention{named}."
            if missing else
            "Related experience: close to what the posting asks for, not the same thing."
        )
    return support, rationale, missing


def used_lines(cv: StructuredCV, bullets: dict[str, SourceLine], cited: list, text: str, limit: int = 3) -> list:
    """The cited CV lines plus any other line the text clearly draws on (shares most of its words)."""
    used = list(cited)
    words = meaningful(text)
    for bullet_id, (exp, bullet, position) in bullets.items():
        mine = meaningful(bullet.text)
        overlap = len(mine & words)
        if len(used) < limit and all(b.id != bullet_id for _, b, _ in used) and overlap >= 3 and overlap / len(mine) >= 0.4:
            used.append((exp, bullet, position))
    return used
