import pytest
from pydantic import ValidationError

from app.models.schemas import GeneratedCVContent


def test_generated_content_accepts_valid_llm_output():
    raw = {
        "improved_bullets": ["Automated weekly reporting with Python."],
        "summary": "Python developer focused on data automation.",
        "linkedin_headline": "AI Engineer | Python | Data Automation",
    }

    content = GeneratedCVContent.model_validate(raw)

    assert content.improved_bullets == raw["improved_bullets"]
    assert content.summary == raw["summary"]
    assert content.linkedin_headline == raw["linkedin_headline"]


def test_generated_content_rejects_empty_bullet_list():
    raw = {
        "improved_bullets": [],
        "summary": "Python developer focused on data automation.",
        "linkedin_headline": "AI Engineer | Python | Data Automation",
    }

    with pytest.raises(ValidationError):
        GeneratedCVContent.model_validate(raw)


@pytest.mark.parametrize("summary", ["", "   "])
def test_generated_content_rejects_blank_summary(summary):
    raw = {
        "improved_bullets": ["Automated weekly reporting with Python."],
        "summary": summary,
        "linkedin_headline": "AI Engineer | Python | Data Automation",
    }

    with pytest.raises(ValidationError):
        GeneratedCVContent.model_validate(raw)


def _content_with_headline(headline):
    return {
        "improved_bullets": ["Automated weekly reporting with Python."],
        "summary": "Python developer focused on data automation.",
        "linkedin_headline": headline,
    }


def test_generated_content_accepts_headline_at_120_characters():
    headline = "A" * 120

    content = GeneratedCVContent.model_validate(_content_with_headline(headline))

    assert content.linkedin_headline == headline


def test_generated_content_rejects_headline_over_120_characters():
    with pytest.raises(ValidationError):
        GeneratedCVContent.model_validate(_content_with_headline("A" * 121))


@pytest.mark.parametrize("headline", ["", "   "])
def test_generated_content_rejects_blank_headline(headline):
    with pytest.raises(ValidationError):
        GeneratedCVContent.model_validate(_content_with_headline(headline))


@pytest.mark.parametrize(
    "bullets",
    [[""], ["Automated weekly reporting with Python.", "   "]],
)
def test_generated_content_rejects_blank_bullet(bullets):
    raw = {
        "improved_bullets": bullets,
        "summary": "Python developer focused on data automation.",
        "linkedin_headline": "AI Engineer | Python | Data Automation",
    }

    with pytest.raises(ValidationError):
        GeneratedCVContent.model_validate(raw)
