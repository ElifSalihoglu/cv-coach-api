"""
Claim checks shared by every feature that lets a model write CV text: what a draft says
(new numbers, new seniority words, new skills) that the source does not back up.

The word lists behind them live in a `ClaimLexicon`, so a domain can bring its own. The
default lexicon is language-level (English and Turkish seniority words, typographic
skill detection), not IT-specific. It is what the coach, the tailoring step and the
apply step all used before the coach was split into domain agents.
"""
import re
from dataclasses import dataclass, field
from typing import Callable, Literal

from app.models.cv_document import StructuredCV

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


def stem(token: str) -> str:
    token = norm(token).strip(".-/")
    return token[:-1] if len(token) > 3 and token.endswith("s") else token


def tokens(text: str) -> set[str]:
    return {stem(m.group()) for m in _WORD.finditer(text or "")}


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
            terms.add(stem(word))
    return terms


@dataclass(frozen=True)
class ClaimLexicon:
    """The word lists a claim check works with. A domain may bring its own."""

    seniority: re.Pattern[str] = field(default=_SENIORITY)
    skill_terms: Callable[[str], set[str]] = field(default=skill_like_terms)


GENERIC_LEXICON = ClaimLexicon()


@dataclass(frozen=True)
class Problem:
    """Something a draft claims that the CV does not back up."""

    kind: Literal["numbers", "seniority", "skills"]
    terms: tuple[str, ...]  # as written in the draft


def faithfulness_problems(
    text: str, source: str, job_terms: set[str], lexicon: ClaimLexicon = GENERIC_LEXICON
) -> list[Problem]:
    """
    What `text` claims that `source` does not back up: new numbers, new
    seniority words, and job-description skills the source never mentions.
    """
    problems: list[Problem] = []

    new_numbers = set(_NUMBER.findall(text)) - set(_NUMBER.findall(source))
    if new_numbers:
        problems.append(Problem("numbers", tuple(sorted(new_numbers))))

    source_seniority = {norm(m.group()) for m in lexicon.seniority.finditer(source)}
    seniority = {
        norm(m.group()): m.group() for m in lexicon.seniority.finditer(text)
        if norm(m.group()) not in source_seniority
    }
    if seniority:
        problems.append(Problem("seniority", tuple(sorted(seniority.values(), key=str.casefold))))

    spelled = {stem(m.group()): m.group() for m in _WORD.finditer(text or "")}
    new_skills = (tokens(text) & job_terms) - tokens(source)
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
