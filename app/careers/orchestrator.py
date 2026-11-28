"""
CareerOrchestrator: runs one request through the agent hierarchy. It is not an LLM agent.

The General agent is the main agent. Unless the caller names an agent, it runs a bounded loop with
model tool calling (`delegation.py`): it may call a specialist, receive a summary of the result as the
tool message, call another specialist, or stop; with no specialist called it answers the posting
itself. At most `max_specialists` are called, each once. One result is returned as it is; several are
merged by code (`AgentEngine.merge`), which checks every item again. A model that wrote the final text
would bypass the validation gates, so none does. The orchestrator records who answered.

Model errors are not retried with another agent: they reach the caller unchanged. Any other
specialist failure is answered by the General agent once. Every model call of the request goes
through one `BudgetedLLM`. Specialists are known only through the registry, so adding a domain
changes none of this.
"""

import logging
import time

from app.careers.budget import DEFAULT_MAX_MODEL_CALLS, DEFAULT_MAX_SPECIALISTS, BudgetedLLM, BudgetExceeded
from app.careers.core.agent import CareerAgent
from app.careers.core.engine import DEFAULT_ENGINE
from app.careers.core.state import (
    AgentRun,
    CareerCase,
    Orchestration,
    OrchestrationError,
    RoutingDecision,
)
from app.careers.delegation import choose_specialist, summarize, tool_name
from app.careers.registry import AgentRegistry, name_key
from app.careers.router import DefaultRouter
from app.logging_utils import log_event
from app.models.coaching import CoachResult
from app.services.llm_client import ContentGenerator, LLMError, ToolStep

logger = logging.getLogger("app.orchestrator")


def _provenance(result: CoachResult, agent_id: str) -> dict[str, str]:
    ids = [s.id for s in result.suggestions] + [q.id for q in result.questions] + [t.id for t in result.tracks]
    return {item_id: agent_id for item_id in ids}


class CareerOrchestrator:
    """`registry` holds the specialists; `general` answers what no specialist clearly claims."""

    def __init__(
        self,
        registry: AgentRegistry,
        general: CareerAgent,
        llm: ContentGenerator,
        max_model_calls: int = DEFAULT_MAX_MODEL_CALLS,
        max_specialists: int = DEFAULT_MAX_SPECIALISTS,
    ) -> None:
        if registry.has(general.card.id) or any(
            name_key(c.domain) == name_key(general.card.domain) for c in registry.cards()
        ):
            raise ValueError("The registry holds specialists only; it must not contain the general agent.")
        self._registry = registry
        self._general = general
        self._llm = llm
        self._max_model_calls = max_model_calls
        self._max_specialists = max_specialists
        self._router = DefaultRouter(general.card)

    async def run(self, case: CareerCase) -> Orchestration:
        llm = BudgetedLLM(self._llm, self._max_model_calls)
        if not case.domain_override.strip():
            return await self._delegate(case, llm)
        routing = self._router.route(case.domain_override, self._registry)
        agent = self._general if routing.primary == self._general.card.id else self._registry.get(routing.primary)
        outcome = Orchestration(case=case, routing=routing)
        run, result, failure = await self._run_agent(agent, case, llm)
        outcome.runs.append(run)
        if failure is None:
            outcome.result, outcome.provenance = result, _provenance(result, agent.card.id)
            return outcome
        if isinstance(failure, (LLMError, BudgetExceeded)):
            # The provider is the problem (or the budget is spent); another agent would meet the same.
            raise failure
        if agent is self._general:
            raise OrchestrationError("The general agent failed.")
        return await self._answer_with_general(outcome, llm, failed=[agent.card.id])

    async def _delegate(self, case: CareerCase, llm: BudgetedLLM) -> Orchestration:
        """The General agent's loop: call a specialist, read its result, call another or finish."""
        steps: list[ToolStep] = []
        done: list[tuple[CareerAgent, CoachResult]] = []
        failed: list[str] = []
        runs: list[AgentRun] = []
        remaining = self._registry.cards()
        while remaining and len(steps) < self._max_specialists:
            chosen = await choose_specialist(remaining, case, llm, steps)
            if chosen is None:
                break
            agent = self._registry.get(chosen)
            run, result, failure = await self._run_agent(agent, case, llm)
            runs.append(run)
            if isinstance(failure, (LLMError, BudgetExceeded)):
                raise failure
            steps.append(ToolStep(tool_name(agent.card), f"call_{len(steps) + 1}", summarize(chosen, result)))
            remaining = [card for card in remaining if card.id != chosen]
            if failure is not None:
                failed.append(chosen)
                continue
            if result.kind == "suggestions" or not done:
                done.append((agent, result))
            if result.kind != "suggestions":  # the user must choose a focus first: nothing to combine
                break

        called = tuple(f"delegated:{step.name.removeprefix('ask_')}" for step in steps)
        if not done:
            reason = called or ("no_clear_match",)
            routing = RoutingDecision(
                primary=self._general.card.id, method="fallback", confidence="low", reasons=reason
            )
            outcome = Orchestration(case=case, routing=routing, runs=runs)
            if failed:
                return await self._answer_with_general(outcome, llm, failed=failed)
            return await self._answer_with_general(outcome, llm, failed=[])
        if len(done) == 1:
            agent, result = done[0]
            routing = RoutingDecision(primary=agent.card.id, method="delegation", confidence="high", reasons=called)
            return Orchestration(
                case=case, routing=routing, runs=runs, result=result, provenance=_provenance(result, agent.card.id)
            )
        merged, provenance = self._engine_merge(case, done)
        routing = RoutingDecision(primary=self._general.card.id, method="delegation", confidence="high", reasons=called)
        return Orchestration(case=case, routing=routing, runs=runs, result=merged, provenance=provenance)

    def _engine_merge(
        self, case: CareerCase, done: list[tuple[CareerAgent, CoachResult]]
    ) -> tuple[CoachResult, dict[str, str]]:
        parts = [(agent.card.id, agent.profile, result) for agent, result in done]
        return DEFAULT_ENGINE.merge(parts, case, self._general.profile)

    async def _run_agent(
        self, agent: CareerAgent, case: CareerCase, llm: BudgetedLLM
    ) -> tuple[AgentRun, CoachResult | None, Exception | None]:
        started = time.perf_counter()
        try:
            result = await agent.analyze(case, llm)
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

    async def _answer_with_general(self, outcome: Orchestration, llm: BudgetedLLM, failed: list[str]) -> Orchestration:
        """The General agent analyses the posting itself, after no specialist (or one that broke) answered."""
        if failed:
            outcome.routing = RoutingDecision(
                primary=self._general.card.id,
                method="fallback",
                confidence="low",
                reasons=(*outcome.routing.reasons, *(f"agent_failed:{agent_id}" for agent_id in failed)),
            )
        run, result, failure = await self._run_agent(self._general, outcome.case, llm)
        outcome.runs.append(run)
        if failure is not None:
            if isinstance(failure, (LLMError, BudgetExceeded)):
                raise failure
            raise OrchestrationError("No agent could produce a result.")
        outcome.result, outcome.provenance = result, _provenance(result, self._general.card.id)
        return outcome
