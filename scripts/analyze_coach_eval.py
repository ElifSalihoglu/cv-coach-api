"""
Explains a saved live evaluation (evals/results/coach_run_*.json) WITHOUT any model call.

It replays our validation on the raw model answers the run saved, so a dropped
proposal can be told apart as "the model claimed something the CV does not say" or
"our checker was wrong". Synthetic data only.

Usage:
    python -m scripts.analyze_coach_eval                # newest coach_run_*.json
    python -m scripts.analyze_coach_eval path\\to\\run.json
"""
import json
import re
import sys
from pathlib import Path

from app.evals.coach_fixture import (
    CLEAR_JOB_DESCRIPTION, CLEAR_JOB_TITLE, CV, JOB_DESCRIPTION, JOB_TITLE,
)
from app.models.coaching import CoachModelOutput, CoachResult
from app.services.job_coach import _fold, _is_generic, _quote_in, _slug
from app.services.cv_tailoring import cv_source_text, faithfulness_problems, skill_like_terms

RESULTS = Path(__file__).resolve().parents[1] / "evals" / "results"
POSTINGS = {"choice": JOB_DESCRIPTION, "ai": JOB_DESCRIPTION, "python": JOB_DESCRIPTION, "clear": CLEAR_JOB_DESCRIPTION}


def cv_lines() -> list[tuple[str, str]]:
    lines = [("summary", CV.summary), ("skills", ", ".join(CV.skills))]
    for exp in CV.experiences:
        for b in exp.bullets:
            lines.append((b.id, b.text))
    return lines


def lines_with(term: str) -> list[str]:
    needle = _fold(term)
    return [f"{lid}: {text}" for lid, text in cv_lines() if needle in _fold(text)]


def calls_of(run: dict, label: str) -> list[dict]:
    return [c for c in run["calls"] if c["scenario"] == label]


def raw_of(call: dict) -> CoachModelOutput | None:
    return CoachModelOutput(**call["raw"]) if call.get("raw") else None


def sentence_with(text: str, term: str) -> str:
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if _fold(term) in _fold(sentence):
            return re.sub(re.escape(term), f"[[{term}]]", sentence, flags=re.IGNORECASE)
    return text[:160]


def heading(text: str) -> None:
    print(f"\n{'=' * 78}\n{text}\n{'=' * 78}")


def header(run: dict) -> None:
    heading("RUN")
    print(f"model {run['model']} | prompt {run['prompt_version']} | budget {run['budget']} | calls made {len(run['calls'])}")
    print("fingerprint (prompt / validation / faithfulness / sample data):", run["fingerprint"])
    for label, status in run["status"].items():
        print(f"  {label:12} {status}")
    print("calls:")
    for c in run["calls"]:
        print(f"  #{c['n']:<2} {c['scenario']:10} focus={c['focus']!r:18} offers_choice={c['posting_offers_choice']} -> {c['status']}")


# ------------------------------------------------------------------ question 1


def q1(run: dict) -> None:
    heading("1. AI SUMMARY: kept, or dropped and why")
    job_terms = skill_like_terms(JOB_DESCRIPTION)
    cv_text = cv_source_text(CV)
    for label in [l for l in run["results"] if l.endswith("/ai")] + [l for l, s in run["status"].items() if l.endswith("/ai") and s != "done"]:
        print(f"\n[{label}] {run['status'][label]}")
        if label not in run["results"]:
            continue
        result = run["results"][label]
        print("  dropped_reasons:", result["dropped_reasons"])
        for call in calls_of(run, label):
            raw = raw_of(call)
            if raw is None:
                continue
            for item in raw.suggestions:
                if item.kind != "summary":
                    continue
                kept = next((s for s in result["suggestions"] if s["kind"] == "summary"), None)
                print(f"  model summary: {item.after}")
                print(f"  model targeted: “{item.requirement_quote}” ({item.level}, {item.support}); sources {item.source_ids}")
                problems = faithfulness_problems(item.after, cv_text, job_terms)
                if kept:
                    print(f"  -> KEPT. final target: “{kept['requirement']}” ({kept['level']}, {kept['support']})")
                if not problems:
                    print("  faithfulness replay: no problem found" + ("" if kept else " (it was dropped by another rule)"))
                for p in problems:
                    print(f"  faithfulness replay: {p.kind} {list(p.terms)}")
                    for term in p.terms:
                        print(f"     summary sentence : {sentence_with(item.after, term)}")
                        print(f"     CV lines with it : {lines_with(term) or 'none (the CV never says it)'}")
                        print(f"     in the posting   : {_fold(term) in _fold(JOB_DESCRIPTION)}")


# ------------------------------------------------------------------ question 2


