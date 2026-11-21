import logging
import time
import uuid

from fastapi import FastAPI, Request

from app.api.v1.routes_cv import router as cv_router
from app.api.v1.routes_jobs import router as jobs_router
from app.logging_utils import configure_logging, log_event, request_id_var

configure_logging()
logger = logging.getLogger("app.request")

app = FastAPI(title="CV Coach API")
app.include_router(cv_router)
app.include_router(jobs_router)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    """Give each request an id (never taken from the client) and log start/end."""
    request_id = uuid.uuid4().hex[:12]
    token = request_id_var.set(request_id)
    started = time.perf_counter()
    log_event(
        logger, logging.INFO, "request_start",
        method=request.method, endpoint=request.url.path,
    )
    try:
        response = await call_next(request)
    except Exception as exc:
        log_event(
            logger, logging.ERROR, "request_end",
            endpoint=request.url.path, status=500, reason="unhandled_exception",
            exception=type(exc).__name__,
            duration_ms=round((time.perf_counter() - started) * 1000),
        )
        raise
    else:
        log_event(
            logger, logging.INFO, "request_end",
            endpoint=request.url.path, status=response.status_code,
            duration_ms=round((time.perf_counter() - started) * 1000),
        )
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        request_id_var.reset(token)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
