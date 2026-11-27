"""
What an agent is given, how it describes itself, and what the orchestration records.

Routing reads `RoutingSignals`, which has no CV field: the CV cannot influence which agent
is chosen, by construction.
"""

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

from app.models.coaching import CoachResult
from app.models.cv_document import StructuredCV


@dataclass(frozen=True)
class CareerCase:
    """One coaching request: the confirmed CV, the posting, the chosen track and routing hints."""

    cv: StructuredCV
    job_title: str
    job_description: str
    focus: str = ""
    domain_override: str = ""  # an agent id or domain name the caller asks for; "" = route automatically
    career_goal: str = ""  # the position the user is aiming at, if they said


@dataclass(frozen=True)
class RoutingSignals:
    """The only inputs of routing: the posting and the target position. Never the CV."""

    job_title: str
    job_description: str
    career_goal: str = ""

    @classmethod
    def from_case(cls, case: CareerCase) -> "RoutingSignals":
        return cls(case.job_title, case.job_description, case.career_goal)


@dataclass(frozen=True)
class AgentCard:
    """
    Who an agent is, as the registry and the router see it.

    `routing_cues` are the few phrases this agent itself claims as a clear sign of its
    field (matched in the job title or target position). They live with the agent, so a
    new agent brings its own cues and no central occupation list exists. The general agent
    has none: it is chosen when nothing else clearly fits.
    """

    id: str  # "it"
    domain: str  # "Information technology"
    description: str  # also what a router reads to tell agents apart
    version: str = "1"
    capabilities: tuple[str, ...] = ("suggestions", "choose_focus", "questions")
    routing_cues: tuple[str, ...] = ()


# ------------------------------------------------------------ orchestration records


class OrchestrationError(Exception):
    """No agent could produce a result. `code` is safe to show."""

    code = "orchestration_failed"


class RoutingDecision(BaseModel):
    primary: str  # agent id
    secondary: tuple[str, ...] = ()  # further agents consulted; empty while one agent answers
    method: Literal["override", "rules", "fallback"]
    confidence: Literal["high", "low"]
    reasons: tuple[str, ...] = ()  # short codes, e.g. "title_cue:software engineer"


class AgentRun(BaseModel):
    agent_id: str
    status: Literal["ok", "failed"]
    duration_ms: int = 0
    error_code: str = ""  # a safe code, never exception text


class CoachMeta(BaseModel):
    """Routing and provenance, returned next to the coaching result (additive, optional)."""

    routing: RoutingDecision
    runs: list[AgentRun] = Field(default_factory=list)
    provenance: dict[str, str] = Field(default_factory=dict)  # item id -> agent id that produced it


class CoachResponse(CoachResult):
    """The API answer: the coaching result plus where it came from."""

    meta: CoachMeta | None = None


@dataclass
class Orchestration:
    case: CareerCase
    routing: RoutingDecision
    runs: list[AgentRun] = field(default_factory=list)
    result: CoachResult | None = None
    provenance: dict[str, str] = field(default_factory=dict)

    def response(self) -> CoachResponse:
        assert self.result is not None
        return CoachResponse(
            **self.result.model_dump(),
            meta=CoachMeta(routing=self.routing, runs=self.runs, provenance=self.provenance),
        )
