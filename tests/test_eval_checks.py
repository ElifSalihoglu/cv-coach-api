from app.evals.checks import (
    check_generated_content,
    find_unsupported_numbers,
    find_unsupported_terms,
)
from app.models.schemas import GeneratedCVContent

SOURCE = ["Automated weekly reporting with Python for 3 teams."]


# --- numbers -----------------------------------------------------------------

def test_flags_percentage_not_in_source():
    output = "Reduced reporting time by 40% using Python."

    assert find_unsupported_numbers(output, SOURCE) == ["40%"]


def test_allows_number_that_appears_in_source():
    output = "Automated reporting for 3 teams with Python."

    assert find_unsupported_numbers(output, SOURCE) == []


def test_flags_years_of_experience_not_in_source():
    output = "Python developer with 5+ years of experience."

    assert find_unsupported_numbers(output, SOURCE) == ["5"]


def test_number_inside_a_word_is_not_a_metric():
    output = "Used GPT4 and Python3 for reporting."

    assert find_unsupported_numbers(output, SOURCE) == []


# --- terms -------------------------------------------------------------------

def test_flags_forbidden_term_case_insensitively():
    output = "Deployed reporting services on kubernetes."

    assert find_unsupported_terms(output, ["Kubernetes", "AWS"]) == ["Kubernetes"]


def test_term_must_match_a_whole_word():
    # "AWS" should not match inside "laws" or "draws".
    output = "Drew charts that follow data protection laws."

    assert find_unsupported_terms(output, ["AWS"]) == []


def test_matches_terms_with_symbols():
    output = "Wrote services in C++ and Python."

    assert find_unsupported_terms(output, ["C++"]) == ["C++"]


# --- combined ----------------------------------------------------------------

def test_check_generated_content_looks_at_every_field():
    generated = GeneratedCVContent(
        improved_bullets=["Automated weekly reporting with Python for 3 teams."],
        summary="Engineer who cut costs by 25%.",
        linkedin_headline="AI Engineer | Python | Kubernetes",
    )

    result = check_generated_content(
        generated, source_bullets=SOURCE, forbidden_terms=["Kubernetes"]
    )

    assert result.unsupported_numbers == ["25%"]
    assert result.unsupported_terms == ["Kubernetes"]
    assert result.passed is False


def test_check_generated_content_passes_faithful_output():
    generated = GeneratedCVContent(
        improved_bullets=["Automated weekly Python reporting for 3 teams."],
        summary="Python developer focused on reporting automation.",
        linkedin_headline="Python Developer | Reporting Automation",
    )

    result = check_generated_content(
        generated, source_bullets=SOURCE, forbidden_terms=["Kubernetes"]
    )

    assert result.passed is True
