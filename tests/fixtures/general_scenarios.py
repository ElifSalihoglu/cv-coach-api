"""Canned model answers for the non-IT fixtures (fake model, no API)."""

from app.models.coaching import CoachModelOutput, ModelQuestion, ModelRequirement, ModelSuggestion

# ---- nurse
Q_LICENCE = "Registered Nurse licence (required)"
Q_MEDS = "Administer medication and monitor vital signs"
Q_HANDOVER = "Lead the ward handover and mentor new nurses"
Q_RECORD = "Record care in the electronic patient record"
Q_YEARS = "3+ years of ward experience"
Q_ACLS = "Advanced Cardiac Life Support (ACLS) certification"

NURSE_SUMMARY = (
    "Registered nurse with eight years in medical wards and elderly care, who reduced medication "
    "errors on a medical ward by 30% and trained 6 new nurses on its handover procedure."
)


def nurse_output() -> CoachModelOutput:
    return CoachModelOutput(
        mode="suggestions",
        focus="Staff Nurse",
        responsibilities=["Care for surgical patients", "Administer medication", "Mentor new nurses"],
        requirements=[
            ModelRequirement(text="Registered Nurse licence", quote=Q_LICENCE, level="required"),
            ModelRequirement(
                text="BLS certification", quote="Basic Life Support (BLS) certification", level="required"
            ),
            ModelRequirement(text="ACLS certification", quote=Q_ACLS, level="preferred"),
        ],
        suggestions=[
            ModelSuggestion(
                kind="summary",
                requirement_quote=Q_MEDS,
                level="required",
                source_ids=["exp1.b3"],
                support="direct",
                after=NURSE_SUMMARY,
                priority=1,
                rationale="Leads with the measured medication-safety result.",
            ),
            ModelSuggestion(
                kind="promote",
                requirement_quote=Q_HANDOVER,
                level="required",
                source_ids=["exp1.b2"],
                support="related",
                priority=2,
                rationale="Related: training new nurses on handover, not leading the ward handover.",
            ),
            ModelSuggestion(
                kind="promote",
                requirement_quote=Q_YEARS,
                level="required",
                source_ids=["exp1.b4"],
                support="related",
                priority=3,
                rationale="Years of experience.",
            ),
        ],
        questions=[ModelQuestion(requirement_quote=Q_ACLS, level="preferred", term="ACLS")],
    )


# ---- marketing
Q_COMMUNICATION = "Strong written communication"
Q_REPORT = "Report weekly on campaign spend, conversion and revenue"


def marketing_output() -> CoachModelOutput:
    return CoachModelOutput(
        mode="suggestions",
        focus="Digital Marketing Manager",
        suggestions=[
            ModelSuggestion(
                kind="promote",
                requirement_quote=Q_REPORT,
                level="required",
                source_ids=["exp1.b2"],
                support="direct",
                priority=1,
                rationale="Weekly reporting.",
            ),
            ModelSuggestion(
                kind="promote",
                requirement_quote=Q_COMMUNICATION,
                level="required",
                source_ids=["exp1.b3"],
                support="related",
                priority=2,
                rationale="Related: briefing writers.",
            ),
        ],
    )


# ---- mechanical engineering
Q_DESIGN = "Design pump housings and mounting parts in SolidWorks"
MECH_DESIGN_SUMMARY = "Engineer who designed pump housings and mounting parts for the product team."
MECH_LICENSED_SUMMARY = "Licensed mechanical engineer with six years in product design and testing."


def mech_output(summary: str) -> CoachModelOutput:
    return CoachModelOutput(
        mode="suggestions",
        focus="Mechanical Design Engineer",
        suggestions=[
            ModelSuggestion(
                kind="summary",
                requirement_quote=Q_DESIGN,
                level="required",
                source_ids=["exp1.b1"],
                support="related",
                after=summary,
                priority=1,
                rationale="Related: enclosure design.",
            )
        ],
    )
