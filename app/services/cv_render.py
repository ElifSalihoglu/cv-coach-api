"""
Preview and PDF output for a StructuredCV.

Both are produced from the same StructuredCV object and never call a model.
The PDF is a single column with an embedded Unicode font, so Turkish
characters render correctly and the text stays selectable.
"""
import re
from pathlib import Path

from fpdf import FPDF

from app.models.cv_document import StructuredCV

FONT_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"
FONT_REGULAR = FONT_DIR / "DejaVuSans.ttf"
FONT_BOLD = FONT_DIR / "DejaVuSans-Bold.ttf"

_PART_MAX = 40


def _dates(start: str, end: str) -> str:
    return " – ".join(x for x in (start, end) if x)


def _join(*parts: str, sep: str = " | ") -> str:
    return sep.join(p for p in parts if p)


def cv_filename(cv: StructuredCV, company: str, job_title: str) -> str:
    """Candidate_Company_Position.pdf, with characters that are safe in file names."""

    def part(value: str, fallback: str) -> str:
        cleaned = re.sub(r"[^\w]+", "_", value or "", flags=re.UNICODE).strip("_")
        return cleaned[:_PART_MAX].strip("_") or fallback

    return "_".join(
        [part(cv.name, "CV"), part(company, "Company"), part(job_title, "Position")]
    ) + ".pdf"


def _md_lines(value: str) -> str:
    """Keep the line breaks of a multi-line description in Markdown."""
    return "  \n".join(line for line in value.splitlines() if line.strip())


def _first_and_rest(value: str) -> tuple[str, list[str]]:
    lines = [line for line in value.splitlines() if line.strip()]
    return (lines[0], lines[1:]) if lines else ("", [])


def render_markdown(cv: StructuredCV) -> str:
    """Preview text for the UI; same content and order as the PDF."""
    lines: list[str] = []
    if cv.name:
        lines.append(f"# {cv.name}")
    contact = _join(cv.email, cv.phone, cv.location, *cv.links)
    if contact:
        lines.append(contact)
    if cv.summary:
        lines += ["", "## Summary", cv.summary]
    if cv.experiences:
        lines += ["", "## Experience"]
        for exp in cv.experiences:
            lines.append("")
            lines.append(f"**{_join(exp.title, exp.employer, sep=' — ')}**")
            meta = _join(_dates(exp.start, exp.end), exp.location)
            if meta:
                lines.append(f"*{meta}*")
            lines += [f"- {b.text}" for b in exp.bullets]
    if cv.projects:
        lines += ["", "## Projects"]
        for proj in cv.projects:
            lines += ["", f"**{proj.name}**"]
            if proj.description:
                lines.append(_md_lines(proj.description))
    if cv.education:
        lines += ["", "## Education"]
        for edu in cv.education:
            dates = _dates(edu.start, edu.end)
            lines.append(
                f"- **{_join(edu.degree, edu.school, sep=' — ')}**"
                + (f" ({dates})" if dates else "")
            )
            if edu.details:
                lines.append("  " + _md_lines(edu.details).replace("  \n", "  \n  "))
    if cv.certifications:
        lines += ["", "## Certifications"]
        for cert in cv.certifications:
            lines.append("- " + _join(cert.name, cert.issuer, cert.date, sep=" — "))
    if cv.skills:
        lines += ["", "## Skills", ", ".join(cv.skills)]
    if cv.languages:
        lines += ["", "## Languages", ", ".join(cv.languages)]
    return "\n".join(lines)


def render_pdf(cv: StructuredCV) -> bytes:
    """A4, single column, selectable text, automatic page breaks."""
    pdf = FPDF(format="A4", unit="mm")
    pdf.set_margins(18, 16, 18)
    pdf.set_auto_page_break(True, margin=16)
    pdf.add_font("DejaVu", "", str(FONT_REGULAR))
    pdf.add_font("DejaVu", "B", str(FONT_BOLD))
    pdf.set_title(_join(cv.name, "CV", sep=" – "))
    if cv.name:
        pdf.set_author(cv.name)
    pdf.add_page()

    def text(value: str, size: float = 10, bold: bool = False, indent: float = 0,
             height: float = 5.2, after: float = 0, border: str = "0") -> None:
        pdf.set_font("DejaVu", "B" if bold else "", size)
        pdf.set_x(pdf.l_margin + indent)
        pdf.multi_cell(
            pdf.epw - indent, height, value,
            border=border, new_x="LMARGIN", new_y="NEXT",
        )
        if after:
            pdf.ln(after)

    def heading(value: str) -> None:
        pdf.ln(3)
        pdf.set_draw_color(120, 120, 120)
        text(value.upper(), size=10.5, bold=True, height=6, border="B", after=1.5)

    if cv.name:
        text(cv.name, size=19, bold=True, height=9)
    contact = _join(cv.email, cv.phone, cv.location, *cv.links)
    if contact:
        text(contact, size=9.5, after=1)

    if cv.summary:
        with pdf.unbreakable():
            heading("Summary")
            text(cv.summary)

    if cv.experiences:
        heading("Experience")
        for exp in cv.experiences:
            # Title, dates and the first bullet stay on one page.
            with pdf.unbreakable():
                text(_join(exp.title, exp.employer, sep=" — "), bold=True, height=5.6)
                meta = _join(_dates(exp.start, exp.end), exp.location)
                if meta:
                    text(meta, size=9, height=4.8)
                if exp.bullets:
                    text("•  " + exp.bullets[0].text, indent=2)
            for bullet in exp.bullets[1:]:
                text("•  " + bullet.text, indent=2)
            pdf.ln(2.5)

    if cv.projects:
        heading("Projects")
        for proj in cv.projects:
            first, rest = _first_and_rest(proj.description)
            with pdf.unbreakable():  # name stays with the first description line
                text(proj.name, bold=True, height=5.6)
                if first:
                    text(first, indent=2)
            for line in rest:
                text(line, indent=2)
            pdf.ln(2)

    if cv.education:
        heading("Education")
        for edu in cv.education:
            first, rest = _first_and_rest(edu.details)
            with pdf.unbreakable():
                text(_join(edu.degree, edu.school, sep=" — "), bold=True, height=5.6)
                if _dates(edu.start, edu.end):
                    text(_dates(edu.start, edu.end), size=9, height=4.8)
                if first:
                    text(first, indent=2)
            for line in rest:
                text(line, indent=2)
            pdf.ln(1.5)

    if cv.certifications:
        heading("Certifications")
        for cert in cv.certifications:
            text("•  " + _join(cert.name, cert.issuer, cert.date, sep=" — "), indent=2)

    if cv.skills:
        with pdf.unbreakable():
            heading("Skills")
            text(", ".join(cv.skills))

    if cv.languages:
        with pdf.unbreakable():
            heading("Languages")
            text(", ".join(cv.languages))

    return bytes(pdf.output())
