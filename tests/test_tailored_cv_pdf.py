"""
Acceptance test: one synthetic CV, two jobs -> two PDFs.

The PDFs are read back as text to check that each file holds its own job's
summary, that employers and dates are untouched, and that every bullet stays
under its own employer. A fake model counts calls, so we can also show that
rendering and re-downloading never reach the model.
"""
import asyncio
import io
import re

import pytest
from PyPDF2 import PdfReader

from app.models.cv_document import ParsedCV, StructuredCV, TailoredContent
from app.models.schemas import MatchedJob
from app.services.cv_coach import OpenAICVCoach
from app.services.cv_parsing import assign_ids, check_against_text
from app.services.cv_render import cv_filename, render_markdown, render_pdf
from app.services.cv_tailoring import build_tailored_cv, model_input
from app.services.job_optimization import optimize_for_jobs

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
    name="Çağla Şahin", email="cagla@example.com", phone="+90 555 000 00 00",
    location="İstanbul", summary="Veri odaklı yazılım mühendisi.",
    experiences=[
        {"employer": "Acme Teknoloji", "title": "Kıdemli Veri Mühendisi",
         "start": "Mart 2021", "end": "Devam", "bullets": [A1, A2]},
        {"employer": "Beta Yazılım", "title": "Yazılım Mühendisi",
         "start": "2018", "end": "2021", "bullets": [B1, B2]},
    ],
    education=[{"school": "İstanbul Teknik Üniversitesi",
                "degree": "Bilgisayar Mühendisliği", "start": "2014", "end": "2018",
                "details": 'Bitirme tezi: Akış verisinde anomali tespiti.\n'
                           'Yayın: Çağla Şahin, "Gerçek zamanlı veri kalitesi", '
                           'Ulusal Yazılım Sempozyumu 2018.'}],
    skills=["Python", "SQL", "Docker", "Airflow"],
    projects=[{"name": "Veri Kalitesi Paneli",
               "description": "Açık kaynak bir panel; şema değişikliklerini otomatik raporlar.\n"
                              "Python ve SQL ile geliştirildi."}],
    certifications=[{"name": "Google Professional Data Engineer",
                     "issuer": "Google Cloud", "date": "2022"}],
    languages=["İngilizce - C1", "Almanca - B1"],
)

DATA_SUMMARY = "Veri hatları ve SQL odağında deneyimli mühendis."
BACKEND_SUMMARY = "REST API ve Docker dağıtımı deneyimi olan yazılım mühendisi."


def _answer(summary, exp1, exp2):
    return TailoredContent(
        summary=summary,
        experiences=[
            {"id": "exp1", "bullets": [{"source_id": i, "text": t} for i, t in exp1]},
            {"id": "exp2", "bullets": [{"source_id": i, "text": t} for i, t in exp2]},
        ],
    )


class FakeLLM:
    """Counts calls and answers per job title; records exactly what it was sent."""

    def __init__(self):
        self.calls = []

    async def generate(self, system_prompt, user_content, output_model=None):
        self.calls.append((output_model, user_content))
        if output_model is ParsedCV:
            return PARSED
        if user_content["job_title"] == "Data Engineer":
            return _answer(
                DATA_SUMMARY,
                [("exp1.b2", "SQL sorguları ve raporlama panelleriyle yükleme süresini %30 azalttım."),
                 ("exp1.b1", "Python ve Airflow ile günlük veri hatlarını geliştirdim.")],
                [("exp2.b1", B1), ("exp2.b2", B2)],
            )
        return _answer(
            BACKEND_SUMMARY,
            [("exp1.b1", A1), ("exp1.b2", A2)],
            [("exp2.b2", "Docker ile üç kişilik ekipte dağıtım kurdum."), ("exp2.b1", B1)],
        )


def _job(title, company, description):
    return MatchedJob(
        title=title, company=company, location="İstanbul",
        source_url=f"https://example.com/{company}",
        job_description=description, status="ready",
    )


def _flat_pdf_text(cv: StructuredCV) -> str:
    reader = PdfReader(io.BytesIO(render_pdf(cv)))
    return re.sub(r"\s+", " ", "\n".join(p.extract_text() or "" for p in reader.pages))


