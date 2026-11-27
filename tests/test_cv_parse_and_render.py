"""
CV parsing and rendering with one synthetic Turkish CV.

The PDF is read back as text to check that facts survive the round trip (Turkish characters,
employers, dates) and that every bullet stays under its own employer. Parsing uses a fake model.
"""

import asyncio
import io
import re

from pypdf import PdfReader

from app.models.cv_document import ParsedCV, StructuredCV
from app.services.cv_parsing import assign_ids, check_against_text, parse_cv_text
from app.services.cv_render import cv_filename, render_pdf

CV_TEXT = """Çağla Şahin
cagla@example.com +90 555 000 00 00 İstanbul
ÖZET
Veri odaklı yazılım mühendisi.
DENEYİM
Kıdemli Veri Mühendisi - Acme Teknoloji (Mart 2021 - Devam)
- Python ve Airflow ile günlük veri hatları geliştirdim.
- Raporlama panelleri için SQL sorguları yazdım, yükleme süresini %30 azalttım.
Yazılım Mühendisi - Beta Yazılım (2018 - 2021)
- Müşteri portalı için REST API'leri geliştirdim.
- Üç kişilik ekiple Docker tabanlı dağıtım kurdum.
EĞİTİM
İstanbul Teknik Üniversitesi - Bilgisayar Mühendisliği (2014 - 2018)
Bitirme tezi: Akış verisinde anomali tespiti.
Yayın: Çağla Şahin, "Gerçek zamanlı veri kalitesi", Ulusal Yazılım Sempozyumu 2018.
SEÇİLMİŞ PROJELER
Veri Kalitesi Paneli
Açık kaynak bir panel; şema değişikliklerini otomatik raporlar.
Python ve SQL ile geliştirildi.
SERTİFİKALAR
Google Professional Data Engineer - Google Cloud - 2022
BECERİLER
Python, SQL, Docker, Airflow
DİLLER
İngilizce - C1, Almanca - B1
"""

A1 = "Python ve Airflow ile günlük veri hatları geliştirdim."
A2 = "Raporlama panelleri için SQL sorguları yazdım, yükleme süresini %30 azalttım."
B1 = "Müşteri portalı için REST API'leri geliştirdim."
B2 = "Üç kişilik ekiple Docker tabanlı dağıtım kurdum."

PARSED = ParsedCV(
    name="Çağla Şahin",
    email="cagla@example.com",
    phone="+90 555 000 00 00",
    location="İstanbul",
    summary="Veri odaklı yazılım mühendisi.",
    experiences=[
        {
            "employer": "Acme Teknoloji",
            "title": "Kıdemli Veri Mühendisi",
            "start": "Mart 2021",
            "end": "Devam",
            "bullets": [A1, A2],
        },
        {"employer": "Beta Yazılım", "title": "Yazılım Mühendisi", "start": "2018", "end": "2021", "bullets": [B1, B2]},
    ],
    education=[
        {
            "school": "İstanbul Teknik Üniversitesi",
            "degree": "Bilgisayar Mühendisliği",
            "start": "2014",
            "end": "2018",
            "details": "Bitirme tezi: Akış verisinde anomali tespiti.\n"
            'Yayın: Çağla Şahin, "Gerçek zamanlı veri kalitesi", '
            "Ulusal Yazılım Sempozyumu 2018.",
        }
    ],
    skills=["Python", "SQL", "Docker", "Airflow"],
    projects=[
        {
            "name": "Veri Kalitesi Paneli",
            "description": "Açık kaynak bir panel; şema değişikliklerini otomatik raporlar.\n"
            "Python ve SQL ile geliştirildi.",
        }
    ],
    certifications=[{"name": "Google Professional Data Engineer", "issuer": "Google Cloud", "date": "2022"}],
    languages=["İngilizce - C1", "Almanca - B1"],
)


class FakeLLM:
    async def generate(self, system_prompt, user_content, output_model):
        assert output_model is ParsedCV
        return PARSED


def _flat_pdf_text(cv: StructuredCV) -> str:
    reader = PdfReader(io.BytesIO(render_pdf(cv)))
    return re.sub(r"\s+", " ", "\n".join(p.extract_text() or "" for p in reader.pages))


# ---- parsing


def test_parse_assigns_stable_ids_and_finds_everything_in_the_text():
    response = asyncio.run(parse_cv_text(FakeLLM(), CV_TEXT))

    assert response.warnings == []
    cv = response.cv
    assert [e.id for e in cv.experiences] == ["exp1", "exp2"]
    assert [b.id for b in cv.experiences[1].bullets] == ["exp2.b1", "exp2.b2"]
    assert [e.id for e in cv.education] == ["edu1"]


def test_parse_is_clean_when_extra_sections_are_in_the_text():
    response = asyncio.run(parse_cv_text(FakeLLM(), CV_TEXT))

    assert response.warnings == []
    cv = response.cv
    assert [p.id for p in cv.projects] == ["proj1"]
    assert [c.id for c in cv.certifications] == ["cert1"]
    assert cv.languages == ["İngilizce - C1", "Almanca - B1"]
    assert "Bitirme tezi" in cv.education[0].details


