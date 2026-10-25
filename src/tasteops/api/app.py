"""TasteOps FastAPI Application Factory.

Initializes FastAPI with:
- OpenAPI documentation
- Centralized exception handlers (RFC 7807)
- Request correlation and access logging middleware
- Security headers middleware
- Environment-controlled CORS
- Graceful lifecycle management (startup and shutdown)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tasteops.api.errors import register_exception_handlers
from tasteops.api.middleware import (
    RequestCorrelationMiddleware,
    SecurityHeadersMiddleware,
)
from tasteops.api.routes import health_router, sessions_router, spaces_router
from tasteops.api.settings import APISettings

logger = logging.getLogger("tasteops.api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application lifecycle events (graceful startup and shutdown)."""
    settings: APISettings = getattr(app.state, "settings", APISettings())
    logging.basicConfig(level=settings.log_level)
    logger.info("Initializing TasteOps API (version: %s, env: %s)", settings.version, settings.environment)

    yield

    logger.info("TasteOps API shutting down gracefully.")


def create_app(settings: APISettings | None = None) -> FastAPI:
    """Creates and configures a new FastAPI application instance."""
    app_settings = settings or APISettings()

    app = FastAPI(
        title=app_settings.title,
        version=app_settings.version,
        description=app_settings.description,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = app_settings

    # 1. Register Centralized Exception Handlers (RFC 7807)
    register_exception_handlers(app)

    # 2. Register Middlewares (Executed in reverse order of addition)
    # Security Headers
    app.add_middleware(SecurityHeadersMiddleware)

    # Request Correlation & Structured Access Logging
    app.add_middleware(RequestCorrelationMiddleware)

    # Environment-Controlled CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID", "Location", "Retry-After"],
    )

    # 3. Mount Routers
    # System probes mounted at root: /health, /ready
    app.include_router(health_router)

    # Versioned API routes mounted under api_prefix (default: /api/v1)
    app.include_router(spaces_router, prefix=app_settings.api_prefix)
    app.include_router(sessions_router, prefix=app_settings.api_prefix)

    return app


app = create_app()
