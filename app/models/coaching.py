"""
Models for the IT Career Coach: what the model may say (CoachModelOutput), what
the API returns after our own checks (CoachResult), and the decisions the user
makes about suggestions.

Everything the model returns is only a proposal. Ids and CV text come from the
CV itself, and nothing reaches the user's CV without the user's decision.
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.cv_document import StructuredCV

Level = Literal["required", "preferred"]
Support = Literal["direct", "related"]
Coverage = Literal["strong", "partial", "none"]
SuggestionKind = Literal["promote", "rewrite", "summary"]


# ------------------------------------------------------- what the model returns


class ModelRequirement(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = ""
    quote: str = ""
    level: Level = "required"


class ModelEvidence(BaseModel):
    source_id: str = ""
    why: str = ""


class ModelTrack(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = ""
    quote: str = ""
    summary: str = ""
    evidence: list[ModelEvidence] = Field(default_factory=list)


class ModelSuggestion(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    kind: str = ""
    requirement_quote: str = ""
    level: Level = "required"
    source_ids: list[str] = Field(default_factory=list)
    support: Support = "related"
    after: str = ""  # rewrite and summary only; a promoted bullet keeps its text
    rationale: str = ""
    priority: int = 0  # 1 = most useful for the application


class ModelQuestion(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    requirement_quote: str = ""
    level: Level = "required"
    term: str = ""


class CoachModelOutput(BaseModel):
    mode: Literal["suggestions", "choose_focus"] = "suggestions"
    focus: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    requirements: list[ModelRequirement] = Field(default_factory=list)
    tracks: list[ModelTrack] = Field(default_factory=list)
    suggestions: list[ModelSuggestion] = Field(default_factory=list)
    questions: list[ModelQuestion] = Field(default_factory=list)


# ------------------------------------------------------------ what the API returns


class Requirement(BaseModel):
    text: str
    quote: str
    level: Level


class SourceRef(BaseModel):
    id: str
    where: str  # "Senior Software Engineer — Boğaz Yazılım"
    text: str  # the CV bullet, exactly as written


class Evidence(BaseModel):
    source_id: str
    where: str
    text: str
    why: str


class FocusOption(BaseModel):
    id: str
    name: str
    quote: str
    summary: str
    coverage: Coverage
    evidence: list[Evidence]
    note: str = ""  # said only for what we know from the CV


class Suggestion(BaseModel):
    id: str  # "promote:exp1.b4", "rewrite:exp1.b2", "summary"
    kind: SuggestionKind
    requirement: str  # short quote from the posting
    level: Level
    sources: list[SourceRef]
    support: Support  # "related" = close experience, not the same thing
    before: str  # current wording (promote: the bullet; summary: the summary)
    after: str  # proposed wording (promote: the same bullet)
    position: int | None = None  # promote: current place in its role (1-based)
    rationale: str
    priority: int


class Question(BaseModel):
    id: str  # "ask:kubernetes"
    requirement: str
    level: Level
    term: str
    text: str


class CoachResult(BaseModel):
    kind: Literal["suggestions", "choose_focus"]
    focus: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    requirements: list[Requirement] = Field(default_factory=list)
    tracks: list[FocusOption] = Field(default_factory=list)
    suggestions: list[Suggestion] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list)
    dropped: int = 0  # proposals our checks removed (never their text)
    dropped_reasons: dict[str, int] = Field(default_factory=dict)  # why, as codes


# ------------------------------------------------------------ requests and decisions


class CoachRequest(BaseModel):
    cv: StructuredCV
    job_title: str = Field(..., min_length=1)
    job_description: str = Field(..., min_length=1, max_length=20_000)
    focus: str = Field("", max_length=120, description="Track the user chose, if any.")


class Decision(BaseModel):
    action: Literal["accept", "edit"]
    text: str = ""  # edit only
    confirmed_terms: list[str] = Field(default_factory=list)


class AdditionTarget(BaseModel):
    type: Literal["experience", "project"]
    id: str


class Addition(BaseModel):
    """New experience the user wrote in answer to a question."""

    id: str  # the question id
    target: AdditionTarget
    text: str = Field(..., min_length=1)
    confirmed_terms: list[str] = Field(default_factory=list)


class ApplyRequest(BaseModel):
    cv: StructuredCV  # the confirmed main CV; never modified
    suggestions: list[Suggestion]
    decisions: dict[str, Decision] = Field(default_factory=dict)  # accepted or edited only
    additions: list[Addition] = Field(default_factory=list)
    job_description: str = Field("", max_length=20_000)


class CoachChange(BaseModel):
    kind: Literal["moved", "summary", "rewritten", "moved_rewritten", "added"]
    id: str  # "summary" or a bullet id
    suggestion_id: str = ""
    where: str
    before: str = ""
    after: str = ""
    detail: str = ""
    user_added: bool = False  # the user wrote it or confirmed a new claim


class ApplyResult(BaseModel):
    cv: StructuredCV
    changes: list[CoachChange]


class CheckRequest(BaseModel):
    cv: StructuredCV
    job_description: str = Field("", max_length=20_000)
    kind: Literal["rewrite", "summary", "add"]
    source_id: str = ""  # rewrite: the bullet being reworded
    text: str = Field(..., min_length=1)


class Claim(BaseModel):
    kind: Literal["numbers", "seniority", "skills"]
    terms: list[str]


class CheckResult(BaseModel):
    claims: list[Claim]  # what the text says that the CV does not back up
    message: str = ""
