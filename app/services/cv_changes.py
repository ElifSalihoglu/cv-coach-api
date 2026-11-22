"""
What changed between the confirmed CV and a tailored CV.

Pure helpers: no model calls, nothing is generated. Changes are found by
comparing the two CVs through the stable bullet ids, so only edits that really
happened are reported. Each change carries an id (`summary` or a bullet id) so
a later "keep / revert" step can refer to it.
"""
import re
import unicodedata
from typing import Literal

from pydantic import BaseModel

from app.models.cv_document import CVExperience, StructuredCV


class CVChange(BaseModel):
    kind: Literal["moved", "summary", "rewritten", "moved_rewritten"]
    id: str  # "summary" or the bullet id, e.g. "exp1.b2"
    where: str  # "Summary" or the role, e.g. "Data Engineer — Acme"
    before: str = ""  # original text, exactly as in the confirmed CV
    after: str = ""  # original text of the tailored CV
    detail: str = ""  # e.g. "Moved from 3rd to 1st"


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


def describe_changes(original: StructuredCV, tailored: StructuredCV) -> list[CVChange]:
    """
    Every change that really happened, one record per bullet, matched by its
    stable id. Order: the bullet moved up furthest in each role, then the
    summary, then the other reworded bullets. A bullet that was both moved and
    reworded is one record. Wording is compared after `normalize_text`, so a text
    that came back unchanged (or only differently spaced) is not a change.
    """
    lead: list[tuple[int, CVChange]] = []
    rest: list[CVChange] = []
    tailored_by_id = {e.id: e for e in tailored.experiences}

    for exp in original.experiences:
        other = tailored_by_id.get(exp.id)
        if other is None:
            continue
        where = _where(exp, original.experiences)
        old_pos = {b.id: i for i, b in enumerate(exp.bullets, start=1)}
        old_text = {b.id: b.text for b in exp.bullets}

        # The bullet that moved up furthest in this role (first one on a tie).
        best_id, best_gain = None, 0
        for new_index, bullet in enumerate(other.bullets, start=1):
            gain = old_pos.get(bullet.id, new_index) - new_index
            if gain > best_gain:
                best_id, best_gain = bullet.id, gain

        for new_index, bullet in enumerate(other.bullets, start=1):
            if bullet.id not in old_pos:
                continue
            was = old_pos[bullet.id]
            reworded = normalize_text(bullet.text) != normalize_text(old_text[bullet.id])
            moved_text = f"Moved from {_ordinal(was)} to {_ordinal(new_index)}"
            if reworded:
                change = CVChange(
                    kind="moved_rewritten" if was != new_index else "rewritten",
                    id=bullet.id, where=where,
                    before=old_text[bullet.id], after=bullet.text,
                    detail=moved_text if was != new_index else "",
                )
            elif bullet.id == best_id:
                change = CVChange(
                    kind="moved", id=bullet.id, where=where,
                    after=bullet.text, detail=moved_text,
                )
            else:
                continue
            if bullet.id == best_id:
                lead.append((best_gain, change))
            else:
                rest.append(change)

    changes = [c for _, c in sorted(lead, key=lambda pair: -pair[0])]
    if tailored.summary and normalize_text(tailored.summary) != normalize_text(original.summary):
        changes.append(CVChange(
            kind="summary", id="summary", where="Summary",
            before=original.summary, after=tailored.summary,
        ))
    return changes + rest


_ID = re.compile(r"\b(exp\d+)(?:\.b(\d+))?\b")


def readable_tailoring_warning(text: str, cv: StructuredCV) -> str:
    """Replace ids like exp1 or exp1.b2 in a tailoring warning with the employer."""
    employers = {e.id: (e.employer or e.title or "this role") for e in cv.experiences}

    def replace(match: re.Match) -> str:
        employer = employers.get(match[1], "this role")
        return f"bullet {match[2]} at {employer}" if match[2] else employer

    result = _ID.sub(replace, text)
    return result[:1].upper() + result[1:]
