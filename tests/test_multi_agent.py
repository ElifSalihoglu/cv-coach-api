"""
The General agent's bounded loop with a fake model: no specialist, one, several; the step and call
budgets; the deterministic merge. Every specialist runs on the real engine with its real profile.
"""

import asyncio

import pytest

from app.careers.agents.finance import FINANCE_AGENT
from app.careers.agents.general import GENERAL_AGENT
from app.careers.agents.healthcare import HEALTHCARE_AGENT
from app.careers.agents.hr import HR_AGENT
from app.careers.agents.it import IT_AGENT
from app.careers.assembly import build_default_registry
from app.careers.budget import BudgetExceeded
from app.careers.core.engine import DEFAULT_ENGINE
from app.careers.core.state import CareerCase
from app.careers.orchestrator import CareerOrchestrator
from app.models.coaching import CoachModelOutput, CoachResult, ModelTrack, Suggestion
from app.services.llm_client import LLMTimeoutError
from tests.fixtures.fake_tools import ChoosesTool
from tests.fixtures.multi_domain import AI_HEALTH, CV, FINTECH, HR_ANALYTICS, answer, promote
from tests.toy_agents import broken_agent

Q_MODELS = "Build machine learning models that support clinical teams"
Q_AWS = "Deploy Python services on AWS"
Q_FLOW = "Report on patient flow to ward managers"
Q_DASH = "Build workforce analytics dashboards for the HR team"
Q_RECON = "Build payment reconciliation services in Python"


class ByAgentLLM(ChoosesTool):
    """Answers each analysis from the prompt of the agent that asks; `tool` scripts the General agent."""

    def __init__(self, outputs: dict[str, CoachModelOutput], tool):
        self.outputs, self.tool, self.calls = outputs, tool, []

    async def generate(self, system_prompt, user_content, output_model=None):
        self.calls.append(system_prompt)
        return self.outputs[system_prompt]

    @property
    def model_calls(self) -> int:
        return len(self.calls) + len(self.__dict__.get("tool_calls", []))


def run(llm, posting, **options):
    orchestrator = CareerOrchestrator(build_default_registry(), GENERAL_AGENT, llm, **options)
    return asyncio.run(orchestrator.run(CareerCase(CV, posting[0], posting[1])))


IT_PROMPT, HC_PROMPT = IT_AGENT.profile.system_prompt, HEALTHCARE_AGENT.profile.system_prompt
HR_PROMPT, FIN_PROMPT = HR_AGENT.profile.system_prompt, FINANCE_AGENT.profile.system_prompt


# ---- one specialist


def test_one_specialist_a_fintech_posting_goes_to_it_and_its_result_is_returned_as_it_is():
    llm = ByAgentLLM({IT_PROMPT: answer(promote(Q_RECON, "exp1.b4", 1))}, tool=["ask_it", None])
    outcome = run(llm, FINTECH)

    direct = asyncio.run(
        IT_AGENT.analyze(
            CareerCase(CV, *FINTECH), ByAgentLLM({IT_PROMPT: answer(promote(Q_RECON, "exp1.b4", 1))}, None)
        )
    )
    assert outcome.result == direct  # the same validated result, not rewritten
    assert outcome.routing.primary == "it" and outcome.routing.reasons == ("delegated:it",)
    assert [(r.agent_id, r.status) for r in outcome.runs] == [("it", "ok")]
    assert set(outcome.provenance.values()) == {"it"}
    assert llm.model_calls == 3  # decision, the IT agent's call, the decision that ends the loop


# ---- no specialist: the General agent answers itself


def test_directly_the_general_agent_answers_when_it_calls_no_tool():
    general = GENERAL_AGENT.profile.system_prompt
    llm = ByAgentLLM({general: answer(promote(Q_AWS, "exp1.b5", 1))}, tool=None)
    outcome = run(llm, AI_HEALTH)

    assert outcome.routing.primary == "general" and outcome.routing.reasons == ("no_clear_match",)
    assert llm.calls == [general] and llm.model_calls == 2
    assert set(outcome.provenance.values()) == {"general"}


# ---- several specialists: called in turn, merged by code


