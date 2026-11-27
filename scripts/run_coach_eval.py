"""
Live evaluation of the IT Career Coach with the real OpenAI model.

Only synthetic data is used: the candidate and the postings in app/evals/coach_fixture.py.
This makes paid API calls, so it is run by hand, is not part of pytest or CI, and does
nothing unless you pass --run (without it the plan is printed and nothing is called).

Per repetition it makes 4 model calls:
  1. the four-track posting, no focus chosen        -> the coach should ask which track
  2. the same posting, focus "AI"                   -> suggestions
  3. the same posting, focus "Python Backend"       -> suggestions
  4. a posting with one clear focus, no focus given -> suggestions straight away

It then applies decisions without any model (accept one, edit one, reject one) and reads
the PDF back. Every suggestion is printed so a person can judge whether it would help
the application; the checks only cover what can be decided by rules.

Usage (from the project root):
    python -m scripts.run_coach_eval                 # plan only
    python -m scripts.run_coach_eval --run           # 4 calls
    python -m scripts.run_coach_eval --run --repeat 2
"""
import argparse
import asyncio
import hashlib
import io
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import openai
from pypdf import PdfReader

from app.evals.fingerprint import agent_fingerprint
from app.evals.coach_fixture import (
    CLEAR_JOB_DESCRIPTION, CLEAR_JOB_TITLE, CV, JOB_DESCRIPTION, JOB_TITLE,
)
from app.models.coaching import ApplyRequest, CoachResult, Decision
from app.careers.agents.it import IT_AGENT, IT_PROFILE
from app.careers.core.state import CareerCase
from app.services.coach_apply import apply_decisions
from app.services.cv_render import render_pdf
from app.services.llm_client import LLMClient
from app.services.openai_setup import REQUEST_TIMEOUT_SECONDS, get_openai_model

CALLS_PER_REPEAT = 4
RESULTS_DIR = Path(__file__).resolve().parents[1] / "evals" / "results"
OTHER_TRACK_TERMS = re.compile(r"\b(TypeScript|React|Node\.js)\b", re.IGNORECASE)
INFRA_TERMS = re.compile(r"\b(Kubernetes|Terraform)\b", re.IGNORECASE)
BUZZWORDS = re.compile(r"specializ|passionate|results-driven|AI-driven|dynamic|motivated|cutting-edge", re.IGNORECASE)
GENERIC_REQUIREMENT = re.compile(r"\byears?\b|communication|ownership|team", re.IGNORECASE)
API_DESIGN_CLAIM = re.compile(r"API design|designs? (REST )?APIs?|designed (REST )?APIs?", re.IGNORECASE)

Check = tuple[str, bool, str]


class BudgetExhausted(Exception):
    """The call budget is used up: the call that would exceed it is never made."""


class Recording:
    """
    Wraps the model client. Every attempt (also a failed one, also a correction call the
    coach makes by itself) counts against the budget, and every raw answer is kept
    (synthetic data only) so a drop can be explained afterwards without a new call.
    """

    def __init__(self, inner: LLMClient, budget: int) -> None:
        self.inner = inner
        self.budget = budget
        self.scenario = ""
        self.calls: list[dict] = []

    @property
    def attempts(self) -> int:
        return len(self.calls)

    async def generate(self, system_prompt, user_content, output_model):
        if self.attempts >= self.budget:
            raise BudgetExhausted(f"budget of {self.budget} calls used up")
        entry = {
            "n": self.attempts + 1, "scenario": self.scenario,
            "job_title": user_content.get("job_title", ""), "focus": user_content.get("focus", ""),
            "posting_offers_choice": user_content.get("posting_offers_choice"), "status": "pending",
        }
        self.calls.append(entry)
        try:
            result = await self.inner.generate(system_prompt, user_content, output_model)
        except Exception as exc:  # the attempt still counts
            entry["status"] = f"error: {type(exc).__name__}"
            raise
        entry.update(status="ok", raw=result.model_dump())
        return result


def text_of(result: CoachResult) -> str:
    return " ".join(s.after for s in result.suggestions)


def card(s) -> str:
    where = s.sources[0].where if s.sources else ""
    lines = [f"    [{s.priority}] {s.kind.upper()} · {s.level} · {s.support}",
             f"        posting: “{s.requirement}”", f"        CV line: {where}: “{s.sources[0].text}”"]
    if s.kind == "promote":
        lines.append(f"        move from line {s.position} to line 1")
    else:
        lines += [f"        now:       {s.before}", f"        suggested: {s.after}"]
    lines.append(f"        why: {s.rationale}")
    return "\n".join(lines)


