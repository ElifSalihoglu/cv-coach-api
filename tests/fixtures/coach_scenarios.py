"""Canned model answers for the synthetic CV and the four-track posting (fake model, no API)."""

from app.models.coaching import (
    CoachModelOutput,
    ModelEvidence,
    ModelQuestion,
    ModelRequirement,
    ModelSuggestion,
    ModelTrack,
)
from tests.fixtures.fake_tools import ChoosesTool

Q_AI = "ship LLM features to production and keep agents and tools reliable"
Q_AI_EVAL = "You evaluate LLM outputs with test sets and monitor quality in production"
Q_PY = "build backend services and data pipelines with FastAPI and Airflow"
Q_API = "You design and maintain REST APIs and integrate partner webhooks"
Q_PREF_K8S = "Kubernetes or Terraform for the non-DevOps tracks"
Q_PREF_PG = "Experience with PostgreSQL"
Q_REQ = "3+ years of professional software engineering experience"

REQUIREMENTS = [
    ModelRequirement(text="3+ years of software engineering", quote=Q_REQ, level="required"),
    ModelRequirement(
        text="Ownership of services in production", quote="Ownership of services in production", level="required"
    ),
    ModelRequirement(text="PostgreSQL", quote=Q_PREF_PG, level="preferred"),
]

AI_SUMMARY = (
    "Software engineer with seven years in Python, APIs and data pipelines who ships "
    "LLM-based automations to production, such as an invoice triage agent handling "
    "12,000 documents per month."
)
PY_SUMMARY = (
    "Backend engineer with seven years in Python, APIs and data pipelines, who integrates "
    "third-party APIs and webhooks and runs Airflow pipelines that saved about 20 engineer-hours per week."
)


def tracks_output() -> CoachModelOutput:
    return CoachModelOutput(
        mode="choose_focus",
        responsibilities=["Join one of four tracks in a small team"],
        requirements=REQUIREMENTS,
        tracks=[
            ModelTrack(
                name="TypeScript",
                quote="build our player-facing dashboards with React and Node.js",
                summary="Player-facing dashboards.",
            ),
            ModelTrack(
                name="Python",
                quote=Q_PY,
                summary="Backend services and data pipelines.",
                evidence=[
                    ModelEvidence(source_id="exp2.b4", why="Integrated third-party APIs and webhooks."),
                    ModelEvidence(source_id="exp2.b1", why="Python and Airflow pipelines."),
                    ModelEvidence(source_id="exp9.b1", why="not a real line"),
                ],
            ),
            ModelTrack(
                name="DevOps",
                quote="run our platform on Kubernetes and automate infrastructure with Terraform",
                summary="Platform and infrastructure.",
            ),
            ModelTrack(
                name="AI",
                quote=Q_AI,
                summary="LLM features in production.",
                evidence=[
                    ModelEvidence(source_id="exp1.b1", why="LLM invoice triage agent in production."),
                    ModelEvidence(source_id="exp1.b4", why="Model evaluation work."),
                    ModelEvidence(source_id="exp1.b2", why="Queues and retries for reliability."),
                ],
            ),
            ModelTrack(name="Game design", quote="design the next hit game", summary="Not in the posting."),
        ],
    )


def ai_output() -> CoachModelOutput:
    return CoachModelOutput(
        mode="suggestions",
        focus="AI",
        requirements=REQUIREMENTS,
        suggestions=[
            ModelSuggestion(
                kind="summary",
                requirement_quote=Q_AI,
                level="required",
                source_ids=["exp1.b1"],
                support="direct",
                after=AI_SUMMARY,
                priority=1,
                rationale="Shows the production LLM agent and its scale first.",
            ),
            ModelSuggestion(
                kind="promote",
                requirement_quote=Q_AI_EVAL,
                level="required",
                source_ids=["exp1.b4"],
                support="related",
                priority=2,
                rationale="Related: general model evaluation, not specifically LLM outputs.",
            ),
            ModelSuggestion(
                kind="promote",
                requirement_quote=Q_AI,
                level="required",
                source_ids=["exp1.b2"],
                support="related",
                priority=3,
                rationale="Related: queues and retries support reliable automations.",
            ),
        ],
        questions=[ModelQuestion(requirement_quote=Q_PREF_K8S, level="preferred", term="Kubernetes")],
    )


def python_output() -> CoachModelOutput:
    return CoachModelOutput(
        mode="suggestions",
        focus="Python Backend",
        requirements=REQUIREMENTS,
        suggestions=[
            ModelSuggestion(
                kind="promote",
                requirement_quote=Q_API,
                level="required",
                source_ids=["exp2.b4"],
                support="related",
                priority=1,
                rationale="Related: integrating APIs and webhooks, not designing REST APIs.",
            ),
            ModelSuggestion(
                kind="summary",
                requirement_quote=Q_PY,
                level="required",
                source_ids=["exp2.b4", "exp2.b1"],
                support="direct",
                after=PY_SUMMARY,
                priority=2,
                rationale="Leads with API and pipeline work.",
            ),
            ModelSuggestion(
                kind="promote",
                requirement_quote=Q_PY,
                level="required",
                source_ids=["exp2.b2"],
                support="related",
                priority=3,
                rationale="Feature store pipelines.",
            ),
        ],
        questions=[ModelQuestion(requirement_quote=Q_PREF_PG, level="preferred", term="PostgreSQL")],
    )


class FakeLLM(ChoosesTool):
    """Stands in for the language model and counts how often it is called."""

    def __init__(self, *outputs: CoachModelOutput, tool: str | None = None):
        self.tool = tool
        self.outputs = list(outputs)
        self.calls: list[dict] = []

    async def generate(self, system_prompt, user_content, output_model=None):
        self.calls.append(user_content)
        return self.outputs.pop(0) if len(self.outputs) > 1 else self.outputs[0]
