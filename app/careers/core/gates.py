"""
Validation gates for suggestions.

A gate looks at one proposal the model made and says whether to throw it away. Its
`code` is the reason counted in `dropped_reasons` (a code, never the text). The gates
every domain needs are here; a domain agent adds its own (see agents/<domain>/gates.py).
Gates run in order and the first one that rejects wins.
"""
from dataclasses import dataclass
from typing import Callable

from app.careers.core.claims import ClaimLexicon, faithfulness_problems
from app.careers.core.evidence import SourceLine, fold, word_set
from app.models.cv_document import StructuredCV


@dataclass(frozen=True)
class GateContext:
    """What every gate may read: the CV and the posting, plus values computed once."""

    cv: StructuredCV
    job_description: str
    job_terms: set[str]  # skill-like terms of the posting
    cv_text: str  # all CV text, for "does the CV back this up"
    lexicon: ClaimLexicon


@dataclass(frozen=True)
class Proposal:
    """One model suggestion after the quote and the source ids were found to be real."""

    kind: str  # promote | rewrite | summary (anything else is dropped as unknown_kind)
    quote: str  # the requirement quote, already confirmed to be in the posting
    after: str  # the proposed text (promote: the bullet's own text)
    sources: list[SourceLine]


@dataclass(frozen=True)
class Gate:
    code: str
    rejects: Callable[[GateContext, Proposal], bool]
    kinds: frozenset[str] = frozenset()  # empty: applies to every kind

    def applies_to(self, kind: str) -> bool:
        return not self.kinds or kind in self.kinds


def first_rejection(gates: tuple[Gate, ...], ctx: GateContext, proposal: Proposal) -> str | None:
    for gate in gates:
        if gate.applies_to(proposal.kind) and gate.rejects(ctx, proposal):
            return gate.code
    return None


# ---------------------------------------------------------------- the shared gates


def _already_first(ctx: GateContext, p: Proposal) -> bool:
    return p.sources[0][2] <= 1


def _rewrite_not_substantive(ctx: GateContext, p: Proposal) -> bool:
    _, bullet, _ = p.sources[0]
    added = word_set(p.after) - word_set(bullet.text)
    # a one-word tweak is not worth the user's time
    return not p.after or fold(p.after) == fold(bullet.text) or len(added) < 2


def _rewrite_unsupported_claim(ctx: GateContext, p: Proposal) -> bool:
    exp, bullet, _ = p.sources[0]
    return bool(faithfulness_problems(p.after, f"{bullet.text}\n{exp.title}", ctx.job_terms, ctx.lexicon))


def _summary_not_new(ctx: GateContext, p: Proposal) -> bool:
    return not p.after or fold(p.after) == fold(ctx.cv.summary)


def _summary_unsupported_claim(ctx: GateContext, p: Proposal) -> bool:
    return bool(faithfulness_problems(p.after, ctx.cv_text, ctx.job_terms, ctx.lexicon))


CORE_GATES: tuple[Gate, ...] = (
    Gate("already_first", _already_first, frozenset({"promote"})),
    Gate("rewrite_not_substantive", _rewrite_not_substantive, frozenset({"rewrite"})),
    Gate("rewrite_unsupported_claim", _rewrite_unsupported_claim, frozenset({"rewrite"})),
    Gate("summary_not_new", _summary_not_new, frozenset({"summary"})),
    Gate("summary_unsupported_claim", _summary_unsupported_claim, frozenset({"summary"})),
)
