import sys
from pathlib import Path

import requests
import streamlit as st

# `streamlit run app/ui/app.py` puts app/ui on sys.path, not the project root.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.models.cv_document import StructuredCV  # noqa: E402
from app.services.cv_render import cv_filename, render_markdown, render_pdf  # noqa: E402

API_BASE = "http://localhost:8000/v1"
API_URL = f"{API_BASE}/jobs/optimize"
PARSE_URL = f"{API_BASE}/cv/parse"
PARSE_TIMEOUT_SECONDS = 120
REQUEST_TIMEOUT_SECONDS = 900  # each job opens a browser page, so this can take minutes

# Page setup
st.set_page_config(page_title="AI CV Coach", layout="wide")
st.title("🧠 AI CV Coach")

# ---------------------------------
# 1) CV Upload Section (once)
# ---------------------------------
st.header("📄 Upload Your CV")

uploaded_file = st.file_uploader(
    "Upload your CV file (PDF, TXT, DOCX)",
    type=["pdf", "txt", "docx"],
)

cv_text = ""
file_id = ""

if uploaded_file:
    file_id = f"{uploaded_file.name}:{uploaded_file.size}"
    temp_path = Path("temp") / Path(uploaded_file.name).name
    temp_path.parent.mkdir(exist_ok=True)

    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getvalue())

    try:
        if uploaded_file.name.endswith(".txt"):
            cv_text = temp_path.read_text(encoding="utf-8")

        elif uploaded_file.name.endswith(".pdf"):
            import PyPDF2

            reader = PyPDF2.PdfReader(str(temp_path))
            cv_text = "\n".join(page.extract_text() or "" for page in reader.pages)

        else:
            from docx import Document

            doc = Document(str(temp_path))
            cv_text = "\n".join(paragraph.text for paragraph in doc.paragraphs)

    except Exception as e:
        st.error(f"Could not extract text from file: {e}")

# A new file starts over: parsed CV, confirmed CV and old results are dropped.
if st.session_state.get("file_id", file_id) != file_id:
    for key in ("parsed", "confirmed_cv", "job_results", "search_error"):
        st.session_state.pop(key, None)
    st.session_state["file_id"] = file_id

# ---------------------------------
# 2) Extracted text -> parse once with the model
# ---------------------------------
if cv_text:
    st.subheader("Extracted text")
    st.caption(
        "This exact text is sent to the language model once, to structure it. "
        "Edit or remove anything you do not want sent."
    )
    text_to_parse = st.text_area(
        "CV text", value=cv_text, height=250, key=f"text_{file_id}"
    )

    if st.button("Parse CV with AI"):
        with st.spinner("Structuring your CV..."):
            try:
                response = requests.post(
                    PARSE_URL,
                    json={"cv_text": text_to_parse},
                    timeout=PARSE_TIMEOUT_SECONDS,
                )
                if response.status_code == 200:
                    version = st.session_state.get("parse_count", 0) + 1
                    st.session_state["parse_count"] = version
                    st.session_state["parsed"] = {**response.json(), "version": version}
                    st.session_state.pop("confirmed_cv", None)
                    st.session_state.pop("job_results", None)
                else:
                    st.error(f"API Error: {response.status_code}")
                    st.write(response.text)
            except requests.RequestException as err:
                st.error(f"Failed to connect to API: {err}")

# ---------------------------------
# 3) Review and confirm the parsed CV
# ---------------------------------
parsed = st.session_state.get("parsed")


def _items(value: str) -> list[str]:
    return [x.strip() for x in value.replace(",", "\n").splitlines() if x.strip()]


