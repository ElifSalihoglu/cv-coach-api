from typing import List
from pydantic import BaseModel, Field


class CVOptimizeRequest(BaseModel):
    """
    Request body for /v1/cv/optimize.
    The user provides:
    - target job title
    - job description text
    - current CV bullet points
    """

    job_title: str = Field(
        ...,
        description="Target role, e.g. 'AI Engineer'.",
        examples=["AI Engineer", "Machine Learning Engineer"],
    )
    job_description: str = Field(
        ...,
        description="Full job description text pasted from the job posting.",
    )
    current_bullets: List[str] = Field(
        default_factory=list,
        description="Existing CV bullet points related to the target role.",
        examples=[[
            "Built ML pipelines using Python and FastAPI.",
            "Implemented RAG systems with vector databases."
        ]],
    )


class RetrievedJobExample(BaseModel):
    """
    Represents one job listing retrieved from the local CSV dataset.
    Used to show which jobs were used during the RAG step.
    """

    job_title: str = Field(..., description="Job title from scraped data.")
    company_name: str = Field(..., description="Company name.")
    location: str = Field(..., description="Location as shown on Indeed.")
    job_url: str = Field(..., description="URL to the job posting.")


class CVOptimizeResponse(BaseModel):
    """
    Response returned by /v1/cv/optimize.
    The LLM generates:
    - improved bullet points
    - a professional summary
    - a LinkedIn headline
    We also return similar job listings used as context.
    """

    improved_bullets: List[str] = Field(
        ...,
        description="Improved, role-aligned CV bullet points.",
    )
    summary: str = Field(
        ...,
        description="A short professional summary tailored to the target role.",
    )
    linkedin_headline: str = Field(
        ...,
        description="A suggested LinkedIn headline.",
    )
    retrieved_jobs: List[RetrievedJobExample] = Field(
        default_factory=list,
        description="Similar job listings used during RAG.",
    )
    
class JobListing(BaseModel):
    """
    Internal model representing one job listing loaded from the local CSV file.
    This is used by the RAG pipeline to work with typed objects instead of raw dicts.
    """

    title: str = Field(..., description="Job title from the scraped dataset.")
    company_name: str = Field(..., description="Company name from the job listing.")
    location: str = Field(..., description="Location string from the job listing.")
    url: str = Field(..., description="URL pointing to the job listing page.")
