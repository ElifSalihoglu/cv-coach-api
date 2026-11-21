"""Sanity checks for the evaluation data itself, so a mislabelled case
does not silently produce a wrong score."""

import pytest

from app.evals.cases import DEFAULT_CASES_PATH, load_cases
from app.evals.checks import find_unsupported_terms

CASES = load_cases(DEFAULT_CASES_PATH)


def test_case_ids_are_unique():
    ids = [case.id for case in CASES]

    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.id)
def test_forbidden_terms_are_not_in_candidate_bullets(case):
    # If a forbidden term is already in the CV, the check would punish a
    # faithful answer.
    bullets = "\n".join(case.current_bullets)

    assert find_unsupported_terms(bullets, case.forbidden_terms) == []


def test_there_are_enough_cases_to_report_a_rate():
    assert len(CASES) >= 8
