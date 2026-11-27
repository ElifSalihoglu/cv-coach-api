"""GeneralAgent.handle with a fake model: routing, delegation, provenance, failure handling, IT behaviour kept."""
import asyncio

import pytest

from app.careers.agents.general import GeneralAgent
from app.careers.agents.general.prompt import GENERAL_SYSTEM_PROMPT
from app.careers.assembly import build_default_general_agent, build_default_registry
from app.careers.core.gates import Gate
from app.careers.core.state import CareerCase, OrchestrationError
from app.careers.registry import AgentRegistry, UnknownDomainError
from app.evals.coach_fixture import CV, JOB_DESCRIPTION, JOB_TITLE
from app.evals.general_fixtures import (
    MARKETING_CV, MARKETING_JOB_DESCRIPTION, MARKETING_JOB_TITLE, NURSE_CV,
    NURSE_JOB_DESCRIPTION, NURSE_JOB_TITLE,
)
from app.models.coaching import CoachModelOutput, ModelSuggestion
from app.prompts.coach_templates import COACH_SYSTEM_PROMPT
from app.services.job_coach import ITCareerCoach
from app.services.llm_client import LLMTimeoutError
from tests.coach_scenarios import ai_output, tracks_output
from tests.general_scenarios import marketing_output, nurse_output
from tests.test_coach_regression import RecordingLLM
from tests.toy_agents import Broken, specialist


def handle(general: GeneralAgent, llm, cv, title, description, focus="", **hints):
    return asyncio.run(general.handle(CareerCase(cv, title, description, focus, **hints), llm))


def general_with(*specialists) -> GeneralAgent:
    return GeneralAgent(AgentRegistry(specialists))


# ---- the IT specialist behaves exactly as before, reached through the General agent

def test_an_it_posting_gets_the_same_answer_as_the_plain_it_coach_plus_provenance():
    old = asyncio.run(ITCareerCoach(RecordingLLM(ai_output())).analyze(CV, JOB_TITLE, JOB_DESCRIPTION, "AI"))
    llm = RecordingLLM(ai_output())
    outcome = handle(build_default_general_agent(), llm, CV, JOB_TITLE, JOB_DESCRIPTION, "AI")
    new = outcome.response().model_dump()

    meta = new.pop("meta")
    assert new == old.model_dump()  # every legacy field identical
    assert len(llm.calls) == 1 and llm.calls[0][0] == COACH_SYSTEM_PROMPT
    assert (meta["routing"]["primary"], meta["routing"]["method"]) == ("it", "rules")
    assert [(r["agent_id"], r["status"]) for r in meta["runs"]] == [("it", "ok")]
    assert set(meta["provenance"].values()) == {"it"}
    assert set(meta["provenance"]) == {"summary", "promote:exp1.b4", "promote:exp1.b2", "ask:kubernetes"}


def test_the_choice_flow_still_costs_one_call_through_the_general_agent():
    llm = RecordingLLM(tracks_output())
    response = handle(build_default_general_agent(), llm, CV, JOB_TITLE, JOB_DESCRIPTION).response()
    assert response.kind == "choose_focus" and len(llm.calls) == 1
    assert set(response.meta.provenance.values()) == {"it"} and "ai" in response.meta.provenance


# ---- other occupations: the General agent analyses them itself, through the same engine

def test_a_nurse_posting_is_answered_by_the_general_agent_with_its_own_prompt():
    llm = RecordingLLM(nurse_output())
    outcome = handle(build_default_general_agent(), llm, NURSE_CV, NURSE_JOB_TITLE, NURSE_JOB_DESCRIPTION)

    assert llm.calls[0][0] == GENERAL_SYSTEM_PROMPT != COACH_SYSTEM_PROMPT
    assert outcome.routing.primary == "general" and outcome.routing.method == "fallback"
    assert [s.id for s in outcome.result.suggestions] == ["summary", "promote:exp1.b2"]
    assert set(outcome.provenance.values()) == {"general"}


def test_a_manual_override_sends_the_posting_to_the_named_agent():
    llm = RecordingLLM(ai_output())
    outcome = handle(build_default_general_agent(), llm, CV, JOB_TITLE, JOB_DESCRIPTION, "AI", domain_override="general")
    assert outcome.routing.method == "override" and llm.calls[0][0] == GENERAL_SYSTEM_PROMPT


