"""FastAPI Application Entrypoint for TasteOps Cultural Intelligence OS.

Production command:
    uvicorn tasteops.api.main:app --host 0.0.0.0 --port $PORT
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from tasteops.agents.mcp_adapter import CulturalIntelligenceMCPAdapter
from tasteops.api.routes import router
from tasteops.api.schemas import ErrorResponse
from tasteops.client import QlooClient
from tasteops.config import QlooSettings, ServerSettings
from tasteops.mcp import create_cultural_intelligence_mcp
from tasteops.workflows.orchestrator import TasteOpsOrchestrator
from tasteops.workflows.persistence import FileStateStore

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("tasteops.api")


def build_default_orchestrator(
    settings: ServerSettings,
) -> TasteOpsOrchestrator:
    """Builds the default TasteOpsOrchestrator with persistence and Qloo adapter if configured."""
    store = FileStateStore(base_dir=settings.storage_dir)

    mcp_adapter: CulturalIntelligenceMCPAdapter | None = None
    try:
        qloo_settings = QlooSettings()
        if qloo_settings.raw_api_key:
            client = QlooClient(settings=qloo_settings)
            server = create_cultural_intelligence_mcp(client=client)
            mcp_adapter = CulturalIntelligenceMCPAdapter(server=server)
            logger.info(
                "Initialized Cultural Intelligence MCP Adapter with Qloo base URL: %s",
                qloo_settings.base_url,
            )
    except Exception as exc:
        logger.warning(
            "Starting in offline/degraded mode (QLOO_API_KEY not configured or invalid): %s",
            exc,
        )

    return TasteOpsOrchestrator(store=store, mcp_adapter=mcp_adapter)


def create_app(
    server_settings: ServerSettings | None = None,
    orchestrator: TasteOpsOrchestrator | None = None,
) -> FastAPI:
    """Application factory for the TasteOps HTTP Service."""
    cfg = server_settings or ServerSettings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        logger.info(
            "Starting TasteOps Backend in %s mode on %s:%s",
            cfg.environment,
            cfg.host,
            cfg.port,
        )
        if not hasattr(app.state, "orchestrator") or app.state.orchestrator is None:
            app.state.orchestrator = orchestrator or build_default_orchestrator(cfg)
        app.state.server_settings = cfg
        yield
        logger.info("TasteOps Backend shutdown complete.")

    app = FastAPI(
        title="TasteOps Cultural Intelligence API",
        version="0.1.0",
        description=(
            "Cultural Intelligence Operating System for Physical Spaces. "
            "Exposes deterministic agent orchestration and Qloo taste intelligence."
        ),
        lifespan=lifespan,
    )

    # Initial state assignment
    app.state.server_settings = cfg
    app.state.orchestrator = orchestrator or build_default_orchestrator(cfg)

    # ==========================================================================
    # CORS Configuration
    # ==========================================================================
    cors_origins = cfg.cors_origins_list
    allow_all = "*" in cors_origins

    # In production, disallow credentials if wildcard origin is configured
    allow_credentials = not allow_all
    logger.info(
        "Configured CORS origins: %s (credentials: %s)", cors_origins, allow_credentials
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins if not allow_all else ["*"],
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ==========================================================================
    # Request Correlation & Diagnostic Middleware
    # ==========================================================================
    @app.middleware("http")
    async def request_id_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        req_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
        request.state.request_id = req_id

        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response

    # ==========================================================================
    # Structured Exception Handlers (Never Leaking Secrets or Internal Paths)
    # ==========================================================================
    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        req_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=f"http_{exc.status_code}",
                message=str(exc.detail),
                request_id=req_id,
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        req_id = getattr(request.state, "request_id", None)
        logger.warning("Validation error on %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error="validation_error",
                message=f"Request validation failed: {exc}",
                request_id=req_id,
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        req_id = getattr(request.state, "request_id", None)
        logger.error(
            "Unhandled server exception on %s (request_id=%s): %s",
            request.url.path,
            req_id,
            exc,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error="internal_server_error",
                message="An unexpected server error occurred. Please contact support.",
                request_id=req_id,
            ).model_dump(),
        )

    # Register routes
    app.include_router(router)

    return app


# Production ASGI instance
app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = ServerSettings()
    port = int(os.getenv("PORT", str(settings.port)))
    uvicorn.run(
        "tasteops.api.main:app",
        host=settings.host,
        port=port,
        reload=(settings.environment == "development"),
    )
