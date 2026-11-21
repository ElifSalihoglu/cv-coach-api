from typing import Protocol

from app.models.schemas import CVOptimizeRequest, CVOptimizeResponse


class CVCoach(Protocol):
    async def optimize(self, request: CVOptimizeRequest) -> CVOptimizeResponse:
        ...