def q2(run: dict) -> None:
    heading("2. DOES THE USER GET A TRACK CHOICE?")
    for label in run["status"]:
        key = label.split("/")[1]
        if key not in ("clear", "choice"):
            continue
        print(f"\n[{label}] {run['status'][label]}")
        for call in calls_of(run, label):
            raw = raw_of(call)
            mode = raw.mode if raw else call["status"]
            names = [t.name for t in raw.tracks] if raw else []
            print(f"  model call #{call['n']} (focus={call['focus']!r}): mode={mode}" + (f", tracks it proposed: {names}" if names else ""))
        if label in run["results"]:
            r = run["results"][label]
            if r["kind"] == "choose_focus":
                shown = [(t["name"], t["coverage"]) for t in r["tracks"]]
                print(f"  USER SEES: a track choice -> {shown}")
            else:
                print(f"  USER SEES: {len(r['suggestions'])} suggestion(s), {len(r['questions'])} question(s), no choice")


# ------------------------------------------------------------------ question 3


def passes_over(source_id: str) -> list[str]:
    exp_id = source_id.split(".b")[0]
    exp = next(e for e in CV.experiences if e.id == exp_id)
    pos = next(i for i, b in enumerate(exp.bullets, start=1) if b.id == source_id)
    return [f"line {i}: {b.text}" for i, b in enumerate(exp.bullets[: pos - 1], start=1)]


def q3(run: dict) -> None:
    heading("3. CARDS: what moves in front of what, and where a summary was re-aimed")
    for label, result in run["results"].items():
        key = label.split("/")[1]
        if key not in ("ai", "python", "clear"):
            continue
        raws = [raw_of(c) for c in calls_of(run, label) if c.get("raw")]
        raw_items = [i for r in raws if r for i in r.suggestions]
        print(f"\n[{label}] kind={result['kind']}")
        for s in result["suggestions"]:
            print(f"  [{s['priority']}] {s['kind'].upper()} · {s['level']} · {s['support']}")
            print(f"      posting target : “{s['requirement']}”")
            print(f"      CV line        : {s['sources'][0]['where']}: “{s['sources'][0]['text']}”")
            if s["kind"] == "promote":
                print(f"      jumps over     : {passes_over(s['sources'][0]['id'])}")
            else:
                print(f"      now            : {s['before']}")
                print(f"      suggested      : {s['after']}")
            print(f"      why            : {s['rationale']}")
            original = next((i for i in raw_items if i.kind == s["kind"] and (s["kind"] == "summary" or s["sources"][0]["id"] in i.source_ids)), None)
            if original and original.requirement_quote != s["requirement"]:
                print(f"      RE-AIMED from  : “{original.requirement_quote}” (model's own target)")
                print(f"      new target backed by the source lines? source words in common with the target: "
                      f"{sorted(set(re.findall(r'[a-z]{4,}', _fold(s['requirement']))) & set(re.findall(r'[a-z]{4,}', _fold(' '.join(r['text'] for r in s['sources'])+' '+s['after']))))}")
        for q in result["questions"]:
            print(f"  QUESTION [{q['level']}] {q['term']}: “{q['requirement']}”")


# ------------------------------------------------------------------ question 4


def q4(run: dict) -> None:
    heading("4. WHERE DOES THE 'monitoring' QUESTION GET LOST? (clear posting)")
    cv_folded = _fold(cv_source_text(CV))
    print(f"posting mentions 'monitoring': {'monitoring' in _fold(CLEAR_JOB_DESCRIPTION)} | CV mentions it: {'monitoring' in cv_folded}")
    for label in [l for l in run["status"] if l.endswith("/clear")]:
        print(f"\n[{label}] {run['status'][label]}")
        for call in calls_of(run, label):
            raw = raw_of(call)
            if raw is None:
                continue
            print(f"  call #{call['n']} (focus={call['focus']!r}, mode={raw.mode})")
            reqs = [r for r in raw.requirements if "monitor" in _fold(r.quote + " " + r.text)]
            print(f"   a) requirement mentioning monitoring: " + (str([(r.level, r.quote) for r in reqs]) if reqs else "none extracted"))
            print(f"   b) responsibilities mentioning it: {[x for x in raw.responsibilities if 'monitor' in _fold(x)] or 'none'}")
            print(f"   c) questions the model proposed: {[(q.term, q.level) for q in raw.questions] or 'none'}")
            for q in raw.questions:
                term = _fold(q.term.strip())
                checks = {
                    "quote is in the posting": _quote_in(_fold(CLEAR_JOB_DESCRIPTION), q.requirement_quote),
                    "term is in that quote": term in _fold(q.requirement_quote),
                    "term is in the posting": term in _fold(CLEAR_JOB_DESCRIPTION),
                    "CV is silent about it": term not in cv_folded,
                }
                bad = [k for k, ok in checks.items() if not ok]
                print(f"      replay for {q.term!r}: " + ("passes every filter" if not bad else f"FILTERED because: {bad}"))
        if label in run["results"]:
            print(f"   d) questions the user sees: {[q['term'] for q in run['results'][label]['questions']] or 'none'}")
    print("\n(If 'none extracted' and 'none proposed': the loss is at the model, before any filter of ours.)")


def main() -> None:
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        path = sorted(RESULTS.glob("coach_run_*.json"))[-1]
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    run = json.loads(path.read_text(encoding="utf-8"))
    print(f"file: {path.name}")
    header(run)
    q1(run)
    q2(run)
    q3(run)
    q4(run)


if __name__ == "__main__":
    main()
