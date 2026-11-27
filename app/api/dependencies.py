from functools import lru_cache

from fastapi import HTTPException

from app.services.llm_client import LLMClient, LLMOutputError, LLMTimeoutError, LLMUnavailableError
from app.services.openai_setup import create_openai_client, get_openai_model


@lru_cache
def get_llm_client() -> LLMClient | None:
    """The shared model client, or None when no API key is configured."""
    openai_client = create_openai_client()
    if openai_client is None:
        return None
    return LLMClient(openai_client=openai_client, model=get_openai_model())


def llm_http_error(exc: LLMTimeoutError | LLMUnavailableError | LLMOutputError) -> HTTPException:
    """The HTTP error for a model failure: timeout, provider unavailable, or an unusable answer."""
    if isinstance(exc, LLMTimeoutError):
        return HTTPException(status_code=504, detail=str(exc))
    if isinstance(exc, LLMUnavailableError):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=502, detail=str(exc))
