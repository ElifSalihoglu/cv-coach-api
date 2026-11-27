"""Text normalisation and role labels, which the agents use to compare wording and to name roles."""

from app.careers.core.evidence import normalize_text, role_label
from app.models.cv_document import CVBullet, CVExperience

NBSP = chr(0xA0)  # non-breaking space, as PDF text extraction produces it


def test_line_breaks_spaces_non_breaking_spaces_and_invisible_characters_count_as_one_space():
    pdf_text = f"Built a billing API for{NBSP}200 merchants\nusing Python  and FastAPI. "
    assert normalize_text(pdf_text) == "Built a billing API for 200 merchants using Python and FastAPI."
    assert normalize_text("soft­hyphen and​zero-width") == "softhyphen andzero-width"


def test_letters_digits_and_case_are_kept_so_a_changed_number_still_differs():
    assert normalize_text("3 years") != normalize_text("5 years")
    assert normalize_text("Python") != normalize_text("python")
    assert normalize_text(None) == ""


def test_role_labels_tell_apart_same_title_same_employer_and_same_employer_other_role():
    def exp(i, employer, title, start, end):
        return CVExperience(
            id=f"exp{i}",
            employer=employer,
            title=title,
            start=start,
            end=end,
            bullets=[CVBullet(id=f"exp{i}.b1", text="x")],
        )

    roles = [
        exp(1, "Acme", "Engineer", "2018", "2020"),
        exp(2, "Acme", "Engineer", "2020", "2022"),  # same title, same employer
        exp(3, "Beta", "Engineer", "2022", "2024"),  # same title, other employer
        exp(4, "Beta", "Lead", "2024", ""),  # same employer, other role
    ]

    assert [role_label(role, roles) for role in roles] == [
        "Engineer — Acme (2018 – 2020)",
        "Engineer — Acme (2020 – 2022)",
        "Engineer — Beta",
        "Lead — Beta",
    ]
