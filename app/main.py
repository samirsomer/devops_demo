from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.config import get_settings
from app.core.log_config import configure_logging, req_id_ctx_var
from app.routers import health, simulate

settings = get_settings()
configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Minimal FastAPI service used as a base for CI/CD and observability "
        "experiments: health/readiness probes, latency injection, error "
        "injection, and CPU/memory load endpoints."
    ),
)


@app.middleware("http")
async def add_request_id_and_log(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Attach a correlation id to every request and log a start/end line.

    The request id is taken from an inbound `X-Request-ID` header when
    present (so it can be propagated across services behind a gateway),
    otherwise a new UUID4 is generated.
    """
    incoming_id = request.headers.get("x-request-id")
    request_id = incoming_id or str(uuid.uuid4())
    request.state.request_id = request_id
    token = req_id_ctx_var.set(request_id)

    start = time.perf_counter()
    logger.info(
        "request started",
        extra={"method": request.method, "path": request.url.path},
    )
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request failed",
            extra={"method": request.method, "path": request.url.path},
        )
        raise
    finally:
        req_id_ctx_var.reset(token)

    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request finished",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
        },
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return a consistent, structured 422 body for validation errors."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "validation_error", "detail": exc.errors()},
    )


# Prometheus metrics, exposed at GET /metrics (scrape target for Prometheus).
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

app.include_router(health.router)
app.include_router(simulate.router)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    """Redirect-style landing endpoint pointing to the interactive docs."""
    return {"service": settings.app_name, "docs": "/docs", "metrics": "/metrics"}