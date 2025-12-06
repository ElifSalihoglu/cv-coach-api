"""
Centralized OpenAI client bootstrapper that exposes a single AsyncOpenAI
instance plus the active model name. This keeps the integration surface small
and guarantees that downstream services all share the same configuration.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
import openai

load_dotenv()

# Required configuration ----------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError(
        "Missing OPENAI_API_KEY in environment. "
        "Add it to your .env file or export it before running the app."
    )

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4-mini")

# Shared AsyncOpenAI client -------------------------------------------------
openai_client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)

__all__ = [
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "openai_client",
]
