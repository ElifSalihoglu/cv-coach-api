import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routes_coach import router as coach_router
from app.api.v1.routes_cv import router as cv_router
from app.logging_utils import configure_logging, log_event, request_id_var

configure_logging()
logger = logging.getLogger("app.request")

app = FastAPI(title="CV Coach API")
app.include_router(cv_router)
app.include_router(coach_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
    expose_headers=["Content-Disposition"],
)


@app.middleware("http")
async def request_logging(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Give each request an id (never taken from the client) and log start/end."""
    request_id = uuid.uuid4().hex[:12]
    token = request_id_var.set(request_id)
    started = time.perf_counter()
    log_event(
        logger,
        logging.INFO,
        "request_start",
        method=request.method,
        endpoint=request.url.path,
    )
    try:
        response = await call_next(request)
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "request_end",
            endpoint=request.url.path,
            status=500,
            reason="unhandled_exception",
            exception=type(exc).__name__,
            duration_ms=round((time.perf_counter() - started) * 1000),
        )
        raise
    else:
        log_event(
            logger,
            logging.INFO,
            "request_end",
            endpoint=request.url.path,
            status=response.status_code,
            duration_ms=round((time.perf_counter() - started) * 1000),
        )
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        request_id_var.reset(token)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