def test_several_specialists_ai_in_healthcare_calls_it_then_healthcare_and_merges_their_results():
    llm = ByAgentLLM(
        {
            IT_PROMPT: answer(promote(Q_AWS, "exp1.b5", 1), promote(Q_MODELS, "exp1.b2", 2)),
            HC_PROMPT: answer(promote(Q_MODELS, "exp1.b2", 1), promote(Q_FLOW, "exp1.b3", 2)),
        },
        tool=["ask_it", "ask_healthcare"],
    )
    outcome = run(llm, AI_HEALTH)

    assert [(r.agent_id, r.status) for r in outcome.runs] == [("it", "ok"), ("healthcare", "ok")]
    assert outcome.routing.primary == "general" and outcome.routing.method == "delegation"
    assert outcome.routing.reasons == ("delegated:it", "delegated:healthcare")
    # the second decision saw the IT result as a tool message and offered the others, not IT again
    assert [t.name for t in llm.tool_calls[1][2]] == ["ask_healthcare", "ask_hr", "ask_finance"]
    assert llm.tool_steps[1][0].name == "ask_it" and '"suggestions": 2' in llm.tool_steps[1][0].result

    ids = [s.id for s in outcome.result.suggestions]
    assert ids == ["promote:exp1.b5", "promote:exp1.b2", "promote:exp1.b3"]  # a duplicate is kept once
    # first agent keeps what both produced; each other item belongs to the agent that made it
    assert outcome.provenance == {
        "promote:exp1.b5": "it",
        "promote:exp1.b2": "it",
        "promote:exp1.b3": "healthcare",
    }
    assert outcome.result.dropped_reasons.get("over_limit_or_duplicate") == 1
    assert llm.calls == [IT_PROMPT, HC_PROMPT] and llm.model_calls == 4  # 2 decisions + 2 analyses


def test_several_specialists_hr_analytics_calls_hr_then_it():
    llm = ByAgentLLM(
        {
            HR_PROMPT: answer(promote(Q_DASH, "exp1.b3", 1)),
            IT_PROMPT: answer(promote("Write Python and SQL for people data", "exp1.b3", 1)),
        },
        tool=["ask_hr", "ask_it"],
    )
    outcome = run(llm, HR_ANALYTICS)
    assert [r.agent_id for r in outcome.runs] == ["hr", "it"]
    assert [s.id for s in outcome.result.suggestions] == ["promote:exp1.b3"]
    assert outcome.provenance == {"promote:exp1.b3": "hr"}


# ---- the budgets


def test_at_most_two_specialists_are_called_and_the_third_is_never_asked_for():
    llm = ByAgentLLM(
        {IT_PROMPT: answer(promote(Q_RECON, "exp1.b4", 1)), HR_PROMPT: answer(), FIN_PROMPT: answer()},
        tool=["ask_it", "ask_hr", "ask_finance"],
    )
    outcome = run(llm, FINTECH)
    assert [r.agent_id for r in outcome.runs] == ["it", "hr"]
    assert len(llm.tool_calls) == 2 and FIN_PROMPT not in llm.calls
    assert llm.model_calls <= 8


def test_a_specialist_is_never_called_twice_and_an_invented_tool_is_ignored():
    llm = ByAgentLLM({IT_PROMPT: answer(promote(Q_RECON, "exp1.b4", 1))}, tool=["ask_it", "ask_it"])
    assert [r.agent_id for r in run(llm, FINTECH).runs] == ["it"]
    llm = ByAgentLLM({IT_PROMPT: answer(promote(Q_RECON, "exp1.b4", 1))}, tool=["ask_it", "ask_plumbing"])
    assert [r.agent_id for r in run(llm, FINTECH).runs] == ["it"]


def test_the_call_budget_refuses_the_call_that_would_exceed_it():
    llm = ByAgentLLM(
        {IT_PROMPT: answer(promote(Q_AWS, "exp1.b5", 1)), HC_PROMPT: answer(promote(Q_FLOW, "exp1.b3", 1))},
        tool=["ask_it", "ask_healthcare"],
    )
    with pytest.raises(BudgetExceeded):
        run(llm, AI_HEALTH, max_model_calls=3)  # the fourth call, the healthcare analysis, is refused
    assert llm.model_calls == 3 and HC_PROMPT not in llm.calls


def test_a_specialist_limit_of_one_ends_the_loop_after_the_first_result():
    llm = ByAgentLLM({IT_PROMPT: answer(promote(Q_AWS, "exp1.b5", 1))}, tool=["ask_it", "ask_healthcare"])
    outcome = run(llm, AI_HEALTH, max_specialists=1)
    assert [r.agent_id for r in outcome.runs] == ["it"] and len(llm.tool_calls) == 1


# ---- failures inside the loop


def test_a_second_specialist_that_breaks_leaves_the_first_ones_result():
    registry = build_default_registry()
    registry._agents["healthcare"] = broken_agent("healthcare", "Healthcare", "nurse")  # a bug in its own code
    llm = ByAgentLLM({IT_PROMPT: answer(promote(Q_AWS, "exp1.b5", 1))}, tool=["ask_it", "ask_healthcare"])
    outcome = asyncio.run(CareerOrchestrator(registry, GENERAL_AGENT, llm).run(CareerCase(CV, *AI_HEALTH)))
    assert [(r.agent_id, r.status) for r in outcome.runs] == [("it", "ok"), ("healthcare", "failed")]
    assert [s.id for s in outcome.result.suggestions] == ["promote:exp1.b5"]
    assert '"status": "failed"' not in str(llm.tool_steps[1])  # it failed after the second decision, not before


