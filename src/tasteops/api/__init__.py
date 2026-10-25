"""TasteOps API Package."""

from typing import Any

__all__ = [
    "APISettings",
    "TasteOpsApplicationService",
    "app",
    "create_app",
]


def __getattr__(name: str) -> Any:
    if name in ("app", "create_app"):
        from tasteops.api.app import app, create_app

        return app if name == "app" else create_app
    if name == "TasteOpsApplicationService":
        from tasteops.api.service import TasteOpsApplicationService

        return TasteOpsApplicationService
    if name == "APISettings":
        from tasteops.api.settings import APISettings

        return APISettings
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
