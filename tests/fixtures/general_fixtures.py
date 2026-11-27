"""
Synthetic candidates and postings from professions outside IT, for the General agent, the
router and the orchestrator (fake-model tests). Nothing here is
real personal or company data.
"""
from app.models.cv_document import (
    CVBullet, CVCertification, CVEducation, CVExperience, StructuredCV,
)


def _exp(exp_id: str, title: str, employer: str, start: str, end: str, bullets: list[str]) -> CVExperience:
    return CVExperience(
        id=exp_id, title=title, employer=employer, start=start, end=end,
        bullets=[CVBullet(id=f"{exp_id}.b{i}", text=t) for i, t in enumerate(bullets, start=1)],
    )


# ------------------------------------------------------------------ a nurse (credentials matter)

NURSE_JOB_TITLE = "Staff Nurse - Surgical Ward"

NURSE_JOB_DESCRIPTION = """\
Staff Nurse - Surgical Ward

About the role
Bayview Hospital is hiring a Staff Nurse for its 30-bed surgical ward.

What you will do
- Provide pre- and post-operative care for surgical patients
- Administer medication and monitor vital signs
- Lead the ward handover and mentor new nurses
- Record care in the electronic patient record

What you bring
- Registered Nurse licence (required)
- Basic Life Support (BLS) certification
- 3+ years of ward experience
- Wound care experience

Nice to have
- Advanced Cardiac Life Support (ACLS) certification
- Experience with surgical drains
"""

NURSE_CV = StructuredCV(
    name="Aylin Demir",
    email="aylin.demir@example.com",
    phone="+90 532 000 00 00",
    location="Izmir",
    links=["https://example.com/aylin"],
    summary="Registered nurse with eight years of experience in medical wards and elderly care.",
    skills=["Patient assessment", "Medication administration", "Wound care", "Electronic patient records"],
    languages=["Turkish (native)", "English (B2)"],
    experiences=[
        _exp("exp1", "Staff Nurse", "Anadolu Medical Centre", "2019", "Present", [
            "Cared for 12 medical-ward patients per shift, giving medication and monitoring vital signs.",
            "Trained 6 new nurses on the ward's handover procedure.",
            "Reduced medication errors on the ward by 30% by introducing a double-check routine.",
            "Coordinated discharge plans with physiotherapists and social workers.",
        ]),
        _exp("exp2", "Healthcare Assistant", "Marmara Care Home", "2016", "2019", [
            "Supported 25 elderly residents with daily care and mobility.",
            "Recorded care notes in the electronic patient record system.",
        ]),
    ],
    education=[CVEducation(
        id="edu1", school="Ege University", degree="BSc Nursing", start="2012", end="2016",
        details="Thesis on pressure-ulcer prevention (2016)",
    )],
    certifications=[
        CVCertification(id="cert1", name="Basic Life Support (BLS)", issuer="Turkish Red Crescent", date="2023"),
        CVCertification(id="cert2", name="Registered Nurse Licence No: 123456", issuer="Ministry of Health", date="2016"),
    ],
)

# ------------------------------------------------------------------ marketing (one clear role)

MARKETING_JOB_TITLE = "Digital Marketing Manager"

MARKETING_JOB_DESCRIPTION = """\
Digital Marketing Manager

About the role
Cedar & Co sells home textiles online and is looking for a Digital Marketing Manager to grow
paid and organic traffic.

What you will do
- Plan and run paid campaigns on social and search channels
- Report weekly on campaign spend, conversion and revenue
- Manage the content calendar and two freelance writers

What you bring
- Hands-on experience with Google Ads and Meta Ads
- Strong written communication
"""

MARKETING_CV = StructuredCV(
    name="Mert Aksoy",
    email="mert.aksoy@example.com",
    location="Ankara",
    summary="Marketing coordinator with four years in e-commerce campaigns and reporting.",
    skills=["Google Ads", "Meta Ads", "Excel", "Content planning"],
    experiences=[
        _exp("exp1", "Marketing Coordinator", "Lale Home", "2021", "Present", [
            "Ran Google Ads and Meta Ads campaigns with a monthly budget of 8,000 EUR.",
            "Built a weekly report of spend, conversion and revenue for the management team.",
            "Kept the content calendar for three social channels and briefed two freelance writers.",
        ]),
    ],
    education=[CVEducation(id="edu1", school="Bilkent University", degree="BA Business Administration")],
)

# ------------------------------------------------------------------ mechanical engineering
# (no engineering agent yet: the router has no clear match and the general agent answers)

MECH_JOB_TITLE = "Mechanical Design Engineer"

MECH_JOB_DESCRIPTION = """\
Mechanical Design Engineer

About the role
Voltaic Pumps designs industrial pumps and needs a Mechanical Design Engineer for its product team.

What you will do
- Design pump housings and mounting parts in SolidWorks
- Run FEA to check stress and fatigue
- Support ISO 9001 audits of the design process

What you bring
- Professional Engineer (PE) licence
- 5+ years of mechanical design experience
"""

MECH_CV = StructuredCV(
    name="Kerem Yildiz",
    email="kerem.yildiz@example.com",
    summary="Mechanical engineer with six years in product design and testing.",
    skills=["SolidWorks", "Stress analysis", "Technical drawing"],
    experiences=[
        _exp("exp1", "Mechanical Engineer", "Dogu Makina", "2018", "Present", [
            "Designed sheet-metal enclosures for industrial pumps, cutting part cost by 12%.",
            "Ran tolerance and stress checks for 40 parts using SolidWorks Simulation.",
            "Supported ISO 9001 audits for the design department.",
        ]),
    ],
    education=[CVEducation(id="edu1", school="Istanbul Technical University", degree="BSc Mechanical Engineering")],
)
