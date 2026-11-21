"""
Builds the OpenAI client from environment variables.

Importing this module never fails: a missing API key only means the CV
coach is unavailable (the route returns 503), while /health and the local
tests keep working.
"""

from __future__ import annotations

import os

import openai
from dotenv import load_dotenv

load_dotenv()

DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
REQUEST_TIMEOUT_SECONDS = 30.0
MAX_RETRIES = 2


def create_openai_client() -> openai.AsyncOpenAI | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return openai.AsyncOpenAI(
        api_key=api_key,
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=MAX_RETRIES,
    )


def get_openai_model() -> str:
    return os.getenv("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL
