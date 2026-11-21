from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.models.schemas import CVOptimizeRequest, CVOptimizeResponse
from app.services.cv_coach import CVCoach, OpenAICVCoach
from app.services.llm_client import (
    LLMClient,
    LLMOutputError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from app.services.openai_setup import create_openai_client, get_openai_model

router = APIRouter(prefix="/v1/cv")


@lru_cache
def get_cv_coach() -> CVCoach | None:
    """Build the coach once; return None when no API key is configured."""
    openai_client = create_openai_client()
    if openai_client is None:
        return None
    return OpenAICVCoach(LLMClient(openai_client=openai_client, model=get_openai_model()))


@router.post("/optimize", response_model=CVOptimizeResponse)
async def optimize_cv(
    request: CVOptimizeRequest,
    coach: Annotated[CVCoach | None, Depends(get_cv_coach)],
) -> CVOptimizeResponse:
    if coach is None:
        raise HTTPException(status_code=503, detail="CV coach is unavailable.")

    try:
        return await coach.optimize(request)
    except LLMTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMOutputError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc