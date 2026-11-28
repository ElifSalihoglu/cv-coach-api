"""
Regression net for the IT agent: its prompt, model input, call count and validation behaviour.

It pins, with a fake model and no API call:
- the exact model input (hash of the payload; the full payload for one scenario),
- the exact system prompt (hash),
- how many model calls a scenario costs,
- the full CoachResult, including `dropped_reasons`, for scenarios built to hit every
  validation gate,
- the answers of the claim checks (`faithfulness_problems`, `unsupported_design_claims`,
  `offers_choice`, `skill_like_terms`).

The expected values live in tests/golden/coach_regression.json. If this test fails, behaviour
changed. Regenerate only for an intended change: `python -m tests.test_coach_regression --write`.
"""

import asyncio
import hashlib
import json
import sys
from pathlib import Path

from app.careers.agents.it import IT_AGENT
from app.careers.agents.it.rules import offers_choice, unsupported_design_claims
from app.careers.core.claims import cv_source_text, faithfulness_problems, skill_like_terms
from app.careers.core.state import CareerCase
from app.models.coaching import (
    CoachModelOutput,
    ModelEvidence,
    ModelQuestion,
    ModelRequirement,
    ModelSuggestion,
    ModelTrack,
)
from tests.fixtures.coach_fixture import (
    CLEAR_JOB_DESCRIPTION,
    CLEAR_JOB_TITLE,
    CV,
    JOB_DESCRIPTION,
    JOB_TITLE,
)
from tests.fixtures.coach_scenarios import (
    AI_SUMMARY,
    Q_AI,
    Q_API,
    Q_PREF_K8S,
    Q_PREF_PG,
    Q_PY,
    Q_REQ,
    ai_output,
    python_output,
    tracks_output,
)
from tests.fixtures.fake_tools import ChoosesTool

GOLDEN = Path(__file__).parent / "golden" / "coach_regression.json"


class RecordingLLM(ChoosesTool):
    """A fake model that records exactly what the coach sends."""

    def __init__(self, *outputs: CoachModelOutput, tool: str | None = None):
        self.tool = tool
        self.outputs = list(outputs)
        self.calls: list[tuple[str, dict]] = []

    async def generate(self, system_prompt, user_content, output_model=None):
        self.calls.append((system_prompt, user_content))
        return self.outputs.pop(0) if len(self.outputs) > 1 else self.outputs[0]


def _suggestions(*items: ModelSuggestion, questions=()) -> CoachModelOutput:
    return CoachModelOutput(mode="suggestions", focus="AI", suggestions=list(items), questions=list(questions))


def _s(**over) -> ModelSuggestion:
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


Q_CLEAR_WEBHOOKS = "Integrate third-party APIs and webhooks into internal tools"
Q_CLEAR_SHIP = "Experience shipping automation or LLM features to production"
Q_CLEAR_MONITOR = "Design workflows with queues, retries and monitoring"


def _clear_output() -> CoachModelOutput:
    """An answer for the one-focus posting (its quotes are really in that posting)."""
    return CoachModelOutput(
        mode="suggestions",
        focus="AI Automation",
        responsibilities=["Build agents that classify documents"],
        requirements=[ModelRequirement(text="Ship LLM features", quote=Q_CLEAR_SHIP, level="required")],
        suggestions=[
            _s(
                kind="promote",
                source_ids=["exp2.b4"],
                requirement_quote=Q_CLEAR_WEBHOOKS,
                priority=1,
                rationale="Related: integration work.",
            ),
            _s(
                kind="summary",
                source_ids=["exp1.b1"],
                requirement_quote=Q_CLEAR_SHIP,
                support="direct",
                after=AI_SUMMARY,
                priority=2,
                rationale="Leads with the production agent.",
            ),
        ],
        questions=[ModelQuestion(requirement_quote=Q_CLEAR_MONITOR, level="required", term="monitoring")],
    )