def test_an_unknown_override_is_refused_before_any_model_call():
    llm = RecordingLLM(ai_output())
    with pytest.raises(UnknownDomainError):
        handle(build_default_general_agent(), llm, CV, JOB_TITLE, JOB_DESCRIPTION, domain_override="plumbing")
    assert llm.calls == []


def test_the_cv_does_not_change_the_routing():
    general = build_default_general_agent()
    a = handle(general, RecordingLLM(marketing_output()), MARKETING_CV, MARKETING_JOB_TITLE, MARKETING_JOB_DESCRIPTION)
    b = handle(general, RecordingLLM(marketing_output()), NURSE_CV, MARKETING_JOB_TITLE, MARKETING_JOB_DESCRIPTION)
    assert a.routing == b.routing


# ---- failures

class Failing:
    def __init__(self, error: Exception):
        self.error, self.calls = error, 0

    async def generate(self, **_):
        self.calls += 1
        raise self.error


def test_a_model_failure_is_not_retried_with_another_agent_and_keeps_its_error_type():
    llm = Failing(LLMTimeoutError("slow"))
    with pytest.raises(LLMTimeoutError):
        handle(build_default_general_agent(), llm, CV, JOB_TITLE, JOB_DESCRIPTION)
    assert llm.calls == 1


def test_a_specialist_that_breaks_is_replaced_by_the_general_agent_and_the_run_says_so():
    general = general_with(Broken("it", "Information technology", "developer"))
    llm = RecordingLLM(ai_output())
    outcome = handle(general, llm, CV, "Backend Developer", JOB_DESCRIPTION, "AI")

    assert [(r.agent_id, r.status, r.error_code) for r in outcome.runs] == [
        ("it", "failed", "agent_error"), ("general", "ok", "")]
    assert outcome.routing.primary == "general" and outcome.routing.method == "fallback"
    assert "agent_failed:it" in outcome.routing.reasons
    assert set(outcome.provenance.values()) == {"general"}
    assert llm.calls[0][0] == GENERAL_SYSTEM_PROMPT  # the replacement ran on the shared engine, with its own prompt
    assert "bug in the agent" not in outcome.response().model_dump_json()  # never exception text


def test_when_every_agent_fails_the_general_agent_says_so():
    general = general_with(Broken("it", "IT", "developer"))
    llm = Failing(RuntimeError("bug in the general analysis"))  # not a model error: the agent's own failure
    with pytest.raises(OrchestrationError):
        handle(general, llm, CV, "Backend Developer", JOB_DESCRIPTION)
    assert llm.calls == 1  # the broken specialist never reached the model; the general agent asked once


def test_a_failing_general_analysis_is_not_asked_twice():
    llm = Failing(RuntimeError("bug"))
    with pytest.raises(OrchestrationError):
        handle(build_default_general_agent(), llm, CV, "Chef", "Cook.")
    assert llm.calls == 1


# ---- a new specialist needs no change to the General agent, the router or the engine

def test_a_newly_registered_specialist_runs_on_the_real_engine_with_its_own_prompt_input_and_gate():
    reject_promotes = Gate("legal_rule", lambda ctx, p: True, frozenset({"promote"}))
    legal = specialist("legal", "Legal", "lawyer", prompt="You are the legal test coach.", gates=(reject_promotes,))
    registry = build_default_registry()
    registry.register(legal)

    quote = "Review supplier contracts"
    posting = f"Corporate Lawyer\n\nWhat you will do\n- {quote}\n"
    output = CoachModelOutput(mode="suggestions", suggestions=[
        ModelSuggestion(kind="promote", requirement_quote=quote, level="required", source_ids=["exp1.b4"],
                        support="related", priority=1, rationale="r")])
    llm = RecordingLLM(output)
    outcome = handle(GeneralAgent(registry), llm, CV, "Corporate Lawyer", posting, "Contracts")

    system_prompt, user_content = llm.calls[0]
    assert outcome.routing.primary == "legal" and outcome.routing.method == "rules"
    assert system_prompt == "You are the legal test coach."
    assert list(user_content) == ["title", "posting", "focus", "bullets"]  # the toy specialist's own projection
    assert outcome.result.suggestions == [] and outcome.result.dropped_reasons == {"legal_rule": 1}
    assert [r.agent_id for r in outcome.runs] == ["legal"]
