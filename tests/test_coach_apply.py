"""Decisions become a CV: only what the user accepted, main CV untouched, no model call."""
import asyncio

import pytest

from tests.fixtures.coach_fixture import CV, JOB_DESCRIPTION, JOB_TITLE
from app.models.coaching import Addition, AdditionTarget, ApplyRequest, CheckRequest, Decision
from app.models.cv_document import CVBullet, CVProject
from app.services.coach_apply import (
    DecisionError, UnconfirmedClaims, apply_decisions, check_text,
)
from app.services.job_coach import ITCareerCoach
from tests.fixtures.coach_scenarios import AI_SUMMARY, FakeLLM, ai_output

ACCEPT = Decision(action="accept")


def ai_suggestions():
    result = asyncio.run(ITCareerCoach(FakeLLM(ai_output())).analyze(CV, JOB_TITLE, JOB_DESCRIPTION, "AI"))
    return {s.id: s for s in result.suggestions}


def apply(decisions=None, additions=(), suggestions=None, cv=CV):
    suggestions = suggestions if suggestions is not None else ai_suggestions()
    return apply_decisions(ApplyRequest(
        cv=cv, suggestions=list(suggestions.values()), decisions=decisions or {},
        additions=list(additions), job_description=JOB_DESCRIPTION,
    ))


def bullets(cv, exp="exp1"):
    return [(b.id, b.text) for e in cv.experiences if e.id == exp for b in e.bullets]


def test_nothing_accepted_is_the_main_cv():
    result = apply()
    assert result.cv == CV and result.changes == []


def test_accepting_a_move_puts_that_line_first_and_changes_only_the_order():
    result = apply({"promote:exp1.b4": ACCEPT})

    assert [i for i, _ in bullets(result.cv)] == ["exp1.b4", "exp1.b1", "exp1.b2", "exp1.b3", "exp1.b5"]
    assert dict(bullets(result.cv)) == dict(bullets(CV))  # same texts
    assert result.cv.summary == CV.summary
    (change,) = result.changes
    assert (change.kind, change.id, change.detail) == ("moved", "exp1.b4", "Moved from 4th to 1st")


def test_accepting_the_summary_replaces_only_the_summary():
    result = apply({"summary": ACCEPT})
    assert result.cv.summary == AI_SUMMARY
    assert bullets(result.cv) == bullets(CV)
    (change,) = result.changes
    assert (change.kind, change.before, change.after) == ("summary", CV.summary, AI_SUMMARY)


def test_the_main_cv_is_never_modified():
    before = CV.model_dump()
    apply({"summary": ACCEPT, "promote:exp1.b4": ACCEPT, "promote:exp1.b2": ACCEPT})
    assert CV.model_dump() == before


def test_a_rejected_or_undecided_suggestion_is_not_applied():
    # only the summary is accepted; the two moves are rejected or undecided (not sent)
    result = apply({"summary": ACCEPT})
    assert [i for i, _ in bullets(result.cv)] == [i for i, _ in bullets(CV)]


def test_two_accepted_moves_in_one_role_put_the_more_useful_line_first():
    result = apply({"promote:exp1.b4": ACCEPT, "promote:exp1.b2": ACCEPT})
    assert [i for i, _ in bullets(result.cv)][:2] == ["exp1.b4", "exp1.b2"]  # b4 has priority 2, b2 has 3


# ---- move and rewrite of the same line are independent ----

def rewrite_and_move():
    suggestions = ai_suggestions()
    rewrite = suggestions["promote:exp1.b4"].model_copy(update={
        "id": "rewrite:exp1.b4", "kind": "rewrite", "position": None, "priority": 9,
        "after": "Set up evaluation dashboards and offline test sets that track model quality across every release.",
    })
    suggestions[rewrite.id] = rewrite
    return suggestions


def test_move_and_rewrite_of_the_same_line_both_apply_as_one_change():
    suggestions = rewrite_and_move()
    result = apply({"promote:exp1.b4": ACCEPT, "rewrite:exp1.b4": ACCEPT}, suggestions=suggestions)

    assert bullets(result.cv)[0] == ("exp1.b4", suggestions["rewrite:exp1.b4"].after)
    (change,) = result.changes
    assert change.kind == "moved_rewritten" and change.id == "exp1.b4"
    assert change.detail == "Moved from 4th to 1st"
    assert change.before == CV.experiences[0].bullets[3].text


def test_undoing_the_move_keeps_the_rewrite_and_undoing_the_rewrite_keeps_the_move():
    suggestions = rewrite_and_move()

    only_rewrite = apply({"rewrite:exp1.b4": ACCEPT}, suggestions=suggestions)
    assert [i for i, _ in bullets(only_rewrite.cv)] == [i for i, _ in bullets(CV)]  # not moved
    assert dict(bullets(only_rewrite.cv))["exp1.b4"] == suggestions["rewrite:exp1.b4"].after
    assert [c.kind for c in only_rewrite.changes] == ["rewritten"]

    only_move = apply({"promote:exp1.b4": ACCEPT}, suggestions=suggestions)
    assert bullets(only_move.cv)[0] == ("exp1.b4", CV.experiences[0].bullets[3].text)  # original wording
    assert [c.kind for c in only_move.changes] == ["moved"]


