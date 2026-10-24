"""Error models for Qloo responses and application error payloads."""

from typing import Any

from pydantic import BaseModel, Field


class QlooError(BaseModel):
    """Normalized error model for Qloo API failures."""

    status_code: int = Field(..., description="HTTP status code")
    error_type: str = Field(..., description="Classification category of the error")
    message: str = Field(..., description="Human-readable explanation of error")
    details: dict[str, Any] | None = Field(
        default=None, description="Detailed diagnostic or error response metadata"
    )

    def __str__(self) -> str:
        return f"[{self.status_code}] {self.error_type}: {self.message}"
