"""
One synthetic candidate and three postings that span two fields each, with canned answers per agent
prompt (fake model, no API). The candidate has done work in all four fields, so each agent finds
something real to say; nothing here is real personal or company data.
"""

from app.models.coaching import CoachModelOutput, ModelSuggestion
from app.models.cv_document import CVBullet, CVCertification, CVEducation, CVExperience, StructuredCV

CV = StructuredCV(
    name="Deniz Arslan",
    email="deniz.arslan@example.com",
    phone="+90 555 000 00 00",
    location="Ankara",
    summary="Machine learning engineer with experience in hospital analytics, HR reporting and payments.",
    skills=["Python", "SQL", "AWS", "pytest"],
    languages=["Turkish (native)", "English (C1)"],
    experiences=[
        CVExperience(
            id="exp1",
            title="ML Engineer",
            employer="Example Analytics",
            start="2021",
            end="Present",
            bullets=[
                CVBullet(id="exp1.b1", text="Wrote unit tests for the team's model code."),
                CVBullet(id="exp1.b2", text="Built a model that flags patient-note backlogs for a hospital team."),
                CVBullet(id="exp1.b3", text="Built payroll analytics dashboards for the HR team in Python and SQL."),
                CVBullet(id="exp1.b4", text="Reconciled monthly payment reports with the finance team using Python."),
                CVBullet(id="exp1.b5", text="Deployed Python services on AWS with automated checks."),
            ],
        )
    ],
    education=[CVEducation(id="edu1", school="Example University", degree="B.Sc. Computer Engineering")],
    certifications=[CVCertification(id="cert1", name="AWS Certified Cloud Practitioner", issuer="Amazon", date="2023")],
)

# ---- postings: (title, description)

AI_HEALTH = (
    "AI Engineer, Healthcare",
    """AI Engineer, Healthcare

What you will do
- Build machine learning models that support clinical teams
- Deploy Python services on AWS
- Report on patient flow to ward managers
""",
)
HR_ANALYTICS = (
    "HR Analytics Specialist",
    """HR Analytics Specialist

What you will do
- Build workforce analytics dashboards for the HR team
- Report on headcount and attrition
- Write Python and SQL for people data
""",
)
FINTECH = (
    "FinTech Software Engineer",
    """FinTech Software Engineer

What you will do
- Build payment reconciliation services in Python
- Deploy services on AWS
- Work with the finance team on monthly reports
""",
)


def promote(quote: str, bullet: str, priority: int, level: str = "required") -> ModelSuggestion:
    return ModelSuggestion(
        kind="promote",
        requirement_quote=quote,
        level=level,
        source_ids=[bullet],
        support="related",
        priority=priority,
        rationale="Related work.",
    )


def answer(*suggestions: ModelSuggestion) -> CoachModelOutput:
    return CoachModelOutput(mode="suggestions", suggestions=list(suggestions))
