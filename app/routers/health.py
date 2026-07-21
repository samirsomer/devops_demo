from __future__ import annotations

import platform
import random

from fastapi import APIRouter, Response, status

from app.core.config import get_settings
from app.models.models import HealthResponse, VersionResponse


router = APIRouter(tags=['health'])


_READINESS_FAILURE_PROBABILITY = 0.05


@router.get("/health/live", response_model=HealthResponse)
def liveness() -> HealthResponse:
    """Liveness probe: answers "is the process running at all?".

    Should almost never fail; a failure here tells the orchestrator to
    restart the container.
    """
    return HealthResponse(status="ok")


@router.get(
    "/health/ready",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse}},
)
def readiness(response: Response) -> HealthResponse:
    """Readiness probe: answers "can this instance serve traffic right now?".

    Randomly reports "not ready" a small percentage of the time to simulate
    a flaky downstream dependency, so you can exercise rollout-gating and
    load-balancer draining behavior in your pipeline.
    """
    if random.random() < _READINESS_FAILURE_PROBABILITY:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="not_ready", detail="dependency check failed")
    return HealthResponse(status="ok")


@router.get("/version", response_model=VersionResponse)
def version() -> VersionResponse:
    """Report build/runtime metadata, handy for verifying a deployment."""
    settings = get_settings()
    return VersionResponse(
        app_name=settings.app_name,
        app_version=settings.app_version,
        environment=settings.environment,
        python_version=platform.python_version(),
        hostname=platform.node()
    )