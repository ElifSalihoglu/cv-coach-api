from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.dependencies import get_llm_client, llm_http_error
from app.careers.agents.general import GENERAL_CARD
from app.careers.assembly import build_default_registry, build_orchestrator
from app.careers.core.state import CareerCase, CoachResponse, OrchestrationError
from app.careers.orchestrator import CareerOrchestrator
from app.careers.registry import UnknownDomainError
from app.models.coaching import (
    ApplyRequest,
    ApplyResult,
    CheckRequest,
    CheckResult,
    CoachRequest,
)
from app.services.coach_apply import DecisionError, UnconfirmedClaims, apply_decisions, check_text
from app.services.llm_client import LLMOutputError, LLMTimeoutError, LLMUnavailableError

router = APIRouter(prefix="/v1/coach")


@lru_cache
def get_orchestrator() -> CareerOrchestrator | None:
    """Build the orchestrator once; return None when no API key is configured."""
    llm = get_llm_client()
    return build_orchestrator(llm) if llm is not None else None


def _decision_error(exc: DecisionError) -> HTTPException:
    detail: dict = {"code": exc.code, "message": exc.message, "item_id": exc.item_id}
    if isinstance(exc, UnconfirmedClaims):
        detail["claims"] = [claim.model_dump() for claim in exc.claims]
    return HTTPException(status_code=422, detail=detail)


class AgentInfo(BaseModel):
    id: str
    domain: str
    description: str


@router.get("/agents", response_model=list[AgentInfo])
def agents() -> list[AgentInfo]:
    """The agents a request may name in `domain`: every registered specialist, then the General agent."""
    cards = [*build_default_registry().cards(), GENERAL_CARD]
    return [AgentInfo(id=c.id, domain=c.domain, description=c.description) for c in cards]


@router.post("/analyze", response_model=CoachResponse)
async def analyze(
    request: CoachRequest,
    orchestrator: Annotated[CareerOrchestrator | None, Depends(get_orchestrator)],
) -> CoachResponse:
    """
    Without a focus the answer is either suggestions (a clear posting) or the tracks to choose from;
    with a focus it is suggestions. The General agent decides with tool calling which specialists to
    call, at most two (or `domain` names one agent and skips that decision); `meta` says who answered.
    """
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="The career coach is unavailable.")
    try:
        case = CareerCase(
            request.cv,
            request.job_title,
            request.job_description,
            request.focus.strip(),
            domain_override=request.domain.strip(),
            career_goal=request.career_goal.strip(),
        )
        return (await orchestrator.run(case)).response()
    except UnknownDomainError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": exc.code,
                "message": str(exc),
                "available": exc.available,
            },
        ) from exc
    except OrchestrationError as exc:
        raise HTTPException(status_code=500, detail="The career coach could not produce a result.") from exc
    except (LLMTimeoutError, LLMUnavailableError, LLMOutputError) as exc:
        raise llm_http_error(exc) from exc


@router.post("/check", response_model=CheckResult)
def check(request: CheckRequest) -> CheckResult:
    """What a text the user wrote says that their CV does not. No model call."""
    try:
        return check_text(request)
    except DecisionError as exc:
        raise _decision_error(exc) from exc


@router.post("/apply", response_model=ApplyResult)
def apply(request: ApplyRequest) -> ApplyResult:
    """The CV with the accepted suggestions applied. No model call; the main CV is untouched."""
    try:
        return apply_decisions(request)
    except DecisionError as exc:
        raise _decision_error(exc) from exc
