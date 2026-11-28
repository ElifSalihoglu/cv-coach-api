"""
What an agent is given, how it describes itself, and what the orchestration records.

The General agent chooses a specialist from the posting and the target position alone; the CV is
not part of that decision.
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
class AgentCard:
    """
    Who an agent is, as the registry and the router see it.

    `routing_cues` are example job titles of this agent's field. They live with the agent and
    are shown to the General agent in the description of the agent's tool, so a new agent
    brings its own and no central occupation list exists. The general agent has none.
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
    method: Literal["override", "delegation", "fallback"]
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
