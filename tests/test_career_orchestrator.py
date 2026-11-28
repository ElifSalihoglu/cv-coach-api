"""CareerOrchestrator with a fake model: routing, delegation, provenance, failure handling, IT behaviour kept."""

import asyncio

import pytest

from app.careers.agents.general import GENERAL_AGENT
from app.careers.agents.general.prompt import GENERAL_SYSTEM_PROMPT
from app.careers.agents.it import IT_AGENT
from app.careers.agents.it.prompt import IT_SYSTEM_PROMPT
from app.careers.assembly import build_default_registry, build_orchestrator
from app.careers.budget import BudgetExceeded
from app.careers.core.gates import Gate
from app.careers.core.state import CareerCase, OrchestrationError
from app.careers.orchestrator import CareerOrchestrator
from app.careers.registry import AgentRegistry, UnknownDomainError
from app.models.coaching import CoachModelOutput, ModelSuggestion
from app.services.llm_client import LLMTimeoutError
from tests.fixtures.coach_fixture import CV, JOB_DESCRIPTION, JOB_TITLE
from tests.fixtures.coach_scenarios import ai_output, tracks_output
from tests.fixtures.fake_tools import ChoosesTool
from tests.fixtures.general_fixtures import (
    MARKETING_CV,
    MARKETING_JOB_DESCRIPTION,
    MARKETING_JOB_TITLE,
    NURSE_CV,
    NURSE_JOB_DESCRIPTION,
    NURSE_JOB_TITLE,
)
from tests.fixtures.general_scenarios import marketing_output, nurse_output
from tests.test_coach_regression import RecordingLLM
from tests.toy_agents import broken_agent, career_agent


def run(orchestrator, cv, title, description, focus="", **hints):
    return asyncio.run(orchestrator.run(CareerCase(cv, title, description, focus, **hints)))


def orchestrator_with(llm, *specialists) -> CareerOrchestrator:
    return CareerOrchestrator(AgentRegistry(specialists), GENERAL_AGENT, llm)


# ---- the IT specialist behaves exactly as when it was called directly


def test_an_it_posting_gets_the_same_answer_as_the_it_agent_plus_provenance():
    direct = asyncio.run(
        IT_AGENT.analyze(CareerCase(CV, JOB_TITLE, JOB_DESCRIPTION, "AI"), RecordingLLM(ai_output(), tool="ask_it"))
    )
    llm = RecordingLLM(ai_output(), tool="ask_it")
    outcome = run(build_orchestrator(llm), CV, JOB_TITLE, JOB_DESCRIPTION, "AI")
    new = outcome.response().model_dump()

    meta = new.pop("meta")
    assert new == direct.model_dump()  # every field except `meta` is identical
    assert len(llm.calls) == 1 and llm.calls[0][0] == IT_SYSTEM_PROMPT
    assert (meta["routing"]["primary"], meta["routing"]["method"]) == ("it", "delegation")
    assert [(r["agent_id"], r["status"]) for r in meta["runs"]] == [("it", "ok")]
    assert set(meta["provenance"].values()) == {"it"}
    assert set(meta["provenance"]) == {"summary", "promote:exp1.b4", "promote:exp1.b2", "ask:kubernetes"}


def test_the_choice_flow_still_costs_one_call_through_the_orchestrator():
    llm = RecordingLLM(tracks_output(), tool="ask_it")
    response = run(build_orchestrator(llm), CV, JOB_TITLE, JOB_DESCRIPTION).response()
    assert response.kind == "choose_focus" and len(llm.calls) == 1
    assert set(response.meta.provenance.values()) == {"it"} and "ai" in response.meta.provenance


# ---- other occupations: the general agent analyses them, on the same engine


def test_a_nurse_posting_is_answered_by_the_general_agent_with_its_own_prompt():
    llm = RecordingLLM(nurse_output())
    outcome = run(build_orchestrator(llm), NURSE_CV, NURSE_JOB_TITLE, NURSE_JOB_DESCRIPTION)

    assert llm.calls[0][0] == GENERAL_SYSTEM_PROMPT != IT_SYSTEM_PROMPT
    assert outcome.routing.primary == "general" and outcome.routing.method == "fallback"
    assert [s.id for s in outcome.result.suggestions] == ["summary", "promote:exp1.b2"]
    assert set(outcome.provenance.values()) == {"general"}


def test_a_manual_override_sends_the_posting_to_the_named_agent():
    llm = RecordingLLM(ai_output(), tool="ask_it")
    outcome = run(build_orchestrator(llm), CV, JOB_TITLE, JOB_DESCRIPTION, "AI", domain_override="general")
    assert outcome.routing.method == "override" and llm.calls[0][0] == GENERAL_SYSTEM_PROMPT


