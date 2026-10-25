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


@lru_cache(maxsize=1)
def get_api_settings() -> APISettings:
    """Provides cached APISettings instance."""
    return APISettings()


def get_qloo_settings() -> QlooSettings | None:
    """Attempts to read QlooSettings if environment variables are set."""
    try:
        return QlooSettings()
    except Exception:
        return None


@lru_cache(maxsize=1)
def get_state_store() -> BaseStateStore:
    """Provides default persistent state store for workflow contexts and audit events."""
    return InMemoryStateStore()


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
) -> TasteOpsApplicationService:
    """Provides the application service facade coordinating spaces and orchestrator workflows."""
    return TasteOpsApplicationService(
        orchestrator=orchestrator,
        store=store,
        settings=settings,
    )


def get_correlation_id(request: Request) -> str:
    """Extracts the correlation ID assigned by middleware."""
    return getattr(request.state, "correlation_id", "unknown-correlation-id")


# Common dependency annotations for clean typing in route definitions
APISettingsDep = Annotated[APISettings, Depends(get_api_settings)]
ServiceDep = Annotated[TasteOpsApplicationService, Depends(get_service)]
CorrelationIdDep = Annotated[str, Depends(get_correlation_id)]
