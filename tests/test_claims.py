"""
The claim checks shared by the coach and the apply step: new numbers, seniority words and skills
that a draft adds to the CV.

Regression: a source summary "3+ years" and a posting saying "what takes 3 years elsewhere" made the
literal "3" a "skill not in the CV", so a harmless summary was refused.
"""
import pytest

from app.careers.core.claims import Problem, faithfulness_problems, skill_like_terms

JOB = "We ship fast: what takes 3 years elsewhere takes months here. You know Python and APIs."
SOURCE = "Python engineer with 3+ years of experience building APIs."


def problems(draft: str, job: str = JOB, source: str = SOURCE) -> list[Problem]:
    return faithfulness_problems(draft, source, skill_like_terms(job))


def test_a_number_in_the_posting_is_not_treated_as_a_skill():
    assert "3" not in skill_like_terms(JOB)
    assert problems("Python engineer with 3 years of experience building APIs.") == []


@pytest.mark.parametrize("text", ["3", "3+", "24/7", "2.5", "10-12", "2024"])
def test_words_without_letters_are_never_skills(text):
    assert skill_like_terms(f"You bring {text} of drive, plus Python.") == {"python"}


@pytest.mark.parametrize("name", ["S3", "EC2", "C#", "Web3", "Python3"])
def test_technical_names_with_digits_are_still_skills(name):
    assert name.casefold() in skill_like_terms(f"Experience with {name} is needed.")


@pytest.mark.parametrize("claimed,number", [("5 years", "5"), ("10 years", "10"), ("3 to 5 years", "5")])
def test_a_changed_number_of_years_is_still_caught(claimed, number):
    assert problems(f"Python engineer with {claimed} of experience building APIs.") == [Problem("numbers", (number,))]


def test_a_technical_name_with_a_digit_that_is_not_in_the_cv_is_still_caught():
    job = JOB + " You work with S3 and Lambda."
    assert problems("Python engineer with 3+ years of S3 experience.", job) == [Problem("skills", ("S3",))]


def test_a_technical_name_with_a_digit_that_is_in_the_cv_is_allowed():
    source = "Python engineer who builds APIs and stores data in S3."
    job = JOB + " You work with S3 and Lambda."
    assert problems("Python engineer who builds APIs on S3.", job, source) == []


def test_an_unverified_term_is_named():
    job = JOB + " You run services on Kubernetes (optional)."
    assert problems("Python and Kubernetes engineer with 3+ years of experience.", job) == [
        Problem("skills", ("Kubernetes",))
    ]


MULTI_TRACK_JOB = (
    "We hire for four tracks: TypeScript, Python, DevOps (Kubernetes, Terraform) and AI (PyTorch). "
    "Pick one. Bonus for the DevOps track: Kubernetes."
)


def test_optional_skills_of_other_tracks_are_not_added():
    source = "Python engineer who builds APIs. Python, FastAPI"

    leaked = problems("Python engineer who builds APIs and runs Kubernetes with Terraform and PyTorch.",
                      MULTI_TRACK_JOB, source)
    assert leaked == [Problem("skills", ("Kubernetes", "PyTorch", "Terraform"))]

    assert problems("Python engineer who builds and ships APIs with FastAPI.", MULTI_TRACK_JOB, source) == []
