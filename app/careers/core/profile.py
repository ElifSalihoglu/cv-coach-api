"""What makes one domain agent different from another, as data and small functions."""

from dataclasses import dataclass, field
from typing import Any, Callable

from app.careers.core.claims import GENERIC_LEXICON, ClaimLexicon
from app.careers.core.gates import Gate
from app.models.cv_document import StructuredCV


@dataclass(frozen=True)
class PipelineLimits:
    max_suggestions: int = 5
    max_questions: int = 2
    per_kind: dict[str, int] = field(default_factory=lambda: {"promote": 3, "rewrite": 1, "summary": 1})


@dataclass(frozen=True)
class DomainProfile:
    """
    Everything the engine needs to know about a field of work.

    - `system_prompt`: written for this field's postings and CVs.
    - `build_input`: the model input. Built only from core.minimize building blocks.
    - `offers_choice`: does a posting of this field ask the applicant to pick a track?
    - `requirement_gates`: run first, on what the posting asks for (e.g. a generic condition).
    - `draft_gates`: run after the shared gates, on the text the model proposes.
    - `lexicon`: the word lists of the claim checks.
    """

    id: str
    system_prompt: str
    build_input: Callable[[StructuredCV, str, str, str], dict[str, Any]]
    offers_choice: Callable[[str], bool]
    requirement_gates: tuple[Gate, ...] = ()
    draft_gates: tuple[Gate, ...] = ()
    lexicon: ClaimLexicon = GENERIC_LEXICON
    limits: PipelineLimits = field(default_factory=PipelineLimits)