def print_result(title: str, result: CoachResult) -> None:
    print(f"\n  {title}: {result.kind}" + (f" (focus: {result.focus})" if result.focus else "")
          + f", {result.dropped} proposal(s) dropped by our checks {result.dropped_reasons or ''}")
    for track in result.tracks:
        print(f"    track {track.name}: {track.coverage}, evidence {[e.source_id for e in track.evidence]}"
              + (f" — {track.note}" if track.note else ""))
    for s in result.suggestions:
        print(card(s))
    for q in result.questions:
        print(f"    QUESTION [{q.level}] {q.term}: “{q.requirement}”")


def ids(result: CoachResult) -> set[str]:
    return {r.id for s in result.suggestions for r in s.sources}


# ---------------------------------------------------------------- the checks


def check_quality(result: CoachResult) -> list[Check]:
    """Rules about what makes a card worth the user's time (shared by every focus)."""
    summary = next((s for s in result.suggestions if s.kind == "summary"), None)
    generic = [s.requirement for s in result.suggestions if GENERIC_REQUIREMENT.search(s.requirement)]
    source_has_number = bool(summary and any(re.search(r"\d", r.text) for r in summary.sources))
    return [
        ("no card targets a generic condition (years, communication, ownership)", not generic, str(generic)),
        ("the mentoring line (exp1.b5) is not pushed up", "exp1.b5" not in {
            r.id for s in result.suggestions if s.kind == "promote" for r in s.sources}, ""),
        ("the summary has no buzzwords or self-labels", not (summary and BUZZWORDS.search(summary.after)),
         summary.after[:120] if summary else ""),
        ("the summary uses a figure from its source", not source_has_number or bool(re.search(r"\d", summary.after)),
         summary.after[:120] if summary else ""),
    ]


def check_choice(result: CoachResult) -> list[Check]:
    names = {t.name.casefold(): t for t in result.tracks}
    find = lambda key: next((t for n, t in names.items() if key in n), None)  # noqa: E731
    ai, py, ts, devops = find("ai"), find("python"), find("typescript"), find("devops")
    return [
        ("asks which track (does not guess)", result.kind == "choose_focus", result.kind),
        ("all four tracks are listed", all([ai, py, ts, devops]), str(sorted(names))),
        ("AI and Python are backed by evidence", bool(ai and py and ai.evidence and py.evidence), ""),
        ("TypeScript and DevOps say only what is known",
         bool(ts and devops and not ts.evidence and not devops.evidence
              and "No explicit" in ts.note and "No explicit" in devops.note), ""),
        ("backed tracks come first", [t.coverage for t in result.tracks][:2] != ["none", "none"], ""),
    ]


def check_ai(result: CoachResult) -> list[Check]:
    text = text_of(result)
    summary = next((s for s in result.suggestions if s.kind == "summary"), None)
    eval_cards = [s for s in result.suggestions if "exp1.b4" in {r.id for r in s.sources}
                  and "llm" in s.requirement.casefold()]
    return [
        ("suggestions, not another question", result.kind == "suggestions", result.kind),
        ("the production LLM agent (exp1.b1) is brought forward", "exp1.b1" in ids(result), str(sorted(ids(result)))),
        ("the summary leads with the invoice agent",
         bool(summary and re.search(r"invoice|12,000", summary.after[:160], re.I)), summary.after[:100] if summary else "no summary"),
        ("no TypeScript/React in the text", not OTHER_TRACK_TERMS.search(text), ""),
        ("no Kubernetes/Terraform added to the text", not INFRA_TERMS.search(text), ""),
        ("general model evaluation is not called direct LLM evaluation",
         all(s.support == "related" for s in eval_cards), str([s.support for s in eval_cards])),
        ("at most one reword and one summary, five cards", sum(s.kind == "rewrite" for s in result.suggestions) <= 1
         and sum(s.kind == "summary" for s in result.suggestions) <= 1 and len(result.suggestions) <= 5, ""),
        ("every question rests on the posting", all(q.term.casefold() in JOB_DESCRIPTION.casefold() for q in result.questions), ""),
    ]


