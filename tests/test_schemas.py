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
