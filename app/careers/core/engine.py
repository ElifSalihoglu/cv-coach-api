"""
AgentEngine: the shared execution machinery every agent runs on. It is not an agent.

One model call reads a posting against the confirmed CV and proposes what could be shown
for it. The model only proposes; `build_result` is our own code and throws away anything it
cannot back up (quotes that are not in the posting, ids that are not in the CV, claims the
CV does not make) and fills every CV text from the CV itself. Nothing here changes the CV;
the user decides (see services.coach_apply).

Who does what (no duplication with `LLMClient`):

- `LLMClient` owns the model call itself: it turns (system prompt, input dict) into chat
  messages, calls the provider, parses the JSON, validates it against the output schema
  (`CoachModelOutput`), maps provider failures to `LLMError`s, and logs the call.
- `AgentEngine` owns everything around it: what is sent (`prepare`, built by the profile from
  `core.minimize` blocks), when to ask again (`run`), what is kept (`build_result`: evidence
  gates, faithfulness gates and the profile's domain gates, in that order), how the result is
  built, and the result log line. It never catches model errors: they reach the caller unchanged.

The engine holds no state and knows no field of work. Everything that differs between
domains arrives in the `DomainProfile` argument (prompt, input, gates, lexicon, limits).
Privacy: logs carry counts and reason codes only, never CV or posting text.
"""
import logging
from collections import Counter
from typing import Any

from app.careers.core.claims import cv_source_text, stem
from app.careers.core.evidence import (
    bullet_index, checked_support, fold, quote_in, slug, used_lines, word_set,
)
from app.careers.core.gates import CORE_GATES, GateContext, Proposal, first_rejection
from app.careers.core.profile import DomainProfile
from app.careers.core.state import CareerCase
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
from app.models.cv_document import StructuredCV
from app.services.cv_changes import _where
from app.services.llm_client import ContentGenerator

logger = logging.getLogger("app.coach")


