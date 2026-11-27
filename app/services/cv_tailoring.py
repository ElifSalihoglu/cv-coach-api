"""
Turning the model's tailoring answer into a job-specific CV.

The model may only write the summary and the wording/order of bullets. Names,
contact details, employers, titles, dates, education and skills are copied from
the confirmed CV; the model never sees or returns them (identity and contact
are not even sent).

Every model answer is checked before it is used. When a check fails we fall
back to the original text for the affected bullet (or summary) and record a
warning, so a bad answer degrades to "less tailored" and never to "invented".
"""
from typing import Any

# The claim checks now live in the shared core; these names stay importable from here.
from app.careers.core.claims import (  # noqa: F401
    Problem,
    cv_source_text,
    explain_problems,
    faithfulness_problems,
    norm,
    skill_like_terms,
    stem as _stem,
    tokens as _tokens,
)
from app.models.cv_document import (
    CVBullet,
    CVExperience,
    StructuredCV,
    TailoredCVResult,
    TailoredContent,
)


def model_input(cv: StructuredCV, job_title: str, job_description: str) -> dict[str, Any]:
    """The payload sent to the model. No name, email, phone, links or dates."""
    return {
        "job_title": job_title,
        "job_description": job_description,
        "candidate": {
            "summary": cv.summary,
            "skills": cv.skills,
            "experiences": [
                {
                    "id": exp.id,
                    "title": exp.title,
                    "employer": exp.employer,
                    "bullets": [{"id": b.id, "text": b.text} for b in exp.bullets],
                }
                for exp in cv.experiences
            ],
        },
    }


def build_tailored_cv(
    original: StructuredCV, content: TailoredContent, job_description: str
) -> TailoredCVResult:
    """Apply a model answer to a copy of the original CV, with all checks."""
    warnings: list[str] = []
    job_terms = skill_like_terms(job_description)
    answered = {exp.id: exp for exp in content.experiences}

    experiences: list[CVExperience] = []
    for exp in original.experiences:
        by_id = {b.id: b for b in exp.bullets}
        answer = answered.get(exp.id)
        bullets = _tailor_bullets(exp, by_id, answer, job_terms, warnings)
        experiences.append(exp.model_copy(update={"bullets": bullets}))

    unknown = set(answered) - {e.id for e in original.experiences}
    if unknown:
        warnings.append("ignored unknown experience ids: " + ", ".join(sorted(unknown)))

    summary = content.summary
    problems = faithfulness_problems(summary, cv_source_text(original), job_terms)
    if problems:
        warnings.append("Original summary kept. " + explain_problems(problems))
        summary = original.summary

    cv = original.model_copy(update={"summary": summary, "experiences": experiences})
    return TailoredCVResult(cv=cv, warnings=warnings)


def _tailor_bullets(exp, by_id, answer, job_terms, warnings) -> list[CVBullet]:
    original = list(exp.bullets)
    if not original:
        return original
    if answer is None:
        warnings.append(f"{exp.id}: missing in the model answer; kept original order")
        return original

    ids = [b.source_id for b in answer.bullets]
    # Every bullet exactly once, and only this experience's own bullets: this is
    # what keeps each bullet under the right employer, whatever order the model
    # chose.
    if sorted(ids) != sorted(by_id):
        warnings.append(
            f"{exp.id}: bullet ids did not match this experience; kept the original bullets"
        )
        return original

    result: list[CVBullet] = []
    for tailored in answer.bullets:
        source = by_id[tailored.source_id]
        text = tailored.text
        if text != source.text:
            problems = faithfulness_problems(
                text, f"{source.text}\n{exp.title}", job_terms
            )
            if problems:
                warnings.append(
                    f"{source.id}: original wording kept. " + explain_problems(problems)
                )
                text = source.text
        result.append(CVBullet(id=source.id, text=text))
    return result
