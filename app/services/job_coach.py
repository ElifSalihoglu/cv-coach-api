"""
IT Career Coach: one model call that reads a posting against the confirmed CV and
proposes what could be shown for it.

The model only proposes. `build_result` is our own code: it throws away anything it
cannot back up (quotes that are not in the posting, ids that are not in the CV,
claims the CV does not make) and fills every CV text from the CV itself.
Nothing here changes the CV; the user decides (see coach_apply).
"""
import logging
import re
from collections import Counter
from typing import Any

from app.logging_utils import log_event
from app.models.coaching import (
    CoachModelOutput,
    CoachResult,
    Evidence,
    FocusOption,
    Question,
    Requirement,
    SourceRef,
    Suggestion,
)
from app.models.cv_document import CVBullet, CVExperience, StructuredCV
from app.prompts.coach_templates import COACH_SYSTEM_PROMPT
from app.services.cv_changes import _where, normalize_text
from app.services.cv_coach import ContentGenerator
from app.services.cv_tailoring import _stem, cv_source_text, faithfulness_problems, skill_like_terms

logger = logging.getLogger("app.coach")

MAX_SUGGESTIONS = 5
MAX_PROMOTES = 3
MAX_QUESTIONS = 2
_WORDS = re.compile(r"\w+", re.UNICODE)


def coach_input(
    cv: StructuredCV, job_title: str, job_description: str, focus: str
) -> dict[str, Any]:
    """The payload sent to the model. No name, contact details, dates or education."""
    return {
        "job_title": job_title,
        "job_description": job_description,
        "posting_offers_choice": offers_choice(job_description),
        "focus": focus,
        "candidate": {
            "summary": cv.summary,
            "skills": cv.skills,
            "experiences": [
                {
                    "id": exp.id,
                    "title": exp.title,
                    "employer": exp.employer,
                    "bullets": [
                        {"id": b.id, "position": i, "text": b.text}
                        for i, b in enumerate(exp.bullets, start=1)
                    ],
                }
                for exp in cv.experiences
            ],
            "projects": [{"id": p.id, "name": p.name, "description": p.description} for p in cv.projects],
        },
    }


class ITCareerCoach:
    def __init__(self, llm: ContentGenerator) -> None:
        self._llm = llm

    async def analyze(
        self, cv: StructuredCV, job_title: str, job_description: str, focus: str = ""
    ) -> CoachResult:
        """One model call; a second one only if the model invents a choice the posting never offers."""
        output = await self._llm.generate(
            system_prompt=COACH_SYSTEM_PROMPT,
            user_content=coach_input(cv, job_title, job_description, focus),
            output_model=CoachModelOutput,
        )
        if not focus and output.mode == "choose_focus" and not offers_choice(job_description):
            # Responsibilities mistaken for tracks. The posting has one focus: ask again, for it.
            log_event(logger, logging.INFO, "coach_choice_not_offered")
            focus = job_title
            output = await self._llm.generate(
                system_prompt=COACH_SYSTEM_PROMPT,
                user_content=coach_input(cv, job_title, job_description, focus),
                output_model=CoachModelOutput,
            )
        return build_result(cv, job_description, output, focus)


# ---------------------------------------------------------------- our checks


_CHOICE_WORDS = re.compile(
    r"\b(tracks?|streams?|paths?|choose|pick|select|either|one of (the|our|these|four|three|two|five))\b",
    re.IGNORECASE,
)


def offers_choice(job_description: str) -> bool:
    """The posting asks the applicant to pick a track or role (we can tell from its words)."""
    return bool(_CHOICE_WORDS.search(job_description or ""))


def _fold(text: str) -> str:
    return normalize_text(text).casefold()


def _quote_in(job_folded: str, quote: str) -> bool:
    """The quote is really in the posting (spacing and case aside)."""
    cleaned = _fold(quote).strip(" \"'“”‘’…")
    cleaned = cleaned.removesuffix("...").strip()
    return len(cleaned) >= 4 and cleaned in job_folded


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _fold(text)).strip("-") or "item"


