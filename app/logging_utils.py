"""
Structured, privacy-safe logging helpers.

Every line is `event=<name> request_id=<id> key=value ...`. Values go through a strict
allow-list pattern, so free text (CV content, job descriptions, full URLs, exception
messages) can never be written by accident: anything that is not a short identifier or a
number is replaced.
"""

import logging
import os
import re
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_SAFE_VALUE = re.compile(r"[A-Za-z0-9_.:/\-]{1,64}")


def _format_value(value: object) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return f"{value:.1f}" if isinstance(value, float) else str(value)
    text = str(value)
    return text if _SAFE_VALUE.fullmatch(text) else "<redacted>"


def log_event(logger: logging.Logger, level: int, event: str, **fields: object) -> None:
    request_id = request_id_var.get()
    parts = [f"event={event}", f"request_id={request_id}"]

    parts.extend(f"{key}={_format_value(value)}" for key, value in fields.items() if value is not None)
    logger.log(level, " ".join(parts), extra={"request_id": request_id, "event": event})


def configure_logging() -> None:
    """Send `app.*` logs to stderr at INFO (override with LOG_LEVEL). Idempotent."""
    logger = logging.getLogger("app")
    if not any(h.get_name() == "cv_coach" for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        handler.set_name("cv_coach")
        logger.addHandler(handler)
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
