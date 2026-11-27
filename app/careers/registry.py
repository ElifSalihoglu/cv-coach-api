"""
The specialist agents the system knows about. The general agent is not one of them: the orchestrator
holds it separately, as the agent for whatever no specialist clearly claims.

Adding a domain means registering one more specialist (see `assembly.py`); the orchestrator, the
router and the engine only ever ask the registry, so none of them changes.
"""

import re
from typing import Iterable

from app.careers.core.agent import CareerAgent
from app.careers.core.state import AgentCard

_ID = re.compile(r"[a-z][a-z0-9_-]{0,31}")


class RegistryError(Exception):
    """Base class; `code` is safe to show and to log."""

    code = "registry_error"


class InvalidAgentError(RegistryError):
    code = "invalid_agent"


class DuplicateAgentError(RegistryError):
    code = "duplicate_agent"


class UnknownAgentError(RegistryError):
    code = "unknown_agent"


class UnknownDomainError(RegistryError):
    """A caller asked for a domain no agent covers."""

    code = "unknown_domain"

    def __init__(self, name: str, available: list[str]) -> None:
        super().__init__(f"No agent for domain {name!r}.")
        self.name = name
        self.available = available


def name_key(text: str) -> str:
    """Case and spacing aside: how ids and domain names are compared."""
    return " ".join(text.casefold().split())


class AgentRegistry:
    def __init__(self, agents: Iterable[CareerAgent] = ()) -> None:
        self._agents: dict[str, CareerAgent] = {}
        for agent in agents:
            self.register(agent)

    # ------------------------------------------------------------ registering

    def register(self, agent: CareerAgent) -> None:
        card = agent.card
        if not _ID.fullmatch(card.id):
            raise InvalidAgentError(f"Agent id {card.id!r} must be lowercase letters, digits, - or _.")
        if not card.domain.strip():
            raise InvalidAgentError(f"Agent {card.id!r} has no domain.")
        if any(not cue.strip() or cue != cue.casefold() for cue in card.routing_cues):
            raise InvalidAgentError(f"Agent {card.id!r} has an empty or non-lowercase routing cue.")
        if card.id in self._agents:
            raise DuplicateAgentError(f"Agent id {card.id!r} is already registered.")
        for other in self._agents.values():
            if name_key(other.card.domain) == name_key(card.domain):
                raise DuplicateAgentError(f"Domain {card.domain!r} is already covered by {other.card.id!r}.")
        self._agents[card.id] = agent

    # ------------------------------------------------------------ discovering

    def __len__(self) -> int:
        return len(self._agents)

    def has(self, agent_id: str) -> bool:
        return agent_id in self._agents

    def get(self, agent_id: str) -> CareerAgent:
        try:
            return self._agents[agent_id]
        except KeyError:
            raise UnknownAgentError(f"No agent with id {agent_id!r}.") from None

    def cards(self) -> list[AgentCard]:
        return [a.card for a in self._agents.values()]

    def resolve(self, name: str) -> AgentCard:
        """The specialist a caller named, by id or by domain name (case and spacing aside)."""
        wanted = name_key(name)
        for card in self.cards():
            if wanted in (name_key(card.id), name_key(card.domain)):
                return card
        raise UnknownDomainError(name, sorted(self._agents))