def _bullet_index(cv: StructuredCV) -> dict[str, tuple[CVExperience, CVBullet, int]]:
    return {
        b.id: (exp, b, i)
        for exp in cv.experiences
        for i, b in enumerate(exp.bullets, start=1)
    }


def _tokens(text: str) -> set[str]:
    return set(_WORDS.findall(_fold(text)))


_GENERIC_REQUIREMENT = re.compile(
    r"\b\d+\s*\+?\s*years?\b|\bcommunication\b|\bownership\b|\bteam\s?(player|work)\b"
    r"|\bcollaborat\w*|\bproblem[- ]solving\b",
    re.IGNORECASE,
)
_OVERSTATED = re.compile(r"\bdirect(ly)?\b|\bexact(ly)?\b|\bmatches?\b", re.IGNORECASE)


def _is_generic(quote: str) -> bool:
    """Years of experience, communication, ownership...: true of any engineer, a weak target."""
    return bool(_GENERIC_REQUIREMENT.search(quote))


def _parts(term: str) -> list[str]:
    return [p for p in re.split(r"[^\w+#]+", term) if p]


def _root(word: str) -> str:
    """Crude word root, so "designed", "designing" and "design" (or "APIs" and "API") compare equal."""
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def _meaningful(text: str) -> set[str]:
    return {_root(t) for t in _tokens(text) if len(t) >= 4}


