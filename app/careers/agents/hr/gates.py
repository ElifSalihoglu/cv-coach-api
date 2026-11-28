"""The Human resources agent's own validation gates."""

from app.careers.agents.general.rules import is_years_requirement
from app.careers.agents.hr.rules import unsupported_hr_processes, unsupported_qualifications
from app.careers.core.gates import Gate, GateContext, Proposal


def _years_requirement(ctx: GateContext, p: Proposal) -> bool:
    return is_years_requirement(p.quote)


def _unlisted_qualification(ctx: GateContext, p: Proposal) -> bool:
    return bool(unsupported_qualifications(p.after, ctx.cv_text))


def _domain_claim(ctx: GateContext, p: Proposal) -> bool:
    return bool(unsupported_hr_processes(p.after, ctx.cv_text))


REQUIREMENT_GATES: tuple[Gate, ...] = (Gate("years_requirement", _years_requirement),)

DRAFT_GATES: tuple[Gate, ...] = (
    Gate("rewrite_unlisted_qualification", _unlisted_qualification, frozenset({"rewrite"})),
    Gate("summary_unlisted_qualification", _unlisted_qualification, frozenset({"summary"})),
    Gate("unsupported_hr_process", _domain_claim, frozenset({"rewrite", "summary"})),
)
