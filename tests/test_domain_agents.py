"""The Healthcare, HR and Finance agents: own card, prompt, model input and validation, on the shared engine."""

import asyncio

import pytest

from app.careers.agents.finance import FINANCE_AGENT
from app.careers.agents.general import GENERAL_AGENT
from app.careers.agents.healthcare import HEALTHCARE_AGENT
from app.careers.agents.hr import HR_AGENT
from app.careers.agents.it import IT_AGENT
from app.careers.core.engine import DEFAULT_ENGINE
from app.careers.core.state import CareerCase
from app.models.coaching import CoachModelOutput, ModelSuggestion
from tests.fixtures.fake_tools import ChoosesTool
from tests.fixtures.multi_domain import AI_HEALTH, CV, FINTECH, HR_ANALYTICS

AGENTS = [HEALTHCARE_AGENT, HR_AGENT, FINANCE_AGENT]
POSTINGS = {"healthcare": AI_HEALTH, "hr": HR_ANALYTICS, "finance": FINTECH}
QUOTES = {
    "healthcare": "Build machine learning models that support clinical teams",
    "hr": "Build workforce analytics dashboards for the HR team",
    "finance": "Build payment reconciliation services in Python",
}
# a summary that claims something only this field's rule knows to refuse, and the gate that names it
CLAIMS = {
    "healthcare": ("Machine learning engineer who prescribed fixes for hospital teams.", "unsupported_clinical_act"),
    "hr": ("Machine learning engineer who handled disciplinary cases for HR teams.", "unsupported_hr_process"),
    "finance": (
        "Machine learning engineer who audited payment portfolios for finance teams.",
        "unsupported_finance_scope",
    ),
}


class Recorder(ChoosesTool):
    def __init__(self, output: CoachModelOutput):
        self.output, self.calls = output, []

    async def generate(self, system_prompt, user_content, output_model=None):
        self.calls.append((system_prompt, user_content))
        return self.output


def summary(agent_id: str, text: str) -> CoachModelOutput:
    item = ModelSuggestion(
        kind="summary",
        requirement_quote=QUOTES[agent_id],
        level="required",
        source_ids=["exp1.b4"],
        support="related",
        after=text,
        priority=1,
        rationale="Related work.",
    )
    return CoachModelOutput(mode="suggestions", suggestions=[item])


def analyze(agent, output):
    llm = Recorder(output)
    case = CareerCase(CV, *POSTINGS[agent.card.id])
    return asyncio.run(agent.analyze(case, llm)), llm


@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.card.id)
def test_each_agent_has_its_own_card_prompt_profile_and_runs_on_the_shared_engine(agent):
    prompts = {a.profile.system_prompt for a in [*AGENTS, IT_AGENT, GENERAL_AGENT]}
    assert len(prompts) == 5  # five different prompts
    assert agent.card.routing_cues and all(cue == cue.casefold() for cue in agent.card.routing_cues)
    assert agent.profile.id == agent.card.id and agent.profile.requirement_gates and agent.profile.draft_gates
    assert agent._engine is DEFAULT_ENGINE


@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.card.id)
def test_the_model_input_has_no_identifiers_and_certificates_without_issuer_or_date(agent):
    _, llm = analyze(agent, CoachModelOutput())
    payload = llm.calls[0][1]
    text = str(payload)
    assert llm.calls[0][0] == agent.profile.system_prompt
    assert payload["candidate"]["certifications"] == [{"id": "cert1", "name": "AWS Certified Cloud Practitioner"}]
    for private in ("Deniz", "deniz.arslan", "+90", "Ankara", "Example University", "Amazon", "2023", "2021"):
        assert private not in text


@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.card.id)
def test_a_claim_only_this_fields_rule_refuses_is_dropped_with_its_own_reason(agent):
    text, code = CLAIMS[agent.card.id]
    result, _ = analyze(agent, summary(agent.card.id, text))
    assert result.suggestions == [] and result.dropped_reasons == {code: 1}


@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.card.id)
def test_a_supported_summary_and_an_unlisted_licence_are_told_apart(agent):
    ok = "Machine learning engineer who reconciled monthly payment reports with the finance team using Python."
    result, _ = analyze(agent, summary(agent.card.id, ok))
    assert [s.id for s in result.suggestions] == ["summary"] and result.dropped == 0

    licensed = "Licensed machine learning engineer who reconciled monthly payment reports using Python."
    result, _ = analyze(agent, summary(agent.card.id, licensed))
    assert result.suggestions == [] and result.dropped_reasons == {"summary_unlisted_qualification": 1}


def test_the_other_agents_rules_do_not_leak_into_each_agent():
    # "audited" is refused for finance only, "prescribed" for healthcare only
    result, _ = analyze(HR_AGENT, summary("hr", CLAIMS["finance"][0]))
    assert result.dropped_reasons == {} and len(result.suggestions) == 1
    result, _ = analyze(FINANCE_AGENT, summary("finance", CLAIMS["healthcare"][0]))
    assert result.dropped_reasons == {} and len(result.suggestions) == 1
