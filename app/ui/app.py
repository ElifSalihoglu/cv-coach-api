import sys
from pathlib import Path

import requests
import streamlit as st

# `streamlit run app/ui/app.py` puts app/ui on sys.path, not the project root.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.cv_text import extract_bullets  # noqa: E402

API_URL = "http://localhost:8000/v1/jobs/optimize"
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

if uploaded_file:
    temp_path = Path("temp") / Path(uploaded_file.name).name
    temp_path.parent.mkdir(exist_ok=True)

    with open(temp_path, "wb") as f:
        f.write(uploaded_file.read())

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

cv_bullets: list[str] = []
if cv_text:
    cv_bullets = extract_bullets(cv_text)
    with st.expander(f"Detected CV bullet points ({len(cv_bullets)})"):
        st.write(cv_bullets)

# ---------------------------------
# 2) Search + per-job optimization
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

if st.button("Search and optimize"):
    if not cv_bullets:
        st.warning("Please upload a CV with readable bullet points first.")
    elif not search_query.strip():
        st.warning("Please enter a role before searching.")
    else:
        payload = {
            "query": search_query.strip(),
            "city": city.strip() or "Berlin",
            "country": country.strip() or "Germany",
            "cv_bullets": cv_bullets,
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
                    st.session_state.pop("job_results", None)
                    st.error(f"API Error: {response.status_code}")
                    st.write(response.text)
            except requests.RequestException as err:
                st.session_state.pop("job_results", None)
                st.error(f"Failed to connect to API: {err}")

# ---------------------------------
# 3) Results (one block per job, search order)
# ---------------------------------
results = st.session_state.get("job_results")

if results is not None:
    st.header("📌 Results")
    if not results:
        st.info("No jobs found for your search.")

    for item in results:
        job = item["job"]
        with st.container(border=True):
            st.subheader(job["title"] or "Untitled job")
            st.markdown(
                f"**Company:** {job['company']}  \n"
                f"**Location:** {job['location']}  \n"
                f"**Source:** [{job['source_url']}]({job['source_url']})"
            )

            if item["status"] == "optimized":
                optimization = item["optimization"]
                st.markdown("**✨ Improved bullet points**")
                for bullet in optimization["improved_bullets"]:
                    st.markdown(f"- {bullet}")
                st.markdown("**📌 Summary**")
                st.write(optimization["summary"])
                st.markdown("**💼 LinkedIn headline**")
                st.write(optimization["linkedin_headline"])
            elif item["status"] == "missing_description":
                st.warning(
                    "The full job description could not be retrieved, "
                    "so no suggestions were generated for this job."
                )
            else:
                st.error(f"Optimization failed for this job: {item.get('error')}")
