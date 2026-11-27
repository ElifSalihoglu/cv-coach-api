"""
Live check of the IT agent against the real OpenAI model, on synthetic data only
(tests/fixtures/coach_fixture.py).

It makes paid API calls, so it is run by hand, is not part of pytest, and does nothing unless
you pass --run (without it the plan is printed). Four scenarios, one call each (the agent may
make one extra call on its own):

  choice   the four-track posting, no focus       -> the agent should ask which track
  ai       the same posting, focus "AI"           -> suggestions
  python   the same posting, focus "Python"       -> suggestions
  clear    a posting with one focus, no focus     -> suggestions straight away

The checks only cover what rules can decide; read the printed suggestions to judge their quality.

    python -m scripts.run_coach_eval              # plan only
    python -m scripts.run_coach_eval --run        # make the calls
"""
import argparse
import asyncio
import os
import re
import sys

import openai

from app.careers.agents.it import IT_AGENT
from app.careers.core.state import CareerCase
from app.models.coaching import CoachResult
from app.services.llm_client import LLMClient
from app.services.openai_setup import REQUEST_TIMEOUT_SECONDS, get_openai_model
from tests.fixtures.coach_fixture import (
    CLEAR_JOB_DESCRIPTION, CLEAR_JOB_TITLE, CV, JOB_DESCRIPTION, JOB_TITLE,
)

SCENARIOS = {
    "choice": (JOB_TITLE, JOB_DESCRIPTION, ""),
    "ai": (JOB_TITLE, JOB_DESCRIPTION, "AI"),
    "python": (JOB_TITLE, JOB_DESCRIPTION, "Python Backend"),
    "clear": (CLEAR_JOB_TITLE, CLEAR_JOB_DESCRIPTION, ""),
}

OTHER_TRACK_TERMS = re.compile(r"\b(TypeScript|React|Node\.js)\b", re.IGNORECASE)
INFRA_TERMS = re.compile(r"\b(Kubernetes|Terraform)\b", re.IGNORECASE)
BUZZWORDS = re.compile(r"specializ|passionate|results-driven|AI-driven|dynamic|motivated|cutting-edge", re.IGNORECASE)
GENERIC_REQUIREMENT = re.compile(r"\byears?\b|communication|ownership|team", re.IGNORECASE)
API_DESIGN_CLAIM = re.compile(r"API design|designs? (REST )?APIs?|designed (REST )?APIs?", re.IGNORECASE)

Check = tuple[str, bool]


class BudgetExhausted(Exception):
    pass


class CallBudget:
    """Wraps the model client and refuses the call that would exceed the budget."""

    def __init__(self, inner: LLMClient, budget: int) -> None:
        self._inner, self._budget, self.calls = inner, budget, 0

    async def generate(self, system_prompt, user_content, output_model):
        if self.calls >= self._budget:
            raise BudgetExhausted(f"budget of {self._budget} calls used up")
        self.calls += 1
        return await self._inner.generate(system_prompt, user_content, output_model)


# ---------------------------------------------------------------- checks


def text_of(result: CoachResult) -> str:
    return " ".join(s.after for s in result.suggestions)


def source_ids(result: CoachResult) -> set[str]:
    return {r.id for s in result.suggestions for r in s.sources}


def quality_checks(result: CoachResult) -> list[Check]:
    """What makes a card worth the user's time, for every focus."""
    summary = next((s for s in result.suggestions if s.kind == "summary"), None)
    source_has_number = bool(summary and any(re.search(r"\d", r.text) for r in summary.sources))
    moved = {r.id for s in result.suggestions if s.kind == "promote" for r in s.sources}
    return [
        ("no card targets a generic condition (years, communication, ownership)",
         not any(GENERIC_REQUIREMENT.search(s.requirement) for s in result.suggestions)),
        ("the mentoring line (exp1.b5) is not pushed up", "exp1.b5" not in moved),
        ("the summary has no buzzwords or self-labels", not (summary and BUZZWORDS.search(summary.after))),
        ("the summary uses a figure from its source",
         not source_has_number or bool(re.search(r"\d", summary.after))),
    ]


def check_choice(result: CoachResult) -> list[Check]:
    tracks = {t.name.casefold(): t for t in result.tracks}
    find = lambda key: next((t for name, t in tracks.items() if key in name), None)  # noqa: E731
    ai, py, ts, devops = find("ai"), find("python"), find("typescript"), find("devops")
    return [
        ("asks which track (does not guess)", result.kind == "choose_focus"),
        ("all four tracks are listed", all([ai, py, ts, devops])),
        ("AI and Python are backed by evidence", bool(ai and py and ai.evidence and py.evidence)),
        ("TypeScript and DevOps say only what is known",
         bool(ts and devops and not ts.evidence and not devops.evidence
              and "No explicit" in ts.note and "No explicit" in devops.note)),
        ("backed tracks come first", [t.coverage for t in result.tracks][:2] != ["none", "none"]),
    ]


