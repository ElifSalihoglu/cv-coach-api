"""
Deterministic faithfulness checks for generated CV content.

These checks do not judge writing quality. They only catch two concrete
kinds of invented claims:
- numbers (metrics, percentages, years) that the candidate never gave
- terms (skills, tools) that the case marks as not belonging to the candidate
"""

import re
from dataclasses import dataclass, field

from app.models.schemas import GeneratedCVContent

# A number that is not glued to a letter, e.g. "40%", "3", "2.5" but not "GPT4".
NUMBER_PATTERN = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?%?(?!\w)")


def _numeric_value(token: str) -> str:
    return token.rstrip("%").replace(",", ".")


def find_unsupported_numbers(output: str, source_texts: list[str]) -> list[str]:
    source_values = {
        _numeric_value(token)
        for text in source_texts
        for token in NUMBER_PATTERN.findall(text)
    }
    unsupported: list[str] = []
    for token in NUMBER_PATTERN.findall(output):
        if _numeric_value(token) not in source_values and token not in unsupported:
            unsupported.append(token)
    return unsupported


def find_unsupported_terms(output: str, forbidden_terms: list[str]) -> list[str]:
    found: list[str] = []
    for term in forbidden_terms:
        pattern = rf"(?<!\w){re.escape(term)}(?!\w)"
        if re.search(pattern, output, flags=re.IGNORECASE):
            found.append(term)
    return found


@dataclass
class CheckResult:
    unsupported_numbers: list[str] = field(default_factory=list)
    unsupported_terms: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.unsupported_numbers and not self.unsupported_terms


def check_generated_content(
    generated: GeneratedCVContent,
    source_bullets: list[str],
    forbidden_terms: list[str],
) -> CheckResult:
    output = "\n".join(
        [*generated.improved_bullets, generated.summary, generated.linkedin_headline]
    )
    return CheckResult(
        unsupported_numbers=find_unsupported_numbers(output, source_bullets),
        unsupported_terms=find_unsupported_terms(output, forbidden_terms),
    )
