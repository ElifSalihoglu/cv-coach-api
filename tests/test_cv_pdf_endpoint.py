"""POST /v1/cv/render-pdf: renders the CV the client sends, with no model call."""

import io
import re
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.api.dependencies import get_llm_client
from app.main import app

SUMMARY_A = "Automation engineer who turns manual workflows into reliable LLM pipelines."
SUMMARY_B = "Machine learning engineer focused on training, evaluating and serving models."


def _cv(summary: str, bullet: str) -> dict:
    return {
        "name": "Elçin Yıldız",
        "email": "elcin@example.com",
        "summary": summary,
        "experiences": [
            {
                "id": "exp1",
                "employer": "Örnek Teknoloji",
                "title": "Yazılım Mühendisi",
                "start": "2021",
                "end": "2024",
                "bullets": [{"id": "exp1.b1", "text": bullet}],
            }
        ],
        "skills": ["Python", "FastAPI"],
    }


def _pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    return re.sub(r"\s+", " ", " ".join(p.extract_text() or "" for p in reader.pages))


@pytest.fixture
def client(monkeypatch) -> TestClient:
    def boom():
        raise AssertionError("render-pdf must not request a model client")

    monkeypatch.setitem(app.dependency_overrides, get_llm_client, boom)
    return TestClient(app)


def test_each_pdf_contains_only_its_own_summary(client):
    a = client.post(
        "/v1/cv/render-pdf",
        json={
            "cv": _cv(SUMMARY_A, "Built an invoice triage agent."),
            "company": "Acme",
            "job_title": "AI Automation Engineer",
        },
    )
    b = client.post(
        "/v1/cv/render-pdf",
        json={
            "cv": _cv(SUMMARY_B, "Shipped a ranking model to production."),
            "company": "Globex",
            "job_title": "Machine Learning Engineer",
        },
    )
    assert a.status_code == b.status_code == 200
    assert a.headers["content-type"] == "application/pdf"
    text_a, text_b = _pdf_text(a.content), _pdf_text(b.content)
    assert SUMMARY_A in text_a and SUMMARY_B not in text_a
    assert SUMMARY_B in text_b and SUMMARY_A not in text_b
    assert "Elçin Yıldız" in text_a and "Yazılım Mühendisi" in text_a


def test_filename_keeps_turkish_characters(client):
    response = client.post(
        "/v1/cv/render-pdf",
        json={
            "cv": _cv(SUMMARY_A, "x"),
            "company": "Şeker Ürünleri A.Ş.",
            "job_title": "Veri Mühendisi",
        },
    )
    header = response.headers["content-disposition"]
    assert header.startswith("attachment;")
    encoded = re.search(r"filename\*=UTF-8''([^;]+)", header).group(1)
    assert unquote(encoded) == "Elçin_Yıldız_Şeker_Ürünleri_A_Ş_Veri_Mühendisi.pdf"
    ascii_name = re.search(r'filename="([^"]+)"', header).group(1)
    assert ascii_name.isascii() and ascii_name.endswith(".pdf")


def test_invalid_body_is_422(client):
    assert client.post("/v1/cv/render-pdf", json={"company": "x"}).status_code == 422


def test_cors_allows_vite_origin_and_exposes_filename(client):
    response = client.post(
        "/v1/cv/render-pdf",
        json={"cv": _cv(SUMMARY_A, "x")},
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "content-disposition" in response.headers["access-control-expose-headers"].lower()
