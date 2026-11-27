"""IT agent with a fake model: what survives our checks, and how many calls it takes."""

import asyncio

import pytest

from app.careers.agents.it import IT_AGENT, IT_PROFILE
from app.careers.agents.it.model_input import it_input
from app.careers.agents.it.prompt import IT_SYSTEM_PROMPT
from app.careers.agents.it.rules import offers_choice
from app.careers.core.engine import DEFAULT_ENGINE
from app.careers.core.state import CareerCase
from app.models.coaching import CoachModelOutput, ModelQuestion, ModelRequirement, ModelSuggestion
from tests.fixtures.coach_fixture import CLEAR_JOB_DESCRIPTION, CLEAR_JOB_TITLE, CV, JOB_DESCRIPTION, JOB_TITLE
from tests.fixtures.coach_scenarios import (
    AI_SUMMARY,
    PY_SUMMARY,
    Q_AI,
    Q_AI_EVAL,
    Q_PREF_K8S,
    Q_PREF_PG,
    Q_PY,
    FakeLLM,
    ai_output,
    python_output,
    tracks_output,
)


def analyze(llm: FakeLLM, focus: str = ""):
    return asyncio.run(IT_AGENT.analyze(CareerCase(CV, JOB_TITLE, JOB_DESCRIPTION, focus), llm))


def build_result(cv, job_description, output, focus=""):
    return DEFAULT_ENGINE.build_result(IT_PROFILE, cv, job_description, output, focus)


def result_for(output: CoachModelOutput, focus: str = ""):
    return build_result(CV, JOB_DESCRIPTION, output, focus)


def suggestion(**over) -> ModelSuggestion:
    base = dict(
        kind="promote",
        requirement_quote=Q_AI,
        level="required",
        source_ids=["exp1.b4"],
        support="related",
        priority=1,
        rationale="r",
    )
    return ModelSuggestion(**{**base, **over})


def out(*suggestions: ModelSuggestion, questions=()) -> CoachModelOutput:
    return CoachModelOutput(mode="suggestions", suggestions=list(suggestions), questions=list(questions))


# ---- focus: a choice only when the posting really has several tracks ----


def test_a_posting_with_several_tracks_returns_the_choice_after_one_call():
    llm = FakeLLM(tracks_output())
    result = analyze(llm)

    assert len(llm.calls) == 1
    assert result.kind == "choose_focus"
    assert result.suggestions == []
    assert [(t.name, t.coverage) for t in result.tracks] == [
        ("AI", "strong"),
        ("Python", "strong"),
        ("TypeScript", "none"),
        ("DevOps", "none"),
    ]  # strong evidence first; the other tracks stay, after them


def test_tracks_say_only_what_is_known_from_the_cv():
    tracks = {t.name: t for t in analyze(FakeLLM(tracks_output())).tracks}

    assert tracks["TypeScript"].note == "No explicit TypeScript experience found in your CV."
    assert tracks["TypeScript"].evidence == []
    assert tracks["AI"].note == ""
    # evidence text and place come from the CV, not from the model
    first = tracks["AI"].evidence[0]
    assert first.text == CV.experiences[0].bullets[0].text
    assert first.where == "Senior Software Engineer — Boğaz Yazılım"
    # a made-up evidence id is dropped, and so is a track the posting never names
    assert [e.source_id for e in tracks["Python"].evidence] == ["exp2.b4", "exp2.b1"]
    assert "Game design" not in tracks


def test_a_clear_posting_needs_one_call_and_goes_straight_to_suggestions():
    llm = FakeLLM(ai_output())
    result = analyze(llm)
    assert len(llm.calls) == 1
    assert result.kind == "suggestions" and result.suggestions


def test_choosing_a_focus_is_the_second_call_and_never_asks_again():
    llm = FakeLLM(tracks_output(), ai_output())
    first = analyze(llm)
    second = analyze(llm, focus=first.tracks[0].name)

    assert len(llm.calls) == 2
    assert llm.calls[1]["focus"] == "AI"
    assert second.kind == "suggestions" and second.focus == "AI"