def check_python(result: CoachResult) -> list[Check]:
    text = text_of(result)
    api_cards = [s for s in result.suggestions if "exp2.b4" in {r.id for r in s.sources} and "design" in s.requirement.casefold()]
    return [
        ("suggestions, not another question", result.kind == "suggestions", result.kind),
        ("the API and webhook integration (exp2.b4) is brought forward", "exp2.b4" in ids(result), str(sorted(ids(result)))),
        ("pipeline work (exp2.b1 or exp2.b2) is brought forward", bool({"exp2.b1", "exp2.b2"} & ids(result)), ""),
        ("integration is not claimed as API design",
         not API_DESIGN_CLAIM.search(text) and all(s.support == "related" for s in api_cards), str([s.support for s in api_cards])),
        ("no TypeScript/React in the text", not OTHER_TRACK_TERMS.search(text), ""),
        ("no Kubernetes/Terraform added to the text", not INFRA_TERMS.search(text), ""),
    ]


def check_different(ai: CoachResult, py: CoachResult) -> list[Check]:
    return [
        ("AI and Python bring different sources forward", ids(ai) != ids(py), f"{sorted(ids(ai))} vs {sorted(ids(py))}"),
        ("the two summaries differ", text_of(ai) != text_of(py), ""),
    ]


def check_clear(result: CoachResult) -> list[Check]:
    return [
        ("a clear posting goes straight to suggestions (one call)", result.kind == "suggestions" and bool(result.suggestions), result.kind),
        ("the required term the CV lacks (monitoring) is asked about",
         "monitoring" in {q.term.casefold() for q in result.questions}, str([q.term for q in result.questions])),
    ]


def check_decisions(result: CoachResult) -> list[Check]:
    """No model: accept one, edit one, reject one; the PDF must show exactly that."""
    suggestions = list(result.suggestions)
    promote = next((s for s in suggestions if s.kind == "promote"), None)
    summary = next((s for s in suggestions if s.kind == "summary"), None)
    if not promote or not summary:
        return [("a move and a summary exist to decide on", False, "missing")]
    edited = summary.after.rstrip(".") + ". I enjoy mentoring."
    rejected = next((s for s in suggestions if s is not promote and s is not summary and s.kind == "promote"), None)
    decisions = {promote.id: Decision(action="accept"), summary.id: Decision(action="edit", text=edited)}
    applied = apply_decisions(ApplyRequest(cv=CV, suggestions=suggestions, decisions=decisions, job_description=JOB_DESCRIPTION))

    reader = PdfReader(io.BytesIO(render_pdf(applied.cv)))
    pdf = re.sub(r"\s+", " ", " ".join(p.extract_text() or "" for p in reader.pages))
    exp_id = promote.sources[0].id.split(".b")[0]
    order = [b.id for e in applied.cv.experiences if e.id == exp_id for b in e.bullets]
    checks: list[Check] = [
        ("the edited summary is in the PDF", edited in pdf, ""),
        ("the old summary is not", CV.summary not in pdf, ""),
        ("the accepted move happened", order[0] == promote.sources[0].id, str(order)),
        ("the main CV is unchanged", CV == CV.model_copy(deep=True) and applied.cv is not CV
         and CV.experiences[0].bullets[0].id == "exp1.b1", ""),
    ]
    if rejected:
        rid = rejected.sources[0].id
        after = [b.id for e in applied.cv.experiences if e.id == rid.split(".b")[0] for b in e.bullets]
        checks.append(("the rejected move did not happen (its line is not first)", after[0] != rid, str(after)))
    return checks


# ---------------------------------------------------------------------- run

SCENARIOS = ("choice", "ai", "python", "clear")


def scenario_checks(key: str, result: CoachResult) -> list[Check]:
    if key == "choice":
        return check_choice(result)
    if key == "ai":
        return check_ai(result) + check_quality(result)
    if key == "python":
        return check_python(result) + check_quality(result)
    return check_clear(result) + check_quality(result)


