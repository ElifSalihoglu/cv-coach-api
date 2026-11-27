"""DefaultRouter (owned by the General agent): override, clear matches, unclear postings. No model involved."""
import dataclasses
import inspect

import pytest

from app.careers.core.state import RoutingSignals
from app.careers.agents.general import GENERAL_CARD
from app.careers.assembly import build_default_registry
from app.careers.registry import AgentRegistry, UnknownDomainError
from app.careers.router import DefaultRouter
from tests.fixtures.coach_fixture import CLEAR_JOB_DESCRIPTION, CLEAR_JOB_TITLE, JOB_DESCRIPTION, JOB_TITLE
from tests.fixtures.general_fixtures import (
    MARKETING_JOB_DESCRIPTION, MARKETING_JOB_TITLE, MECH_JOB_DESCRIPTION, MECH_JOB_TITLE,
    NURSE_JOB_DESCRIPTION, NURSE_JOB_TITLE,
)
from tests.toy_agents import specialist


def route(signals: RoutingSignals, registry=None, override=""):
    return DefaultRouter(GENERAL_CARD).route(signals, registry or build_default_registry(), override=override)


def test_the_router_can_not_see_the_cv():
    assert {f.name for f in dataclasses.fields(RoutingSignals)} == {"job_title", "job_description", "career_goal"}
    assert set(inspect.signature(DefaultRouter.route).parameters) == {"self", "signals", "registry", "override"}


@pytest.mark.parametrize("title,description", [
    (JOB_TITLE, JOB_DESCRIPTION),
    (CLEAR_JOB_TITLE, CLEAR_JOB_DESCRIPTION),
    ("Kıdemli Yazılım Geliştirici", "Python ve bulut deneyimi aranıyor."),
    ("Senior Backend Developer (m/f/d)", "Build services."),
])
def test_a_clear_it_title_goes_to_the_it_agent_by_rules(title, description):
    decision = route(RoutingSignals(title, description))
    assert (decision.primary, decision.method, decision.confidence) == ("it", "rules", "high")
    assert decision.reasons and all(r.startswith("title_cue:") for r in decision.reasons)


@pytest.mark.parametrize("title,description", [
    (NURSE_JOB_TITLE, NURSE_JOB_DESCRIPTION),
    (MARKETING_JOB_TITLE, MARKETING_JOB_DESCRIPTION),
    (MECH_JOB_TITLE, MECH_JOB_DESCRIPTION),  # engineering has no agent yet
])
def test_anything_unclear_or_unsupported_goes_to_the_general_agent(title, description):
    decision = route(RoutingSignals(title, description))
    assert (decision.primary, decision.method, decision.confidence) == ("general", "fallback", "low")
    assert decision.reasons == ("no_clear_match",)


def test_the_description_alone_never_settles_a_match():
    # an IT-heavy description under a neutral title is "unclear", not "IT"
    decision = route(RoutingSignals("Team Member", "You are a developer and a backend programmer working in devops."))
    assert decision.primary == "general" and decision.method == "fallback"


def test_cues_match_whole_words_only():
    assert route(RoutingSignals("Retail Assistant", "Help customers.")).primary == "general"  # not "ai" inside "retail"
    assert route(RoutingSignals("Email Marketing Lead", "Newsletters.")).primary == "general"  # not "ai" inside "email"


def test_the_target_position_counts_like_the_title():
    decision = route(RoutingSignals("Team Member", "Help the team.", career_goal="I want to become a backend developer"))
    assert decision.primary == "it" and decision.method == "rules"


def test_a_manual_override_wins_and_is_resolved_by_id_or_domain_name():
    assert route(RoutingSignals(JOB_TITLE, JOB_DESCRIPTION), override="general").primary == "general"
    assert route(RoutingSignals(JOB_TITLE, JOB_DESCRIPTION), override=" General  Career ").primary == "general"
    decision = route(RoutingSignals(NURSE_JOB_TITLE, NURSE_JOB_DESCRIPTION), override="Information Technology")
    assert (decision.primary, decision.method, decision.confidence) == ("it", "override", "high")


def test_an_unknown_override_is_an_error_not_a_guess():
    with pytest.raises(UnknownDomainError) as caught:
        route(RoutingSignals(JOB_TITLE, JOB_DESCRIPTION), override="plumbing")
    assert caught.value.available == ["general", "it"]  # the general agent is a valid target too


def test_two_specialists_claiming_the_title_is_unclear_and_goes_to_the_general_agent():
    registry = build_default_registry()
    registry.register(specialist("embedded", "Embedded systems", "firmware", "developer"))
    decision = route(RoutingSignals("Firmware Developer", "Devices."), registry)
    assert decision.primary == "general" and decision.method == "fallback"


def test_a_new_agent_is_routed_to_by_its_own_cues_with_no_router_change():
    registry = build_default_registry()
    registry.register(specialist("legal", "Legal", "lawyer", "legal counsel"))
    assert route(RoutingSignals("Corporate Legal Counsel", "Contracts."), registry).primary == "legal"
    assert route(RoutingSignals(NURSE_JOB_TITLE, NURSE_JOB_DESCRIPTION), registry).primary == "general"


def test_the_description_can_veto_a_title_match_when_another_agent_fits_it_better():
    registry = AgentRegistry([specialist("a", "Field A", "analyst", "data"),
                              specialist("b", "Field B", "ledger", "audit", "tax")])
    clear = route(RoutingSignals("Analyst", "Reporting."), registry)
    doubtful = route(RoutingSignals("Analyst", "Ledger work, audit trails and tax filings."), registry)
    assert clear.primary == "a" and doubtful.primary == "general"


def test_the_router_only_ever_returns_registered_agents():
    registry = build_default_registry()
    for title, description in [(JOB_TITLE, JOB_DESCRIPTION), (NURSE_JOB_TITLE, NURSE_JOB_DESCRIPTION), ("", "")]:
        decision = route(RoutingSignals(title, description), registry)
        assert registry.has(decision.primary) or decision.primary == GENERAL_CARD.id
