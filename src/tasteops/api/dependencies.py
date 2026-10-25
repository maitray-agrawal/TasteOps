"""TasteOps API Dependency Injection Providers.

Centralizes dependency wiring for settings, persistence state stores,
orchestrators, and the application service facade.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request

from tasteops.api.service import TasteOpsApplicationService
from tasteops.api.settings import APISettings
from tasteops.config import QlooSettings
from tasteops.workflows.orchestrator import TasteOpsOrchestrator
from tasteops.workflows.persistence import BaseStateStore, InMemoryStateStore


def get_api_settings(request: Request = None) -> APISettings:  # type: ignore[assignment]
    """Provides APISettings instance, prioritizing app.state.settings when mounted."""
    if request is not None and hasattr(request, "app") and hasattr(request.app.state, "settings"):
        return request.app.state.settings
    return APISettings()


def get_qloo_settings() -> QlooSettings | None:
    """Attempts to read QlooSettings if environment variables are set."""
    try:
        return QlooSettings()
    except Exception:
        return None


from tasteops.persistence.database import Database
from tasteops.persistence.space_repository import (
    BaseSpaceRepository,
    SQLiteSpaceRepository,
)
from tasteops.persistence.store import SQLiteStateStore


@lru_cache(maxsize=1)
def get_database() -> Database:
    """Provides persistent database manager."""
    return Database("storage/tasteops.db")


@lru_cache(maxsize=1)
def get_space_repository(
    db: Annotated[Database, Depends(get_database)],
) -> BaseSpaceRepository:
    """Provides repository for physical spaces and briefs."""
    return SQLiteSpaceRepository(db)


@lru_cache(maxsize=1)
def get_state_store(
    db: Annotated[Database, Depends(get_database)],
) -> BaseStateStore:
    """Provides persistent state store for workflow contexts and audit events."""
    return SQLiteStateStore(db)


@lru_cache(maxsize=1)
def get_orchestrator(
    store: Annotated[BaseStateStore, Depends(get_state_store)],
) -> TasteOpsOrchestrator:
    """Provides the core TasteOpsOrchestrator singleton."""
    return TasteOpsOrchestrator(store=store)


@lru_cache(maxsize=1)
def get_service(
    orchestrator: Annotated[TasteOpsOrchestrator, Depends(get_orchestrator)],
    store: Annotated[BaseStateStore, Depends(get_state_store)],
    settings: Annotated[QlooSettings | None, Depends(get_qloo_settings)],
    space_repo: Annotated[BaseSpaceRepository, Depends(get_space_repository)],
) -> TasteOpsApplicationService:
    """Provides the application service facade coordinating spaces and orchestrator workflows."""
    return TasteOpsApplicationService(
        orchestrator=orchestrator,
        store=store,
        settings=settings,
        space_repo=space_repo,
    )


def get_correlation_id(request: Request) -> str:
    """Extracts the correlation ID assigned by middleware."""
    return getattr(request.state, "correlation_id", "unknown-correlation-id")


def verify_auth_boundary(
    request: Request,
    settings: Annotated[APISettings, Depends(get_api_settings)],
) -> str:
    """Enforces authentication and authorization boundaries on sensitive operations.

    Rules:
    1. If `TASTEOPS_API_KEY` is configured: Validates Bearer token or X-API-Key header.
       Rejects missing or invalid tokens with HTTP 401 Unauthorized / HTTP 403 Forbidden.
    2. If `TASTEOPS_AUTH_ENFORCED` or environment is 'production': Requires configured key.
       Rejects with HTTP 401 if unauthenticated.
    3. In local development / test mode when no key is configured:
       Allows access with advisory actor 'dev-curator'.
    """
    from fastapi import HTTPException, status
    from tasteops.security import constant_time_compare

    configured_key = settings.api_key
    auth_header = request.headers.get("Authorization")
    api_key_header = request.headers.get("X-API-Key")

    presented_token = None
    if auth_header and auth_header.startswith("Bearer "):
        presented_token = auth_header[7:].strip()
    elif api_key_header:
        presented_token = api_key_header.strip()

    is_production = settings.environment.lower() == "production"

    if configured_key:
        if not presented_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication credentials. Provide 'Authorization: Bearer <token>' or 'X-API-Key'.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not constant_time_compare(presented_token, configured_key):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid API key or insufficient permissions for this operation.",
            )
        return "authorized-curator"

    if is_production or settings.auth_enforced:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: TASTEOPS_API_KEY must be configured in production.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return "dev-curator"


# Common dependency annotations for clean typing in route definitions
APISettingsDep = Annotated[APISettings, Depends(get_api_settings)]
ServiceDep = Annotated[TasteOpsApplicationService, Depends(get_service)]
CorrelationIdDep = Annotated[str, Depends(get_correlation_id)]
AuthDep = Annotated[str, Depends(verify_auth_boundary)]
