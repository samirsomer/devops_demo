from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["Ok"])
    detail: str | None = None


class VersionResponse(BaseModel):
    app_name: str
    app_version: str
    environment: str
    python_version: str
    hostname: str


class DelayResponse(BaseModel):
    requested_range_ms: tuple[int, int]
    actual_delay_ms: float


class CPUTaskResponse(BaseModel):
    iterations: int
    primes_found: int
    duration_ms: float


class MemoryTaskResponse(BaseModel):
    """Result of the memory-allocation workload endpoint."""

    requested_mb: int
    allocated_bytes: int
    duration_ms: float


class EchoRequest(BaseModel):
    """Arbitrary payload accepted by the echo endpoint."""

    message: str
    payload: dict[str, Any] | None = None


class EchoResponse(BaseModel):
    """Echo endpoint response, includes the correlation id for tracing."""

    request_id: str | None
    received: EchoRequest


class ErrorDetail(BaseModel):
    """Standard error body returned by the error-simulation endpoint."""

    error: str
    status_code: int