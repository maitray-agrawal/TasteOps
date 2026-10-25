"""TasteOps API Health & Readiness Routes.

Provides liveness and readiness probe endpoints for load balancers and orchestrators.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Response, status

from tasteops.api.dependencies import ServiceDep
from tasteops.api.schemas.health import HealthResponse, ReadyResponse

router = APIRouter(tags=["System"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness Probe",
    description="Returns OK if the TasteOps API process is running and responding.",
)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        service="tasteops-api",
        version="0.1.0",
        timestamp=datetime.now(UTC),
    )


@router.get(
    "/ready",
    response_model=ReadyResponse,
    status_code=status.HTTP_200_OK,
    summary="Readiness Probe",
    description="Verifies that state store, orchestrator, and runtime configuration are healthy.",
    responses={
        503: {
            "model": ReadyResponse,
            "description": "One or more critical subsystems are unavailable",
        }
    },
)
async def readiness_check(service: ServiceDep, response: Response) -> ReadyResponse:
    checks = service.check_readiness()
    all_healthy = all(v == "ok" for v in checks.values())

    if not all_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        overall_status = "not_ready"
    else:
        overall_status = "ready"

    return ReadyResponse(
        status=overall_status,
        service="tasteops-api",
        version="0.1.0",
        checks=checks,
        timestamp=datetime.now(UTC),
    )
