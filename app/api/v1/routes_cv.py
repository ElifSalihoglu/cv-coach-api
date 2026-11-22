from functools import lru_cache
from typing import Annotated

from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field

from app.models.cv_document import (
    CVParseRequest,
    CVParseResponse,
    StructuredCV,
    TailoredCVResult,
)
from app.services.cv_extract import (
    MAX_CV_BYTES,
    CVExtractError,
    CVFileTooLarge,
    UnreadableCVFile,
    UnsupportedCVFile,
    extract_text,
)
from app.services.cv_render import cv_filename, render_pdf
from app.models.schemas import CVOptimizeRequest, CVOptimizeResponse
from app.services.cv_coach import CVCoach, OpenAICVCoach
from app.services.llm_client import (
    LLMClient,
    LLMOutputError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from app.services.openai_setup import create_openai_client, get_openai_model

router = APIRouter(prefix="/v1/cv")


class CVRenderPDFRequest(BaseModel):
    cv: StructuredCV
    company: str = ""
    job_title: str = ""


@lru_cache
def get_cv_coach() -> CVCoach | None:
    """Build the coach once; return None when no API key is configured."""
    openai_client = create_openai_client()
    if openai_client is None:
        return None
    return OpenAICVCoach(LLMClient(openai_client=openai_client, model=get_openai_model()))


@router.post("/optimize", response_model=CVOptimizeResponse)
async def optimize_cv(
    request: CVOptimizeRequest,
    coach: Annotated[CVCoach | None, Depends(get_cv_coach)],
) -> CVOptimizeResponse:
    if coach is None:
        raise HTTPException(status_code=503, detail="CV coach is unavailable.")

    try:
        return await coach.optimize(request)
    except LLMTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMOutputError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

class CVTailorRequest(BaseModel):
    cv: StructuredCV
    job_title: str = Field(..., min_length=1)
    job_description: str = Field(..., min_length=1, max_length=20_000)


@router.post("/tailor", response_model=TailoredCVResult)
async def tailor_cv(
    request: CVTailorRequest,
    coach: Annotated[CVCoach | None, Depends(get_cv_coach)],
) -> TailoredCVResult:
    """One model call: the confirmed CV tailored to one job. Facts are never changed."""
    if coach is None:
        raise HTTPException(status_code=503, detail="CV coach is unavailable.")
    try:
        return await coach.tailor(request.cv, request.job_title, request.job_description)
    except LLMTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMOutputError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


class CVExtractResponse(BaseModel):
    filename: str
    text: str


@router.post("/extract-text", response_model=CVExtractResponse)
async def extract_cv_text(file: UploadFile = File(...)) -> CVExtractResponse:
    """Plain text of an uploaded CV, for the user to review. Never calls a model."""
    data = await file.read(MAX_CV_BYTES + 1)
    try:
        text = extract_text(file.filename or "", data)
    except CVExtractError as exc:
        status = {
            UnsupportedCVFile: 415, CVFileTooLarge: 413, UnreadableCVFile: 422,
        }.get(type(exc), 422)
        raise HTTPException(
            status_code=status, detail={"code": exc.code, "message": exc.message}
        ) from exc
    return CVExtractResponse(filename=file.filename or "", text=text)


@router.post("/render-pdf")
def render_cv_pdf(request: CVRenderPDFRequest) -> Response:
    """Render the CV the client is showing as a PDF. Never calls a model."""
    filename = cv_filename(request.cv, request.company, request.job_title)
    ascii_name = filename.encode("ascii", "ignore").decode() or "CV.pdf"
    ascii_name = ascii_name.replace('"', "")
    disposition = (
        f'attachment; filename="{ascii_name}"; '
        f"filename*=UTF-8''{quote(filename, safe='')}"
    )
    return Response(
        content=render_pdf(request.cv),
        media_type="application/pdf",
        headers={"Content-Disposition": disposition},
    )


@router.post("/parse", response_model=CVParseResponse)
async def parse_cv(
    request: CVParseRequest,
    coach: Annotated[CVCoach | None, Depends(get_cv_coach)],
) -> CVParseResponse:
    """Structure CV text once; the user reviews and confirms the result."""
    if coach is None:
        raise HTTPException(status_code=503, detail="CV coach is unavailable.")

    try:
        return await coach.parse(request.cv_text)
    except LLMTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMOutputError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
