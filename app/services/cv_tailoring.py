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
import re
from dataclasses import dataclass
from typing import Any, Literal

from app.models.cv_document import (
    CVBullet,
    CVExperience,
    StructuredCV,
    TailoredCVResult,
    TailoredContent,
)

_WORD = re.compile(r"[^\W_][\w+#.\-/]*[\w+#]|[^\W_]")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
# Seniority / leadership claims that must come from the source.
_SENIORITY = re.compile(
    r"\b(senior|lead(?:er|ership)?|principal|staff|head|manager|director|architect"
    r"|kıdemli|lider\w*|yönetici\w*|müdür\w*|direktör\w*|mimar\w*|başkan\w*)",
    re.IGNORECASE,
)
_SENTENCE_END = set(".!?:;\n•-*–—")


def norm(text: str) -> str:
    """Case/diacritic-insensitive form for comparing Turkish and English text."""
    table = str.maketrans({"İ": "i", "I": "i", "ı": "i"})
    return (text or "").translate(table).casefold()


def _stem(token: str) -> str:
    token = norm(token).strip(".-/")
    return token[:-1] if len(token) > 3 and token.endswith("s") else token


def _tokens(text: str) -> set[str]:
    return {_stem(m.group()) for m in _WORD.finditer(text or "")}


def skill_like_terms(job_description: str) -> set[str]:
    """
    Terms in the job description that look like skills or tools: ALLCAPS,
    CamelCase, names with digits or + # . / -, and capitalised words that are
    not at the start of a sentence (Python, Kubernetes, Machine Learning).
    """
    terms: set[str] = set()
    for match in _WORD.finditer(job_description or ""):
        word = match.group()
        if not any(ch.isalpha() for ch in word):
            # "3", "3+", "24/7", "2.5": numbers, not skills. Numeric claims are
            # checked separately (new numbers); names like S3 or EC2 have letters.
            continue
        before = job_description[: match.start()].rstrip(" \t")
        sentence_start = not before or before[-1] in _SENTENCE_END
        if (
            re.search(r"\d", word)
            or re.search(r"[+#]", word)
            or (len(word) >= 2 and word.isupper())
            or re.search(r"[a-zçğıöşü][A-ZÇĞİÖŞÜ]", word)
            or (word[0].isupper() and len(word) > 2 and not sentence_start)
        ):
            terms.add(_stem(word))
    return terms


@dataclass(frozen=True)
class Problem:
    """Something a draft claims that the CV does not back up."""

    kind: Literal["numbers", "seniority", "skills"]
    terms: tuple[str, ...]  # as written in the draft


def faithfulness_problems(text: str, source: str, job_terms: set[str]) -> list[Problem]:
    """
    What `text` claims that `source` does not back up: new numbers, new
    seniority words, and job-description skills the source never mentions.
    """
    problems: list[Problem] = []

    new_numbers = set(_NUMBER.findall(text)) - set(_NUMBER.findall(source))
    if new_numbers:
        problems.append(Problem("numbers", tuple(sorted(new_numbers))))

    source_seniority = {norm(m.group()) for m in _SENIORITY.finditer(source)}
    seniority = {
        norm(m.group()): m.group() for m in _SENIORITY.finditer(text)
        if norm(m.group()) not in source_seniority
    }
    if seniority:
        problems.append(Problem("seniority", tuple(sorted(seniority.values(), key=str.casefold))))

    spelled = {_stem(m.group()): m.group() for m in _WORD.finditer(text or "")}
    new_skills = (_tokens(text) & job_terms) - _tokens(source)
    if new_skills:
        problems.append(Problem(
            "skills", tuple(sorted((spelled.get(t, t) for t in new_skills), key=str.casefold)),
        ))
    return problems


def explain_problems(problems: list[Problem]) -> str:
    """One plain sentence naming the flagged terms, e.g. for the user to read."""
    parts = []
    for problem in problems:
        terms = ", ".join(problem.terms)
        if problem.kind == "skills":
            parts.append(f"mentioned {terms}, which we couldn't verify in your CV")
        elif problem.kind == "numbers":
            noun = "number" if len(problem.terms) == 1 else "numbers"
            parts.append(f"used the {noun} {terms}, which {'is' if len(problem.terms) == 1 else 'are'} not in your CV")
        else:
            parts.append(f"claimed {terms}, which your CV does not say")
    return "The draft " + " and ".join(parts) + "."


def cv_source_text(cv: StructuredCV) -> str:
    parts = [cv.summary, *cv.skills]
    for exp in cv.experiences:
        parts += [exp.title, exp.employer, *(b.text for b in exp.bullets)]
    for edu in cv.education:
        parts += [edu.school, edu.degree, edu.details]
    for proj in cv.projects:
        parts += [proj.name, proj.description]
    for cert in cv.certifications:
        parts += [cert.name, cert.issuer]
    parts += cv.languages
    return "\n".join(p for p in parts if p)


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