def _gate_scenarios() -> dict[str, tuple[CoachModelOutput, str]]:
    """Each model answer is built to hit one gate; the result pins what the gate does."""
    return {
        "quote_not_in_posting": (_suggestions(_s(requirement_quote="Kubernetes mastery is required")), "AI"),
        "source_not_in_cv": (_suggestions(_s(source_ids=["exp9.b1"])), "AI"),
        "generic_requirement": (_suggestions(_s(requirement_quote=Q_REQ)), "AI"),
        "already_first": (_suggestions(_s(source_ids=["exp1.b1"])), "AI"),
        "rewrite_not_substantive": (
            _suggestions(
                _s(
                    kind="rewrite",
                    source_ids=["exp2.b1"],
                    requirement_quote=Q_PY,
                    after=(
                        "Automated nightly ETL pipelines in Python and Airflow, "
                        "saving about 20 engineer-hours per week now."
                    ),
                )
            ),
            "Python",
        ),
        "rewrite_ok": (
            _suggestions(
                _s(
                    kind="rewrite",
                    source_ids=["exp2.b4"],
                    requirement_quote=Q_API,
                    after=(
                        "Integrated third-party APIs and webhooks into internal tools "
                        "used by the operations team every week."
                    ),
                )
            ),
            "Python",
        ),
        "rewrite_unsupported_claim": (
            _suggestions(
                _s(
                    kind="rewrite",
                    source_ids=["exp2.b4"],
                    requirement_quote=Q_API,
                    after="Integrated third-party APIs and webhooks on Kubernetes, cutting incidents by 40%.",
                )
            ),
            "Python",
        ),
        "summary_ok": (
            _suggestions(_s(kind="summary", source_ids=["exp1.b1"], support="direct", after=AI_SUMMARY)),
            "AI",
        ),
        "summary_same_as_cv": (_suggestions(_s(kind="summary", source_ids=["exp1.b1"], after=CV.summary)), "AI"),
        "summary_unsupported_claim": (
            _suggestions(
                _s(
                    kind="summary",
                    source_ids=["exp1.b1"],
                    after="Engineer who runs LLM agents on Kubernetes for 12,000 documents per month.",
                )
            ),
            "AI",
        ),
        "summary_unsupported_action": (
            _suggestions(
                _s(
                    kind="summary",
                    source_ids=["exp2.b4"],
                    requirement_quote=Q_API,
                    after="Engineer who designed REST APIs for partner webhooks and integrated third-party tools.",
                )
            ),
            "Python",
        ),
        "requirement_quote_not_in_posting": (
            CoachModelOutput(
                mode="suggestions",
                requirements=[
                    ModelRequirement(text="Rust", quote="Rust experience required", level="required"),
                    ModelRequirement(text="PostgreSQL", quote=Q_PREF_PG, level="preferred"),
                    ModelRequirement(text="", quote=Q_PREF_PG, level="preferred"),
                ],
                responsibilities=["a", " ", "b"],
            ),
            "AI",
        ),
        "unknown_kind": (_suggestions(_s(kind="delete")), "AI"),
        "over_limit_and_duplicates": (
            _suggestions(
                _s(source_ids=["exp1.b2"], priority=1),
                _s(source_ids=["exp1.b3"], priority=2),
                _s(source_ids=["exp1.b4"], priority=3),
                _s(source_ids=["exp1.b5"], priority=4),
                _s(source_ids=["exp1.b2"], priority=5),
                _s(kind="summary", source_ids=["exp1.b1"], support="direct", after=AI_SUMMARY, priority=6),
                _s(kind="summary", source_ids=["exp1.b1"], support="direct", after=AI_SUMMARY + " More.", priority=7),
            ),
            "AI",
        ),
        "direct_claim_without_support": (
            _suggestions(
                _s(
                    kind="promote",
                    source_ids=["exp2.b4"],
                    requirement_quote=Q_API,
                    support="direct",
                    rationale="The bullet directly shows REST API design.",
                )
            ),
            "Python",
        ),
        "priority_order": (
            _suggestions(
                _s(source_ids=["exp1.b2"], priority=0),
                _s(source_ids=["exp1.b3"], priority=2),
                _s(source_ids=["exp1.b4"], priority=1),
            ),
            "AI",
        ),
        "questions": (
            _suggestions(
                questions=[
                    ModelQuestion(requirement_quote=Q_PREF_K8S, level="preferred", term="Kubernetes"),
                    ModelQuestion(requirement_quote=Q_PREF_K8S, level="preferred", term="kubernetes"),
                    ModelQuestion(requirement_quote=Q_PREF_K8S, level="preferred", term="Terraform"),
                    ModelQuestion(requirement_quote=Q_PREF_PG, level="preferred", term="PostgreSQL"),
                    ModelQuestion(requirement_quote=Q_PREF_PG, level="preferred", term="Go"),
                    ModelQuestion(requirement_quote=Q_PREF_K8S, level="preferred", term="Python"),
                ]
            ),
            "AI",
        ),
        "tracks_edge_cases": (
            CoachModelOutput(
                mode="choose_focus",
                tracks=[
                    ModelTrack(
                        name="Python",
                        quote=Q_PY,
                        summary="s",
                        evidence=[
                            ModelEvidence(source_id="exp2.b1", why="w"),
                            ModelEvidence(source_id="exp2.b1", why="again"),
                            ModelEvidence(source_id="exp8.b1", why="missing"),
                        ],
                    ),
                    ModelTrack(name="python", quote=Q_PY, summary="duplicate name"),
                    ModelTrack(
                        name="AI", quote=Q_AI, summary="s", evidence=[ModelEvidence(source_id="exp1.b1", why="w")]
                    ),
                    ModelTrack(name="Quantum", quote="build quantum computers", summary="not in the posting"),
                ],
            ),
            "",
        ),
        "single_track_falls_back_to_suggestions": (
            CoachModelOutput(
                mode="choose_focus",
                focus="Python",
                tracks=[ModelTrack(name="Python", quote=Q_PY, summary="s")],
                suggestions=[_s(source_ids=["exp2.b2"], requirement_quote=Q_PY)],
            ),
            "",
        ),
    }


