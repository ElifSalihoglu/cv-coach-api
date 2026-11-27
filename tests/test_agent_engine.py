"""
AgentEngine: stateless, domain-agnostic, shared by every agent. Fake model only.

Also the architecture boundaries that make "a new domain needs no engine, General-agent or router
change" true: who may import whom, and that nothing leaks between concurrent requests.
"""

import asyncio
import copy
import re
from pathlib import Path

import pytest

from app.careers.agents.general import GENERAL_AGENT, GENERAL_PROFILE
from app.careers.agents.it import IT_AGENT, IT_PROFILE
from app.careers.assembly import build_default_registry
from app.careers.core.engine import DEFAULT_ENGINE, AgentEngine
from app.careers.core.gates import Gate
from app.careers.core.state import CareerCase
from app.careers.orchestrator import CareerOrchestrator
from app.models.coaching import CoachModelOutput, ModelSuggestion
from app.models.cv_document import CVBullet, CVExperience, StructuredCV
from app.services.llm_client import LLMOutputError, LLMTimeoutError
from tests.fixtures.coach_fixture import CV, JOB_DESCRIPTION, JOB_TITLE
from tests.fixtures.coach_scenarios import ai_output, tracks_output
from tests.test_coach_regression import RecordingLLM
from tests.toy_agents import career_agent

ROOT = Path(__file__).resolve().parents[1] / "app"
CORE = ROOT / "careers" / "core"


def run(profile, llm, focus="AI", engine=DEFAULT_ENGINE):
    return asyncio.run(engine.run(profile, CareerCase(CV, JOB_TITLE, JOB_DESCRIPTION, focus), llm))


# ---- what the engine does, in order


def test_the_engine_sends_the_profiles_prompt_and_input_and_returns_the_checked_result():
    llm = RecordingLLM(ai_output())
    result = run(IT_PROFILE, llm)

    ((system_prompt, user_content),) = llm.calls
    assert system_prompt == IT_PROFILE.system_prompt
    assert user_content == IT_PROFILE.build_input(CV, JOB_TITLE, JOB_DESCRIPTION, "AI")
    assert [s.id for s in result.suggestions] == ["summary", "promote:exp1.b4", "promote:exp1.b2"]


def test_the_engine_asks_again_only_when_the_profile_says_the_posting_offers_no_choice():
    llm = RecordingLLM(tracks_output(), ai_output())
    never_a_choice = career_agent("x", "X")  # its offers_choice is always False
    result = asyncio.run(DEFAULT_ENGINE.run(never_a_choice.profile, CareerCase(CV, JOB_TITLE, JOB_DESCRIPTION), llm))
    assert len(llm.calls) == 2 and result.kind == "suggestions"
    assert llm.calls[1][1]["focus"] == JOB_TITLE  # asked again, for the posting's one focus

    llm = RecordingLLM(tracks_output(), ai_output())
    assert run(IT_PROFILE, llm, focus="").kind == "choose_focus" and len(llm.calls) == 1  # a real choice


def test_model_errors_reach_the_caller_unchanged():
    class Failing:
        def __init__(self, error):
            self.error = error

        async def generate(self, **_):
            raise self.error

    for error in (LLMTimeoutError("slow"), LLMOutputError("bad", "llm_invalid_output")):
        with pytest.raises(type(error)):
            run(IT_PROFILE, Failing(error))


def test_domain_rules_enter_only_through_the_profile_and_run_after_the_shared_gates():
    never = Gate("profile_rule", lambda ctx, p: True, frozenset({"promote"}))
    with_rule = career_agent("x", "X", gates=(never,)).profile
    output = CoachModelOutput(
        suggestions=[
            ModelSuggestion(
                kind="promote",
                requirement_quote="ship LLM features to production and keep agents and tools reliable",
                level="required",
                source_ids=["exp1.b4"],
                support="related",
                priority=1,
                rationale="r",
            )
        ]
    )

    kept = DEFAULT_ENGINE.build_result(career_agent("y", "Y").profile, CV, JOB_DESCRIPTION, output, "AI")
    refused = DEFAULT_ENGINE.build_result(with_rule, CV, JOB_DESCRIPTION, output, "AI")
    assert [s.id for s in kept.suggestions] == ["promote:exp1.b4"]
    assert refused.dropped_reasons == {"profile_rule": 1}


# ---- one engine for everybody, holding nothing


