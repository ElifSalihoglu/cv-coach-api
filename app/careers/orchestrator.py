"""
CareerOrchestrator: route a case, delegate it to one agent, and fall back to the general agent.

It does no analysis itself. The router decides who should answer (`DefaultRouter`), the agent does
the work (on the shared `AgentEngine`), and the orchestrator records who answered. Model errors are
not retried with another agent: they reach the caller unchanged. Any other agent failure is answered
by the general agent once. It knows specialists only through the registry, so adding a domain
changes none of this.
"""

import logging
import time

from app.careers.core.agent import CareerAgent
from app.careers.core.state import (
    AgentRun,
    CareerCase,
    Orchestration,
    OrchestrationError,
    RoutingDecision,
    RoutingSignals,
)
from app.careers.registry import AgentRegistry, name_key
from app.careers.router import DefaultRouter
from app.logging_utils import log_event
from app.models.coaching import CoachResult
from app.services.llm_client import ContentGenerator, LLMError

logger = logging.getLogger("app.orchestrator")


def _provenance(result: CoachResult, agent_id: str) -> dict[str, str]:
    ids = [s.id for s in result.suggestions] + [q.id for q in result.questions] + [t.id for t in result.tracks]
    return {item_id: agent_id for item_id in ids}


class CareerOrchestrator:
    """`registry` holds the specialists; `general` answers what no specialist clearly claims."""

    def __init__(self, registry: AgentRegistry, general: CareerAgent, llm: ContentGenerator) -> None:
        if registry.has(general.card.id) or any(
            name_key(c.domain) == name_key(general.card.domain) for c in registry.cards()
        ):
            raise ValueError("The registry holds specialists only; it must not contain the general agent.")
        self._registry = registry
        self._general = general
        self._llm = llm
        self._router = DefaultRouter(general.card)

    async def run(self, case: CareerCase) -> Orchestration:
        routing = self._router.route(RoutingSignals.from_case(case), self._registry, override=case.domain_override)
        outcome = Orchestration(case=case, routing=routing)

        agent = self._general if routing.primary == self._general.card.id else self._registry.get(routing.primary)
        run, result, failure = await self._run_agent(agent, case)
        outcome.runs.append(run)
        if failure is None:
            outcome.result, outcome.provenance = result, _provenance(result, agent.card.id)
            return outcome

        if isinstance(failure, LLMError):
            # The provider is the problem; another agent would meet the same one.
            raise failure
        if agent is self._general:
            raise OrchestrationError("The general agent failed.")
        return await self._answer_with_general(outcome, failed_id=agent.card.id)

    async def _run_agent(
        self, agent: CareerAgent, case: CareerCase
    ) -> tuple[AgentRun, CoachResult | None, Exception | None]:
        started = time.perf_counter()
        try:
            result = await agent.analyze(case, self._llm)
        except Exception as exc:  # recorded here; what to do about it is decided in `run`
            code = exc.reason_code if isinstance(exc, LLMError) else "agent_error"
            run = AgentRun(
                agent_id=agent.card.id,
                status="failed",
                error_code=code,
                duration_ms=round((time.perf_counter() - started) * 1000),
            )
            log_event(
                logger,
                logging.WARNING,
                "coach_agent_run",
                agent=run.agent_id,
                status="failed",
                reason=code,
                duration_ms=run.duration_ms,
            )
            return run, None, exc
        run = AgentRun(agent_id=agent.card.id, status="ok", duration_ms=round((time.perf_counter() - started) * 1000))
        log_event(logger, logging.INFO, "coach_agent_run", agent=run.agent_id, status="ok", duration_ms=run.duration_ms)
        return run, result, None

    async def _answer_with_general(self, outcome: Orchestration, failed_id: str) -> Orchestration:
        outcome.routing = RoutingDecision(
            primary=self._general.card.id,
            method="fallback",
            confidence="low",
            reasons=(*outcome.routing.reasons, f"agent_failed:{failed_id}"),
        )
        run, result, failure = await self._run_agent(self._general, outcome.case)
        outcome.runs.append(run)
        if failure is not None:
            if isinstance(failure, LLMError):
                raise failure
            raise OrchestrationError("No agent could produce a result.")
        outcome.result, outcome.provenance = result, _provenance(result, self._general.card.id)
        return outcome
