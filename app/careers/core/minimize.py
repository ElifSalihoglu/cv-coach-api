"""
Data minimization: the one place that decides which parts of a CV may reach a model.

An agent assembles its model input from these building blocks and from nothing else,
so what leaves the system is reviewable in one file. The CV's name, email, phone,
location, links, dates and education are not offered here at all; a field that is not
a building block here cannot be sent by accident.
"""
import re
from typing import Any

from app.models.cv_document import CVCertification, CVEducation, CVExperience, CVProject


def experience_payload(exp: CVExperience, *, positions: bool) -> dict[str, Any]:
    """A role as the model sees it: id, title, employer and its bullets (no dates)."""
    bullets = (
        [{"id": b.id, "position": i, "text": b.text} for i, b in enumerate(exp.bullets, start=1)]
        if positions
        else [{"id": b.id, "text": b.text} for b in exp.bullets]
    )
    return {"id": exp.id, "title": exp.title, "employer": exp.employer, "bullets": bullets}


def project_payload(project: CVProject) -> dict[str, Any]:
    return {"id": project.id, "name": project.name, "description": project.description}


# ---- education and certifications: professional evidence without personal identifiers
#
# A degree or a certificate name is what a recruiter needs; the school, the issuer, dates,
# licence or credential numbers, contact details and links identify the person and are not
# offered here at all. Free text that stays (a degree line, a note under it) goes through
# `strip_identifiers` first.

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_PHONE = re.compile(r"\+?\d[\d ()\-]{7,}\d")
_NUMBER_ID = re.compile(r"\b[A-Za-z]{0,5}[-/#:]?\d{4,}\b")  # years, licence and credential numbers
_LEFTOVER = re.compile(r"\(\s*[-–—,;:/]?\s*\)|\[\s*\]")
_NO_LABEL = re.compile(r"\b(?:no|nr|num|number|numara\w*)\.?\s*[:#]?\s*(?=$|[\s,;)\]])", re.IGNORECASE)


def strip_identifiers(text: str) -> str:
    """Remove emails, links, phone numbers, years and long numbers (licence and credential ids)."""
    for pattern in (_EMAIL, _URL, _PHONE, _NUMBER_ID):
        text = pattern.sub(" ", text or "")
    text = _LEFTOVER.sub(" ", text)
    text = _NO_LABEL.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    return re.sub(r"^[\s,;:\-–—/]+|[\s,;:\-–—/]+$", "", text)


def education_payload(edu: CVEducation) -> dict[str, Any]:
    """The degree and its note. Not the school, not the dates."""
    return {"id": edu.id, "degree": strip_identifiers(edu.degree), "details": strip_identifiers(edu.details)}


def certification_payload(cert: CVCertification) -> dict[str, Any]:
    """The certificate or licence name only. Not the issuer, the date or any number."""
    return {"id": cert.id, "name": strip_identifiers(cert.name)}