class AgentEngine:
    """Stateless: no attributes, every method takes the profile (and the model) it works with."""

    # ------------------------------------------------------------ the run

    async def run(self, profile: DomainProfile, case: CareerCase, llm: ContentGenerator) -> CoachResult:
        """One model call; a second one only if the model invents a choice the posting never offers."""
        focus = case.focus
        output = await self.invoke(profile, llm, self.prepare(profile, case, focus))
        if not focus and output.mode == "choose_focus" and not profile.offers_choice(case.job_description):
            # Responsibilities mistaken for tracks. The posting has one focus: ask again, for it.
            log_event(logger, logging.INFO, "coach_choice_not_offered")
            focus = case.job_title
            output = await self.invoke(profile, llm, self.prepare(profile, case, focus))
        return self.build_result(profile, case.cv, case.job_description, output, focus)

    def prepare(self, profile: DomainProfile, case: CareerCase, focus: str) -> dict[str, Any]:
        """What the model is given: the profile's projection of the CV and the posting (data minimization)."""
        return profile.build_input(case.cv, case.job_title, case.job_description, focus)

    async def invoke(
        self, profile: DomainProfile, llm: ContentGenerator, user_content: dict[str, Any]
    ) -> CoachModelOutput:
        """Hand the prompt and the input to the model client, which returns a validated `CoachModelOutput`."""
        return await llm.generate(
            system_prompt=profile.system_prompt,
            user_content=user_content,
            output_model=CoachModelOutput,
        )

    # ------------------------------------------------------------ our checks

    def build_result(
        self, profile: DomainProfile, cv: StructuredCV, job_description: str,
        output: CoachModelOutput, focus: str = "",
    ) -> CoachResult:
        job_folded = fold(job_description)
        bullets = bullet_index(cv)
        drops: Counter[str] = Counter()  # why proposals were thrown away (codes only, never text)

        requirements: list[Requirement] = []
        for req in output.requirements:
            if req.text and quote_in(job_folded, req.quote):
                requirements.append(Requirement(text=req.text, quote=req.quote, level=req.level))
            else:
                drops["requirement_quote_not_in_posting"] += 1
        responsibilities = [r for r in output.responsibilities if r.strip()][:8]

        if not focus and output.mode == "choose_focus":
            tracks = self._tracks(cv, bullets, job_folded, output, drops)
            if len(tracks) >= 2:
                log_event(logger, logging.INFO, "coach_result", kind="choose_focus",
                          tracks=len(tracks), dropped=sum(drops.values()))
                return CoachResult(
                    kind="choose_focus", responsibilities=responsibilities,
                    requirements=requirements, tracks=tracks,
                    dropped=sum(drops.values()), dropped_reasons=dict(drops),
                )
            # fewer than two real tracks: there is nothing to choose

        suggestions = self._suggestions(profile, cv, bullets, job_description, job_folded, output, focus, drops)
        questions = self._questions(profile, cv, job_folded, output, drops)
        log_event(logger, logging.INFO, "coach_result", kind="suggestions",
                  suggestions=len(suggestions), questions=len(questions), dropped=sum(drops.values()))
        return CoachResult(
            kind="suggestions", focus=focus or output.focus.strip(),
            responsibilities=responsibilities, requirements=requirements,
            suggestions=suggestions, questions=questions,
            dropped=sum(drops.values()), dropped_reasons=dict(drops),
        )

    def _suggestions(
        self, profile: DomainProfile, cv, bullets, job_description, job_folded, output, focus: str, drops: Counter
    ) -> list[Suggestion]:
        ctx = GateContext(
            cv=cv, job_description=job_description,
            job_terms=profile.lexicon.skill_terms(job_description),
            cv_text=cv_source_text(cv), lexicon=profile.lexicon,
        )
        # Order matters: the first gate that rejects names the reason.
        gates = (*profile.requirement_gates, *CORE_GATES, *profile.draft_gates)
        candidates: list[tuple[int, int, Suggestion]] = []

        for index, item in enumerate(output.suggestions):
            priority = item.priority if item.priority > 0 else 99
            kind = item.kind.strip().lower()
            if not quote_in(job_folded, item.requirement_quote):
                drops["quote_not_in_posting"] += 1
                continue
            sources = [bullets[i] for i in dict.fromkeys(item.source_ids) if i in bullets]
            if not sources:
                drops["source_not_in_cv"] += 1
                continue
            quote, level = item.requirement_quote, item.level
            if kind == "summary":
                sources = used_lines(cv, bullets, sources, item.after)  # show every line it draws on
            after = sources[0][1].text if kind == "promote" else item.after.strip()
            rejected = first_rejection(
                gates, ctx, Proposal(kind=kind, quote=quote, after=after, sources=sources)
            )
            if rejected:
                drops[rejected] += 1
                continue
            refs = [
                SourceRef(id=b.id, where=_where(exp, cv.experiences), text=b.text)
                for exp, b, _ in sources
            ]
            # Only the lines count: a technology in the skills list proves no particular work.
            support, rationale, _ = checked_support(
                item.support, quote, [b.text for _, b, _ in sources], item.rationale,
                ignore=frozenset(stem(t) for t in word_set(focus)),
                lexicon=profile.lexicon,
            )
            common = dict(
                requirement=quote, level=level, support=support,
                rationale=rationale, priority=priority,
            )

            if kind == "promote":
                _, bullet, position = sources[0]
                suggestion = Suggestion(
                    id=f"promote:{bullet.id}", kind="promote", sources=refs[:1],
                    before=bullet.text, after=bullet.text, position=position, **common,
                )
            elif kind == "rewrite":
                _, bullet, _ = sources[0]
                suggestion = Suggestion(
                    id=f"rewrite:{bullet.id}", kind="rewrite", sources=refs[:1],
                    before=bullet.text, after=after, **common,
                )
            elif kind == "summary":
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
        counts = {kind: 0 for kind in profile.limits.per_kind}
        for _, _, suggestion in candidates:
            duplicate = any(s.id == suggestion.id for s in chosen)
            if (duplicate or counts[suggestion.kind] >= profile.limits.per_kind[suggestion.kind]
                    or len(chosen) >= profile.limits.max_suggestions):
                drops["over_limit_or_duplicate"] += 1
                continue
            counts[suggestion.kind] += 1
            chosen.append(suggestion.model_copy(update={"priority": len(chosen) + 1}))
        return chosen

    def _questions(self, profile: DomainProfile, cv, job_folded, output, drops: Counter) -> list[Question]:
        cv_folded = fold(cv_source_text(cv))
        questions: list[Question] = []
        for item in output.questions:
            term = item.term.strip()
            term_folded = fold(term)
            valid = (
                term
                and quote_in(job_folded, item.requirement_quote)
                and term_folded in fold(item.requirement_quote)  # the question rests on that quote
                and term_folded in job_folded  # only about words the posting really uses
                and term_folded not in cv_folded  # and only where the CV is silent
                and all(f"ask:{slug(term)}" != q.id for q in questions)
            )
            if not valid:
                drops["question_not_grounded"] += 1
                continue
            if len(questions) >= profile.limits.max_questions:
                drops["too_many_questions"] += 1
                continue
            wording = "requires" if item.level == "required" else "prefers"
            questions.append(Question(
                id=f"ask:{slug(term)}", requirement=item.requirement_quote, level=item.level, term=term,
                text=f"The posting {wording} {term}. Your CV doesn't mention it. Have you used it?",
            ))
        return questions

    def _tracks(self, cv, bullets, job_folded, output, drops: Counter) -> list[FocusOption]:
        tracks: list[FocusOption] = []
        seen: set[str] = set()
        for track in output.tracks:
            track_slug = slug(track.name)
            if not track.name or track_slug in seen or not quote_in(job_folded, track.quote):
                drops["track_not_in_posting"] += 1  # a track the posting does not name is not offered
                continue
            seen.add(track_slug)
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
                id=track_slug, name=track.name, quote=track.quote, summary=track.summary,
                coverage=coverage, evidence=evidence,
                note=f"No explicit {track.name} experience found in your CV." if not evidence else "",
            ))
        order = {"strong": 0, "partial": 1, "none": 2}
        # strongest evidence first; ties keep the posting's order (the sort is stable)
        tracks.sort(key=lambda t: (order[t.coverage], -len(t.evidence)))
        return tracks


DEFAULT_ENGINE = AgentEngine()  # stateless, so one instance serves every agent and every request
