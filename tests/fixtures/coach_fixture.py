"""
Synthetic candidate and a synthetic multi-track posting, shared by the fake-model
tests and the live evaluation. Nothing here is real personal or company data.
"""
from app.models.cv_document import CVBullet, CVExperience, StructuredCV

JOB_TITLE = "Software Engineer (m/f/d) - choose your track"

JOB_DESCRIPTION = """\
Software Engineer (m/f/d) - choose your track

About the role
Northstar Games builds the live-ops platform behind several mobile games. You join one of four tracks and work in a small cross-functional team.

Tracks
- TypeScript: build our player-facing dashboards with React and Node.js.
- Python: build backend services and data pipelines with FastAPI and Airflow. You design and maintain REST APIs and integrate partner webhooks.
- DevOps: run our platform on Kubernetes and automate infrastructure with Terraform.
- AI: ship LLM features to production and keep agents and tools reliable. You evaluate LLM outputs with test sets and monitor quality in production.

What you bring (all tracks)
- 3+ years of professional software engineering experience
- Ownership of services in production
- Clear written communication

Nice to have
- Experience with PostgreSQL
- Kubernetes or Terraform for the non-DevOps tracks
- Knowledge of mobile gaming
"""


def _exp(exp_id: str, title: str, employer: str, start: str, end: str, bullets: list[str]) -> CVExperience:
    return CVExperience(
        id=exp_id, title=title, employer=employer, start=start, end=end,
        bullets=[CVBullet(id=f"{exp_id}.b{i}", text=t) for i, t in enumerate(bullets, start=1)],
    )


CV = StructuredCV(
    name="Deniz Kaya",
    email="deniz.kaya@example.com",
    location="Istanbul",
    summary="Software engineer with seven years of experience in Python, APIs and data pipelines.",
    skills=["Python", "FastAPI", "Airflow", "SQL", "Docker", "REST APIs"],
    experiences=[
        _exp("exp1", "Senior Software Engineer", "Boğaz Yazılım", "2022", "Present", [
            "Built an LLM-based invoice triage agent handling 12,000 documents per month and cut manual review by 60%.",
            "Designed workflow automations with queues and retries, replacing five hand-run scripts.",
            "Trained and deployed a churn-prediction model that lifted retention campaign precision by 18%.",
            "Set up evaluation dashboards and offline test sets to track model quality across releases.",
            "Mentored four engineers and led the weekly architecture review.",
        ]),
        _exp("exp2", "Data Engineer", "Çınar Veri", "2018", "2022", [
            "Automated nightly ETL pipelines in Python and Airflow, saving about 20 engineer-hours per week.",
            "Built a feature store serving 40 features to three production models.",
            "Introduced data-quality checks that caught schema drift before it reached reports.",
            "Integrated third-party APIs and webhooks into internal tools for the operations team.",
        ]),
    ],
)


# A posting with one clear focus: the coach should go straight to suggestions.
CLEAR_JOB_TITLE = "AI Automation Engineer"

CLEAR_JOB_DESCRIPTION = """\
AI Automation Engineer

About the role
We are looking for an AI Automation Engineer to replace manual, error-prone workflows with reliable LLM-powered automations.

What you will do
- Build agents that classify documents and route them to the right team
- Design workflows with queues, retries and monitoring
- Integrate third-party APIs and webhooks into internal tools

What we are looking for
- Strong Python and API experience
- Experience shipping automation or LLM features to production
"""