def test_an_unknown_override_is_refused_before_any_model_call():
    llm = RecordingLLM(ai_output(), tool="ask_it")
    with pytest.raises(UnknownDomainError):
        run(build_orchestrator(llm), CV, JOB_TITLE, JOB_DESCRIPTION, domain_override="plumbing")
    assert llm.calls == []


def test_the_cv_does_not_change_the_routing():
    orchestrator = build_orchestrator(RecordingLLM(marketing_output()))
    a = run(orchestrator, MARKETING_CV, MARKETING_JOB_TITLE, MARKETING_JOB_DESCRIPTION)
    b = run(orchestrator, NURSE_CV, MARKETING_JOB_TITLE, MARKETING_JOB_DESCRIPTION)
    assert a.routing == b.routing


# ---- failures


class Failing(ChoosesTool):
    def __init__(self, error: Exception, tool: str | None = None):
        self.error, self.calls, self.tool = error, 0, tool

    async def generate(self, **_):
        self.calls += 1
        raise self.error


def test_a_model_failure_is_not_retried_with_another_agent_and_keeps_its_error_type():
    llm = Failing(LLMTimeoutError("slow"), tool="ask_it")
    with pytest.raises(LLMTimeoutError):
        run(build_orchestrator(llm), CV, JOB_TITLE, JOB_DESCRIPTION)
    assert llm.calls == 1


def test_a_specialist_that_breaks_is_replaced_by_the_general_agent_and_the_run_says_so():
    llm = RecordingLLM(ai_output(), tool="ask_it")
    orchestrator = orchestrator_with(llm, broken_agent("it", "Information technology", "developer"))
    outcome = run(orchestrator, CV, "Backend Developer", JOB_DESCRIPTION, "AI")

    assert [(r.agent_id, r.status, r.error_code) for r in outcome.runs] == [
        ("it", "failed", "agent_error"),
        ("general", "ok", ""),
    ]
    assert outcome.routing.primary == "general" and outcome.routing.method == "fallback"
    assert "agent_failed:it" in outcome.routing.reasons
    assert set(outcome.provenance.values()) == {"general"}
    assert llm.calls[0][0] == GENERAL_SYSTEM_PROMPT  # the replacement ran on the shared engine, with its own prompt
    assert "bug in the agent" not in outcome.response().model_dump_json()  # never exception text


def test_when_every_agent_fails_the_orchestrator_says_so():
    # not a model error: the agent's own failure
    llm = Failing(RuntimeError("bug in the general analysis"), tool="ask_it")
    orchestrator = orchestrator_with(llm, broken_agent("it", "IT", "developer"))
    with pytest.raises(OrchestrationError):
        run(orchestrator, CV, "Backend Developer", JOB_DESCRIPTION)
    assert llm.calls == 1  # the broken specialist never reached the model; the general agent asked once


def test_a_failing_general_analysis_is_not_asked_twice():
    llm = Failing(RuntimeError("bug"))
    with pytest.raises(OrchestrationError):
        run(build_orchestrator(llm), CV, "Chef", "Cook.")
    assert llm.calls == 1


# ---- a new specialist needs no change to the orchestrator, the router or the engine


def test_a_newly_registered_specialist_runs_on_the_real_engine_with_its_own_prompt_input_and_gate():
    reject_promotes = Gate("legal_rule", lambda ctx, p: True, frozenset({"promote"}))
    legal = career_agent("legal", "Legal", "lawyer", prompt="You are the legal test coach.", gates=(reject_promotes,))
    registry = build_default_registry()
    registry.register(legal)

    quote = "Review supplier contracts"
    posting = f"Corporate Lawyer\n\nWhat you will do\n- {quote}\n"
    output = CoachModelOutput(
        mode="suggestions",
        suggestions=[
            ModelSuggestion(
                kind="promote",
                requirement_quote=quote,
                level="required",
                source_ids=["exp1.b4"],
                support="related",
                priority=1,
                rationale="r",
            )
        ],
    )
    llm = RecordingLLM(output, tool="ask_legal")
    outcome = run(CareerOrchestrator(registry, GENERAL_AGENT, llm), CV, "Corporate Lawyer", posting, "Contracts")

    system_prompt, user_content = llm.calls[0]
    assert outcome.routing.primary == "legal" and outcome.routing.method == "delegation"
    assert system_prompt == "You are the legal test coach."
    assert list(user_content) == ["title", "posting", "focus", "bullets"]  # the toy agent's own projection
    assert outcome.result.suggestions == [] and outcome.result.dropped_reasons == {"legal_rule": 1}
    assert [r.agent_id for r in outcome.runs] == ["legal"]


# ---- hierarchical delegation: the General agent calls a specialist as a tool and gets the result back


