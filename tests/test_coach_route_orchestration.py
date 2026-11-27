"""POST /v1/coach/analyze through the General agent: routing hints, `meta`, errors, old clients."""
import pytest
from fastapi.testclient import TestClient

from app.api.v1.routes_coach import get_job_coach
from app.careers.assembly import build_default_general_agent
from app.careers.facade import CoachFacade
from app.evals.coach_fixture import CV, JOB_DESCRIPTION, JOB_TITLE
from app.evals.general_fixtures import NURSE_CV, NURSE_JOB_DESCRIPTION, NURSE_JOB_TITLE
from app.main import app
from tests.coach_scenarios import ai_output
from tests.general_scenarios import nurse_output
from tests.test_coach_regression import RecordingLLM

IT_BODY = {"cv": CV.model_dump(), "job_title": JOB_TITLE, "job_description": JOB_DESCRIPTION, "focus": "AI"}
NURSE_BODY = {"cv": NURSE_CV.model_dump(), "job_title": NURSE_JOB_TITLE, "job_description": NURSE_JOB_DESCRIPTION}


@pytest.fixture
def llm(monkeypatch):
    fake = RecordingLLM(ai_output())
    coach = CoachFacade(build_default_general_agent(), fake)
    monkeypatch.setitem(app.dependency_overrides, get_job_coach, lambda: coach)
    return fake


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_an_old_client_request_without_routing_fields_still_works_and_says_who_answered(llm, client):
    response = client.post("/v1/coach/analyze", json=IT_BODY)
    body = response.json()

    assert response.status_code == 200
    assert body["kind"] == "suggestions" and body["focus"] == "AI"  # the legacy contract
    assert body["meta"]["routing"]["primary"] == "it"
    assert body["meta"]["runs"][0]["status"] == "ok"
    assert body["meta"]["provenance"]["summary"] == "it"


def test_a_posting_outside_it_is_answered_by_the_general_agent(monkeypatch, client):
    fake = RecordingLLM(nurse_output())
    coach = CoachFacade(build_default_general_agent(), fake)
    monkeypatch.setitem(app.dependency_overrides, get_job_coach, lambda: coach)

    body = client.post("/v1/coach/analyze", json=NURSE_BODY).json()
    assert body["meta"]["routing"] == {
        "primary": "general", "secondary": [], "method": "fallback", "confidence": "low", "reasons": ["no_clear_match"]}
    assert [s["id"] for s in body["suggestions"]] == ["summary", "promote:exp1.b2"]


def test_the_optional_domain_forces_an_agent_and_the_career_goal_is_a_routing_hint(llm, client):
    forced = client.post("/v1/coach/analyze", json={**IT_BODY, "domain": "general"}).json()
    assert forced["meta"]["routing"]["method"] == "override" and forced["meta"]["routing"]["primary"] == "general"


def test_the_career_goal_helps_routing(monkeypatch, client):
    fake = RecordingLLM(ai_output())
    coach = CoachFacade(build_default_general_agent(), fake)
    monkeypatch.setitem(app.dependency_overrides, get_job_coach, lambda: coach)
    body = {**IT_BODY, "job_title": "Team Member", "job_description": "Help the team.", "career_goal": "Backend developer"}
    assert client.post("/v1/coach/analyze", json=body).json()["meta"]["routing"]["primary"] == "it"


def test_an_unknown_domain_is_422_with_the_available_ones_and_no_model_call(llm, client):
    response = client.post("/v1/coach/analyze", json={**IT_BODY, "domain": "plumbing"})
    detail = response.json()["detail"]
    assert response.status_code == 422
    assert detail["code"] == "unknown_domain" and detail["available"] == ["general", "it"]
    assert llm.calls == []


def test_too_long_routing_fields_are_rejected(llm, client):
    assert client.post("/v1/coach/analyze", json={**IT_BODY, "domain": "x" * 41}).status_code == 422
    assert client.post("/v1/coach/analyze", json={**IT_BODY, "career_goal": "x" * 201}).status_code == 422
