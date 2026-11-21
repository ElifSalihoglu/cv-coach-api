import pytest

from app.models.schemas import GeneratedCVContent
from app.prompts.cv_templates import BASE_CV_SYSTEM_PROMPT


@pytest.mark.parametrize("field_name", GeneratedCVContent.model_fields.keys())
def test_prompt_requests_every_schema_field(field_name):
    assert f'"{field_name}"' in BASE_CV_SYSTEM_PROMPT


@pytest.mark.parametrize("legacy_field", ["optimized_bullets", "source_example_ids"])
def test_prompt_does_not_request_legacy_fields(legacy_field):
    assert legacy_field not in BASE_CV_SYSTEM_PROMPT
