from __future__ import annotations

import asyncio
import logging
import random
import time
from http import HTTPStatus
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from app.core.config import get_settings
from app.models.models import (
    CPUTaskResponse,
    DelayResponse,
    EchoRequest,
    EchoResponse,
    MemoryTaskResponse,
)

router = APIRouter(prefix="/simulate", tags=["simulate"])
logger = logging.getLogger(__name__)


# Status codes that /simulate/error is allowed to randomly return.
_ERROR_STATUS_CODES: tuple[int, ...] = (400, 404, 429, 500, 503)


@router.get("/delay", response_model=DelayResponse)
async def random_delay(
    min_ms: int | None = Query(default=None, ge=0, description="Lower bound in milliseconds"),
    max_ms: int | None = Query(default=None, ge=0, description="Upper bound in milliseconds"),
) -> DelayResponse:
    """Sleep for a random duration to simulate variable downstream latency.

    Falls back to the configured default range when min/max are not
    supplied. Useful for testing timeouts, latency percentile dashboards
    (p50/p95/p99), and alerting thresholds.
    """
    settings = get_settings()
    lo = min_ms if min_ms is not None else settings.default_min_delay_ms
    hi = max_ms if max_ms is not None else settings.default_max_delay_ms
    if lo > hi:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="min_ms must be less than or equal to max_ms",
        )

    delay_ms = random.uniform(lo, hi)
    start = time.perf_counter()
    await asyncio.sleep(delay_ms / 1000)
    actual_ms = (time.perf_counter() - start) * 1000

    logger.info("random_delay completed", extra={"actual_delay_ms": actual_ms})
    return DelayResponse(requested_range_ms=(lo, hi), actual_delay_ms=round(actual_ms, 2))


_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    code: {"description": HTTPStatus(code).phrase} for code in _ERROR_STATUS_CODES
}


@router.get("/error", responses=_ERROR_RESPONSES)
async def random_error(
    error_rate: float | None = Query(
        default=None,
        ge=0.0,
        le=1.0,
        description="Probability (0-1) of returning an error response",
    ),
) -> dict[str, str]:
    """Randomly raise an HTTP error to simulate an unreliable endpoint.

    Falls back to the configured default error rate when `error_rate` is
    not supplied. Great for testing retry logic, circuit breakers, and
    error-rate alerting rules.
    """
    settings = get_settings()
    rate = error_rate if error_rate is not None else settings.default_error_rate

    if random.random() < rate:
        status_code = random.choice(_ERROR_STATUS_CODES)
        logger.warning("random_error triggered", extra={"status_code": status_code})
        raise HTTPException(status_code=status_code, detail=f"Simulated {status_code} error")

    return {"status": "ok"}


@router.get("/cpu", response_model=CPUTaskResponse)
async def cpu_task(
    iterations: int = Query(
        default=200_000,
        ge=1_000,
        le=5_000_000,
        description="Upper bound to search for prime numbers within",
    ),
) -> CPUTaskResponse:
    """Run a CPU-bound workload (naive prime sieve) to simulate load.

    Runs in a worker thread via `asyncio.to_thread` so it doesn't block the
    event loop, but it will still consume a CPU core — useful for testing
    autoscaling on CPU utilization and profiler/APM integrations.
    """

    def _count_primes(n: int) -> int:
        sieve = bytearray([1]) * (n + 1)
        sieve[0:2] = bytearray([0, 0])
        for i in range(2, int(n**0.5) + 1):
            if sieve[i]:
                sieve[i * i :: i] = bytearray(len(sieve[i * i :: i]))
        return sum(sieve)

    start = time.perf_counter()
    primes_found = await asyncio.to_thread(_count_primes, iterations)
    duration_ms = (time.perf_counter() - start) * 1000

    logger.info(
        "cpu_task completed",
        extra={"iterations": iterations, "primes_found": primes_found, "duration_ms": duration_ms},
    )
    return CPUTaskResponse(
        iterations=iterations,
        primes_found=primes_found,
        duration_ms=round(duration_ms, 2),
    )


@router.get("/memory", response_model=MemoryTaskResponse)
async def memory_task(
    size_mb: int = Query(default=10, ge=1, le=512, description="Megabytes to allocate briefly"),
    hold_ms: int = Query(
        default=100, ge=0, le=5_000, description="Milliseconds to hold the allocation"
    ),
) -> MemoryTaskResponse:
    """Allocate and briefly hold a block of memory to simulate memory pressure.

    Useful for testing memory-based autoscaling, OOM-kill alerting, and
    container memory limit configuration.
    """
    start = time.perf_counter()
    block = bytearray(size_mb * 1024 * 1024)
    await asyncio.sleep(hold_ms / 1000)
    allocated_bytes = len(block)
    del block
    duration_ms = (time.perf_counter() - start) * 1000

    logger.info(
        "memory_task completed",
        extra={"size_mb": size_mb, "duration_ms": duration_ms},
    )
    return MemoryTaskResponse(
        requested_mb=size_mb,
        allocated_bytes=allocated_bytes,
        duration_ms=round(duration_ms, 2),
    )


@router.get("/status/{code}")
async def force_status(code: int) -> dict[str, str]:
    """Return (or raise) a specific HTTP status code on demand.

    Handy for scripting synthetic checks or dashboards that need to
    deterministically trigger a given response code, rather than relying
    on the random endpoints above.
    """
    if code < 200 or code > 599:
        raise HTTPException(status_code=400, detail="code must be a valid HTTP status code")
    if code >= 400:
        raise HTTPException(status_code=code, detail=f"Forced {code} response")
    return {"status": str(code)}


@router.post("/echo", response_model=EchoResponse)
async def echo(request: Request, body: EchoRequest) -> EchoResponse:
    """Echo back the submitted payload along with the request's correlation id.

    Useful for verifying request/response logging and tracing end-to-end.
    """
    request_id = getattr(request.state, "request_id", None)
    return EchoResponse(request_id=request_id, received=body)
