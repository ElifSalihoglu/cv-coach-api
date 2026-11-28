"""What the Healthcare agent sends to the model: work history plus degrees and certificates."""

from typing import Any

from app.careers.agents.healthcare.rules import offers_choice
from app.careers.core.minimize import certification_payload, education_payload, experience_payload
from app.models.cv_document import StructuredCV


def healthcare_input(cv: StructuredCV, job_title: str, job_description: str, focus: str) -> dict[str, Any]:
    """No name, contact details, links or dates; certificates and degrees without issuer, school or numbers."""
    return {
        "job_title": job_title,
        "job_description": job_description,
        "posting_offers_choice": offers_choice(job_description),
        "focus": focus,
        "candidate": {
            "summary": cv.summary,
            "skills": cv.skills,
            "experiences": [experience_payload(exp, positions=True) for exp in cv.experiences],
            "education": [education_payload(e) for e in cv.education],
            "certifications": [certification_payload(c) for c in cv.certifications],
        },
    }
