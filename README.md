# CV Coach API

FastAPI service that rewrites CV bullet points for a target job, and generates a short summary and a LinkedIn headline, without inventing facts about the candidate.

## Setup

Requires Python 3.11+.

```powershell
python -m pip install -r requirements-dev.txt
```

Copy `.env.example` to `.env` and set your key:

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-mini
```

Without a key, the API still starts: `/health` works and `/v1/cv/optimize` returns `503`.

## Run

```powershell
python -m uvicorn app.main:app --reload
```

> Use `python -m uvicorn` rather than `uvicorn`. On Windows (especially the Microsoft Store Python), the `Scripts` folder is often not on `PATH`, so the bare `uvicorn` command is not found.

The key is read at startup. After editing `.env`, restart the server; `--reload` only watches `.py` files.

## Test

```powershell
python -m pytest
```

Tests use fake clients and never call OpenAI, so no API key is needed.
