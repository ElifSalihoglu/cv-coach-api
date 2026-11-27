"""The shape of the agent architecture: what is shared, what is domain-specific, what is sent."""
import asyncio
import json
from dataclasses import replace
from pathlib import Path

from app.careers.agents.it import IT_AGENT, IT_PROFILE
from app.careers.core.agent import CareerAgent
from app.careers.core.engine import DEFAULT_ENGINE
from app.careers.core.gates import CORE_GATES, Gate
from app.careers.core.state import CareerCase
from tests.fixtures.coach_fixture import CV, JOB_DESCRIPTION, JOB_TITLE
from app.models.coaching import CoachModelOutput, ModelSuggestion
from tests.fixtures.coach_scenarios import FakeLLM, Q_REQ

CORE_DIR = Path(__file__).resolve().parents[1] / "app" / "careers" / "core"


def _generic_suggestion() -> CoachModelOutput:
    # "3+ years" is a generic condition: the IT agent refuses to aim a card at it.
    return CoachModelOutput(mode="suggestions", suggestions=[ModelSuggestion(
        kind="promote", requirement_quote=Q_REQ, level="required", source_ids=["exp1.b4"],
        support="related", priority=1, rationale="r")])


def test_the_shared_core_knows_nothing_about_a_domain():
    for path in CORE_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "careers.agents" not in text, f"{path.name} imports a domain agent"
    shared_codes = {g.code for g in CORE_GATES}
    assert shared_codes.isdisjoint({"generic_requirement", "summary_unsupported_action"})


def test_the_it_rules_live_in_the_it_profile_not_in_the_shared_pipeline():
    assert [g.code for g in IT_PROFILE.requirement_gates] == ["generic_requirement"]
    assert [g.code for g in IT_PROFILE.draft_gates] == ["summary_unsupported_action"]

    without_it_gates = replace(IT_PROFILE, id="other", requirement_gates=(), draft_gates=())
    kept = DEFAULT_ENGINE.build_result(without_it_gates, CV, JOB_DESCRIPTION, _generic_suggestion(), "AI")
    dropped = DEFAULT_ENGINE.build_result(IT_PROFILE, CV, JOB_DESCRIPTION, _generic_suggestion(), "AI")

    assert [s.id for s in kept.suggestions] == ["promote:exp1.b4"]  # a profile without the IT gate keeps it
    assert dropped.suggestions == [] and dropped.dropped_reasons == {"generic_requirement": 1}


def test_a_domain_can_add_its_own_gate_and_its_code_is_counted():
    never = Gate("my_domain_rule", lambda ctx, p: True, frozenset({"promote"}))
    profile = replace(IT_PROFILE, id="x", requirement_gates=(), draft_gates=(never,))
    result = DEFAULT_ENGINE.build_result(profile, CV, JOB_DESCRIPTION, _generic_suggestion(), "AI")
    assert result.suggestions == [] and result.dropped_reasons == {"my_domain_rule": 1}


def test_the_it_agent_is_a_career_agent_that_runs_the_shared_engine():
    assert isinstance(IT_AGENT, CareerAgent) and IT_AGENT.card.id == "it"

    case = CareerCase(CV, JOB_TITLE, JOB_DESCRIPTION, "AI")
    through_agent = asyncio.run(IT_AGENT.analyze(case, FakeLLM(_generic_suggestion())))
    through_engine = asyncio.run(DEFAULT_ENGINE.run(IT_PROFILE, case, FakeLLM(_generic_suggestion())))
    assert through_agent == through_engine


def test_the_it_model_input_has_exactly_these_fields_and_no_personal_identifiers():
    payload = IT_PROFILE.build_input(CV, JOB_TITLE, JOB_DESCRIPTION, "AI")

    assert list(payload) == ["job_title", "job_description", "posting_offers_choice", "focus", "candidate"]
    assert list(payload["candidate"]) == ["summary", "skills", "experiences", "projects"]
    assert list(payload["candidate"]["experiences"][0]) == ["id", "title", "employer", "bullets"]
    assert list(payload["candidate"]["experiences"][0]["bullets"][0]) == ["id", "position", "text"]

    sent = json.dumps(payload, ensure_ascii=False)
    for private in (CV.name, CV.email, CV.location):
        assert private and private not in sent
    for exp in CV.experiences:
        assert exp.start not in sent.replace(JOB_DESCRIPTION, "")