def test_a_model_that_returns_tracks_again_after_a_focus_still_gives_suggestions():
    result = result_for(tracks_output(), focus="AI")
    assert result.kind == "suggestions"


def test_fewer_than_two_real_tracks_is_not_a_choice():
    output = tracks_output()
    output.tracks = output.tracks[3:4]  # only AI
    assert result_for(output).kind == "suggestions"


# ---- the AI and the Python scenario ----


def test_ai_focus_leads_with_the_invoice_agent():
    result = analyze(FakeLLM(ai_output()), focus="AI")

    summary = next(s for s in result.suggestions if s.kind == "summary")
    assert summary.after == AI_SUMMARY
    assert "12,000 documents per month" in summary.after
    assert [r.id for r in summary.sources] == ["exp1.b1"]
    assert summary.sources[0].text == CV.experiences[0].bullets[0].text
    assert summary.requirement == Q_AI and summary.level == "required"
    assert [s.id for s in result.suggestions] == ["summary", "promote:exp1.b4", "promote:exp1.b2"]
    assert [s.priority for s in result.suggestions] == [1, 2, 3]


def test_python_focus_puts_api_and_webhook_work_first():
    result = analyze(FakeLLM(python_output()), focus="Python Backend")

    first = result.suggestions[0]
    assert (first.id, first.kind, first.position) == ("promote:exp2.b4", "promote", 4)
    assert (
        first.sources[0].text == "Integrated third-party APIs and webhooks into internal tools for the operations team."
    )
    assert first.after == first.before  # a promoted line keeps its text
    assert result.suggestions[1].after == PY_SUMMARY


def test_related_experience_is_labelled_related_not_direct():
    result = analyze(FakeLLM(python_output()), focus="Python Backend")
    first = result.suggestions[0]
    assert first.support == "related"  # API integration is not API design
    assert "not designing" in first.rationale


def test_the_posting_requirements_keep_required_and_preferred_apart():
    result = analyze(FakeLLM(ai_output()), focus="AI")
    assert [(r.level, r.quote) for r in result.requirements] == [
        ("required", "3+ years of professional software engineering experience"),
        ("required", "Ownership of services in production"),
        ("preferred", "Experience with PostgreSQL"),
    ]


# ---- what our checks throw away ----


def test_a_suggestion_whose_quote_is_not_in_the_posting_is_dropped():
    result = result_for(out(suggestion(requirement_quote="Must know Rust and COBOL")))
    assert result.suggestions == [] and result.dropped == 1


def test_a_suggestion_pointing_at_a_line_that_is_not_in_the_cv_is_dropped():
    assert result_for(out(suggestion(source_ids=["exp7.b1"]))).suggestions == []


def test_moving_a_line_that_is_already_first_is_dropped():
    assert result_for(out(suggestion(source_ids=["exp1.b1"]))).suggestions == []


def test_a_wording_only_rewrite_is_dropped_and_no_rewrite_is_fine():
    tweak = suggestion(
        kind="rewrite",
        source_ids=["exp1.b2"],
        after=("Designed reliable workflow automations with queues and retries, replacing five hand-run scripts."),
    )
    assert result_for(out(tweak)).suggestions == []


@pytest.mark.parametrize(
    "after",
    [
        "Designed workflow automations on Kubernetes with queues and retries, replacing five hand-run scripts.",
        "Designed workflow automations with queues and retries, replacing 12 hand-run scripts for the team.",
    ],
)
def test_a_rewrite_that_claims_something_new_is_dropped(after):
    result = result_for(out(suggestion(kind="rewrite", source_ids=["exp1.b2"], after=after)))
    assert result.suggestions == []


def test_a_rewrite_that_shows_real_substance_is_kept_with_the_cv_text_as_before():
    after = "Cut manual review by 60% with an LLM-based invoice triage agent that handles 12,000 documents per month."
    (kept,) = result_for(out(suggestion(kind="rewrite", source_ids=["exp1.b1"], after=after))).suggestions
    assert (kept.id, kept.before, kept.after) == ("rewrite:exp1.b1", CV.experiences[0].bullets[0].text, after)


