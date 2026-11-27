"""
Evidence checks every domain agent shares: is a quote really in the posting, does a
source id really point at a CV line, and does a CV line really support what a
suggestion says it supports. Nothing here knows about a field of work.
"""

import re
import unicodedata

from app.careers.core.claims import GENERIC_LEXICON, ClaimLexicon, stem
from app.models.cv_document import CVBullet, CVExperience, StructuredCV

_WORDS = re.compile(r"\w+", re.UNICODE)

SourceLine = tuple[CVExperience, CVBullet, int]  # (role, bullet, 1-based position in the role)

# Wording that overstates a "related" card; a related card never keeps it.
_OVERSTATED = re.compile(r"\bdirect(ly)?\b|\bexact(ly)?\b|\bmatches?\b", re.IGNORECASE)


# zero-width space and joiners, word joiner, BOM, soft hyphen: invisible in PDF text
_INVISIBLE = dict.fromkeys([0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF, 0x00AD])


def normalize_text(text: str) -> str:
    """
    Form used only to compare wording: line breaks, repeated spaces, non-breaking spaces and invisible
    characters (all common in text read from a PDF) count as one space. Letters, digits and case are
    untouched, so "3 years" and "5 years" stay different.
    """
    text = unicodedata.normalize("NFC", text or "").translate(_INVISIBLE)
    return " ".join(text.split())


def role_label(exp: CVExperience, all_experiences: list[CVExperience]) -> str:
    """Role label; dates are added only when two roles would otherwise look the same."""
    label = " — ".join(x for x in (exp.title, exp.employer) if x) or "Experience"
    twins = [e for e in all_experiences if " — ".join(x for x in (e.title, e.employer) if x) == label]
    if len(twins) > 1:
        when = " – ".join(x for x in (exp.start, exp.end) if x)
        label += f" ({when or f'role {all_experiences.index(exp) + 1}'})"
    return label


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
    return {b.id: (exp, b, i) for exp in cv.experiences for i, b in enumerate(exp.bullets, start=1)}


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


def _mentions(term: str, line_words: set[str]) -> bool:
    return all(stem(part) in line_words for part in _parts(term))


def checked_support(
    claimed: str,
    quote: str,
    source_texts: list[str],
    rationale: str,
    ignore: frozenset[str] = frozenset(),
    lexicon: ClaimLexicon = GENERIC_LEXICON,
) -> tuple[str, str]:
    """
    "direct" means a CV line shows the very thing the posting names. The model's claim is kept
    only when a *supporting* line (one that shares meaningful words with the requirement) also
    contains every distinctive term of it (LLM, FastAPI, ...). So a technology that appears in one
    line (or only in the skills list) never makes another line count as work done with it, and
    general model evaluation is never presented as LLM evaluation. `ignore` holds words that only
    name the focus ("AI"), not a skill. A "related" card never keeps a rationale that says
    "directly" or "exactly".
    """
    terms = [t for t in lexicon.skill_terms(quote) if any(stem(p) not in ignore for p in _parts(t))]
    term_words = {stem(p) for t in terms for p in _parts(t)}
    quote_words = meaningful(quote) - term_words - ignore
    lines = [({stem(x) for x in word_set(text)}, meaningful(text)) for text in source_texts]
    supporting = [have for have, words in lines if not quote_words or quote_words & words]
    direct = claimed == "direct" and any(all(_mentions(t, have) for t in terms) for have in supporting)
    if direct:
        return "direct", rationale

    missing = [t for t in terms if not any(_mentions(t, have) for have in supporting)] if claimed == "direct" else []
    if missing or _OVERSTATED.search(rationale):
        named = f" {', '.join(sorted(missing))}" if missing else ""
        rationale = (
            f"Related experience: this line is close to the requirement but does not mention{named}."
            if missing
            else "Related experience: close to what the posting asks for, not the same thing."
        )
    return "related", rationale


def used_lines(
    cv: StructuredCV, bullets: dict[str, SourceLine], cited: list[SourceLine], text: str, limit: int = 3
) -> list[SourceLine]:
    """The cited CV lines plus any other line the text clearly draws on (shares most of its words)."""
    used = list(cited)
    words = meaningful(text)
    for bullet_id, (exp, bullet, position) in bullets.items():
        mine = meaningful(bullet.text)
        overlap = len(mine & words)
        if (
            len(used) < limit
            and all(b.id != bullet_id for _, b, _ in used)
            and overlap >= 3
            and overlap / len(mine) >= 0.4
        ):
            used.append((exp, bullet, position))
    return used
