"""
What the General agent sends to the model.

Like the IT input it carries no name, contact details, links or dates. Unlike it, it also
carries education and certifications, because for many professions a degree, a licence or a
certificate is the evidence. They are projected through `core.minimize`: the degree and the
certificate name only, with the school, the issuer, dates and any number removed.
"""

from typing import Any

from app.careers.agents.general.rules import offers_choice
from app.careers.core.minimize import (
    certification_payload,
    education_payload,
    experience_payload,
    project_payload,
)
from app.models.cv_document import StructuredCV


def general_input(cv: StructuredCV, job_title: str, job_description: str, focus: str) -> dict[str, Any]:
    return {
        "job_title": job_title,
        "job_description": job_description,
        "posting_offers_choice": offers_choice(job_description),
        "focus": focus,
        "candidate": {
            "summary": cv.summary,
            "skills": cv.skills,
            "languages": cv.languages,
            "experiences": [experience_payload(exp, positions=True) for exp in cv.experiences],
            "projects": [project_payload(p) for p in cv.projects],
            "education": [education_payload(e) for e in cv.education],
            "certifications": [certification_payload(c) for c in cv.certifications],
        },
    }