def _tailor_two_jobs():
    llm = FakeLLM()
    cv = assign_ids(PARSED)
    jobs = [
        _job("Data Engineer", "Gamma A.Ş.", "Build data pipelines with SQL and Airflow."),
        _job("Backend Developer", "Delta Ltd", "Build REST APIs and ship services."),
    ]
    results = asyncio.run(optimize_for_jobs(OpenAICVCoach(llm), jobs, [], cv))
    return llm, cv, results


def test_parse_assigns_stable_ids_and_finds_everything_in_the_text():
    response = asyncio.run(OpenAICVCoach(FakeLLM()).parse(CV_TEXT))

    assert response.warnings == []
    cv = response.cv
    assert [e.id for e in cv.experiences] == ["exp1", "exp2"]
    assert [b.id for b in cv.experiences[1].bullets] == ["exp2.b1", "exp2.b2"]
    assert [e.id for e in cv.education] == ["edu1"]


def test_two_jobs_give_two_pdfs_with_own_summary_and_preserved_facts():
    _, _, results = _tailor_two_jobs()
    assert [r.status for r in results] == ["optimized", "optimized"]
    assert all(r.tailoring_warnings == [] for r in results)

    data_text, backend_text = (_flat_pdf_text(r.tailored_cv) for r in results)

    assert DATA_SUMMARY in data_text and BACKEND_SUMMARY not in data_text
    assert BACKEND_SUMMARY in backend_text and DATA_SUMMARY not in backend_text

    for text in (data_text, backend_text):
        # Turkish characters survive the PDF round trip as selectable text.
        assert "Çağla Şahin" in text
        assert "Acme Teknoloji" in text and "Beta Yazılım" in text
        assert "Kıdemli Veri Mühendisi" in text and "Yazılım Mühendisi" in text
        assert "Mart 2021" in text and "2018" in text
        assert "İstanbul Teknik Üniversitesi" in text
        assert "cagla@example.com" in text


def test_bullets_stay_under_their_own_employer_even_when_reordered():
    _, _, results = _tailor_two_jobs()

    for result in results:
        text = _flat_pdf_text(result.tailored_cv)
        acme = text.index("Acme Teknoloji")
        beta = text.index("Beta Yazılım")
        end = text.index("PROJECTS")
        acme_part, beta_part = text[acme:beta], text[beta:end]
        assert "Airflow" in acme_part and "SQL" in acme_part
        assert "Airflow" not in beta_part and "SQL" not in beta_part
        assert "REST API" in beta_part and "Docker" in beta_part

    first = results[0].tailored_cv.experiences
    assert [b.id for b in first[0].bullets] == ["exp1.b2", "exp1.b1"]  # reordered
    assert [b.id for b in first[1].bullets] == ["exp2.b1", "exp2.b2"]
    assert [e.employer for e in first] == ["Acme Teknoloji", "Beta Yazılım"]
    assert [(e.start, e.end) for e in first] == [("Mart 2021", "Devam"), ("2018", "2021")]


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


def test_projects_languages_certifications_and_thesis_reach_preview_and_pdf():
    _, original, results = _tailor_two_jobs()

    for result in results:
        cv = result.tailored_cv
        assert cv.projects == original.projects
        assert cv.certifications == original.certifications
        assert cv.languages == original.languages
        assert cv.education == original.education

        preview = re.sub(r"\s+", " ", render_markdown(cv))
        pdf_text = _flat_pdf_text(cv)
        for fact in EXTRA_FACTS:
            assert fact in preview, fact
            assert fact in pdf_text, fact
        # The thesis stays under the degree, before the next section.
        assert pdf_text.index("Bitirme tezi") > pdf_text.index("İstanbul Teknik")
        assert pdf_text.index("Bitirme tezi") < pdf_text.index("CERTIFICATIONS")


def test_parse_is_clean_when_extra_sections_are_in_the_text():
    response = asyncio.run(OpenAICVCoach(FakeLLM()).parse(CV_TEXT))

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


def test_original_cv_is_untouched_and_identity_is_not_sent_to_the_model():
    llm, original, _ = _tailor_two_jobs()

    assert original == assign_ids(PARSED)
    payload = str([content for _, content in llm.calls])
    for private in ("Çağla", "cagla@example.com", "555", "Mart 2021", "2014"):
        assert private not in payload


def test_preview_and_pdf_download_never_call_the_model_again():
    llm, _, results = _tailor_two_jobs()
    assert len(llm.calls) == 2  # exactly one call per job

    for _ in range(2):  # download twice
        for result in results:
            render_markdown(result.tailored_cv)
            render_pdf(result.tailored_cv)

    assert len(llm.calls) == 2


