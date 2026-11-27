"""
Structured CV models.

StructuredCV is the single source for the preview and the PDF. The parsed CV
(ParsedCV) comes from the model without ids; our own code assigns the stable
ids, so a rewritten bullet can always be traced back to its source bullet and
its employer.
"""
from typing import Annotated, List

from pydantic import BaseModel, ConfigDict, Field


class CVBullet(BaseModel):
    id: str = Field(..., description="Stable id such as 'exp1.b2'.")
    text: str


class CVExperience(BaseModel):
    id: str = Field(..., description="Stable id such as 'exp1'.")
    employer: str = ""
    title: str = ""
    start: str = ""
    end: str = ""
    location: str = ""
    bullets: List[CVBullet] = Field(default_factory=list)


class CVEducation(BaseModel):
    id: str = Field(..., description="Stable id such as 'edu1'.")
    school: str = ""
    degree: str = ""
    start: str = ""
    end: str = ""
    details: str = Field("", description="Thesis, publication or other note under the degree.")


class CVProject(BaseModel):
    id: str = Field(..., description="Stable id such as 'proj1'.")
    name: str = ""
    description: str = ""


class CVCertification(BaseModel):
    id: str = Field(..., description="Stable id such as 'cert1'.")
    name: str = ""
    issuer: str = ""
    date: str = ""


class StructuredCV(BaseModel):
    """Everything that ends up in the CV. Missing values stay empty strings."""

    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    links: List[str] = Field(default_factory=list)
    summary: str = ""
    experiences: List[CVExperience] = Field(default_factory=list)
    education: List[CVEducation] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    projects: List[CVProject] = Field(default_factory=list)
    certifications: List[CVCertification] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)


# ---- what the model returns when parsing (no ids, no invention) ----


class ParsedExperience(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    employer: str = ""
    title: str = ""
    start: str = ""
    end: str = ""
    location: str = ""
    bullets: List[Annotated[str, Field(min_length=1)]] = Field(default_factory=list)


class ParsedEducation(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    school: str = ""
    degree: str = ""
    start: str = ""
    end: str = ""
    details: str = ""


class ParsedProject(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = ""
    description: str = ""


class ParsedCertification(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = ""
    issuer: str = ""
    date: str = ""


class ParsedCV(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    links: List[str] = Field(default_factory=list)
    summary: str = ""
    experiences: List[ParsedExperience] = Field(default_factory=list)
    education: List[ParsedEducation] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    projects: List[ParsedProject] = Field(default_factory=list)
    certifications: List[ParsedCertification] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)


class CVParseRequest(BaseModel):
    cv_text: str = Field(..., min_length=1, description="Text extracted from the CV.")


class CVParseResponse(BaseModel):
    cv: StructuredCV
    warnings: List[str] = Field(
        default_factory=list,
        description="Fields the user should check against the original text.",
    )
