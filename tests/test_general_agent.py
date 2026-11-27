"""General Career Agent: its own prompt, input and gates; untouched by the IT rules. Fake model only."""
import asyncio
import difflib
import json
from pathlib import Path

from app.careers.agents.general import GENERAL_PROFILE, GeneralAgent
from app.careers.core.engine import DEFAULT_ENGINE
from app.careers.registry import AgentRegistry
from app.careers.agents.it import IT_AGENT, IT_PROFILE
from app.careers.agents.general.prompt import GENERAL_SYSTEM_PROMPT
from app.careers.core.state import CareerCase
from tests.fixtures.general_fixtures import (
    MARKETING_CV, MARKETING_JOB_DESCRIPTION, MARKETING_JOB_TITLE, MECH_CV, MECH_JOB_DESCRIPTION,
    MECH_JOB_TITLE, NURSE_CV, NURSE_JOB_DESCRIPTION, NURSE_JOB_TITLE,
)
from app.models.coaching import CoachModelOutput, ModelSuggestion
from app.prompts.coach_templates import COACH_SYSTEM_PROMPT
from tests.fixtures.general_scenarios import (
    MECH_DESIGN_SUMMARY, MECH_LICENSED_SUMMARY, NURSE_SUMMARY, Q_COMMUNICATION, Q_DESIGN, Q_YEARS,
    marketing_output, mech_output, nurse_output,
)
from tests.test_coach_regression import RecordingLLM

GENERAL_DIR = Path(__file__).resolve().parents[1] / "app" / "careers" / "agents" / "general"


def general(cv, description, output, focus=""):
    return DEFAULT_ENGINE.build_result(GENERAL_PROFILE, cv, description, output, focus)


def it(cv, description, output, focus=""):
    return IT_AGENT.build_result(cv, description, output, focus)


# ---- a real agent, not a renamed copy

def test_the_general_prompt_is_its_own_text_not_a_copy_of_the_it_prompt():
    assert GENERAL_SYSTEM_PROMPT != COACH_SYSTEM_PROMPT
    assert difflib.SequenceMatcher(None, GENERAL_SYSTEM_PROMPT, COACH_SYSTEM_PROMPT).ratio() < 0.5
    for it_only in ("IT Career Coach", "technical recruiter", "LLM", "Kubernetes", "API"):
        assert it_only not in GENERAL_SYSTEM_PROMPT
    for general_only in ("licence", "transferable", "measured", "education", "certifications"):
        assert general_only in GENERAL_SYSTEM_PROMPT
    assert GENERAL_PROFILE.system_prompt is GENERAL_SYSTEM_PROMPT


def test_the_general_agent_shares_no_validation_gate_with_the_it_agent_and_imports_nothing_from_it():
    general_codes = {g.code for g in (*GENERAL_PROFILE.requirement_gates, *GENERAL_PROFILE.draft_gates)}
    it_codes = {g.code for g in (*IT_PROFILE.requirement_gates, *IT_PROFILE.draft_gates)}
    assert general_codes and general_codes.isdisjoint(it_codes)
    assert GENERAL_PROFILE.lexicon is not IT_PROFILE.lexicon
    for path in GENERAL_DIR.glob("*.py"):
        assert "agents.it" not in path.read_text(encoding="utf-8"), path.name


# ---- the model input: education and certifications without personal identifiers

def test_education_and_certifications_reach_the_model_without_school_issuer_dates_or_numbers():
    payload = GENERAL_PROFILE.build_input(NURSE_CV, NURSE_JOB_TITLE, NURSE_JOB_DESCRIPTION, "")
    candidate = payload["candidate"]

    assert candidate["education"] == [{"id": "edu1", "degree": "BSc Nursing", "details": "Thesis on pressure-ulcer prevention"}]
    assert candidate["certifications"] == [
        {"id": "cert1", "name": "Basic Life Support (BLS)"},
        {"id": "cert2", "name": "Registered Nurse Licence"},
    ]
    assert list(candidate) == ["summary", "skills", "languages", "experiences", "projects", "education", "certifications"]

    sent = json.dumps(payload, ensure_ascii=False)
    for private in ("Aylin", "aylin.demir", "+90", "example.com", "Izmir", "Ege University", "Ministry of Health",
                    "Red Crescent", "123456", "2012", "2016", "2019", "2023"):
        assert private not in sent.replace(NURSE_JOB_DESCRIPTION, ""), private


def test_the_it_input_is_unchanged_and_still_carries_no_education_or_certifications():
    candidate = IT_PROFILE.build_input(NURSE_CV, "t", "d", "")["candidate"]
    assert list(candidate) == ["summary", "skills", "experiences", "projects"]


# ---- what it does with a non-IT CV

