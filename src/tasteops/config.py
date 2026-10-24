"""TasteOps Configuration for Qloo Cultural Intelligence."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class QlooSettings(BaseSettings):
    """Qloo API client configuration.

    Reads from environment variables or .env file.
    API keys are protected via SecretStr to prevent accidental leakage in logs.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_key: SecretStr = Field(
        ...,
        alias="QLOO_API_KEY",
        description="Qloo Hackathon API key. Must not be empty.",
    )
    base_url: str = Field(
        default="https://hackathon.api.qloo.com",
        alias="QLOO_BASE_URL",
        description="Qloo Hackathon base URL.",
    )
    timeout_seconds: float = Field(
        default=15.0,
        alias="QLOO_TIMEOUT_SECONDS",
        description="HTTP client timeout in seconds.",
        ge=1.0,
        le=120.0,
    )
    max_retries: int = Field(
        default=3,
        alias="QLOO_MAX_RETRIES",
        description="Maximum retry attempts for transient errors (429, 5xx).",
        ge=0,
        le=10,
    )
    retry_backoff_factor: float = Field(
        default=0.5,
        alias="QLOO_RETRY_BACKOFF_FACTOR",
        description="Exponential backoff factor in seconds.",
        ge=0.001,
        le=10.0,
    )
    cache_enabled: bool = Field(
        default=True,
        alias="QLOO_CACHE_ENABLED",
        description="Whether to enable in-memory TTL caching of GET responses.",
    )
    cache_ttl_seconds: int = Field(
        default=3600,
        alias="QLOO_CACHE_TTL_SECONDS",
        description="Default TTL in seconds for cached Qloo GET responses.",
        ge=0,
        le=86400,
    )

    @property
    def raw_api_key(self) -> str:
        """Returns the raw secret string for header injection."""
        return self.api_key.get_secret_value()

    def __repr__(self) -> str:
        return (
            f"QlooSettings(base_url={self.base_url!r}, "
            f"timeout_seconds={self.timeout_seconds}, "
            f"max_retries={self.max_retries}, "
            f"api_key='***REDACTED***')"
        )
