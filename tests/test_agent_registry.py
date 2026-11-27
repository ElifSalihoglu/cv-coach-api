"""AgentRegistry (specialists only): registering, discovering and refusing bad agents. No model involved."""

import pytest

from app.careers.agents.general import GENERAL_AGENT, GENERAL_CARD
from app.careers.agents.it import IT_AGENT
from app.careers.assembly import build_default_registry, build_orchestrator
from app.careers.orchestrator import CareerOrchestrator
from app.careers.registry import (
    AgentRegistry,
    DuplicateAgentError,
    InvalidAgentError,
    UnknownAgentError,
    UnknownDomainError,
)
from tests.toy_agents import career_agent


def test_the_default_registry_holds_the_it_specialist_and_not_the_general_agent():
    registry = build_default_registry()
    assert [c.id for c in registry.cards()] == ["it"]
    assert registry.get("it") is IT_AGENT
    assert not registry.has(GENERAL_CARD.id)
    assert isinstance(build_orchestrator(llm=None), CareerOrchestrator)  # the orchestrator owns the registry


def test_cards_carry_id_domain_version_capabilities_and_a_description():
    for card in [*build_default_registry().cards(), GENERAL_CARD]:
        assert card.id and card.domain and card.description and card.version
        assert {"suggestions", "choose_focus", "questions"} <= set(card.capabilities)


def test_a_duplicate_id_or_domain_is_refused():
    registry = AgentRegistry([career_agent("legal", "Legal")])
    with pytest.raises(DuplicateAgentError):
        registry.register(career_agent("legal", "Something else"))
    with pytest.raises(DuplicateAgentError):
        registry.register(career_agent("law", "  legal "))  # the same domain, spacing and case aside
    assert len(registry) == 1


def test_the_orchestrator_refuses_a_registry_that_contains_it_by_id_or_by_domain():
    with pytest.raises(ValueError):
        CareerOrchestrator(AgentRegistry([career_agent("general", "Something")]), GENERAL_AGENT, llm=None)
    with pytest.raises(ValueError):
        CareerOrchestrator(AgentRegistry([career_agent("generalist", "general  career")]), GENERAL_AGENT, llm=None)


@pytest.mark.parametrize(
    "bad",
    [
        career_agent("Legal", "Legal"),  # id must be lowercase
        career_agent("1legal", "Legal"),  # must start with a letter
        career_agent("legal", "   "),  # a domain is required
        career_agent("legal", "Legal", "Lawyer"),  # cues are lowercase
        career_agent("legal", "Legal", "  "),  # no empty cue
    ],
)
def test_a_malformed_agent_is_refused(bad):
    with pytest.raises(InvalidAgentError):
        AgentRegistry().register(bad)


def test_unknown_agent_and_unknown_domain_are_reported_not_guessed():
    registry = build_default_registry()
    with pytest.raises(UnknownAgentError):
        registry.get("plumbing")
    with pytest.raises(UnknownDomainError) as caught:
        registry.resolve("Plumbing")
    assert caught.value.available == ["it"]


def test_a_specialist_is_found_by_id_or_by_name_whatever_the_case():
    registry = build_default_registry()
    assert registry.resolve("IT").id == "it"
    assert registry.resolve("information  technology").id == "it"
