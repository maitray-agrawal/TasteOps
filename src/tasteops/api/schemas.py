"""Pydantic schemas for the TasteOps HTTP API layer."""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness health check response."""

    status: str = Field(default="ok", description="Server health status.")
    version: str = Field(default="0.1.0", description="Application version.")


class ReadyResponse(BaseModel):
    """Readiness check response verifying downstream configuration."""

    status: str = Field(..., description="Readiness status (ready or not_ready).")
    version: str = Field(default="0.1.0", description="Application version.")
    qloo_configured: bool = Field(
        ..., description="Whether QLOO_API_KEY is configured."
    )
    storage_ready: bool = Field(
        ..., description="Whether persistent state storage is writable."
    )
    details: str | None = Field(default=None, description="Diagnostic notes.")


class CreateSessionRequest(BaseModel):
    """Request payload to initialize a new physical space cultural activation session."""

    raw_intent: str = Field(
        ...,
        min_length=3,
        max_length=5000,
        description="User cultural intent, brief, or anchor demographic description.",
        examples=[
            "Design a listening bar in Tokyo Shibuya for indie vinyl collectors and specialty coffee enthusiasts."
        ],
    )
    space_id: str | None = Field(
        default=None,
        max_length=200,
        description="Optional unique identifier for the physical space venue.",
        examples=["venue_shibuya_001"],
    )
    hints: dict[str, Any] | None = Field(
        default=None,
        description="Optional pre-parsed hints for space characteristics, audience, or aesthetic tags.",
    )


class RunPipelineRequest(BaseModel):
    """Request payload to drive workflow forward until the human approval gate."""

    hints: dict[str, Any] | None = Field(
        default=None,
        description="Optional auxiliary hints to refine cultural twin extraction.",
    )
    take_per_category: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of affinity recommendations to query per cultural category.",
    )


class ApproveRequest(BaseModel):
    """Request payload to approve a generated cultural activation plan."""

    approver: str = Field(
        default="human_curator",
        max_length=200,
        validation_alias=AliasChoices("approver", "curator_id"),
        description="Identifier of the human curator authorizing the plan.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional curator audit notes explaining the approval decision.",
    )


class RejectRequest(BaseModel):
    """Request payload to reject a generated cultural activation plan."""

    reason: str = Field(
        default="Curator rejected plan",
        max_length=1000,
        description="Reason for rejecting the current plan.",
    )


class ConfigResponse(BaseModel):
    """Public non-sensitive application runtime configuration."""

    environment: str
    qloo_base_url: str
    version: str = "0.1.0"
    mcp_tools_available: int


class ErrorResponse(BaseModel):
    """Structured error response schema."""

    error: str = Field(..., description="Error classification code.")
    message: str = Field(..., description="Human-readable explanation of the error.")
    request_id: str | None = Field(
        default=None, description="Correlation ID for diagnostic tracing."
    )
