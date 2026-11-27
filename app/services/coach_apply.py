"""
Turns the user's decisions into a CV. No model is involved, ever.

The confirmed main CV is never modified: `apply_decisions` works on a copy, so
deciding, undoing and downloading cost nothing and always start from the same CV.
Every accepted text is checked again, because the request comes from outside:
a claim the CV does not back up must have been confirmed by the user, and the
change is then recorded as added by the user.
"""

from app.careers.core.claims import cv_source_text, faithfulness_problems, skill_like_terms
from app.careers.core.evidence import role_label
from app.models.coaching import (
    ApplyRequest,
    ApplyResult,
    CheckRequest,
    CheckResult,
    Claim,
    CoachChange,
)
from app.models.cv_document import CVBullet, CVExperience, StructuredCV


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


class DecisionError(Exception):
    """A decision cannot be applied; `code` and `message` are safe to show."""

    code = "invalid_decision"

    def __init__(self, message: str, item_id: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.item_id = item_id


class UnconfirmedClaims(DecisionError):
    """The text says something the CV does not, and the user has not confirmed it."""

    code = "unconfirmed_claims"

    def __init__(self, item_id: str, claims: list[Claim]) -> None:
        self.claims = claims
        super().__init__(explain_claims(claims), item_id)


def explain_claims(claims: list[Claim]) -> str:
    parts = []
    for claim in claims:
        terms = ", ".join(claim.terms)
        if claim.kind == "skills":
            parts.append(f"mentions {terms}, which isn't in your CV")
        elif claim.kind == "numbers":
            one = len(claim.terms) == 1
            parts.append(
                f"uses {'the number' if one else 'the numbers'} {terms}, which {'is' if one else 'are'} not in your CV"
            )
        else:
            parts.append(f"claims {terms}, which your CV does not say")
    return f"Your text {' and '.join(parts)}." if parts else ""


def find_claims(cv: StructuredCV, kind: str, source_id: str, text: str, job_description: str) -> list[Claim]:
    """What `text` says that the CV does not back up (nothing is judged about the claim itself)."""
    if kind == "rewrite":
        found = next(((exp, b) for exp in cv.experiences for b in exp.bullets if b.id == source_id), None)
        if found is None:
            raise DecisionError("That CV line does not exist.", source_id)
        source = f"{found[1].text}\n{found[0].title}"
    else:
        source = cv_source_text(cv)
    problems = faithfulness_problems(text, source, skill_like_terms(job_description))
    return [Claim(kind=p.kind, terms=list(p.terms)) for p in problems]


def check_text(request: CheckRequest) -> CheckResult:
    claims = find_claims(request.cv, request.kind, request.source_id, request.text, request.job_description)
    return CheckResult(claims=claims, message=explain_claims(claims))


def _require_confirmed(item_id: str, claims: list[Claim], confirmed: list[str]) -> bool:
    """True when the text carries new claims the user confirmed; raises when some are unconfirmed."""
    confirmed_folded = {t.casefold() for t in confirmed}
    open_claims = []
    for claim in claims:
        missing = [t for t in claim.terms if t.casefold() not in confirmed_folded]
        if missing:
            open_claims.append(Claim(kind=claim.kind, terms=missing))
    if open_claims:
        raise UnconfirmedClaims(item_id, open_claims)
    return bool(claims)


def apply_decisions(request: ApplyRequest) -> ApplyResult:
    original = request.cv
    cv = original.model_copy(deep=True)
    by_id = {s.id: s for s in request.suggestions}
    bullets = {b.id: b for exp in cv.experiences for b in exp.bullets}

    rewritten: dict[str, tuple[str, bool, bool]] = {}  # bullet id -> (suggestion id, user_added, edited)
    promoted: dict[str, tuple[int, str]] = {}  # bullet id -> (priority, suggestion id)
    summary_change: CoachChange | None = None

    for suggestion_id, decision in request.decisions.items():
        suggestion = by_id.get(suggestion_id)
        if suggestion is None:
            raise DecisionError("That suggestion is not part of this request.", suggestion_id)
        edited = decision.action == "edit"
        if suggestion.kind == "promote":
            if edited:
                raise DecisionError("A moved line has no text to edit.", suggestion_id)
            promoted[suggestion.sources[0].id] = (suggestion.priority, suggestion_id)
            continue

        text = decision.text.strip() if edited else suggestion.after
        if not text:
            raise DecisionError("The text is empty.", suggestion_id)
        kind = "rewrite" if suggestion.kind == "rewrite" else "summary"
        source_id = suggestion.sources[0].id if kind == "rewrite" else ""
        claims = find_claims(original, kind, source_id, text, request.job_description)
        user_added = _require_confirmed(suggestion_id, claims, decision.confirmed_terms)

        if kind == "rewrite":
            if source_id not in bullets:
                raise DecisionError("That CV line does not exist.", suggestion_id)
            bullets[source_id].text = text
            rewritten[source_id] = (suggestion_id, user_added, edited)
        else:
            cv.summary = text
            summary_change = CoachChange(
                kind="summary",
                id="summary",
                suggestion_id=suggestion_id,
                where="Summary",
                before=original.summary,
                after=text,
                user_added=user_added,
                detail="Edited by you" if edited else "",
            )

    added: list[CoachChange] = []
    for addition in request.additions:
        claims = find_claims(original, "add", "", addition.text, request.job_description)
        _require_confirmed(addition.id, claims, addition.confirmed_terms)
        text = addition.text.strip()
        if addition.target.type == "experience":
            exp = next((e for e in cv.experiences if e.id == addition.target.id), None)
            if exp is None:
                raise DecisionError("That role does not exist.", addition.id)
            number = 1 + max([0, *(int(b.id.rsplit(".b", 1)[1]) for b in exp.bullets)])
            bullet = CVBullet(id=f"{exp.id}.b{number}", text=text)
            exp.bullets.append(bullet)
            added.append(
                CoachChange(
                    kind="added",
                    id=bullet.id,
                    suggestion_id=addition.id,
                    where=role_label(exp, cv.experiences),
                    after=text,
                    user_added=True,
                )
            )
        else:
            project = next((p for p in cv.projects if p.id == addition.target.id), None)
            if project is None:
                raise DecisionError("That project does not exist.", addition.id)
            project.description = f"{project.description}\n{text}".strip()
            added.append(
                CoachChange(
                    kind="added",
                    id=project.id,
                    suggestion_id=addition.id,
                    where=project.name or "Project",
                    after=text,
                    user_added=True,
                )
            )

    # Moves last, so a moved line keeps whatever wording was accepted for it. The most
    # useful line ends up first: apply the least useful move first, then more useful ones.
    for exp in cv.experiences:
        moves = sorted(((promoted[b.id][0], b.id) for b in exp.bullets if b.id in promoted), reverse=True)
        for _, bullet_id in moves:
            line = next(b for b in exp.bullets if b.id == bullet_id)
            exp.bullets.remove(line)
            exp.bullets.insert(0, line)

    changes: list[CoachChange] = [summary_change] if summary_change else []
    original_exps: dict[str, CVExperience] = {e.id: e for e in original.experiences}
    for exp in cv.experiences:
        before_exp = original_exps[exp.id]
        was = {b.id: i for i, b in enumerate(before_exp.bullets, start=1)}
        old_text = {b.id: b.text for b in before_exp.bullets}
        for now, bullet in enumerate(exp.bullets, start=1):
            if bullet.id not in was:
                continue
            moved = bullet.id in promoted and was[bullet.id] != now
            reworded = bullet.id in rewritten
            if not moved and not reworded:
                continue
            notes = []
            if moved:
                notes.append(f"Moved from {_ordinal(was[bullet.id])} to {_ordinal(now)}")
            suggestion_id, user_added, edited = rewritten.get(bullet.id, ("", False, False))
            if edited:
                notes.append("Edited by you")
            changes.append(
                CoachChange(
                    kind="moved_rewritten" if moved and reworded else "rewritten" if reworded else "moved",
                    id=bullet.id,
                    suggestion_id=suggestion_id or promoted[bullet.id][1],
                    where=role_label(before_exp, original.experiences),
                    before=old_text[bullet.id] if reworded else "",
                    after=bullet.text,
                    detail=" · ".join(notes),
                    user_added=user_added,
                )
            )
    return ApplyResult(cv=cv, changes=[*changes, *added])