def test_the_general_agent_turns_a_nurse_cv_into_checked_suggestions():
    llm = RecordingLLM(nurse_output())
    result = asyncio.run(GeneralAgent(AgentRegistry()).analyze(CareerCase(NURSE_CV, NURSE_JOB_TITLE, NURSE_JOB_DESCRIPTION), llm))

    summary, promote = result.suggestions
    assert (summary.id, summary.after, summary.support) == ("summary", NURSE_SUMMARY, "direct")
    assert (promote.id, promote.support, promote.position) == ("promote:exp1.b2", "related", 2)
    assert [q.term for q in result.questions] == ["ACLS"]  # an optional credential the CV does not list
    assert [r.text for r in result.requirements][:1] == ["Registered Nurse licence"]
    assert result.dropped_reasons == {"years_requirement": 1}  # the "3+ years" card is not worth a line
    assert len(llm.calls) == 1


def test_a_condition_that_is_substance_in_another_field_is_not_dropped_as_generic():
    # "Strong written communication" is generic for an engineer (IT gate) but a real requirement elsewhere.
    kept = general(MARKETING_CV, MARKETING_JOB_DESCRIPTION, marketing_output(), "Digital Marketing Manager")
    refused = it(MARKETING_CV, MARKETING_JOB_DESCRIPTION, marketing_output(), "Digital Marketing Manager")

    assert [s.id for s in kept.suggestions] == ["promote:exp1.b2", "promote:exp1.b3"]
    assert kept.suggestions[1].requirement == Q_COMMUNICATION
    assert [s.id for s in refused.suggestions] == ["promote:exp1.b2"]
    assert refused.dropped_reasons == {"generic_requirement": 1}


def test_the_general_agent_drops_a_years_of_experience_card_that_the_it_agent_phrases_differently():
    result = general(NURSE_CV, NURSE_JOB_DESCRIPTION, CoachModelOutput(suggestions=[ModelSuggestion(
        kind="promote", requirement_quote=Q_YEARS, level="required", source_ids=["exp1.b4"],
        support="related", priority=1, rationale="r")]), "Staff Nurse")
    assert result.suggestions == [] and result.dropped_reasons == {"years_requirement": 1}


def test_a_design_claim_is_an_it_rule_the_general_agent_does_not_apply():
    focus = "Mechanical Design Engineer"
    refused = it(MECH_CV, MECH_JOB_DESCRIPTION, mech_output(MECH_DESIGN_SUMMARY), focus)
    kept = general(MECH_CV, MECH_JOB_DESCRIPTION, mech_output(MECH_DESIGN_SUMMARY), focus)

    assert refused.suggestions == [] and refused.dropped_reasons == {"summary_unsupported_action": 1}
    assert [s.id for s in kept.suggestions] == ["summary"] and kept.dropped_reasons == {}


# ---- its own rules: a qualification is named only when the CV lists it

def test_a_summary_may_name_a_licence_only_if_the_cv_lists_one():
    focus = "Mechanical Design Engineer"
    refused = general(MECH_CV, MECH_JOB_DESCRIPTION, mech_output(MECH_LICENSED_SUMMARY), focus)
    assert refused.suggestions == [] and refused.dropped_reasons == {"summary_unlisted_qualification": 1}

    nurse = general(NURSE_CV, NURSE_JOB_DESCRIPTION, CoachModelOutput(suggestions=[ModelSuggestion(
        kind="summary", requirement_quote="Administer medication and monitor vital signs", level="required",
        source_ids=["exp1.b3"], support="direct", priority=1, rationale="r",
        after="Licensed nurse who reduced medication errors on a medical ward by 30%.")]), "Staff Nurse")
    assert [s.id for s in nurse.suggestions] == ["summary"]  # the nurse's CV lists a licence


def test_a_rewrite_that_adds_a_qualification_the_cv_lacks_is_refused():
    result = general(MECH_CV, MECH_JOB_DESCRIPTION, CoachModelOutput(suggestions=[ModelSuggestion(
        kind="rewrite", requirement_quote=Q_DESIGN, level="required", source_ids=["exp1.b1"], support="related",
        priority=1, rationale="r",
        after="Designed certified, tolerance-checked sheet-metal enclosures for industrial pump housings, cutting part cost by 12%.")]), "x")
    assert result.suggestions == [] and result.dropped_reasons == {"rewrite_unlisted_qualification": 1}


def test_the_general_lexicon_catches_leadership_the_cv_does_not_claim():
    result = general(MECH_CV, MECH_JOB_DESCRIPTION, mech_output(
        "Supervisor of a design team with six years in product design and testing."), "x")
    assert result.suggestions == [] and result.dropped_reasons == {"summary_unsupported_claim": 1}
