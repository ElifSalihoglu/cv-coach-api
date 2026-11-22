"""
What changed between the confirmed CV and a tailored CV.

Pure helpers: no model calls, nothing is generated. Changes are found by
comparing the two CVs through the stable bullet ids, so only edits that really
happened are reported. Each change carries an id (`summary` or a bullet id) so
a later "keep / revert" step can refer to it.
"""
import re
from typing import Literal

from pydantic import BaseModel

from app.models.cv_document import CVExperience, StructuredCV


class CVChange(BaseModel):
    kind: Literal["moved", "summary", "rewritten"]
    id: str  # "summary" or the bullet id, e.g. "exp1.b2"
    where: str  # e.g. "Data Engineer — Acme"
    before: str = ""
    after: str = ""
    detail: str = ""  # e.g. "Moved from 3rd to 1st"


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def _where(exp: CVExperience) -> str:
    return " — ".join(x for x in (exp.title, exp.employer) if x) or "Experience"


def describe_changes(original: StructuredCV, tailored: StructuredCV) -> list[CVChange]:
    """
    Every change that really happened, most telling first: the bullet moved up
    furthest in each role, then the summary, then reworded bullets.
    """
    moved: list[tuple[int, CVChange]] = []
    rewritten: list[CVChange] = []
    tailored_by_id = {e.id: e for e in tailored.experiences}

    for exp in original.experiences:
        other = tailored_by_id.get(exp.id)
        if other is None:
            continue
        old_pos = {b.id: i for i, b in enumerate(exp.bullets, start=1)}
        old_text = {b.id: b.text for b in exp.bullets}

        best_gain, best = 0, None
        for new_index, bullet in enumerate(other.bullets, start=1):
            if bullet.id not in old_pos:
                continue
            gain = old_pos[bullet.id] - new_index
            if gain > best_gain:
                best_gain, best = gain, (bullet, old_pos[bullet.id], new_index)
            if bullet.text != old_text[bullet.id]:
                rewritten.append(CVChange(
                    kind="rewritten", id=bullet.id, where=_where(exp),
                    before=old_text[bullet.id], after=bullet.text,
                ))
        if best:
            bullet, was, now = best
            moved.append((best_gain, CVChange(
                kind="moved", id=bullet.id, where=_where(exp), after=bullet.text,
                detail=f"Moved from {_ordinal(was)} to {_ordinal(now)}",
            )))

    changes = [c for _, c in sorted(moved, key=lambda pair: -pair[0])]
    if tailored.summary and tailored.summary != original.summary:
        changes.append(CVChange(
            kind="summary", id="summary", where="Summary",
            before=original.summary, after=tailored.summary,
        ))
    return changes + rewritten


_ID = re.compile(r"\b(exp\d+)(?:\.b(\d+))?\b")


def readable_tailoring_warning(text: str, cv: StructuredCV) -> str:
    """Replace ids like exp1 or exp1.b2 in a tailoring warning with the employer."""
    employers = {e.id: (e.employer or e.title or "this role") for e in cv.experiences}

    def replace(match: re.Match) -> str:
        employer = employers.get(match[1], "this role")
        return f"bullet {match[2]} at {employer}" if match[2] else employer

    result = _ID.sub(replace, text)
    return result[:1].upper() + result[1:]
