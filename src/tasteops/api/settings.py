"""TasteOps API Configuration Settings.

Reads API operational parameters from environment variables with safe defaults.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class APISettings(BaseSettings):
    """FastAPI application configuration parameters."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    title: str = Field(
        default="TasteOps Cultural Intelligence API",
        description="OpenAPI title",
    )
    version: str = Field(
        default="0.1.0",
        description="Application version",
    )
    description: str = Field(
        default=(
            "Application-facing API for physical venue cultural intelligence activations. "
            "Connects spatial concepts to verified Qloo cultural affinity matrices and "
            "coordinates multi-agent sensory blueprints under human-in-the-loop governance."
        ),
        description="OpenAPI detailed description",
    )
    api_prefix: str = Field(
        default="/api/v1",
        description="URL prefix for versioned endpoints",
    )
    environment: str = Field(
        default="development",
        alias="ENVIRONMENT",
        description="Deployment environment (development, staging, production)",
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:3000",
        ],
        alias="CORS_ORIGINS",
        description="Allowed CORS origins list or JSON array string",
    )
    api_key: str | None = Field(
        default=None,
        alias="TASTEOPS_API_KEY",
        description="Master API key for authenticating management and execution operations",
    )
    auth_enforced: bool = Field(
        default=False,
        alias="TASTEOPS_AUTH_ENFORCED",
        description="Enforces mandatory authentication across all environments",
    )
    log_level: str = Field(
        default="INFO",
        alias="LOG_LEVEL",
        description="Logging level",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        """Supports comma-separated string, JSON array, or native list for CORS origins."""
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed]
                except json.JSONDecodeError, ValueError:
                    return [orig.strip() for orig in value.split(",") if orig.strip()]
            return [orig.strip() for orig in value.split(",") if orig.strip()]
        if isinstance(value, list):
            return [str(orig).strip() for orig in value]
        return ["*"]
