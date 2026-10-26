import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field, SecretStr
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
        default_factory=lambda: SecretStr(os.getenv("QLOO_API_KEY", "")),
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


class ServerSettings(BaseSettings):
    """Server and environment configuration for the TasteOps backend service.

    Manages host, port, CORS, environment mode, and persistence paths.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = Field(
        default="development",
        alias="ENVIRONMENT",
        description="Deployment environment (development, staging, production).",
    )
    host: str = Field(
        default="0.0.0.0",
        alias="HOST",
        description="Host interface for server binding.",
    )
    port: int = Field(
        default=8000,
        validation_alias=AliasChoices("PORT", "X_ZOHO_CATALYST_LISTEN_PORT"),
        description="Port for server binding (supplied by Render via $PORT or Catalyst via $X_ZOHO_CATALYST_LISTEN_PORT).",
    )
    cors_middleware_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "CORS_MIDDLEWARE_ENABLED", "ENABLE_CORS_MIDDLEWARE"
        ),
        description=(
            "Whether FastAPI CORSMiddleware is attached. When running behind reverse-proxy gateways "
            "(such as Catalyst AppSail / ZGS) that manage CORS at the platform level, this can be set to false "
            "to prevent duplicate Access-Control-Allow-Origin headers."
        ),
    )
    cors_allow_credentials: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "CORS_ALLOW_CREDENTIALS", "TASTEOPS_CORS_ALLOW_CREDENTIALS"
        ),
        description=(
            "Whether to allow credentials (cookies, authorization headers) in CORS. Disabled by default "
            "since TasteOps API is a stateless token/header-based API."
        ),
    )
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173,http://localhost:8000,https://tasteops.vercel.app",
        validation_alias=AliasChoices("CORS_ORIGINS", "TASTEOPS_CORS_ORIGINS"),
        description="Comma-separated list of allowed CORS origins.",
    )
    cors_origin_regex: str | None = Field(
        default=r"^https:\/\/tasteops(-[a-zA-Z0-9_-]+)*\.vercel\.app$",
        validation_alias=AliasChoices(
            "CORS_ORIGIN_REGEX", "TASTEOPS_CORS_ORIGIN_REGEX"
        ),
        description="Optional regex pattern for allowed CORS origins (e.g. for Vercel preview deployments). Catalyst origins must be explicitly specified in CORS_ORIGINS.",
    )
    storage_dir: str = Field(
        default="storage/workflows",
        validation_alias=AliasChoices(
            "TASTEOPS_STORAGE_DIR", "STORAGE_DIR", "TASTEOPS_STORAGE_PATH"
        ),
        description="Filesystem path for persistent session snapshots and audit logs.",
    )
    log_level: str = Field(
        default="INFO",
        alias="LOG_LEVEL",
        description="Logging level (DEBUG, INFO, WARNING, ERROR).",
    )

    @property
    def effective_storage_path(self) -> Path:
        """Resolves storage_dir safely, stripping surrounding quotes/whitespace and ensuring absolute path."""
        raw = (self.storage_dir or "storage/workflows").strip().strip("'\"")
        path = Path(raw)
        if not path.is_absolute():
            # If in container environment (/app is a directory), anchor relative path to /app
            if Path("/app").is_dir():
                path = Path("/app") / path
            else:
                path = Path.cwd() / path
        return path.resolve()

    @property
    def cors_origins_list(self) -> list[str]:
        """Parses comma-separated cors_origins string into a list of normalized origins.

        Strips paths, query strings, and trailing slashes so origins match browser Origin headers exactly.
        When running in a Catalyst AppSail container (indicated by X_ZOHO_CATALYST_LISTEN_PORT),
        the Catalyst platform gateway (ZGS) automatically injects CORS headers for Catalyst domains.
        To prevent duplicate Access-Control-Allow-Origin headers, Catalyst domains are excluded from
        FastAPI's application-level allowed origins.
        """
        if not self.cors_origins:
            return []

        def _clean_origin(raw: str) -> str:
            item = raw.strip()
            if not item:
                return ""
            if item == "*":
                return "*"
            parsed = urlsplit(item)
            if parsed.scheme and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}"
            return item.rstrip("/")

        origins: list[str] = []
        for raw in self.cors_origins.split(","):
            cleaned = _clean_origin(raw)
            if cleaned and cleaned not in origins:
                origins.append(cleaned)

        if os.getenv("X_ZOHO_CATALYST_LISTEN_PORT"):
            catalyst_domain_pattern = re.compile(
                r"^https?://[a-zA-Z0-9.-]+\.(catalystserverless|catalystappsail|zohocatalyst)\.(in|com|eu|com\.au|ca|sa|jp|ae)$",
                re.IGNORECASE,
            )
            origins = [o for o in origins if not catalyst_domain_pattern.match(o)]

        return origins