def _checked_support(
    claimed: str, quote: str, source_texts: list[str], rationale: str,
    ignore: frozenset[str] = frozenset(),
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
    terms = [t for t in skill_like_terms(quote) if any(_stem(p) not in ignore for p in _parts(t))]
    term_words = {_stem(p) for t in terms for p in _parts(t)}
    quote_words = _meaningful(quote) - term_words - ignore
    lines = [({_stem(x) for x in _tokens(text)}, _meaningful(text)) for text in source_texts]
    supporting = [have for have, words in lines if not quote_words or quote_words & words]
    found = lambda t, have: all(_stem(p) in have for p in _parts(t))  # noqa: E731
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


def _used_lines(cv: StructuredCV, bullets, cited: list, text: str, limit: int = 3) -> list:
    """The cited CV lines plus any other line the text clearly draws on (shares most of its words)."""
    used = list(cited)
    words = _meaningful(text)
    for bullet_id, (exp, bullet, position) in bullets.items():
        mine = _meaningful(bullet.text)
        overlap = len(mine & words)
        if len(used) < limit and all(b.id != bullet_id for _, b, _ in used) and overlap >= 3 and overlap / len(mine) >= 0.4:
            used.append((exp, bullet, position))
    return used


_DESIGN = re.compile(r"\b(design(?:ed|s|ing)?|architect(?:ed|s|ing)?)\b", re.IGNORECASE)
_FILLER = {"and", "the", "for", "with", "into", "from", "that", "this", "their", "our", "your", "using", "used", "of", "to", "in", "on", "a", "an"}


def _design_objects(text: str) -> list[set[str]]:
    """For each 'design ...' / 'architect ...' phrase, the words of what was designed."""
    found = []
    for m in _DESIGN.finditer(text):
        clause = re.split(r"[.;:\n]", text[m.end():], maxsplit=1)[0]
        words = [w for w in _WORDS.findall(_fold(clause)) if w not in _FILLER and len(w) > 2][:5]
        found.append({_stem(w) for w in words})
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
            flagged.append(text[m.start(): m.end() + 40].split(".")[0].strip())
    return flagged


def build_result(
    cv: StructuredCV, job_description: str, output: CoachModelOutput, focus: str = ""
) -> CoachResult:
    job_folded = _fold(job_description)
    bullets = _bullet_index(cv)
    drops: Counter[str] = Counter()  # why proposals were thrown away (codes only, never text)

    requirements: list[Requirement] = []
    for req in output.requirements:
        if req.text and _quote_in(job_folded, req.quote):
            requirements.append(Requirement(text=req.text, quote=req.quote, level=req.level))
        else:
            drops["requirement_quote_not_in_posting"] += 1
    responsibilities = [r for r in output.responsibilities if r.strip()][:8]

    if not focus and output.mode == "choose_focus":
        tracks = _tracks(cv, bullets, job_folded, output, drops)
        if len(tracks) >= 2:
            log_event(logger, logging.INFO, "coach_result", kind="choose_focus",
                      tracks=len(tracks), dropped=sum(drops.values()))
            return CoachResult(
                kind="choose_focus", responsibilities=responsibilities,
                requirements=requirements, tracks=tracks,
                dropped=sum(drops.values()), dropped_reasons=dict(drops),
            )
        # fewer than two real tracks: there is nothing to choose

    suggestions = _suggestions(cv, bullets, job_description, job_folded, output, focus, drops)
    questions = _questions(cv, job_folded, output, drops)
    log_event(logger, logging.INFO, "coach_result", kind="suggestions",
              suggestions=len(suggestions), questions=len(questions), dropped=sum(drops.values()))
    return CoachResult(
        kind="suggestions", focus=focus or output.focus.strip(),
        responsibilities=responsibilities, requirements=requirements,
        suggestions=suggestions, questions=questions,
        dropped=sum(drops.values()), dropped_reasons=dict(drops),
    )


def _tracks(cv, bullets, job_folded, output, drops: Counter) -> list[FocusOption]:
    tracks: list[FocusOption] = []
    seen: set[str] = set()
    for track in output.tracks:
        slug = _slug(track.name)
        if not track.name or slug in seen or not _quote_in(job_folded, track.quote):
            drops["track_not_in_posting"] += 1  # a track the posting does not name is not offered
            continue
        seen.add(slug)
        evidence: list[Evidence] = []
        for item in track.evidence:
            if item.source_id in bullets and all(e.source_id != item.source_id for e in evidence):
                exp, bullet, _ = bullets[item.source_id]
                evidence.append(Evidence(
                    source_id=bullet.id, where=_where(exp, cv.experiences),
                    text=bullet.text, why=item.why,
                ))
            else:
                drops["evidence_not_in_cv"] += 1
        coverage = "strong" if len(evidence) >= 2 else "partial" if evidence else "none"
        tracks.append(FocusOption(
            id=slug, name=track.name, quote=track.quote, summary=track.summary,
            coverage=coverage, evidence=evidence,
            note=f"No explicit {track.name} experience found in your CV." if not evidence else "",
        ))
    order = {"strong": 0, "partial": 1, "none": 2}
    # strongest evidence first; ties keep the posting's order (the sort is stable)
    tracks.sort(key=lambda t: (order[t.coverage], -len(t.evidence)))
    return tracks


def _suggestions(
    cv, bullets, job_description, job_folded, output, focus: str, drops: Counter
) -> list[Suggestion]:
    job_terms = skill_like_terms(job_description)
    cv_text = cv_source_text(cv)
    candidates: list[tuple[int, int, Suggestion]] = []

    for index, item in enumerate(output.suggestions):
        priority = item.priority if item.priority > 0 else 99
        kind = item.kind.strip().lower()
        if not _quote_in(job_folded, item.requirement_quote):
            drops["quote_not_in_posting"] += 1
            continue
        sources = [bullets[i] for i in dict.fromkeys(item.source_ids) if i in bullets]
        if not sources:
            drops["source_not_in_cv"] += 1
            continue
        quote, level = item.requirement_quote, item.level
        if _is_generic(quote):
            # Not worth moving a line, rewording it or aiming a summary at "3+ years" or
            # "ownership": true of any engineer. The target is never swapped for another one.
            drops["generic_requirement"] += 1
            continue
        if kind == "summary":
            sources = _used_lines(cv, bullets, sources, item.after)  # show every line it draws on
        refs = [
            SourceRef(id=b.id, where=_where(exp, cv.experiences), text=b.text)
            for exp, b, _ in sources
        ]
        # Only the lines count: a technology in the skills list proves no particular work.
        support, rationale, _ = _checked_support(
            item.support, quote, [b.text for _, b, _ in sources], item.rationale,
            ignore=frozenset(_stem(t) for t in _tokens(focus)),
        )
        common = dict(
            requirement=quote, level=level, support=support,
            rationale=rationale, priority=priority,
        )

        if kind == "promote":
            exp, bullet, position = sources[0]
            if position <= 1:
                drops["already_first"] += 1
                continue
            suggestion = Suggestion(
                id=f"promote:{bullet.id}", kind="promote", sources=refs[:1],
                before=bullet.text, after=bullet.text, position=position, **common,
            )
        elif kind == "rewrite":
            exp, bullet, _ = sources[0]
            after = item.after.strip()
            added = _tokens(after) - _tokens(bullet.text)
            if not after or _fold(after) == _fold(bullet.text) or len(added) < 2:
                drops["rewrite_not_substantive"] += 1  # a one-word tweak is not worth the user's time
                continue
            if faithfulness_problems(after, f"{bullet.text}\n{exp.title}", job_terms):
                drops["rewrite_unsupported_claim"] += 1
                continue
            suggestion = Suggestion(
                id=f"rewrite:{bullet.id}", kind="rewrite", sources=refs[:1],
                before=bullet.text, after=after, **common,
            )
        elif kind == "summary":
            after = item.after.strip()
            if not after or _fold(after) == _fold(cv.summary):
                drops["summary_not_new"] += 1
                continue
            if faithfulness_problems(after, cv_text, job_terms):
                drops["summary_unsupported_claim"] += 1
                continue
            if unsupported_design_claims(after, cv):
                drops["summary_unsupported_action"] += 1  # "designing REST APIs" without such a line
                continue
            suggestion = Suggestion(
                id="summary", kind="summary", sources=refs,
                before=cv.summary, after=after, **common,
            )
        else:
            drops["unknown_kind"] += 1
            continue
        candidates.append((priority, index, suggestion))

    candidates.sort(key=lambda c: (c[0], c[1]))
    chosen: list[Suggestion] = []
    counts = {"promote": 0, "rewrite": 0, "summary": 0}
    limits = {"promote": MAX_PROMOTES, "rewrite": 1, "summary": 1}
    for _, _, suggestion in candidates:
        duplicate = any(s.id == suggestion.id for s in chosen)
        if duplicate or counts[suggestion.kind] >= limits[suggestion.kind] or len(chosen) >= MAX_SUGGESTIONS:
            drops["over_limit_or_duplicate"] += 1
            continue
        counts[suggestion.kind] += 1
        chosen.append(suggestion.model_copy(update={"priority": len(chosen) + 1}))
    return chosen


def _questions(cv, job_folded, output, drops: Counter) -> list[Question]:
    cv_folded = _fold(cv_source_text(cv))
    questions: list[Question] = []
    for item in output.questions:
        term = item.term.strip()
        term_folded = _fold(term)
        valid = (
            term
            and _quote_in(job_folded, item.requirement_quote)
            and term_folded in _fold(item.requirement_quote)  # the question rests on that quote
            and term_folded in job_folded  # only about words the posting really uses
            and term_folded not in cv_folded  # and only where the CV is silent
            and all(f"ask:{_slug(term)}" != q.id for q in questions)
        )
        if not valid:
            drops["question_not_grounded"] += 1
            continue
        if len(questions) >= MAX_QUESTIONS:
            drops["too_many_questions"] += 1
            continue
        wording = "requires" if item.level == "required" else "prefers"
        questions.append(Question(
            id=f"ask:{_slug(term)}", requirement=item.requirement_quote, level=item.level, term=term,
            text=f"The posting {wording} {term}. Your CV doesn't mention it. Have you used it?",
        ))
    return questions