def test_parse_warns_about_extra_fields_missing_from_the_text():
    cv = assign_ids(PARSED)
    cv.projects[0].description = "Uydurma açıklama."
    cv.certifications[0].issuer = "Uydurma Kurum"
    cv.languages = ["Japonca - N1"]
    warnings = check_against_text(cv, CV_TEXT)

    assert any("proj1 description" in w for w in warnings)
    assert any("cert1 issuer" in w for w in warnings)
    assert any("Japonca" in w for w in warnings)


def test_parse_warns_when_value_is_not_in_the_text_or_missing():
    cv = assign_ids(PARSED)
    cv.experiences[0].employer = "Uydurma A.Ş."
    cv.experiences[1].start = ""

    warnings = check_against_text(cv, CV_TEXT)

    assert any("exp1 employer" in w and "Uydurma" in w for w in warnings)
    assert any("exp2: start is empty" in w for w in warnings)


# ---- rendering


def test_the_pdf_keeps_every_fact_with_turkish_characters():
    text = _flat_pdf_text(assign_ids(PARSED))

    assert "Çağla Şahin" in text and "cagla@example.com" in text
    assert "Acme Teknoloji" in text and "Beta Yazılım" in text
    assert "Kıdemli Veri Mühendisi" in text and "Yazılım Mühendisi" in text
    assert "Mart 2021" in text and "2018" in text
    assert "İstanbul Teknik Üniversitesi" in text


def test_bullets_stay_under_their_own_employer_even_when_reordered():
    cv = assign_ids(PARSED)
    first = cv.experiences[0]
    reordered = cv.model_copy(
        update={"experiences": [first.model_copy(update={"bullets": list(reversed(first.bullets))}), cv.experiences[1]]}
    )

    text = _flat_pdf_text(reordered)
    acme, beta, end = text.index("Acme Teknoloji"), text.index("Beta Yazılım"), text.index("PROJECTS")
    acme_part, beta_part = text[acme:beta], text[beta:end]

    assert "Airflow" in acme_part and "SQL" in acme_part
    assert "Airflow" not in beta_part and "SQL" not in beta_part
    assert "REST API" in beta_part and "Docker" in beta_part
    assert acme_part.index("SQL") < acme_part.index("Airflow")  # the reordered bullets come out reordered


EXTRA_FACTS = [
    "Veri Kalitesi Paneli",
    "şema değişikliklerini otomatik raporlar.",
    "Python ve SQL ile geliştirildi.",
    "Bitirme tezi: Akış verisinde anomali tespiti.",
    "Ulusal Yazılım Sempozyumu 2018.",
    "Google Professional Data Engineer",
    "Google Cloud",
    "İngilizce - C1",
    "Almanca - B1",
]


def test_projects_languages_certifications_and_thesis_reach_the_pdf():
    pdf_text = _flat_pdf_text(assign_ids(PARSED))

    for fact in EXTRA_FACTS:
        assert fact in pdf_text, fact
    # The thesis stays under the degree, before the next section.
    assert pdf_text.index("Bitirme tezi") > pdf_text.index("İstanbul Teknik")
    assert pdf_text.index("Bitirme tezi") < pdf_text.index("CERTIFICATIONS")


def test_filename_has_candidate_company_and_position():
    cv = assign_ids(PARSED)

    assert cv_filename(cv, "Gamma A.Ş.", "Data Engineer") == "Çağla_Şahin_Gamma_A_Ş_Data_Engineer.pdf"
    assert cv_filename(cv, "Delta Ltd", "Backend Developer") == "Çağla_Şahin_Delta_Ltd_Backend_Developer.pdf"
    unsafe = cv_filename(cv, "A/B", "../x")
    assert "/" not in unsafe and ".." not in unsafe


def test_long_cv_breaks_pages_and_keeps_every_bullet():
    cv = assign_ids(PARSED)
    template = cv.experiences[0].bullets[0]
    cv.experiences[0].bullets = [
        template.model_copy(update={"id": f"exp1.b{i}", "text": f"Madde {i}: " + "uzun açıklama " * 12})
        for i in range(1, 41)
    ]

    reader = PdfReader(io.BytesIO(render_pdf(cv)))
    text = re.sub(r"\s+", " ", "\n".join(p.extract_text() or "" for p in reader.pages))

    assert len(reader.pages) >= 2
    assert all(f"Madde {i}:" in text for i in range(1, 41))


def test_the_pdf_prints_the_sections_in_the_order_the_ui_preview_shows_them():
    # frontend/src/CvPreview.test.tsx checks the same order on the preview side
    text = _flat_pdf_text(assign_ids(PARSED))
    headings = ["SUMMARY", "EXPERIENCE", "PROJECTS", "EDUCATION", "CERTIFICATIONS", "SKILLS", "LANGUAGES"]
    positions = [text.index(h) for h in headings]
    assert positions == sorted(positions)