def test_at_most_one_rewrite_and_one_summary_and_five_suggestions():
    rewrite = lambda sid, n, p: suggestion(  # noqa: E731
        kind="rewrite",
        source_ids=[sid],
        priority=p,
        after=f"{CV.experiences[0].bullets[0].text} Kept the team informed weekly {n}.",
    )
    many = out(
        rewrite("exp1.b1", "a", 2),
        rewrite("exp1.b1", "b", 3),
        suggestion(kind="summary", after=AI_SUMMARY, source_ids=["exp1.b1"], priority=1),
        suggestion(kind="summary", after=AI_SUMMARY + " More.", source_ids=["exp1.b1"], priority=4),
        *[
            suggestion(source_ids=[sid], priority=5 + i)
            for i, sid in enumerate(["exp1.b2", "exp1.b3", "exp1.b4", "exp1.b5", "exp2.b2"])
        ],
    )
    result = result_for(many)
    kinds = [s.kind for s in result.suggestions]
    assert kinds.count("rewrite") <= 1 and kinds.count("summary") == 1
    assert kinds.count("promote") <= 3
    assert len(result.suggestions) <= 5
    assert [s.priority for s in result.suggestions] == list(range(1, len(result.suggestions) + 1))


def test_a_summary_that_adds_a_skill_from_another_track_is_dropped():
    leaked = AI_SUMMARY + " Also runs Kubernetes with Terraform."
    result = result_for(out(suggestion(kind="summary", after=leaked, source_ids=["exp1.b1"])))
    assert result.suggestions == []


def test_a_summary_with_a_made_up_number_is_dropped():
    result = result_for(
        out(suggestion(kind="summary", source_ids=["exp1.b1"], after=AI_SUMMARY.replace("12,000", "50,000")))
    )
    assert result.suggestions == []


# ---- questions ----


def test_a_question_about_a_posting_term_missing_from_the_cv_is_asked():
    result = analyze(FakeLLM(ai_output()), focus="AI")
    (question,) = result.questions
    assert (question.id, question.term, question.level) == ("ask:kubernetes", "Kubernetes", "preferred")
    assert question.text == "The posting prefers Kubernetes. Your CV doesn't mention it. Have you used it?"


@pytest.mark.parametrize(
    "question",
    [
        ModelQuestion(requirement_quote="Experience with Rust", level="preferred", term="Rust"),  # not in the posting
        ModelQuestion(requirement_quote=Q_PREF_PG, level="preferred", term="MySQL"),  # term not in that quote
        ModelQuestion(
            requirement_quote="3+ years of professional Python", level="required", term="Python"
        ),  # fake quote
    ],
)
def test_questions_that_do_not_rest_on_the_posting_are_dropped(question):
    assert result_for(out(questions=[question])).questions == []


def test_no_question_about_something_the_cv_already_says():
    q = ModelQuestion(requirement_quote=Q_PY, level="required", term="Airflow")  # Airflow is in the CV
    assert result_for(out(questions=[q])).questions == []


def test_no_postgresql_question_when_the_posting_does_not_mention_it():
    description = JOB_DESCRIPTION.replace("- Experience with PostgreSQL\n", "")
    result = build_result(
        CV,
        description,
        out(questions=[ModelQuestion(requirement_quote=Q_PREF_PG, level="preferred", term="PostgreSQL")]),
    )
    assert result.questions == []


def test_at_most_two_questions():
    questions = [
        ModelQuestion(requirement_quote=Q_PREF_K8S, level="preferred", term="Kubernetes"),
        ModelQuestion(requirement_quote=Q_PREF_K8S, level="preferred", term="Terraform"),
        ModelQuestion(requirement_quote=Q_PREF_PG, level="preferred", term="PostgreSQL"),
    ]
    assert len(result_for(out(questions=questions)).questions) == 2


# ---- what is sent to the model ----


def test_the_model_never_sees_name_contact_details_or_dates():
    payload = str(it_input(CV, JOB_TITLE, JOB_DESCRIPTION, "AI"))
    for private in ("Deniz", "Kaya", "deniz.kaya@example.com", "Istanbul", "2018", "2022", "Present"):
        assert private not in payload
    assert "exp1.b1" in payload and "'position': 4" in payload


