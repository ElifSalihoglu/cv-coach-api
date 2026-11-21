from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.models.schemas import CVOptimizeRequest, CVOptimizeResponse
from app.services.cv_coach import CVCoach

router = APIRouter(prefix="/v1/cv")


def get_cv_coach() -> CVCoach | None:
    return None


@router.post("/optimize", response_model=CVOptimizeResponse)
async def optimize_cv(
    request: CVOptimizeRequest,
    coach: Annotated[CVCoach | None, Depends(get_cv_coach)],
) -> CVOptimizeResponse:
    if coach is None:
        raise HTTPException(status_code=503, detail="CV coach is unavailable.")

    return await coach.optimize(request)