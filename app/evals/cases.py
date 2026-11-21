from pathlib import Path

from pydantic import BaseModel, Field, TypeAdapter

from app.models.schemas import CVOptimizeRequest

DEFAULT_CASES_PATH = Path(__file__).resolve().parents[2] / "evals" / "cases.json"


class EvalCase(BaseModel):
    """One synthetic CV + job posting pair with labels for invented claims."""

    id: str
    job_title: str
    job_description: str
    current_bullets: list[str] = Field(..., min_length=1)
    forbidden_terms: list[str] = Field(
        ...,
        min_length=1,
        description="Skills or claims from the posting the candidate does not have.",
    )
    notes: str = ""

    def to_request(self) -> CVOptimizeRequest:
        return CVOptimizeRequest(
            job_title=self.job_title,
            job_description=self.job_description,
            current_bullets=self.current_bullets,
        )


def load_cases(path: Path = DEFAULT_CASES_PATH) -> list[EvalCase]:
    return TypeAdapter(list[EvalCase]).validate_json(path.read_bytes())