# ---- "direct" is earned, not claimed ----


def test_a_direct_claim_is_downgraded_when_the_cv_line_lacks_the_requirements_term():
    # general model evaluation (exp1.b4) is not LLM evaluation, whatever the model says
    result = result_for(out(suggestion(source_ids=["exp1.b4"], requirement_quote=Q_AI_EVAL, support="direct")))
    assert [s.support for s in result.suggestions] == ["related"]


def test_a_direct_claim_stays_direct_when_the_line_really_has_the_term():
    # "LLM-based invoice triage agent" does show LLM features in production
    summary = suggestion(
        kind="summary", source_ids=["exp1.b1"], requirement_quote=Q_AI, support="direct", after=AI_SUMMARY
    )
    assert [s.support for s in result_for(out(summary)).suggestions] == ["direct"]


def test_requirements_without_a_distinctive_term_keep_the_models_direct_claim():
    # "integrate partner webhooks" names no tool in capitals: the line says webhooks, so it is direct
    quote = "integrate partner webhooks"
    result = result_for(out(suggestion(source_ids=["exp2.b4"], requirement_quote=quote, support="direct")))
    assert [s.support for s in result.suggestions] == ["direct"]


def test_a_related_claim_is_never_upgraded():
    result = result_for(
        out(suggestion(source_ids=["exp2.b4"], requirement_quote="integrate partner webhooks", support="related"))
    )
    assert [s.support for s in result.suggestions] == ["related"]


# ---- why proposals were thrown away (codes only) ----


def test_the_reasons_for_dropped_proposals_are_counted_without_their_text():
    result = result_for(
        out(
            suggestion(requirement_quote="Must know COBOL", source_ids=["exp1.b4"]),  # quote
            suggestion(source_ids=["exp1.b1"]),  # already first
            suggestion(
                kind="rewrite",
                source_ids=["exp1.b2"],
                after=(
                    "Designed reliable workflow automations with queues and retries, replacing five hand-run scripts."
                ),
            ),
            suggestion(kind="summary", source_ids=["exp1.b1"], after=AI_SUMMARY + " Runs Kubernetes."),  # claim
            questions=[ModelQuestion(requirement_quote="Experience with Rust", level="preferred", term="Rust")],
        )
    )
    assert result.suggestions == []
    assert result.dropped_reasons == {
        "quote_not_in_posting": 1,
        "already_first": 1,
        "rewrite_not_substantive": 1,
        "summary_unsupported_claim": 1,
        "question_not_grounded": 1,
    }
    assert result.dropped == 5


def test_the_prompt_asks_for_focus_specific_targets_and_concrete_summaries():
    prompt = IT_SYSTEM_PROMPT
    assert "Never target" in prompt and "years of experience" in prompt
    assert "No\n  buzzwords" in prompt or "buzzwords" in prompt
    assert "uses it" in prompt  # a figure in the source line goes into the summary
    assert "do not skip it" in prompt  # a missing required term is asked about


# ---- generic conditions are not a worthwhile target ----

GENERIC_QUOTES = [
    "3+ years of professional software engineering experience",
    "Ownership of services in production",
    "Clear written communication",
]


@pytest.mark.parametrize("quote", GENERIC_QUOTES)
@pytest.mark.parametrize(
    "kind,extra",
    [
        ("promote", {}),
        (
            "rewrite",
            {
                "after": (
                    "Cut manual review by 60% with an LLM-based invoice triage agent "
                    "that handles 12,000 documents per month."
                )
            },
        ),
    ],
)
def test_moving_or_rewording_a_line_for_a_generic_condition_is_dropped(quote, kind, extra):
    source = "exp1.b4" if kind == "promote" else "exp1.b1"
    result = result_for(out(suggestion(kind=kind, requirement_quote=quote, source_ids=[source], **extra)))
    assert result.suggestions == []
    assert result.dropped_reasons == {"generic_requirement": 1}