if parsed:
    st.subheader("Review your CV")
    st.caption(
        "Check company, title, dates and education against your CV. Nothing was "
        "guessed: missing fields stay empty. Every job search uses the version "
        "you confirm here."
    )
    for warning in parsed["warnings"]:
        st.warning(warning)

    cv = parsed["cv"]
    ns = f"v{parsed['version']}_"  # a new parse gets fresh widgets
    with st.form("review_cv"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Name", cv["name"], key=ns + "name")
        email = c2.text_input("Email", cv["email"], key=ns + "email")
        phone = c1.text_input("Phone", cv["phone"], key=ns + "phone")
        location = c2.text_input("Location", cv["location"], key=ns + "location")
        links = st.text_input(
            "Links (comma separated)", ", ".join(cv["links"]), key=ns + "links"
        )
        summary = st.text_area("Summary", cv["summary"], key=ns + "summary")

        experiences = []
        for exp in cv["experiences"]:
            key = ns + exp["id"]
            with st.container(border=True):
                st.markdown(f"**Experience** `{exp['id']}`")
                e1, e2 = st.columns(2)
                employer = e1.text_input("Company", exp["employer"], key=key + "_employer")
                title = e2.text_input("Title", exp["title"], key=key + "_title")
                d1, d2, d3 = st.columns(3)
                start = d1.text_input("Start", exp["start"], key=key + "_start")
                end = d2.text_input("End", exp["end"], key=key + "_end")
                exp_location = d3.text_input("Location", exp["location"], key=key + "_loc")
                bullets = []
                for bullet in exp["bullets"]:
                    text = st.text_area(
                        f"Bullet {bullet['id']} (empty = remove)",
                        bullet["text"], key=ns + bullet["id"], height=70,
                    )
                    if text.strip():
                        bullets.append({"id": bullet["id"], "text": text.strip()})
                experiences.append({
                    "id": exp["id"], "employer": employer.strip(),
                    "title": title.strip(), "start": start.strip(), "end": end.strip(),
                    "location": exp_location.strip(), "bullets": bullets,
                })

        education = []
        for edu in cv["education"]:
            key = ns + edu["id"]
            with st.container(border=True):
                st.markdown(f"**Education** `{edu['id']}`")
                s1, s2 = st.columns(2)
                school = s1.text_input("School", edu["school"], key=key + "_school")
                degree = s2.text_input("Degree", edu["degree"], key=key + "_degree")
                t1, t2 = st.columns(2)
                e_start = t1.text_input("Start", edu["start"], key=key + "_start")
                e_end = t2.text_input("End", edu["end"], key=key + "_end")
                edu_details = st.text_area(
                    "Details (thesis, publication, ...)", edu["details"],
                    key=key + "_details", height=90,
                )
                education.append({
                    "id": edu["id"], "school": school.strip(),
                    "degree": degree.strip(), "start": e_start.strip(),
                    "end": e_end.strip(), "details": edu_details.strip(),
                })

        projects = []
        for proj in cv["projects"]:
            key = ns + proj["id"]
            with st.container(border=True):
                st.markdown(f"**Project** `{proj['id']}`")
                proj_name = st.text_input("Name", proj["name"], key=key + "_name")
                proj_description = st.text_area(
                    "Description", proj["description"], key=key + "_description", height=110
                )
                projects.append({
                    "id": proj["id"], "name": proj_name.strip(),
                    "description": proj_description.strip(),
                })

        certifications = []
        for cert in cv["certifications"]:
            key = ns + cert["id"]
            with st.container(border=True):
                st.markdown(f"**Certification** `{cert['id']}`")
                k1, k2, k3 = st.columns([3, 2, 1])
                cert_name = k1.text_input("Name", cert["name"], key=key + "_name")
                issuer = k2.text_input("Issuer", cert["issuer"], key=key + "_issuer")
                cert_date = k3.text_input("Date", cert["date"], key=key + "_date")
                certifications.append({
                    "id": cert["id"], "name": cert_name.strip(),
                    "issuer": issuer.strip(), "date": cert_date.strip(),
                })

        skills = st.text_input(
            "Skills (comma separated)", ", ".join(cv["skills"]), key=ns + "skills"
        )
        languages = st.text_input(
            "Languages (comma separated)", ", ".join(cv["languages"]), key=ns + "languages"
        )
        confirmed = st.form_submit_button(
            "Confirm CV and continue to job search",
            type="primary",
            use_container_width=True,
        )

    if confirmed:
        st.session_state["confirmed_cv"] = StructuredCV.model_validate({
            "name": name.strip(), "email": email.strip(), "phone": phone.strip(),
            "location": location.strip(), "links": _items(links),
            "summary": summary.strip(), "experiences": experiences,
            "education": education, "skills": _items(skills),
            "projects": projects, "certifications": certifications,
            "languages": _items(languages),
        }).model_dump()
        st.session_state.pop("job_results", None)

confirmed_cv = st.session_state.get("confirmed_cv")
if confirmed_cv:
    st.success("CV confirmed. Every job below is tailored from this version.")

# ---------------------------------
# 4) Search + per-job tailoring
# ---------------------------------
st.header("🔍 Search Jobs")

col_role, col_city, col_country, col_limit = st.columns([3, 2, 2, 1])
with col_role:
    search_query = st.text_input("Role", placeholder="e.g., AI Engineer")
with col_city:
    city = st.text_input("City", value="Berlin")
with col_country:
    country = st.text_input("Country", value="Germany")
with col_limit:
    limit = st.number_input("Max jobs", min_value=1, max_value=10, value=5)

def _api_error_message(response) -> str:
    """The API's own user-facing message when it sent one, else the status code."""
    try:
        detail = response.json().get("detail")
    except ValueError:
        detail = None
    if isinstance(detail, dict) and detail.get("message"):
        return detail["message"]
    if isinstance(detail, str) and detail:
        return f"API Error {response.status_code}: {detail}"
    return f"API Error {response.status_code}"


if st.button("Search and tailor CV"):
    st.session_state.pop("search_error", None)
    if not confirmed_cv:
        st.warning("Please upload, parse and confirm your CV first.")
    elif not search_query.strip():
        st.warning("Please enter a role before searching.")
    else:
        payload = {
            "query": search_query.strip(),
            "city": city.strip() or "Berlin",
            "country": country.strip() or "Germany",
            "cv": confirmed_cv,
            "limit": int(limit),
        }
        with st.spinner("Searching, reading job descriptions and tailoring your CV..."):
            try:
                response = requests.post(
                    API_URL, json=payload, timeout=REQUEST_TIMEOUT_SECONDS
                )
                if response.status_code == 200:
                    st.session_state["job_results"] = response.json()["results"]
                else:
                    # Only the search results are dropped; the confirmed CV stays
                    # in the session, so a new search needs no re-upload.
                    st.session_state.pop("job_results", None)
                    st.session_state["search_error"] = _api_error_message(response)
            except requests.RequestException as err:
                st.session_state.pop("job_results", None)
                st.session_state["search_error"] = f"Failed to connect to API: {err}"

search_error = st.session_state.get("search_error")
if search_error:
    st.error(search_error)


@st.cache_data(show_spinner=False)
def _pdf_bytes(cv_json: str) -> bytes:
    """Render from the stored result; downloading again never calls the model."""
    return render_pdf(StructuredCV.model_validate_json(cv_json))


def _show_job_card(item: dict, key: str) -> None:
    job = item["job"]
    with st.container(border=True):
        st.subheader(job["title"] or "Untitled job")
        st.markdown(
            f"**Company:** {job['company']}  \n"
            f"**Location:** {job['location']}  \n"
            f"**Source:** [{job['source_url']}]({job['source_url']})"
        )

        if item["status"] == "optimized" and item.get("tailored_cv"):
            tailored = StructuredCV.model_validate(item["tailored_cv"])
            for warning in item.get("tailoring_warnings", []):
                st.caption(f"⚠️ {warning}")
            with st.expander("Preview CV"):
                st.markdown(render_markdown(tailored))
            st.download_button(
                "Download PDF",
                data=_pdf_bytes(tailored.model_dump_json()),
                file_name=cv_filename(tailored, job["company"], job["title"]),
                mime="application/pdf",
                key=f"download_{key}",
            )
        elif item["status"] == "missing_description":
            st.warning(
                "The full job description could not be retrieved, "
                "so no CV was generated for this job."
            )
        else:
            st.error(f"Tailoring failed for this job: {item.get('error')}")


# ---------------------------------
# 5) Results (one block per job, search order)
# ---------------------------------
results = st.session_state.get("job_results")

if results is not None:
    st.header("📌 Results")
    if not results:
        st.info("No jobs found for your search.")
    for index, item in enumerate(results):
        _show_job_card(item, f"search_{index}")
