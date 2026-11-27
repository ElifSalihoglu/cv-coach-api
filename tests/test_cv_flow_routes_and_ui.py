from fastapi.testclient import TestClient

from app.api.dependencies import get_llm_client
from app.main import app
from tests.test_cv_parse_and_render import CV_TEXT, PARSED


class FakeLLM:
    def __init__(self):
        self.calls = 0

    async def generate(self, system_prompt, user_content, output_model):
        self.calls += 1
        return PARSED


def _client(monkeypatch, llm):
    monkeypatch.setitem(app.dependency_overrides, get_llm_client, lambda: llm)
    return TestClient(app)


def test_parse_route_returns_structured_cv_with_ids(monkeypatch):
    llm = FakeLLM()
    with _client(monkeypatch, llm) as client:
        response = client.post("/v1/cv/parse", json={"cv_text": CV_TEXT})

    assert response.status_code == 200
    body = response.json()
    assert body["cv"]["experiences"][0]["id"] == "exp1"
    assert body["cv"]["experiences"][0]["bullets"][0]["id"] == "exp1.b1"
    assert llm.calls == 1
