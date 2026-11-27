import re

from app.models.cv_document import (
    CVBullet,
    CVCertification,
    CVEducation,
    CVExperience,
    CVParseResponse,
    CVProject,
    ParsedCV,
    StructuredCV,
)
from app.prompts.cv_parse import PARSE_CV_SYSTEM_PROMPT
from app.services.llm_client import ContentGenerator

_BULLET_PREFIX = re.compile(r"^[\s\-•*·–—▪●◦]+")


def collapse(text: str) -> str:
    """Lower-case and collapse whitespace so line breaks do not hide a match."""
    return re.sub(r"\s+", " ", text or "").strip().casefold()


def assign_ids(parsed: ParsedCV) -> StructuredCV:
    """Give experiences, bullets and education stable ids: exp1, exp1.b1, edu1."""
    experiences = []
    for i, exp in enumerate(parsed.experiences, start=1):
        exp_id = f"exp{i}"
        experiences.append(
            CVExperience(
                id=exp_id,
                employer=exp.employer,
                title=exp.title,
                start=exp.start,
                end=exp.end,
                location=exp.location,
                bullets=[CVBullet(id=f"{exp_id}.b{j}", text=text) for j, text in enumerate(exp.bullets, start=1)],
            )
        )
    education = [
        CVEducation(
            id=f"edu{i}",
            school=e.school,
            degree=e.degree,
            start=e.start,
            end=e.end,
            details=e.details,
        )
        for i, e in enumerate(parsed.education, start=1)
    ]
    return StructuredCV(
        name=parsed.name,
        email=parsed.email,
        phone=parsed.phone,
        location=parsed.location,
        links=[x for x in parsed.links if x],
        summary=parsed.summary,
        experiences=experiences,
        education=education,
        skills=[x for x in parsed.skills if x],
        projects=[
            CVProject(id=f"proj{i}", name=p.name, description=p.description)
            for i, p in enumerate(parsed.projects, start=1)
        ],
        certifications=[
            CVCertification(id=f"cert{i}", name=c.name, issuer=c.issuer, date=c.date)
            for i, c in enumerate(parsed.certifications, start=1)
        ],
        languages=[x for x in parsed.languages if x],
    )


def check_against_text(cv: StructuredCV, source_text: str) -> list[str]:
    """
    Flag parsed values the user should look at.

    A value that is not found in the extracted text may have been made up by
    the model; a missing employer, title or date is a gap in the parse. Both
    are only warnings: the user decides in the review form.
    """
    haystack = collapse(source_text)
    warnings: list[str] = []

    def not_in_text(value: str) -> bool:
        return bool(value) and collapse(value) not in haystack

    def check(label: str, value: str) -> None:
        if not_in_text(value):
            warnings.append(f"{label}: '{value}' was not found in the CV text.")

    for field in ("name", "email", "phone", "location"):
        check(field, getattr(cv, field))
    check("summary", cv.summary)

    for exp in cv.experiences:
        name = exp.employer or exp.id
        for field in ("employer", "title", "start", "end"):
            value = getattr(exp, field)
            if not value and field in ("employer", "title", "start"):
                warnings.append(f"{exp.id}: {field} is empty; please fill it in.")
            else:
                check(f"{exp.id} {field}", value)
        for bullet in exp.bullets:
            text = _BULLET_PREFIX.sub("", bullet.text)
            if not_in_text(text):
                warnings.append(f"{bullet.id} (under {name}): bullet text differs from the CV text.")

    for edu in cv.education:
        for field in ("school", "degree", "start", "end"):
            check(f"{edu.id} {field}", getattr(edu, field))
        check(f"{edu.id} details", edu.details)
        if not edu.school and not edu.degree:
            warnings.append(f"{edu.id}: school and degree are both empty.")

    for proj in cv.projects:
        check(f"{proj.id} name", proj.name)
        check(f"{proj.id} description", proj.description)
        if not proj.name:
            warnings.append(f"{proj.id}: name is empty; please fill it in.")
    for cert in cv.certifications:
        for field in ("name", "issuer", "date"):
            check(f"{cert.id} {field}", getattr(cert, field))
    for item in (*cv.skills, *cv.languages):
        check("skill/language", item)
    return warnings


async def parse_cv_text(llm: ContentGenerator, cv_text: str) -> CVParseResponse:
    """One model call per uploaded CV; the user reviews the result before it is used."""
    parsed = await llm.generate(
        system_prompt=PARSE_CV_SYSTEM_PROMPT,
        user_content={"cv_text": cv_text},
        output_model=ParsedCV,
    )
    cv = assign_ids(parsed)
    return CVParseResponse(cv=cv, warnings=check_against_text(cv, cv_text))
