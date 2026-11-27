"""
Text extraction from an uploaded CV (PDF, DOCX or TXT).

Works on bytes in memory only: nothing is written to disk and the CV text is
never logged. The extracted text is shown to the user for review before any
model sees it.
"""

import io
from pathlib import PurePath

SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".txt")
MAX_CV_BYTES = 5 * 1024 * 1024


class CVExtractError(Exception):
    """Base class; `code` and `message` are safe to show to the user."""

    code = "extract_failed"
    message = "Could not read text from this file."


class UnsupportedCVFile(CVExtractError):
    code = "unsupported_file_type"
    message = "Unsupported file type. Upload a PDF, DOCX or TXT file."


class CVFileTooLarge(CVExtractError):
    code = "file_too_large"
    message = f"This file is larger than {MAX_CV_BYTES // (1024 * 1024)} MB."


class UnreadableCVFile(CVExtractError):
    code = "unreadable_file"
    message = "Could not read text from this file. It may be damaged or password-protected."


def _decode_txt(data: bytes) -> str:
    # UTF-8 first; cp1254 covers older Turkish text files.
    for encoding in ("utf-8-sig", "cp1254"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def extract_text(filename: str, data: bytes) -> str:
    suffix = PurePath(filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise UnsupportedCVFile()
    if len(data) > MAX_CV_BYTES:
        raise CVFileTooLarge()

    try:
        if suffix == ".txt":
            return _decode_txt(data)
        if suffix == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        from docx import Document

        return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
    except CVExtractError:
        raise
    except Exception as exc:  # corrupt or encrypted file: report, do not crash
        raise UnreadableCVFile() from exc
