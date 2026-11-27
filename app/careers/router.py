"""
Choosing the agent for a posting. The General agent owns a router and asks it for a decision.

Order: an explicit override, then deterministic rules for clear matches only, then the General
agent itself (it analyses what no specialist clearly claims). The router can only return the
General agent or a specialist in the registry, and its only inputs are the posting, the job
title and the target position (`RoutingSignals`; no CV).

Nothing here lists occupations. The cues come from the registered specialists' own cards.
"""
import logging
import re
from typing import Sequence

from app.careers.core.claims import norm
from app.careers.core.state import AgentCard, RoutingDecision, RoutingSignals
from app.careers.registry import AgentRegistry, UnknownDomainError, name_key
from app.logging_utils import log_event

logger = logging.getLogger("app.router")

_WORD = re.compile(r"[^\W_]+")


def _padded(text: str) -> str:
    """Folded words with single spaces and a space at both ends, so a phrase matches whole words only."""
    return " " + " ".join(_WORD.findall(norm(text))) + " "


def cues_in(text: str, cues: Sequence[str]) -> list[str]:
    haystack = _padded(text)
    return [cue for cue in cues if _padded(cue) in haystack]


class DefaultRouter:
    """`general` is the General agent's card: its id is where an unclear posting goes."""

    def __init__(self, general: AgentCard) -> None:
        self._general = general

    def route(
        self, signals: RoutingSignals, registry: AgentRegistry, *, override: str = ""
    ) -> RoutingDecision:
        if override.strip():
            return self._done(RoutingDecision(
                primary=self._resolve(override, registry), method="override",
                confidence="high", reasons=("override",)))

        decision = self._by_rules(signals, registry)
        if decision is not None:
            return self._done(decision)
        return self._done(RoutingDecision(
            primary=self._general.id, method="fallback", confidence="low", reasons=("no_clear_match",)))

    def _resolve(self, name: str, registry: AgentRegistry) -> str:
        """An explicit request is never guessed at: an unknown domain is an error."""
        if name_key(name) in (name_key(self._general.id), name_key(self._general.domain)):
            return self._general.id
        try:
            return registry.resolve(name).id
        except UnknownDomainError as exc:
            raise UnknownDomainError(name, sorted([*exc.available, self._general.id])) from None

    # ---------------------------------------------------------------- the rules

    def _by_rules(self, signals: RoutingSignals, registry: AgentRegistry) -> RoutingDecision | None:
        """A clear match: exactly one specialist's cue is in the title or the target position."""
        headline = f"{signals.job_title} | {signals.career_goal}"
        hits = {c.id: cues_in(headline, c.routing_cues) for c in registry.cards()}
        matched = {agent_id: found for agent_id, found in hits.items() if found}
        if len(matched) != 1:
            return None  # none: unsupported or unclear; several: interdisciplinary. Not for rules to settle.
        (agent_id, found), = matched.items()
        # The description may only confirm or veto: another agent whose cues fill it more is a doubt.
        mine = len(cues_in(signals.job_description, registry.get(agent_id).card.routing_cues))
        for other in registry.cards():
            if other.id != agent_id and len(cues_in(signals.job_description, other.routing_cues)) > mine:
                return None
        return RoutingDecision(
            primary=agent_id, method="rules", confidence="high",
            reasons=tuple(f"title_cue:{cue}" for cue in found[:3]),
        )

    @staticmethod
    def _done(decision: RoutingDecision) -> RoutingDecision:
        log_event(logger, logging.INFO, "coach_routed", agent=decision.primary,
                  method=decision.method, confidence=decision.confidence)
        return decision