def test_a_model_error_in_any_step_reaches_the_caller():
    class Slow(ByAgentLLM):
        async def generate(self, system_prompt, user_content, output_model=None):
            if system_prompt == HC_PROMPT:
                raise LLMTimeoutError("slow")
            return await super().generate(system_prompt, user_content, output_model)

    llm = Slow({IT_PROMPT: answer(promote(Q_AWS, "exp1.b5", 1))}, tool=["ask_it", "ask_healthcare"])
    with pytest.raises(LLMTimeoutError):
        run(llm, AI_HEALTH)


def test_a_result_that_asks_for_a_focus_ends_the_loop_and_is_returned_alone():
    tracks = [ModelTrack(name="AI", quote="AI track"), ModelTrack(name="Python", quote="Python track")]
    llm = ByAgentLLM({IT_PROMPT: CoachModelOutput(mode="choose_focus", tracks=tracks)}, tool=["ask_it", "ask_hr"])
    posting = ("Engineer", "Engineer\n\nPick one track\n- AI track\n- Python track\n")
    outcome = run(llm, posting)

    assert outcome.result.kind == "choose_focus" and [t.name for t in outcome.result.tracks] == ["AI", "Python"]
    assert [r.agent_id for r in outcome.runs] == ["it"] and len(llm.tool_calls) == 1  # nothing to combine yet


# ---- the deterministic merge validates again


def _result(*suggestions: Suggestion) -> CoachResult:
    return CoachResult(kind="suggestions", suggestions=list(suggestions))


def _suggestion(**over) -> Suggestion:
    base = dict(
        id="rewrite:exp1.b2",
        kind="rewrite",
        requirement=Q_MODELS,
        level="required",
        support="related",
        rationale="r",
        priority=1,
        sources=[{"id": "exp1.b2", "where": "ML Engineer", "text": CV.experiences[0].bullets[1].text}],
        before=CV.experiences[0].bullets[1].text,
        after="Built a model that flags patient-note backlogs for a hospital team and shares weekly summaries.",
    )
    return Suggestion(**{**base, **over})


def merge(*parts):
    return DEFAULT_ENGINE.merge(list(parts), CareerCase(CV, *AI_HEALTH), GENERAL_AGENT.profile)


def test_the_merge_drops_an_item_whose_evidence_no_longer_matches_the_cv():
    tampered = _suggestion(sources=[{"id": "exp1.b2", "where": "ML Engineer", "text": "Something the CV never said."}])
    merged, _ = merge(("it", IT_AGENT.profile, _result(tampered)), ("healthcare", HEALTHCARE_AGENT.profile, _result()))
    assert merged.suggestions == [] and merged.dropped_reasons == {"merge_evidence_lost": 1}


def test_the_merge_drops_a_quote_that_is_not_in_the_posting_and_applies_the_producers_gates():
    wrong_quote = _suggestion(requirement="Lead the hospital board")
    clinical = _suggestion(after="Built a model that flags patient-note backlogs and prescribed fixes for ward staff.")
    merged, provenance = merge(
        ("it", IT_AGENT.profile, _result(wrong_quote)), ("healthcare", HEALTHCARE_AGENT.profile, _result(clinical))
    )
    assert merged.suggestions == []
    assert merged.dropped_reasons == {"merge_evidence_lost": 1, "unsupported_clinical_act": 1} and provenance == {}


def test_the_merge_keeps_valid_items_within_the_general_agents_limits():
    parts = [
        ("it", IT_AGENT.profile, _result(_suggestion())),
        (
            "healthcare",
            HEALTHCARE_AGENT.profile,
            _result(
                _suggestion(
                    id="rewrite:exp1.b3",
                    sources=[{"id": "exp1.b3", "where": "ML Engineer", "text": CV.experiences[0].bullets[2].text}],
                    before=CV.experiences[0].bullets[2].text,
                    after="Built payroll analytics dashboards for the HR team in Python and SQL, used each month.",
                )
            ),
        ),
    ]
    merged, provenance = merge(*parts)
    assert [s.id for s in merged.suggestions] == ["rewrite:exp1.b2"]  # one rewrite at most
    assert provenance == {"rewrite:exp1.b2": "it"} and merged.dropped_reasons == {"over_limit_or_duplicate": 1}
