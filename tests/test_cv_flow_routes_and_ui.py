from fastapi.testclient import TestClient

from app.api.v1.routes_cv import get_cv_coach
from app.main import app
from app.models.cv_document import CVParseResponse
from app.services.cv_parsing import assign_ids
from tests.test_cv_parse_and_render import CV_TEXT, PARSED


class FakeCoach:
    def __init__(self):
        self.parse_calls = 0

    async def parse(self, cv_text):
        self.parse_calls += 1
        return CVParseResponse(cv=assign_ids(PARSED), warnings=[])


def _client(monkeypatch, coach):
    monkeypatch.setitem(app.dependency_overrides, get_cv_coach, lambda: coach)
    return TestClient(app)


def test_parse_route_returns_structured_cv_with_ids(monkeypatch):
    coach = FakeCoach()
    with _client(monkeypatch, coach) as client:
        response = client.post("/v1/cv/parse", json={"cv_text": CV_TEXT})

    assert response.status_code == 200
    body = response.json()
    assert body["cv"]["experiences"][0]["id"] == "exp1"
    assert body["cv"]["experiences"][0]["bullets"][0]["id"] == "exp1.b1"
    assert coach.parse_calls == 1
