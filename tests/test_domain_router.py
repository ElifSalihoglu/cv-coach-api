"""DefaultRouter: an explicit agent request. No model involved; without one the General agent decides."""

import pytest

from app.careers.agents.general import GENERAL_CARD
from app.careers.assembly import build_default_registry
from app.careers.registry import UnknownDomainError
from app.careers.router import DefaultRouter


def route(override: str):
    return DefaultRouter(GENERAL_CARD).route(override, build_default_registry())


def test_an_override_is_resolved_by_id_or_domain_name():
    assert route("general").primary == "general"
    assert route(" General  Career ").primary == "general"
    decision = route("Information Technology")
    assert (decision.primary, decision.method, decision.confidence, decision.reasons) == (
        "it",
        "override",
        "high",
        ("override",),
    )


def test_an_unknown_override_is_an_error_not_a_guess():
    with pytest.raises(UnknownDomainError) as caught:
        route("plumbing")
    assert caught.value.available == [
        "finance",
        "general",
        "healthcare",
        "hr",
        "it",
    ]  # the general agent is a valid target too
