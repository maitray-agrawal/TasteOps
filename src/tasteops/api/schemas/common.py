"""TasteOps API Common Schemas.

Defines standardized error envelopes and shared metadata schemas.
Conforms to RFC 7807 Problem Details.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Standard RFC 7807 problem details error model."""

    type: str = Field(
        default="about:blank",
        description="URI identifier categorizing the error type",
    )
    title: str = Field(
        ...,
        description="Short, human-readable summary of the problem type",
    )
    status: int = Field(
        ...,
        description="HTTP status code applicable to this occurrence of the problem",
    )
    detail: str = Field(
        ...,
        description="Human-readable explanation specific to this occurrence",
    )
    instance: str | None = Field(
        default=None,
        description="URI reference that identifies the specific occurrence of the problem",
    )
    code: str = Field(
        ...,
        description="Application-specific error code for programmatic handling",
    )
    correlation_id: str = Field(
        ...,
        description="Correlation ID for tracing this request across server logs",
    )
    errors: list[dict[str, Any]] | None = Field(
        default=None,
        description="Optional list of field-level validation errors",
    )


class ErrorResponse(BaseModel):
    """Envelope wrapping the standard error details."""

    error: ErrorDetail
