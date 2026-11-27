"""Text normalisation and role labels shared by the coach and the apply step."""
import unicodedata

from app.models.cv_document import CVExperience

# zero-width space/joiners, word joiner, BOM, soft hyphen
_INVISIBLE = dict.fromkeys([0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF, 0x00AD])


def normalize_text(text: str) -> str:
    """
    Form used only to compare wording: line breaks, repeated spaces, non-breaking
    spaces and invisible characters (all common in text read from a PDF) count as
    one space. Letters, digits and case are untouched, so "3 years" and "5 years"
    stay different. Reported texts are never normalized.
    """
    text = unicodedata.normalize("NFC", text or "").translate(_INVISIBLE)
    return " ".join(text.split())


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def _where(exp: CVExperience, all_experiences: list[CVExperience]) -> str:
    """Role label; dates are added only when two roles would otherwise look the same."""
    label = " — ".join(x for x in (exp.title, exp.employer) if x) or "Experience"
    twins = [e for e in all_experiences
             if " — ".join(x for x in (e.title, e.employer) if x) == label]
    if len(twins) > 1:
        when = " – ".join(x for x in (exp.start, exp.end) if x)
        label += f" ({when or f'role {all_experiences.index(exp) + 1}'})"
    return label
