"""
Run the faithfulness evaluation against the real OpenAI model.

This makes one paid API call per case, so it is run by hand and is not
part of pytest or CI.

Usage (from the project root):
    python -m scripts.run_eval
"""

import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.evals.cases import load_cases
from app.evals.checks import check_generated_content
from app.models.schemas import GeneratedCVContent
from app.prompts.cv_templates import BASE_CV_SYSTEM_PROMPT
from app.services.cv_coach import OpenAICVCoach
from app.services.llm_client import LLMClient, LLMError
from app.services.openai_setup import create_openai_client, get_openai_model

RESULTS_DIR = Path(__file__).resolve().parents[1] / "evals" / "results"


async def run() -> int:
    openai_client = create_openai_client()
    if openai_client is None:
        print("OPENAI_API_KEY is not set. Add it to .env first.")
        return 1

    model = get_openai_model()
    prompt_version = hashlib.sha256(BASE_CV_SYSTEM_PROMPT.encode()).hexdigest()[:8]
    coach = OpenAICVCoach(LLMClient(openai_client=openai_client, model=model))
    cases = load_cases()

    print(f"Model: {model} | prompt: {prompt_version} | cases: {len(cases)}\n")

    records = []
    for case in cases:
        try:
            response = await coach.optimize(case.to_request())
        except LLMError as exc:
            print(f"ERROR  {case.id}: {exc}")
            records.append({"id": case.id, "status": "error", "error": str(exc)})
            continue

        generated = GeneratedCVContent(
            improved_bullets=response.improved_bullets,
            summary=response.summary,
            linkedin_headline=response.linkedin_headline,
        )
        result = check_generated_content(
            generated,
            source_bullets=case.current_bullets,
            forbidden_terms=case.forbidden_terms,
        )
        status = "pass" if result.passed else "fail"
        print(f"{status.upper():5}  {case.id}")
        if result.unsupported_numbers:
            print(f"       invented numbers: {result.unsupported_numbers}")
        if result.unsupported_terms:
            print(f"       forbidden terms:  {result.unsupported_terms}")

        records.append(
            {
                "id": case.id,
                "status": status,
                "unsupported_numbers": result.unsupported_numbers,
                "unsupported_terms": result.unsupported_terms,
                "output": generated.model_dump(),
            }
        )

    passed = sum(record["status"] == "pass" for record in records)
    failed = sum(record["status"] == "fail" for record in records)
    errors = sum(record["status"] == "error" for record in records)
    print(f"\nPassed {passed}/{len(records)} | failed {failed} | errors {errors}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = RESULTS_DIR / f"{timestamp}_{model}_{prompt_version}.json"
    out_path.write_text(
        json.dumps(
            {
                "model": model,
                "prompt_version": prompt_version,
                "summary": {"passed": passed, "failed": failed, "errors": errors},
                "cases": records,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"Saved details to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
