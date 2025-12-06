import streamlit as st
import requests
from pathlib import Path

# Page setup
st.set_page_config(page_title="AI CV Coach", layout="wide")
st.title("🧠 AI CV Coach")

API_URL = "http://localhost:8000/v1/cv/optimize"

# ---------------------------------
# 1) CV Upload Section
# ---------------------------------
st.header("📄 Upload Your CV")

uploaded_file = st.file_uploader(
    "Upload your CV file (PDF, TXT, DOCX)",
    type=["pdf", "txt", "docx"]
)

cv_text = ""

if uploaded_file:
    st.success("File uploaded successfully!")

    temp_path = Path("temp") / uploaded_file.name
    temp_path.parent.mkdir(exist_ok=True)

    with open(temp_path, "wb") as f:
        f.write(uploaded_file.read())

    st.subheader("📑 Extracted CV Text")

    try:
        if uploaded_file.name.endswith(".txt"):
            cv_text = temp_path.read_text()

        elif uploaded_file.name.endswith(".pdf"):
            import PyPDF2
            reader = PyPDF2.PdfReader(str(temp_path))
            cv_text = "\n".join([page.extract_text() or "" for page in reader.pages])

        else:
            from docx import Document
            doc = Document(str(temp_path))
            cv_text = "\n".join(paragraph.text for paragraph in doc.paragraphs)

        st.text_area("CV Text", cv_text, height=300)

    except Exception as e:
        st.error(f"Could not extract text from file: {e}")


# ---------------------------------
# 2) Job Description Input
# ---------------------------------
st.header("📝 Job Description")

job_desc = st.text_area(
    "Paste the job description here...",
    height=150
)


# ---------------------------------
# 3) SEARCH JOBS SECTION (New)
# ---------------------------------
st.header("🔍 Search Jobs")

st.write("Use this section to search job postings based on keywords. Later this will be connected to your scraper.")

col1, col2 = st.columns([3, 1])

with col1:
    search_query = st.text_input("Search for job roles, keywords, or locations", placeholder="e.g., AI Engineer, Berlin")

with col2:
    search_button = st.button("Search Jobs")

# Placeholder for job results
job_results_box = st.empty()

if search_button:
    if not search_query:
        job_results_box.warning("Please enter a search query before searching.")
    else:
        # Placeholder response until scraper is connected
        job_results_box.info(
            f"Searching job boards for: **{search_query}**\n\n"
            "This will later display results from your scraping engine."
        )


# ---------------------------------
# 4) Optimization section
# ---------------------------------
st.header("🤖 Optimize with LLM")

if st.button("Optimize CV"):
    if not cv_text:
        st.warning("Please upload a CV before optimization.")
    else:
        payload = {
            "cv_text": cv_text,
            "job_description": job_desc
        }

        with st.spinner("Processing..."):
            try:
                response = requests.post(API_URL, json=payload)

                if response.status_code == 200:
                    result = response.json()

                    st.success("🎉 CV optimized successfully!")

                    st.subheader("✨ Improved Bullet Points")
                    st.write(result.get("new_bullets", []))

                    st.subheader("📌 Summary")
                    st.write(result.get("summary", ""))

                    st.subheader("💼 LinkedIn Headline")
                    st.write(result.get("headline", ""))

                else:
                    st.error(f"API Error: {response.status_code}")
                    st.write(response.text)

            except Exception as err:
                st.error(f"Failed to connect to API: {err}")