# ---- Edit & accept ----

def test_an_edit_uses_the_users_text_and_is_marked_as_edited():
    text = AI_SUMMARY + " I also mentor engineers."  # nothing the CV does not back up
    result = apply({"summary": Decision(action="edit", text=text)})
    assert result.cv.summary == text
    (change,) = result.changes
    assert change.detail == "Edited by you" and change.user_added is False


def test_an_edit_with_a_claim_the_cv_does_not_back_up_needs_confirmation():
    text = AI_SUMMARY + " I run Kubernetes clusters."
    with pytest.raises(UnconfirmedClaims) as caught:
        apply({"summary": Decision(action="edit", text=text)})
    assert caught.value.claims[0].terms == ["Kubernetes"]
    assert "Kubernetes" in caught.value.message and caught.value.item_id == "summary"


def test_a_confirmed_claim_goes_in_and_is_recorded_as_added_by_the_user():
    text = AI_SUMMARY + " I run Kubernetes clusters."
    result = apply({"summary": Decision(action="edit", text=text, confirmed_terms=["kubernetes"])})
    assert result.cv.summary == text
    assert result.changes[0].user_added is True


def test_a_suggestion_whose_text_was_changed_on_the_way_in_is_still_checked():
    suggestions = ai_suggestions()
    suggestions["summary"] = suggestions["summary"].model_copy(update={"after": AI_SUMMARY + " Expert in Terraform."})
    with pytest.raises(UnconfirmedClaims):
        apply({"summary": ACCEPT}, suggestions=suggestions)


def test_an_edit_that_adds_a_number_needs_confirmation_too():
    with pytest.raises(UnconfirmedClaims) as caught:
        apply({"summary": Decision(action="edit", text=AI_SUMMARY.replace("12,000", "90,000"))})
    assert caught.value.claims[0].kind == "numbers"


def test_a_moved_line_has_no_text_to_edit_and_unknown_suggestions_are_refused():
    with pytest.raises(DecisionError):
        apply({"promote:exp1.b4": Decision(action="edit", text="x")})
    with pytest.raises(DecisionError):
        apply({"promote:exp9.b9": ACCEPT})


# ---- answers to questions ----

def test_an_answer_becomes_a_new_line_in_the_chosen_role():
    addition = Addition(id="ask:kubernetes", target=AdditionTarget(type="experience", id="exp1"),
                        text="Deployed the invoice agent to Kubernetes.", confirmed_terms=["Kubernetes"])
    result = apply(additions=[addition])

    assert bullets(result.cv)[-1] == ("exp1.b6", "Deployed the invoice agent to Kubernetes.")
    assert bullets(result.cv, "exp2") == bullets(CV, "exp2")
    (change,) = result.changes
    assert (change.kind, change.user_added, change.where) == (
        "added", True, "Senior Software Engineer — Boğaz Yazılım")


def test_an_answer_can_belong_to_a_project():
    cv = CV.model_copy(update={"projects": [CVProject(id="proj1", name="Mail agent", description="Sorts email.")]})
    addition = Addition(id="ask:kubernetes", target=AdditionTarget(type="project", id="proj1"),
                        text="Runs on Kubernetes.", confirmed_terms=["Kubernetes"])
    result = apply(additions=[addition], cv=cv)
    assert result.cv.projects[0].description == "Sorts email.\nRuns on Kubernetes."
    assert result.changes[0].where == "Mail agent"


def test_an_answer_with_an_unconfirmed_new_term_is_refused_and_an_unknown_role_too():
    risky = Addition(id="ask:kubernetes", target=AdditionTarget(type="experience", id="exp1"),
                     text="Deployed the invoice agent to Kubernetes.")
    with pytest.raises(UnconfirmedClaims):
        apply(additions=[risky])
    nowhere = Addition(id="ask:x", target=AdditionTarget(type="experience", id="exp9"), text="Did a thing.")
    with pytest.raises(DecisionError):
        apply(additions=[nowhere])


# ---- the check the screen runs before asking for confirmation ----

def test_check_tells_what_a_text_says_that_the_cv_does_not():
    result = check_text(CheckRequest(cv=CV, job_description=JOB_DESCRIPTION, kind="summary",
                                     text="Python engineer who runs Kubernetes and Terraform."))
    assert [(c.kind, c.terms) for c in result.claims] == [("skills", ["Kubernetes", "Terraform"])]
    assert result.message == "Your text mentions Kubernetes, Terraform, which isn't in your CV."


def test_check_is_quiet_for_text_the_cv_backs_up():
    assert check_text(CheckRequest(cv=CV, job_description=JOB_DESCRIPTION, kind="summary", text=AI_SUMMARY)).claims == []


def test_a_new_bullet_id_never_reuses_an_existing_one():
    cv = CV.model_copy(deep=True)
    cv.experiences[0].bullets[-1] = CVBullet(id="exp1.b9", text="Mentored four engineers.")
    addition = Addition(id="ask:q", target=AdditionTarget(type="experience", id="exp1"), text="Did a thing.")
    assert bullets(apply(additions=[addition], cv=cv).cv)[-1][0] == "exp1.b10"