def test_a_summary_aimed_at_a_generic_condition_is_dropped_never_re_aimed():
    output = out(
        suggestion(kind="summary", requirement_quote=GENERIC_QUOTES[0], source_ids=["exp1.b1"], after=AI_SUMMARY)
    )
    output.requirements = [ModelRequirement(text="Years", quote=GENERIC_QUOTES[0], level="required")]
    result = result_for(output)
    assert result.suggestions == [] and result.dropped_reasons == {"generic_requirement": 1}


# ---- the explanation never contradicts the label ----


def test_a_downgraded_card_names_what_the_line_does_not_mention():
    (card,) = result_for(
        out(
            suggestion(
                source_ids=["exp1.b4"],
                requirement_quote=Q_AI_EVAL,
                support="direct",
                rationale="This bullet directly shows evaluation of LLM outputs.",
            )
        )
    ).suggestions
    assert card.support == "related"
    assert card.rationale == "Related experience: this line is close to the requirement but does not mention llm."


def test_a_related_card_that_says_directly_gets_a_plain_related_explanation():
    (card,) = result_for(
        out(
            suggestion(
                source_ids=["exp2.b4"],
                requirement_quote="integrate partner webhooks",
                support="related",
                rationale="The bullet directly supports the requirement.",
            )
        )
    ).suggestions
    assert card.rationale == "Related experience: close to what the posting asks for, not the same thing."


def test_an_honest_related_explanation_is_kept_as_written():
    (card,) = result_for(
        out(
            suggestion(
                source_ids=["exp2.b4"],
                requirement_quote="integrate partner webhooks",
                support="related",
                rationale="Related: integration work, not API design.",
            )
        )
    ).suggestions
    assert card.rationale == "Related: integration work, not API design."


# ---- a choice only where the posting offers one ----


def test_the_posting_words_tell_whether_a_choice_is_offered():
    assert offers_choice(JOB_DESCRIPTION) is True
    assert offers_choice(CLEAR_JOB_DESCRIPTION) is False
    assert it_input(CV, JOB_TITLE, JOB_DESCRIPTION, "")["posting_offers_choice"] is True
    assert it_input(CV, CLEAR_JOB_TITLE, CLEAR_JOB_DESCRIPTION, "")["posting_offers_choice"] is False


def test_tracks_invented_for_a_clear_posting_are_not_shown_and_cost_one_more_call():
    llm = FakeLLM(tracks_output(), ai_output())  # first answer: responsibilities mistaken for tracks
    result = asyncio.run(IT_AGENT.analyze(CareerCase(CV, CLEAR_JOB_TITLE, CLEAR_JOB_DESCRIPTION, ""), llm))

    assert result.kind == "suggestions"
    assert len(llm.calls) == 2
    assert llm.calls[1]["focus"] == CLEAR_JOB_TITLE  # asked again, for the posting's one focus


def test_a_real_choice_is_never_asked_twice():
    llm = FakeLLM(tracks_output(), ai_output())
    assert analyze(llm).kind == "choose_focus"
    assert len(llm.calls) == 1


# ---- a summary must answer a requirement its own lines can support ----


# ---- a summary's target is never swapped, and the lines it draws on are all shown ----


def test_a_summary_aimed_at_a_term_none_of_its_lines_mention_stays_aimed_there_but_is_only_related():
    # PostgreSQL is nowhere in the CV: the card says so instead of moving to another requirement
    (card,) = result_for(
        out(
            suggestion(
                kind="summary",
                requirement_quote=Q_PREF_PG,
                level="preferred",
                source_ids=["exp2.b1"],
                support="direct",
                after=PY_SUMMARY,
            )
        )
    ).suggestions
    assert (card.requirement, card.level, card.support) == (Q_PREF_PG, "preferred", "related")
    assert "postgresql" in card.rationale


def test_a_technology_in_the_skills_list_does_not_make_a_summary_direct():
    # FastAPI is only in the skills list; no CV line shows work with it
    (card,) = result_for(
        out(
            suggestion(
                kind="summary",
                requirement_quote=Q_PY,
                source_ids=["exp2.b4", "exp2.b1"],
                support="direct",
                after=PY_SUMMARY,
            )
        )
    ).suggestions
    assert card.support == "related"
    assert "fastapi" in card.rationale
