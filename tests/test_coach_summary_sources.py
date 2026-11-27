"""
Summary cards: what the model wrote, what we keep, and what the user is shown.

The three acceptance examples use the exact summaries from the saved live run
(synthetic CV and posting), replayed offline: no model call.
"""

from app.careers.agents.it import IT_PROFILE
from app.careers.agents.it.rules import unsupported_design_claims
from app.careers.core.engine import DEFAULT_ENGINE
from app.models.coaching import CoachModelOutput, ModelSuggestion
from app.models.cv_document import CVBullet
from tests.fixtures.coach_fixture import CV, JOB_DESCRIPTION
from tests.fixtures.coach_scenarios import Q_AI, Q_AI_EVAL, Q_PY

# r2/python: the model claims design work the CV does not have (it only has integration)
PY_DESIGNING = (
    "Software engineer who automated nightly ETL pipelines in Python and Airflow, saving about 20 "
    "engineer-hours per week. Experienced in designing and integrating REST APIs and webhooks for "
    "internal tools, with seven years of experience in Python and data pipelines."
)
PY_INTEGRATING = PY_DESIGNING.replace("designing and integrating", "integrating")

# r1/ai: the text draws on two lines but the model cited only one
AI_TWO_LINES = (
    "Software engineer who built an LLM-based invoice triage agent handling 12,000 documents per month "
    "and cut manual review by 60%. Experienced in setting up evaluation dashboards and offline test sets "
    "to track model quality across releases."
)


def summary(after: str, quote: str, sources: list[str], support: str = "direct") -> CoachModelOutput:
    return CoachModelOutput(
        mode="suggestions",
        suggestions=[
            ModelSuggestion(
                kind="summary",
                requirement_quote=quote,
                level="required",
                source_ids=sources,
                support=support,
                after=after,
                rationale="r",
                priority=1,
            )
        ],
    )


def build(output: CoachModelOutput, cv=CV, focus: str = ""):
    return DEFAULT_ENGINE.build_result(IT_PROFILE, cv, JOB_DESCRIPTION, output, focus)


# ---- (1) integration experience only: "designing REST APIs" never reaches the user ----


def test_a_designing_claim_without_a_design_line_in_the_cv_is_dropped():
    result = build(summary(PY_DESIGNING, Q_PY, ["exp2.b1"]), focus="Python Backend")

    assert result.suggestions == []  # the user never sees it
    assert result.dropped_reasons == {"summary_unsupported_action": 1}


def test_the_same_summary_without_the_design_claim_is_kept():
    (card,) = build(summary(PY_INTEGRATING, Q_PY, ["exp2.b1"]), focus="Python Backend").suggestions
    assert card.after == PY_INTEGRATING


def test_a_technology_in_the_skills_list_is_not_design_work():
    assert "REST APIs" in CV.skills  # listed as a skill ...
    assert unsupported_design_claims("Experienced in designing REST APIs.", CV)  # ... but never designed


# ---- (2) the CV really says the candidate designed APIs: the same claim stays ----


def test_the_same_claim_is_kept_when_a_cv_line_says_apis_were_designed():
    cv = CV.model_copy(deep=True)
    cv.experiences[1].bullets[3] = CVBullet(
        id="exp2.b4", text="Designed and maintained REST APIs and integrated partner webhooks for the operations team."
    )

    result = build(summary(PY_DESIGNING, Q_PY, ["exp2.b1"]), cv=cv, focus="Python Backend")

    (card,) = result.suggestions
    assert card.after == PY_DESIGNING
    assert [r.id for r in card.sources] == ["exp2.b1", "exp2.b4"]  # and the line that backs it is shown
    assert unsupported_design_claims(PY_DESIGNING, cv) == []


def test_designing_something_else_does_not_back_a_claim_about_apis():
    # exp1.b2 "Designed workflow automations ..." is real design work, but of workflows
    assert unsupported_design_claims("Designed workflow automations with queues.", CV) == []
    assert unsupported_design_claims("Designed REST APIs.", CV) == ["Designed REST APIs"]


# ---- (3) invoice agent plus general model evaluation ----


def test_a_summary_drawing_on_two_lines_shows_both_and_keeps_its_own_target():
    (card,) = build(
        summary(AI_TWO_LINES, "AI: ship LLM features to production and keep agents and tools reliable.", ["exp1.b1"]),
        focus="AI",
    ).suggestions

    assert [r.id for r in card.sources] == ["exp1.b1", "exp1.b4"]  # both lines are on the card
    assert card.requirement == "AI: ship LLM features to production and keep agents and tools reliable."
    assert card.support == "direct"  # the agent line shows LLM features; "AI" only names the focus


def test_general_model_evaluation_is_not_labelled_llm_evaluation():
    # the model aims the same text at "evaluate LLM outputs": only the agent line says LLM,
    # and it does not talk about evaluation; the evaluation line never says LLM
    (card,) = build(summary(AI_TWO_LINES, Q_AI_EVAL, ["exp1.b1"]), focus="AI").suggestions

    assert card.requirement == Q_AI_EVAL  # not swapped for another requirement
    assert card.support == "related"
    assert card.rationale == "Related experience: this line is close to the requirement but does not mention llm."
    assert [r.id for r in card.sources] == ["exp1.b1", "exp1.b4"]


def test_a_summary_does_not_pick_up_unrelated_lines():
    (card,) = build(summary(PY_INTEGRATING, Q_PY, ["exp2.b1"]), focus="Python Backend").suggestions
    assert "exp1.b5" not in [r.id for r in card.sources]  # mentoring is not part of this text
    assert len(card.sources) <= 3


def test_a_summary_is_never_moved_to_another_requirement():
    # the summary stays aimed at the requirement it answers; it is never swapped for another one
    (card,) = build(summary(AI_TWO_LINES, Q_AI, ["exp1.b1"]), focus="AI").suggestions
    assert card.requirement == Q_AI


# ---- the claim is judged by what was designed, not by a banned word ----


def _cv_with(text: str):
    cv = CV.model_copy(deep=True)
    cv.experiences[1].bullets[3] = CVBullet(id="exp2.b4", text=text)
    return cv


def test_designed_api_integrations_needs_a_line_that_says_so():
    claim = "Software engineer who designed API integrations for internal tools, with seven years in Python."
    # the CV only says it INTEGRATED third-party APIs: the design claim never reaches the user
    assert build(summary(claim, Q_PY, ["exp2.b4"]), focus="Python Backend").suggestions == []
    # a line that really says integrations were designed backs the same sentence
    cv = _cv_with("Designed API integrations between the billing platform and partner systems.")
    (card,) = build(summary(claim, Q_PY, ["exp2.b4"]), cv=cv, focus="Python Backend").suggestions
    assert card.after == claim


def test_designing_a_different_thing_is_not_support_even_when_words_overlap():
    # "internal tools" is shared, but the CV line designed tools, not REST APIs
    cv = _cv_with("Designed internal tools for the operations team.")
    assert unsupported_design_claims("Designed internal REST APIs for the operations team.", cv) == [
        "Designed internal REST APIs for the operations team"
    ]
    assert unsupported_design_claims("Designed internal tools for the operations team.", cv) == []


def test_the_banned_word_is_not_the_rule():
    # "designing" is fine wherever a line says what was designed; "building" a REST API is not judged here
    cv = _cv_with("Designed and maintained REST APIs for the operations team.")
    assert unsupported_design_claims("Experienced in designing REST APIs.", cv) == []
    assert unsupported_design_claims("Built REST APIs for webhooks.", CV) == []
