"""AgentRegistry (specialists only): registering, discovering and refusing bad agents. No model involved."""
import pytest

from app.careers.agents.general import GENERAL_CARD, GeneralAgent
from app.careers.agents.it import IT_AGENT
from app.careers.registry import (
    AgentRegistry, DuplicateAgentError, InvalidAgentError, UnknownAgentError, UnknownDomainError,
)
from app.careers.assembly import build_default_general_agent, build_default_registry
from tests.toy_agents import specialist


def test_the_default_registry_holds_the_it_specialist_and_not_the_general_agent():
    registry = build_default_registry()
    assert [c.id for c in registry.cards()] == ["it"]
    assert registry.get("it") is IT_AGENT
    assert not registry.has(GENERAL_CARD.id)
    assert isinstance(build_default_general_agent(), GeneralAgent)  # the entry point owns the registry


def test_cards_carry_id_domain_version_capabilities_and_a_description():
    for card in [*build_default_registry().cards(), GENERAL_CARD]:
        assert card.id and card.domain and card.description and card.version
        assert {"suggestions", "choose_focus", "questions"} <= set(card.capabilities)


def test_a_duplicate_id_or_domain_is_refused():
    registry = AgentRegistry([specialist("legal", "Legal")])
    with pytest.raises(DuplicateAgentError):
        registry.register(specialist("legal", "Something else"))
    with pytest.raises(DuplicateAgentError):
        registry.register(specialist("law", "  legal "))  # the same domain, spacing and case aside
    assert len(registry) == 1


def test_the_general_agent_refuses_a_registry_that_contains_it_by_id_or_by_domain():
    with pytest.raises(ValueError):
        GeneralAgent(AgentRegistry([specialist("general", "Something")]))
    with pytest.raises(ValueError):
        GeneralAgent(AgentRegistry([specialist("generalist", "general  career")]))


@pytest.mark.parametrize("bad", [
    specialist("Legal", "Legal"),                  # id must be lowercase
    specialist("1legal", "Legal"),                 # must start with a letter
    specialist("legal", "   "),                    # a domain is required
    specialist("legal", "Legal", "Lawyer"),        # cues are lowercase
    specialist("legal", "Legal", "  "),            # no empty cue
])
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
