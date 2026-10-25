"""TasteOps API Health and Readiness Schemas."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness probe response model."""

    status: str = Field(default="healthy", description="Service health state")
    service: str = Field(default="tasteops-api", description="Service identifier")
    version: str = Field(default="0.1.0", description="Application version")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Current server UTC timestamp",
    )


class ReadyResponse(BaseModel):
    """Readiness probe response model."""

    status: str = Field(..., description="Overall readiness state: ready | not_ready")
    service: str = Field(default="tasteops-api", description="Service identifier")
    version: str = Field(default="0.1.0", description="Application version")
    checks: dict[str, str] = Field(
        ...,
        description="Status of individual internal components (store, orchestrator, config)",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Current server UTC timestamp",
    )
