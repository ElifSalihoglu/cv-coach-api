"""The IT agent's own validation gates."""

from app.careers.agents.it.rules import is_generic, unsupported_design_claims
from app.careers.core.gates import Gate, GateContext, Proposal


def _generic_requirement(ctx: GateContext, p: Proposal) -> bool:
    # Not worth moving a line, rewording it or aiming a summary at "3+ years" or
    # "ownership": true of any engineer. The target is never swapped for another one.
    return is_generic(p.quote)


def _summary_unsupported_action(ctx: GateContext, p: Proposal) -> bool:
    # "designing REST APIs" without a CV line that says something of that kind was designed
    return bool(unsupported_design_claims(p.after, ctx.cv))


REQUIREMENT_GATES: tuple[Gate, ...] = (Gate("generic_requirement", _generic_requirement),)

DRAFT_GATES: tuple[Gate, ...] = (
    Gate("summary_unsupported_action", _summary_unsupported_action, frozenset({"summary"})),
)
