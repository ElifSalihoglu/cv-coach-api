import re

_BULLET_PREFIX = re.compile(r"^\s*[-•*·–—▪●◦]+\s*")
MIN_BULLET_LENGTH = 20


def extract_bullets(cv_text: str) -> list[str]:
    """
    Turn extracted CV text into a list of bullet-like lines.

    Strips bullet markers and drops very short lines (names, headings, dates).
    This is a simple line-based heuristic; the user's original wording is kept.
    """
    bullets: list[str] = []
    for line in (cv_text or "").splitlines():
        text = _BULLET_PREFIX.sub("", line).strip()
        if len(text) >= MIN_BULLET_LENGTH:
            bullets.append(text)
    return bullets