def test_the_general_agent_is_offered_one_tool_per_specialist_built_from_its_card_and_never_sees_the_cv():
    llm = RecordingLLM(ai_output(), tool="ask_it")
    run(build_orchestrator(llm), CV, JOB_TITLE, JOB_DESCRIPTION, "AI")

    prompt, payload, tools = llm.tool_calls[0]
    assert [t.name for t in tools] == ["ask_it", "ask_healthcare", "ask_hr", "ask_finance"]
    assert IT_AGENT.card.description in tools[0].description and "Information technology" in tools[0].description
    assert set(payload) == {"job_title", "career_goal", "job_description"}  # the posting only: no CV, no name
    assert "Lumen" not in str(payload) and CV.name not in str(payload)


def test_a_specialists_result_comes_back_as_a_tool_message_and_is_then_returned_unchanged():
    llm = RecordingLLM(ai_output(), tool="ask_it")
    outcome = run(build_orchestrator(llm), CV, JOB_TITLE, JOB_DESCRIPTION, "AI")

    # decision 1 calls the IT agent; decision 2 sees its result, offers the other three, and finishes
    assert len(llm.tool_calls) == 2 and len(llm.calls) == 1
    assert [t.name for t in llm.tool_calls[1][2]] == ["ask_healthcare", "ask_hr", "ask_finance"]
    (seen,) = llm.tool_steps[1]
    assert seen.name == "ask_it" and '"agent": "it"' in seen.result and '"status": "ok"' in seen.result
    assert outcome.routing.method == "delegation" and outcome.routing.reasons == ("delegated:it",)
    assert outcome.result.suggestions and set(outcome.provenance.values()) == {"it"}


def test_the_general_agent_keeps_a_posting_no_specialist_claims():
    llm = RecordingLLM(nurse_output(), tool=None)
    outcome = run(build_orchestrator(llm), NURSE_CV, NURSE_JOB_TITLE, NURSE_JOB_DESCRIPTION)

    assert outcome.routing.primary == "general" and outcome.routing.reasons == ("no_clear_match",)
    assert llm.calls[0][0] == GENERAL_SYSTEM_PROMPT and set(outcome.provenance.values()) == {"general"}


def test_a_tool_the_model_invents_is_ignored_and_the_general_agent_answers():
    llm = RecordingLLM(nurse_output(), tool="ask_plumbing")
    outcome = run(build_orchestrator(llm), NURSE_CV, NURSE_JOB_TITLE, NURSE_JOB_DESCRIPTION)
    assert outcome.routing.primary == "general" and outcome.routing.method == "fallback"


def test_an_override_skips_the_delegation_decision_and_costs_no_extra_call():
    llm = RecordingLLM(ai_output(), tool="ask_it")
    outcome = run(build_orchestrator(llm), CV, JOB_TITLE, JOB_DESCRIPTION, "AI", domain_override="it")
    assert outcome.routing.method == "override" and "tool_calls" not in llm.__dict__
    assert len(llm.calls) == 1


def test_a_new_specialist_is_offered_as_a_tool_with_no_change_to_the_general_agent():
    llm = RecordingLLM(ai_output(), tool=None)
    registry = build_default_registry()
    registry.register(career_agent("legal", "Legal", "lawyer", "legal counsel"))
    run(CareerOrchestrator(registry, GENERAL_AGENT, llm), CV, "Lawyer", "Contracts.")

    _, _, tools = llm.tool_calls[0]
    assert [t.name for t in tools][-1] == "ask_legal" and len(tools) == 5
    assert "lawyer" in tools[-1].description


def test_a_broken_specialist_after_delegation_falls_back_to_the_general_agent_within_the_budget():
    llm = RecordingLLM(ai_output(), tool="ask_it")
    orchestrator = orchestrator_with(llm, broken_agent("it", "Information technology", "developer"))
    outcome = run(orchestrator, CV, "Backend Developer", JOB_DESCRIPTION, "AI")

    assert outcome.routing.method == "fallback" and "agent_failed:it" in outcome.routing.reasons
    # no specialist is left to offer after it failed, so the loop ends: 1 decision + the General agent's call
    assert len(llm.tool_calls) == 1 and len(llm.calls) == 1


class Endless(ChoosesTool):
    """A model that keeps asking for another analysis: the choice flow when the posting offers no choice."""

    tool = "ask_it"

    def __init__(self):
        self.calls = 0

    async def generate(self, **_):
        self.calls += 1
        return tracks_output()


def test_the_model_call_budget_stops_a_request_before_the_call_that_would_exceed_it():
    llm = Endless()
    orchestrator = CareerOrchestrator(build_default_registry(), GENERAL_AGENT, llm, max_model_calls=2)
    with pytest.raises(BudgetExceeded):
        run(orchestrator, CV, JOB_TITLE, "Backend Developer\n\nWhat you will do\n- Write code\n")
    assert len(llm.__dict__["tool_calls"]) + llm.calls == 2  # the third call was refused, not made
