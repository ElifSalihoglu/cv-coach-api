from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel

from app.api.dependencies import get_llm_client, llm_http_error
from app.models.cv_document import CVParseRequest, CVParseResponse, StructuredCV
from app.services.cv_extract import (
    MAX_CV_BYTES,
    CVExtractError,
    CVFileTooLarge,
    UnreadableCVFile,
    UnsupportedCVFile,
    extract_text,
)
from app.services.cv_parsing import parse_cv_text
from app.services.cv_render import cv_filename, render_pdf
from app.services.llm_client import (
    LLMClient,
    LLMOutputError,
    LLMTimeoutError,
    LLMUnavailableError,
)

router = APIRouter(prefix="/v1/cv")


class CVRenderPDFRequest(BaseModel):
    cv: StructuredCV
    company: str = ""
    job_title: str = ""


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
            UnsupportedCVFile: 415,
            CVFileTooLarge: 413,
            UnreadableCVFile: 422,
        }.get(type(exc), 422)
        raise HTTPException(status_code=status, detail={"code": exc.code, "message": exc.message}) from exc
    return CVExtractResponse(filename=file.filename or "", text=text)


@router.post("/render-pdf")
def render_cv_pdf(request: CVRenderPDFRequest) -> Response:
    """Render the CV the client is showing as a PDF. Never calls a model."""
    filename = cv_filename(request.cv, request.company, request.job_title)
    ascii_name = filename.encode("ascii", "ignore").decode() or "CV.pdf"
    ascii_name = ascii_name.replace('"', "")
    disposition = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename, safe='')}"
    return Response(
        content=render_pdf(request.cv),
        media_type="application/pdf",
        headers={"Content-Disposition": disposition},
    )


@router.post("/parse", response_model=CVParseResponse)
async def parse_cv(
    request: CVParseRequest,
    llm: Annotated[LLMClient | None, Depends(get_llm_client)],
) -> CVParseResponse:
    """Structure CV text once; the user reviews and confirms the result."""
    if llm is None:
        raise HTTPException(status_code=503, detail="CV coach is unavailable.")

    try:
        return await parse_cv_text(llm, request.cv_text)
    except (LLMTimeoutError, LLMUnavailableError, LLMOutputError) as exc:
        raise llm_http_error(exc) from exc
