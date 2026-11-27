"""The General agent's own validation gates. They share nothing with the IT agent's."""
from app.careers.agents.general.rules import is_years_requirement, unsupported_qualifications
from app.careers.core.gates import Gate, GateContext, Proposal


def _years_requirement(ctx: GateContext, p: Proposal) -> bool:
    return is_years_requirement(p.quote)


def _names_unlisted_qualification(ctx: GateContext, p: Proposal) -> bool:
    return bool(unsupported_qualifications(p.after, ctx.cv_text))


REQUIREMENT_GATES: tuple[Gate, ...] = (
    Gate("years_requirement", _years_requirement),
)

DRAFT_GATES: tuple[Gate, ...] = (
    Gate("rewrite_unlisted_qualification", _names_unlisted_qualification, frozenset({"rewrite"})),
    Gate("summary_unlisted_qualification", _names_unlisted_qualification, frozenset({"summary"})),
)
