"""
Number-like words in a job posting are not skills; numeric claims are checked on their own.

Regression: a source summary "3+ years" and a posting saying "what takes 3 years
elsewhere" made the literal "3" a "skill not in the CV", so a harmless summary
was reverted ("skills not in the CV: 3").
"""
import pytest

from app.models.cv_document import StructuredCV, TailoredContent
from app.prompts.cv_templates import TAILOR_CV_SYSTEM_PROMPT
from app.services.cv_tailoring import build_tailored_cv, skill_like_terms

JOB = "We ship fast: what takes 3 years elsewhere takes months here. You know Python and APIs."
SOURCE_SUMMARY = "Python engineer with 3+ years of experience building APIs."


def _tailor(draft: str, job: str = JOB, cv: StructuredCV | None = None):
    cv = cv or StructuredCV(name="T", summary=SOURCE_SUMMARY, skills=["Python"])
    return build_tailored_cv(cv, TailoredContent(summary=draft, experiences=[]), job)


def test_a_number_in_the_posting_is_not_treated_as_a_skill():
    # Reproduction: this posting used to flag "3" as a skill.
    assert "3" not in skill_like_terms(JOB)
    result = _tailor("Python engineer with 3 years of experience building APIs.")

    assert result.warnings == []
    assert result.cv.summary == "Python engineer with 3 years of experience building APIs."


@pytest.mark.parametrize("text", ["3", "3+", "24/7", "2.5", "10-12", "2024"])
def test_words_without_letters_are_never_skills(text):
    assert skill_like_terms(f"You bring {text} of drive, plus Python.") == {"python"}


@pytest.mark.parametrize("name", ["S3", "EC2", "C#", "Web3", "Python3"])
def test_technical_names_with_digits_are_still_skills(name):
    assert name.casefold() in skill_like_terms(f"Experience with {name} is needed.")


@pytest.mark.parametrize("claimed,number", [("5 years", "5"), ("10 years", "10"), ("3 to 5 years", "5")])
def test_a_changed_number_of_years_is_still_caught(claimed, number):
    result = _tailor(f"Python engineer with {claimed} of experience building APIs.")

    assert result.cv.summary == SOURCE_SUMMARY
    assert result.warnings == [
        f"Original summary kept. The draft used the number {number}, which is not in your CV."
    ]


def test_a_technical_name_with_a_digit_that_is_not_in_the_cv_is_still_caught():
    job = JOB + " You work with S3 and Lambda."
    result = _tailor("Python engineer with 3+ years of S3 experience.", job)

    assert result.cv.summary == SOURCE_SUMMARY
    assert result.warnings == [
        "Original summary kept. The draft mentioned S3, which we couldn't verify in your CV."
    ]


def test_a_technical_name_with_a_digit_that_is_in_the_cv_is_allowed():
    cv = StructuredCV(name="T", summary="Python engineer who builds APIs and stores data in S3.", skills=["Python", "S3"])
    job = JOB + " You work with S3 and Lambda."
    assert _tailor("Python engineer who builds APIs on S3.", job, cv).warnings == []


def test_the_user_is_told_which_unverified_term_was_flagged():
    result = _tailor(
        "Python and Kubernetes engineer with 3+ years of experience.",
        JOB + " You run services on Kubernetes (optional).",
    )
    assert result.warnings == [
        "Original summary kept. The draft mentioned Kubernetes, which we couldn't verify in your CV."
    ]


MULTI_TRACK_JOB = (
    "We hire for four tracks: TypeScript, Python, DevOps (Kubernetes, Terraform) and AI (PyTorch). "
    "Pick one. Bonus for the DevOps track: Kubernetes."
)


def test_optional_skills_of_other_tracks_are_not_added_to_the_summary():
    cv = StructuredCV(name="T", summary="Python engineer who builds APIs.", skills=["Python", "FastAPI"])

    leaked = _tailor("Python engineer who builds APIs and runs Kubernetes with Terraform and PyTorch.", MULTI_TRACK_JOB, cv)
    assert leaked.cv.summary == cv.summary
    assert leaked.warnings == [
        "Original summary kept. The draft mentioned Kubernetes, PyTorch, Terraform, "
        "which we couldn't verify in your CV."
    ]

    focused = _tailor("Python engineer who builds and ships APIs with FastAPI.", MULTI_TRACK_JOB, cv)
    assert focused.warnings == []
    assert focused.cv.summary == "Python engineer who builds and ships APIs with FastAPI."


def test_the_prompt_asks_for_the_supported_track_and_forbids_optional_skills():
    prompt = TAILOR_CV_SYSTEM_PROMPT
    assert "several tracks" in prompt
    assert "experience supports best" in prompt
    assert "optional" in prompt and "Never add them" in prompt
