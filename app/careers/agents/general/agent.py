"""
GeneralAgent: the one entry point of the system.

Two separate responsibilities:

- `handle(case, llm)`: orchestration. Ask the router who should answer, delegate to that
  specialist (found through the registry), and if a specialist breaks, answer itself. Model
  errors are not retried with another agent: they reach the caller unchanged. It records who
  answered (`Orchestration.runs`, `provenance`). It does no routing and no model work itself.
- `analyze(case, llm)`: its own analysis of any occupation, through the same `AgentEngine` as
  every specialist, with the General profile.

It knows specialists only through the registry, so adding a domain changes none of this.
"""
import logging
import time

from app.careers.agents.general.profile import GENERAL_CARD, GENERAL_PROFILE
from app.careers.core.base_agent import BaseCareerAgent
from app.careers.core.engine import DEFAULT_ENGINE, AgentEngine
from app.careers.core.state import (
    AgentRun, CareerCase, Orchestration, OrchestrationError, RoutingDecision, RoutingSignals,
)
from app.careers.registry import AgentRegistry, name_key
from app.careers.router import DefaultRouter
from app.logging_utils import log_event
from app.models.coaching import CoachResult
from app.services.cv_coach import ContentGenerator
from app.services.llm_client import LLMError

logger = logging.getLogger("app.orchestrator")  # unchanged log name, so existing log filters keep working


def _provenance(result: CoachResult, agent_id: str) -> dict[str, str]:
    ids = [s.id for s in result.suggestions] + [q.id for q in result.questions] + [t.id for t in result.tracks]
    return {item_id: agent_id for item_id in ids}


class GeneralAgent:
    card = GENERAL_CARD

    def __init__(
        self, registry: AgentRegistry, router: DefaultRouter | None = None,
        engine: AgentEngine = DEFAULT_ENGINE,
    ) -> None:
        if registry.has(self.card.id) or any(
            name_key(c.domain) == name_key(self.card.domain) for c in registry.cards()
        ):
            raise ValueError("The registry holds specialists only; it must not contain the general agent.")
        self._registry = registry
        self._router = router or DefaultRouter(self.card)
        self._engine = engine

    # ------------------------------------------------------------ its own analysis

    async def analyze(self, case: CareerCase, llm: ContentGenerator) -> CoachResult:
        return await self._engine.run(GENERAL_PROFILE, case, llm)

    # ------------------------------------------------------------ orchestration

    async def handle(self, case: CareerCase, llm: ContentGenerator) -> Orchestration:
        routing = self._router.route(
            RoutingSignals.from_case(case), self._registry, override=case.domain_override)
        outcome = Orchestration(case=case, routing=routing)

        agent = self if routing.primary == self.card.id else self._registry.get(routing.primary)
        run, result, failure = await self._run_agent(agent, case, llm)
        outcome.runs.append(run)
        if failure is None:
            outcome.result, outcome.provenance = result, _provenance(result, agent.card.id)
            return outcome

        if isinstance(failure, LLMError):
            # The provider is the problem; another agent would meet the same one. Same errors as before.
            raise failure
        if agent is self:
            raise OrchestrationError("The general agent failed.")
        return await self._answer_instead(outcome, failed_id=agent.card.id, llm=llm)

    async def _run_agent(
        self, agent: BaseCareerAgent, case: CareerCase, llm: ContentGenerator
    ) -> tuple[AgentRun, CoachResult | None, Exception | None]:
        started = time.perf_counter()
        try:
            result = await agent.analyze(case, llm)
        except Exception as exc:  # recorded here; what to do about it is decided in `handle`
            code = exc.reason_code if isinstance(exc, LLMError) else "agent_error"
            run = AgentRun(agent_id=agent.card.id, status="failed", error_code=code,
                           duration_ms=round((time.perf_counter() - started) * 1000))
            log_event(logger, logging.WARNING, "coach_agent_run", agent=run.agent_id,
                      status="failed", reason=code, duration_ms=run.duration_ms)
            return run, None, exc
        run = AgentRun(agent_id=agent.card.id, status="ok",
                       duration_ms=round((time.perf_counter() - started) * 1000))
        log_event(logger, logging.INFO, "coach_agent_run", agent=run.agent_id,
                  status="ok", duration_ms=run.duration_ms)
        return run, result, None

    async def _answer_instead(
        self, outcome: Orchestration, failed_id: str, llm: ContentGenerator
    ) -> Orchestration:
        """A specialist broke (not the model): the general agent answers instead."""
        outcome.routing = RoutingDecision(
            primary=self.card.id, method="fallback", confidence="low",
            reasons=(*outcome.routing.reasons, f"agent_failed:{failed_id}"),
        )
        run, result, failure = await self._run_agent(self, outcome.case, llm)
        outcome.runs.append(run)
        if failure is not None:
            if isinstance(failure, LLMError):
                raise failure
            raise OrchestrationError("No agent could produce a result.")
        outcome.result, outcome.provenance = result, _provenance(result, self.card.id)
        return outcome
