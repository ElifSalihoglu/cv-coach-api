"""POST /v1/cv/extract-text: PDF, DOCX and TXT to plain text, with no model call."""

import io

import pytest
from docx import Document
from fastapi.testclient import TestClient

from app.api.dependencies import get_llm_client
from app.main import app
from app.models.cv_document import CVBullet, CVExperience, StructuredCV
from app.services.cv_extract import MAX_CV_BYTES
from app.services.cv_render import render_pdf

TURKISH_LINE = "Elçin Yıldız — Yazılım Mühendisi, İstanbul, Şişli"


@pytest.fixture
def client(monkeypatch) -> TestClient:
    def boom():
        raise AssertionError("extract-text must not request a model client")

    monkeypatch.setitem(app.dependency_overrides, get_llm_client, boom)
    return TestClient(app)


def _upload(client, name: str, data: bytes):
    return client.post("/v1/cv/extract-text", files={"file": (name, data)})


def test_txt_keeps_turkish_characters(client):
    response = _upload(client, "cv.txt", TURKISH_LINE.encode("utf-8"))
    assert response.status_code == 200
    assert response.json() == {"filename": "cv.txt", "text": TURKISH_LINE}


def test_txt_in_legacy_turkish_encoding(client):
    response = _upload(client, "old.txt", TURKISH_LINE.encode("cp1254"))
    assert response.json()["text"] == TURKISH_LINE


def test_docx_paragraphs(client):
    doc = Document()
    doc.add_paragraph(TURKISH_LINE)
    doc.add_paragraph("Python, FastAPI")
    buffer = io.BytesIO()
    doc.save(buffer)
    response = _upload(client, "cv.DOCX", buffer.getvalue())
    assert response.status_code == 200
    assert TURKISH_LINE in response.json()["text"]
    assert "Python, FastAPI" in response.json()["text"]


def test_pdf_text(client):
    cv = StructuredCV(
        name="Elçin Yıldız",
        summary="Uçtan uca makine öğrenmesi mühendisi.",
        experiences=[
            CVExperience(
                id="exp1",
                employer="Örnek A.Ş.",
                title="Mühendis",
                bullets=[CVBullet(id="exp1.b1", text="Şirket içi araçlar geliştirdi.")],
            )
        ],
    )
    response = _upload(client, "cv.pdf", render_pdf(cv))
    assert response.status_code == 200
    text = " ".join(response.json()["text"].split())
    assert "Elçin Yıldız" in text and "Uçtan uca makine öğrenmesi" in text


def test_unsupported_type_is_415(client):
    response = _upload(client, "cv.png", b"\x89PNG")
    assert response.status_code == 415
    assert response.json()["detail"]["code"] == "unsupported_file_type"


def test_too_large_is_413(client):
    response = _upload(client, "cv.txt", b"a" * (MAX_CV_BYTES + 10))
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "file_too_large"


@pytest.mark.parametrize("name", ["broken.pdf", "broken.docx"])
def test_damaged_file_is_422_with_message(client, name):
    response = _upload(client, name, b"this is not a real document")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "unreadable_file"


def test_missing_file_is_422(client):
    assert client.post("/v1/cv/extract-text").status_code == 422
