"""
Resolving an explicit agent request. A caller that names a domain (`domain` in the request) gets that
agent, or an error if no agent covers it; an explicit request is never guessed at.

Without an override nothing here decides: the General agent itself chooses whether to hand the posting
to a specialist (see `delegation.py`).
"""

import logging

from app.careers.core.state import AgentCard, RoutingDecision
from app.careers.registry import AgentRegistry, UnknownDomainError, name_key
from app.logging_utils import log_event

logger = logging.getLogger("app.router")


class DefaultRouter:
    """`general` is the general agent's card: naming it by id or domain selects it."""

    def __init__(self, general: AgentCard) -> None:
        self._general = general

    def route(self, override: str, registry: AgentRegistry) -> RoutingDecision:
        decision = RoutingDecision(
            primary=self._resolve(override, registry), method="override", confidence="high", reasons=("override",)
        )
        log_event(logger, logging.INFO, "coach_routed", agent=decision.primary, method=decision.method)
        return decision

    def _resolve(self, name: str, registry: AgentRegistry) -> str:
        if name_key(name) in (name_key(self._general.id), name_key(self._general.domain)):
            return self._general.id
        try:
            return registry.resolve(name).id
        except UnknownDomainError as exc:
            raise UnknownDomainError(name, sorted([*exc.available, self._general.id])) from None