def test_every_agent_runs_on_the_same_stateless_engine():
    assert vars(DEFAULT_ENGINE) == {} and vars(AgentEngine()) == {}  # nothing is kept between requests
    assert IT_AGENT._engine is DEFAULT_ENGINE
    assert GENERAL_AGENT._engine is DEFAULT_ENGINE
    assert career_agent("x", "X")._engine is DEFAULT_ENGINE


def test_the_engine_source_names_no_field_of_work_and_imports_no_agent():
    text = (CORE / "engine.py").read_text(encoding="utf-8").lower()
    assert "careers.agents" not in text
    for word in ("kubernetes", "python", "nurse", "software", "engineer", "licen", "design", "api "):
        assert word not in text, word
    for path in CORE.glob("*.py"):
        assert "careers.agents" not in path.read_text(encoding="utf-8"), path.name


def test_only_the_assembly_imports_the_it_agent():
    allowed = {"careers/assembly.py"}
    importers = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*.py")
        if "careers.agents.it" in path.read_text(encoding="utf-8")
        and not path.relative_to(ROOT).as_posix().startswith("careers/agents/it/")
    }
    assert importers == allowed


def test_the_orchestrator_router_and_registry_name_no_concrete_domain():
    for name in ("careers/orchestrator.py", "careers/router.py", "careers/registry.py"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "agents.it" not in text and "IT_" not in text, name


# ---- concurrent requests share the engine and must not share anything else


def _cv(n: int) -> StructuredCV:
    return StructuredCV(
        name=f"Person{n}",
        email=f"person{n}@example.com",
        summary=f"Professional number {n}.",
        experiences=[
            CVExperience(
                id="exp1",
                title="Role",
                employer=f"Firm{n}",
                bullets=[CVBullet(id=f"exp1.b{i}", text=f"Did task {i} marker{n} for the team.") for i in range(1, 4)],
            )
        ],
    )


class EchoLLM:
    """One shared model client: answers each request from the payload it was given, yielding between steps."""

    def __init__(self):
        self.seen: list[dict] = []

    async def generate(self, system_prompt, user_content, output_model=None):
        self.seen.append(user_content)
        await asyncio.sleep(0)  # let the other requests run in between
        posting = user_content.get("job_description") or user_content.get("posting")
        quote = [line[2:] for line in posting.splitlines() if line.startswith("- ")][0]
        await asyncio.sleep(0)
        return CoachModelOutput(
            suggestions=[
                ModelSuggestion(
                    kind="promote",
                    requirement_quote=quote,
                    level="required",
                    source_ids=["exp1.b2"],
                    support="related",
                    priority=1,
                    rationale=f"echo {system_prompt[:20]}",
                )
            ]
        )


def test_many_concurrent_requests_through_one_orchestrator_never_see_each_others_data():
    registry = build_default_registry()
    registry.register(career_agent("legal", "Legal", "lawyer"))
    llm = EchoLLM()
    orchestrator = CareerOrchestrator(registry, GENERAL_AGENT, llm)
    titles = ["Backend Developer", "Chef", "Corporate Lawyer"]  # it, general, legal
    before = (copy.deepcopy(IT_PROFILE.limits), copy.deepcopy(GENERAL_PROFILE.limits))

    def case(n: int) -> CareerCase:
        posting = f"{titles[n % 3]}\n\nWhat you will do\n- Handle token{n} duties\n"
        return CareerCase(_cv(n), titles[n % 3], posting, "")

    async def main():
        return await asyncio.gather(*(orchestrator.run(case(n)) for n in range(60)))

    outcomes = asyncio.run(main())

    assert len(llm.seen) == 60
    for n, outcome in enumerate(outcomes):
        assert outcome.routing.primary == ["it", "general", "legal"][n % 3]
        (suggestion,) = outcome.result.suggestions
        assert suggestion.requirement == f"Handle token{n} duties"  # its own posting
        assert suggestion.sources[0].text == f"Did task 2 marker{n} for the team."  # its own CV
    for payload in llm.seen:  # what went to the model carries one request's data only
        text = str(payload)
        numbers = set(re.findall(r"marker(\d+)", text)) | set(re.findall(r"token(\d+)", text))
        assert len(numbers) == 1, numbers
        assert "example.com" not in text and "Person" not in text  # no identifiers in any projection
    assert (IT_PROFILE.limits, GENERAL_PROFILE.limits) == before  # shared profiles were not mutated
    assert vars(DEFAULT_ENGINE) == {}