async def run(args: argparse.Namespace) -> int:
    # Names like "Boğaz" must print on a Windows console too.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    model = get_openai_model()
    prompt_version = hashlib.sha256(IT_PROFILE.system_prompt.encode()).hexdigest()[:8]
    fingerprints = agent_fingerprint("it", model)  # the IT agent's: this evaluation is about it alone
    planned = CALLS_PER_REPEAT * args.repeat
    print(f"Model: {model} | prompt: {prompt_version} | repetitions: {args.repeat}")
    print("Fingerprints: " + " | ".join(f"{k} {v}" for k, v in fingerprints.items()))
    print(f"Call budget: {args.budget} (planned without corrections: {planned}). "
          "Corrections and failed attempts count; no hidden SDK retries.")
    print("Data: synthetic candidate and synthetic postings only (app/evals/coach_fixture.py).")
    if not args.run:
        print("\nPlan only. Nothing was called. Pass --run to make the calls.")
        return 0

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY is not set. Add it to .env first.")
        return 1
    # max_retries=0: the SDK would otherwise retry silently and the budget could not be exact.
    client = openai.AsyncOpenAI(api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS, max_retries=0)
    recorder = Recording(LLMClient(openai_client=client, model=model), args.budget)

    jobs = {
        "choice": (JOB_TITLE, JOB_DESCRIPTION, ""),
        "ai": (JOB_TITLE, JOB_DESCRIPTION, "AI"),
        "python": (JOB_TITLE, JOB_DESCRIPTION, "Python Backend"),
        "clear": (CLEAR_JOB_TITLE, CLEAR_JOB_DESCRIPTION, ""),
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = RESULTS_DIR / f"coach_run_{stamp}_{model}_{prompt_version}.json"
    record: dict = {"model": model, "prompt_version": prompt_version, "budget": args.budget,
                    "fingerprint": fingerprints, "status": {}, "results": {}, "checks": {}, "calls": recorder.calls}

    def save() -> None:
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")

    stopped = False
    for rep in range(1, args.repeat + 1):
        for key in SCENARIOS:
            label = f"r{rep}/{key}"
            if stopped or recorder.attempts >= args.budget:
                stopped = True
                record["status"][label] = "not_run: budget used up"
                save()
                continue
            recorder.scenario = label
            try:
                result = await IT_AGENT.analyze(CareerCase(CV, *jobs[key]), recorder)
            except BudgetExhausted:
                stopped = True
                record["status"][label] = "incomplete: budget used up before its correction call"
                save()
                continue
            except Exception as exc:
                record["status"][label] = f"error: {type(exc).__name__}"
                save()
                continue
            record["status"][label] = "done"
            record["results"][label] = result.model_dump()
            record["checks"][label] = [{"name": n, "passed": ok, "detail": d} for n, ok, d in scenario_checks(key, result)]
            save()
            if args.verbose:
                print_result(label, result)
            print(f"  {label}: {result.kind}, {sum(c['passed'] for c in record['checks'][label])}/"
                  f"{len(record['checks'][label])} checks   (calls so far: {recorder.attempts}/{args.budget})")

    # Cross-scenario and no-model checks, only for repetitions where the scenarios finished.
    for rep in range(1, args.repeat + 1):
        ai, py = f"r{rep}/ai", f"r{rep}/python"
        if ai in record["results"] and py in record["results"]:
            ai_r, py_r = CoachResult(**record["results"][ai]), CoachResult(**record["results"][py])
            record["checks"][f"r{rep}/cross"] = [
                {"name": n, "passed": ok, "detail": d} for n, ok, d in check_different(ai_r, py_r)]
        if ai in record["results"]:
            record["checks"][f"r{rep}/decisions"] = [
                {"name": n, "passed": ok, "detail": d}
                for n, ok, d in check_decisions(CoachResult(**record["results"][ai]))]
    save()

    # One line per behaviour: seen in how many of the runs that finished.
    tally: dict[str, list[int]] = {}
    for label, checks in record["checks"].items():
        for c in checks:
            seen = tally.setdefault(c["name"], [0, 0])
            seen[0] += c["passed"]
            seen[1] += 1
    print("\nBehaviour: passed in N of the runs that finished")
    for name, (ok, total) in tally.items():
        print(f"  {ok}/{total}  {name}")
    done = {k: sum(1 for l, v in record["status"].items() if l.endswith(k) and v == "done") for k in SCENARIOS}
    print(f"\nScenarios finished: {done} (of {args.repeat} each)")
    for label, status in record["status"].items():
        if status != "done":
            print(f"  NOT COMPLETED  {label}: {status}")
    print(f"Model calls made: {recorder.attempts} of budget {args.budget}")
    print(f"Saved details to {path}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", action="store_true", help="make the real model calls")
    parser.add_argument("--repeat", type=int, default=1, help="repetitions (4 scenarios each)")
    parser.add_argument("--budget", type=int, default=12, help="hard cap on model calls, corrections included")
    parser.add_argument("--verbose", action="store_true", help="print every card as it arrives")
    sys.exit(asyncio.run(run(parser.parse_args())))
