"""What the IT agent sends to the model. Unchanged by the move to agents; a test pins it."""
from typing import Any

from app.careers.agents.it.rules import offers_choice
from app.careers.core.minimize import experience_payload, project_payload
from app.models.cv_document import StructuredCV


def coach_input(
    cv: StructuredCV, job_title: str, job_description: str, focus: str
) -> dict[str, Any]:
    """The payload sent to the model. No name, contact details, dates or education."""
    return {
        "job_title": job_title,
        "job_description": job_description,
        "posting_offers_choice": offers_choice(job_description),
        "focus": focus,
        "candidate": {
            "summary": cv.summary,
            "skills": cv.skills,
            "experiences": [experience_payload(exp, positions=True) for exp in cv.experiences],
            "projects": [project_payload(p) for p in cv.projects],
        },
    }