def check_ai(result: CoachResult) -> list[Check]:
    summary = next((s for s in result.suggestions if s.kind == "summary"), None)
    evaluation = [s for s in result.suggestions
                  if "exp1.b4" in {r.id for r in s.sources} and "llm" in s.requirement.casefold()]
    return [
        ("suggestions, not another question", result.kind == "suggestions"),
        ("the production LLM agent (exp1.b1) is brought forward", "exp1.b1" in source_ids(result)),
        ("the summary leads with the invoice agent",
         bool(summary and re.search(r"invoice|12,000", summary.after[:160], re.I))),
        ("no TypeScript/React in the text", not OTHER_TRACK_TERMS.search(text_of(result))),
        ("no Kubernetes/Terraform added to the text", not INFRA_TERMS.search(text_of(result))),
        ("general model evaluation is not called direct LLM evaluation",
         all(s.support == "related" for s in evaluation)),
        ("at most one reword and one summary, five cards",
         sum(s.kind == "rewrite" for s in result.suggestions) <= 1
         and sum(s.kind == "summary" for s in result.suggestions) <= 1 and len(result.suggestions) <= 5),
        ("every question rests on the posting",
         all(q.term.casefold() in JOB_DESCRIPTION.casefold() for q in result.questions)),
    ] + quality_checks(result)


def check_python(result: CoachResult) -> list[Check]:
    api_cards = [s for s in result.suggestions
                 if "exp2.b4" in {r.id for r in s.sources} and "design" in s.requirement.casefold()]
    return [
        ("suggestions, not another question", result.kind == "suggestions"),
        ("the API and webhook integration (exp2.b4) is brought forward", "exp2.b4" in source_ids(result)),
        ("pipeline work (exp2.b1 or exp2.b2) is brought forward", bool({"exp2.b1", "exp2.b2"} & source_ids(result))),
        ("integration is not claimed as API design",
         not API_DESIGN_CLAIM.search(text_of(result)) and all(s.support == "related" for s in api_cards)),
        ("no TypeScript/React in the text", not OTHER_TRACK_TERMS.search(text_of(result))),
        ("no Kubernetes/Terraform added to the text", not INFRA_TERMS.search(text_of(result))),
    ] + quality_checks(result)


def check_clear(result: CoachResult) -> list[Check]:
    return [
        ("a clear posting goes straight to suggestions", result.kind == "suggestions" and bool(result.suggestions)),
        ("the required term the CV lacks (monitoring) is asked about",
         "monitoring" in {q.term.casefold() for q in result.questions}),
    ] + quality_checks(result)


CHECKS = {"choice": check_choice, "ai": check_ai, "python": check_python, "clear": check_clear}


# ---------------------------------------------------------------- run


def print_result(name: str, result: CoachResult) -> None:
    print(f"\n{name}: {result.kind}" + (f" (focus: {result.focus})" if result.focus else "")
          + f", {result.dropped} proposal(s) dropped by our checks {result.dropped_reasons or ''}")
    for track in result.tracks:
        print(f"  track {track.name}: {track.coverage}, evidence {[e.source_id for e in track.evidence]}")
    for s in result.suggestions:
        print(f"  [{s.priority}] {s.kind} · {s.level} · {s.support} · for “{s.requirement}”")
        print(f"      {s.after if s.kind != 'promote' else f'move {s.sources[0].id} to line 1'}")
        print(f"      why: {s.rationale}")
    for q in result.questions:
        print(f"  question [{q.level}] {q.term}")


async def run(args: argparse.Namespace) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # names like "Boğaz" on a Windows console
    model = get_openai_model()
    print(f"Model: {model} | scenarios: {', '.join(SCENARIOS)} | call budget: {args.budget}")
    print("Data: synthetic candidate and postings only (tests/fixtures/coach_fixture.py).")
    if not args.run:
        print("\nPlan only. Nothing was called. Pass --run to make the calls.")
        return 0

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY is not set. Add it to .env first.")
        return 1
    # max_retries=0: the SDK would otherwise retry silently and the budget could not be exact.
    client = openai.AsyncOpenAI(api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS, max_retries=0)
    llm = CallBudget(LLMClient(openai_client=client, model=model), args.budget)

    passed = total = 0
    for name, (title, description, focus) in SCENARIOS.items():
        try:
            result = await IT_AGENT.analyze(CareerCase(CV, title, description, focus), llm)
        except Exception as exc:
            print(f"\n{name}: NOT COMPLETED ({type(exc).__name__})")
            continue
        print_result(name, result)
        for label, ok in CHECKS[name](result):
            print(f"    {'pass' if ok else 'FAIL'}  {label}")
            passed, total = passed + ok, total + 1

    print(f"\nChecks passed: {passed}/{total}. Model calls made: {llm.calls} of budget {args.budget}.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", action="store_true", help="make the real model calls")
    parser.add_argument("--budget", type=int, default=8, help="hard cap on model calls, extra calls included")
    sys.exit(asyncio.run(run(parser.parse_args())))