def _run(outputs: list[CoachModelOutput], title: str, description: str, focus: str):
    llm = RecordingLLM(*outputs)
    result = asyncio.run(IT_AGENT.analyze(CareerCase(CV, title, description, focus), llm))
    return llm, result


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _record(llm: RecordingLLM, result, full_payload: bool = False) -> dict:
    record = {
        "calls": len(llm.calls),
        "system_prompts": [_digest(p) for p, _ in llm.calls],
        "inputs": [_digest(u) for _, u in llm.calls],
        "result": result.model_dump(),
    }
    if full_payload:
        record["first_input"] = llm.calls[0][1]
    return record


def snapshot() -> dict:
    snap: dict[str, dict] = {}
    for name, outputs, title, description, focus in [
        ("flow_choice", [tracks_output()], JOB_TITLE, JOB_DESCRIPTION, ""),
        ("flow_ai", [ai_output()], JOB_TITLE, JOB_DESCRIPTION, "AI"),
        ("flow_python", [python_output()], JOB_TITLE, JOB_DESCRIPTION, "Python Backend"),
        (
            "flow_clear_posting_asks_twice",
            [tracks_output(), _clear_output()],
            CLEAR_JOB_TITLE,
            CLEAR_JOB_DESCRIPTION,
            "",
        ),
        ("flow_clear_posting_direct", [_clear_output()], CLEAR_JOB_TITLE, CLEAR_JOB_DESCRIPTION, ""),
    ]:
        llm, result = _run(outputs, title, description, focus)
        snap[name] = _record(llm, result, full_payload=name == "flow_choice")
    for name, (output, focus) in _gate_scenarios().items():
        llm, result = _run([output], JOB_TITLE, JOB_DESCRIPTION, focus)
        snap[f"gate_{name}"] = _record(llm, result)

    samples = [
        "Led the platform team and cut costs by 35% with Kubernetes.",
        "Built an LLM agent with FastAPI for 12,000 documents.",
        "Designed REST APIs and architected the billing platform.",
        "Designed workflow automations with queues and retries.",
        "Senior engineer. Kıdemli mühendis, yönetici olarak çalıştı.",
        "Integrated third-party APIs and webhooks.",
        "",
    ]
    job_terms = skill_like_terms(JOB_DESCRIPTION)
    snap["claims"] = {
        "job_terms": sorted(job_terms),
        "problems": [
            [[p.kind, list(p.terms)] for p in faithfulness_problems(t, cv_source_text(CV), job_terms)] for t in samples
        ],
        "design": [unsupported_design_claims(t, CV) for t in samples],
        "offers_choice": [offers_choice(JOB_DESCRIPTION), offers_choice(CLEAR_JOB_DESCRIPTION), offers_choice("")],
    }
    return snap


def test_the_it_agent_matches_the_golden_snapshot():
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    actual = json.loads(json.dumps(snapshot()))
    assert sorted(actual) == sorted(expected), "scenario set changed"
    for name in expected:
        assert actual[name] == expected[name], f"behaviour changed in scenario {name!r}"


def test_the_scenarios_really_exercise_every_gate():
    """A guard on the net itself: each drop reason the coach knows must appear at least once."""
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    seen: set[str] = set()
    for record in expected.values():
        if "result" in record:
            seen |= set(record["result"]["dropped_reasons"])
    assert seen >= {
        "requirement_quote_not_in_posting",
        "track_not_in_posting",
        "evidence_not_in_cv",
        "quote_not_in_posting",
        "source_not_in_cv",
        "generic_requirement",
        "already_first",
        "rewrite_not_substantive",
        "rewrite_unsupported_claim",
        "summary_not_new",
        "summary_unsupported_claim",
        "summary_unsupported_action",
        "unknown_kind",
        "over_limit_or_duplicate",
        "question_not_grounded",
        "too_many_questions",
    }


if __name__ == "__main__":
    if "--write" not in sys.argv:
        raise SystemExit("Pass --write to regenerate the golden file (only for an intended change).")
    GOLDEN.parent.mkdir(exist_ok=True)
    GOLDEN.write_text(json.dumps(snapshot(), indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    print(f"wrote {GOLDEN}")
