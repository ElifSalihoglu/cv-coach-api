from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.models.coaching import (
    ApplyRequest,
    ApplyResult,
    CheckRequest,
    CheckResult,
    CoachRequest,
    CoachResult,
)
from app.services.coach_apply import DecisionError, UnconfirmedClaims, apply_decisions, check_text
from app.services.job_coach import ITCareerCoach
from app.services.llm_client import (
    LLMClient,
    LLMOutputError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from app.services.openai_setup import create_openai_client, get_openai_model

router = APIRouter(prefix="/v1/coach")


@lru_cache
def get_job_coach() -> ITCareerCoach | None:
    """Build the coach once; return None when no API key is configured."""
    openai_client = create_openai_client()
    if openai_client is None:
        return None
    return ITCareerCoach(LLMClient(openai_client=openai_client, model=get_openai_model()))


def _decision_error(exc: DecisionError) -> HTTPException:
    detail: dict = {"code": exc.code, "message": exc.message, "item_id": exc.item_id}
    if isinstance(exc, UnconfirmedClaims):
        detail["claims"] = [claim.model_dump() for claim in exc.claims]
    return HTTPException(status_code=422, detail=detail)


@router.post("/analyze", response_model=CoachResult)
async def analyze(
    request: CoachRequest,
    coach: Annotated[ITCareerCoach | None, Depends(get_job_coach)],
) -> CoachResult:
    """
    One model call. Without a focus the answer is either suggestions (a clear
    posting) or the tracks to choose from; with a focus it is suggestions.
    """
    if coach is None:
        raise HTTPException(status_code=503, detail="The career coach is unavailable.")
    try:
        return await coach.analyze(
            request.cv, request.job_title, request.job_description, request.focus.strip()
        )
    except LLMTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMOutputError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


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