def test_preview_and_pdf_use_the_same_content():
    _, _, results = _tailor_two_jobs()
    cv = results[0].tailored_cv

    preview = render_markdown(cv)
    pdf_text = _flat_pdf_text(cv)
    for value in (cv.name, cv.summary, "Acme Teknoloji", "Mart 2021",
                  cv.experiences[0].bullets[0].text):
        assert value in preview
        assert value in pdf_text


def test_filename_has_candidate_company_and_position():
    _, _, results = _tailor_two_jobs()
    names = [cv_filename(r.tailored_cv, r.job.company, r.job.title) for r in results]

    assert names == [
        "Çağla_Şahin_Gamma_A_Ş_Data_Engineer.pdf",
        "Çağla_Şahin_Delta_Ltd_Backend_Developer.pdf",
    ]
    unsafe = cv_filename(results[0].tailored_cv, "A/B", "../x")
    assert "/" not in unsafe and ".." not in unsafe


def test_long_cv_breaks_pages_and_keeps_every_bullet():
    cv = assign_ids(PARSED)
    template = cv.experiences[0].bullets[0]
    cv.experiences[0].bullets = [
        template.model_copy(
            update={"id": f"exp1.b{i}", "text": f"Madde {i}: " + "uzun açıklama " * 12}
        )
        for i in range(1, 41)
    ]

    reader = PdfReader(io.BytesIO(render_pdf(cv)))
    text = re.sub(r"\s+", " ", "\n".join(p.extract_text() or "" for p in reader.pages))

    assert len(reader.pages) >= 2
    assert all(f"Madde {i}:" in text for i in range(1, 41))


def test_parse_warns_when_value_is_not_in_the_text_or_missing():
    cv = assign_ids(PARSED)
    cv.experiences[0].employer = "Uydurma A.Ş."
    cv.experiences[1].start = ""

    warnings = check_against_text(cv, CV_TEXT)

    assert any("exp1 employer" in w and "Uydurma" in w for w in warnings)
    assert any("exp2: start is empty" in w for w in warnings)


@pytest.mark.parametrize("rewrite,expected", [
    ("Kubernetes ile günlük veri hatları geliştirdim.", "mentioned Kubernetes"),
    ("Python ve Airflow ile günlük veri hatlarını %50 hızlandırdım.", "the number 50"),
    ("Python ve Airflow ile günlük veri hatlarına liderlik ettim.", "claimed liderlik"),
])
def test_unsupported_rewrite_is_reverted_with_warning(rewrite, expected):
    cv = assign_ids(PARSED)
    content = _answer(
        "Veri odaklı yazılım mühendisi.",
        [("exp1.b1", rewrite), ("exp1.b2", A2)],
        [("exp2.b1", B1), ("exp2.b2", B2)],
    )

    result = build_tailored_cv(
        cv, content, "We use Kubernetes and Python. Senior roles available."
    )

    assert result.cv.experiences[0].bullets[0].text == A1
    assert any(expected in w and "exp1.b1" in w for w in result.warnings)


def test_bullet_from_another_employer_is_rejected():
    cv = assign_ids(PARSED)
    content = _answer(
        "Veri odaklı yazılım mühendisi.",
        [("exp2.b1", B1), ("exp1.b2", A2)],  # exp2's bullet smuggled into exp1
        [("exp2.b1", B1), ("exp2.b2", B2)],
    )

    result = build_tailored_cv(cv, content, "Build APIs.")

    assert result.cv.experiences[0].bullets == cv.experiences[0].bullets
    assert any("exp1" in w and "did not match" in w for w in result.warnings)


def test_summary_with_new_claims_is_reverted_to_the_original():
    cv = assign_ids(PARSED)
    content = _answer(
        "10 yıllık deneyimli Kubernetes uzmanı.",
        [("exp1.b1", A1), ("exp1.b2", A2)],
        [("exp2.b1", B1), ("exp2.b2", B2)],
    )

    result = build_tailored_cv(cv, content, "Kubernetes experience required.")

    assert result.cv.summary == cv.summary
    assert any(w.startswith("Original summary kept") for w in result.warnings)


def test_model_input_has_no_identity_contact_or_dates():
    payload = str(model_input(assign_ids(PARSED), "Data Engineer", "desc"))

    for private in ("Çağla", "cagla@example.com", "555", "Mart 2021", "2014"):
        assert private not in payload
