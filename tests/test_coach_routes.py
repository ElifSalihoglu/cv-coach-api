"""The coach over HTTP with a fake model, including the whole decide-and-download flow."""
import io
import re

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.api.v1 import routes_coach
from app.api.v1.routes_coach import get_job_coach
from app.evals.coach_fixture import CV, JOB_DESCRIPTION, JOB_TITLE
from app.main import app
from app.services.job_coach import ITCareerCoach
from tests.coach_scenarios import AI_SUMMARY, FakeLLM, ai_output, python_output, tracks_output

BODY = {"cv": CV.model_dump(), "job_title": JOB_TITLE, "job_description": JOB_DESCRIPTION}


@pytest.fixture
def llm(monkeypatch):
    fake = FakeLLM(tracks_output(), ai_output(), python_output())
    monkeypatch.setitem(app.dependency_overrides, get_job_coach, lambda: ITCareerCoach(fake))
    return fake


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def pdf_text(content: bytes) -> str:
    return re.sub(r"\s+", " ", " ".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(content)).pages))


def test_without_an_api_key_the_coach_is_503(monkeypatch, client):
    monkeypatch.setitem(app.dependency_overrides, get_job_coach, lambda: None)
    assert client.post("/v1/coach/analyze", json=BODY).status_code == 503


def test_analyze_returns_the_choice_then_suggestions_for_the_chosen_focus(llm, client):
    first = client.post("/v1/coach/analyze", json=BODY).json()
    assert first["kind"] == "choose_focus" and [t["name"] for t in first["tracks"]][:2] == ["AI", "Python"]

    second = client.post("/v1/coach/analyze", json={**BODY, "focus": "AI"}).json()
    assert second["kind"] == "suggestions" and second["focus"] == "AI"
    assert len(llm.calls) == 2


def test_deciding_checking_and_downloading_never_call_the_model(monkeypatch, client):
    def boom():
        raise AssertionError("must not touch the model")

    monkeypatch.setattr(routes_coach, "get_job_coach", boom)
    apply = client.post("/v1/coach/apply", json={"cv": CV.model_dump(), "suggestions": [], "decisions": {}})
    check = client.post("/v1/coach/check", json={"cv": CV.model_dump(), "kind": "summary", "text": "Python engineer."})
    assert apply.status_code == 200 and check.status_code == 200


def test_unconfirmed_claims_are_refused_with_the_terms(client):
    response = client.post("/v1/coach/apply", json={
        "cv": CV.model_dump(), "job_description": JOB_DESCRIPTION,
        "suggestions": [{
            "id": "summary", "kind": "summary", "requirement": "x", "level": "required", "sources": [
                {"id": "exp1.b1", "where": "w", "text": "t"}], "support": "direct",
            "before": CV.summary, "after": CV.summary, "rationale": "r", "priority": 1}],
        "decisions": {"summary": {"action": "edit", "text": "Python engineer who runs Kubernetes."}},
    })
    detail = response.json()["detail"]
    assert response.status_code == 422 and detail["code"] == "unconfirmed_claims"
    assert detail["claims"] == [{"kind": "skills", "terms": ["Kubernetes"]}]


def test_accept_one_edit_one_reject_one_and_the_pdf_shows_exactly_that(llm, client):
    client.post("/v1/coach/analyze", json=BODY)  # the posting has four tracks: the user is asked first
    suggestions = client.post("/v1/coach/analyze", json={**BODY, "focus": "AI"}).json()["suggestions"]
    model_calls = len(llm.calls)
    assert model_calls == 2
    assert [s["id"] for s in suggestions] == ["summary", "promote:exp1.b4", "promote:exp1.b2"]
    edited = AI_SUMMARY + " I enjoy mentoring."

    applied = client.post("/v1/coach/apply", json={
        "cv": CV.model_dump(), "suggestions": suggestions, "job_description": JOB_DESCRIPTION,
        "decisions": {
            "promote:exp1.b4": {"action": "accept"},               # accepted
            "summary": {"action": "edit", "text": edited},         # edited
        },                                                         # promote:exp1.b2 is rejected
    }).json()

    final = applied["cv"]
    assert final["summary"] == edited
    assert [b["id"] for b in final["experiences"][0]["bullets"]] == ["exp1.b4", "exp1.b1", "exp1.b2", "exp1.b3", "exp1.b5"]
    assert [c["kind"] for c in applied["changes"]] == ["summary", "moved"]

    pdf = client.post("/v1/cv/render-pdf", json={"cv": final, "company": "Northstar Games", "job_title": "Software Engineer"})
    text = pdf_text(pdf.content)
    b4, b1, b2 = (CV.experiences[0].bullets[i].text for i in (3, 0, 1))
    assert edited in text and CV.summary not in text  # the edited summary replaced the old one
    assert text.index(b4) < text.index(b1) < text.index(b2)  # accepted move; the rejected one did not happen
    assert len(llm.calls) == model_calls  # deciding and downloading made no model call

    # the main CV was only ever a request body; the same one still gives the same original PDF
    original = pdf_text(client.post("/v1/cv/render-pdf", json={"cv": CV.model_dump(), "company": "c", "job_title": "t"}).content)
    assert CV.summary in original and original.index(b1) < original.index(b4)


def test_ai_and_python_focus_bring_different_sources_forward(llm, client):
    client.post("/v1/coach/analyze", json=BODY)  # consumes the tracks answer
    ai = client.post("/v1/coach/analyze", json={**BODY, "focus": "AI"}).json()
    py = client.post("/v1/coach/analyze", json={**BODY, "focus": "Python Backend"}).json()

    ai_sources = {r["id"] for s in ai["suggestions"] for r in s["sources"]}
    py_sources = {r["id"] for s in py["suggestions"] for r in s["sources"]}
    assert "exp1.b1" in ai_sources and "exp1.b4" in ai_sources and "exp2.b4" not in ai_sources
    assert py["suggestions"][0]["sources"][0]["id"] == "exp2.b4" and "exp2.b4" in py_sources
    assert [q["term"] for q in ai["questions"]] == ["Kubernetes"]
    assert [q["term"] for q in py["questions"]] == ["PostgreSQL"]
