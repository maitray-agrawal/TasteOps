"""FastAPI Route Handlers for the TasteOps Cultural Intelligence API."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from tasteops.agents.governance import UnapprovedExecutionError
from tasteops.api.schemas import (
    ApproveRequest,
    ConfigResponse,
    CreateSessionRequest,
    HealthResponse,
    ReadyResponse,
    RejectRequest,
    RunPipelineRequest,
)
from tasteops.config import QlooSettings, ServerSettings
from tasteops.workflows.context import WorkflowContext
from tasteops.workflows.orchestrator import TasteOpsOrchestrator
from tasteops.workflows.persistence import AuditEvent
from tasteops.workflows.states import InvalidStateTransitionError

logger = logging.getLogger("tasteops.api.routes")

router = APIRouter()


def get_orchestrator(request: Request) -> TasteOpsOrchestrator:
    """Dependency provider for TasteOpsOrchestrator singleton."""
    orchestrator: TasteOpsOrchestrator = request.app.state.orchestrator
    return orchestrator


def get_server_settings(request: Request) -> ServerSettings:
    """Dependency provider for ServerSettings."""
    settings: ServerSettings = request.app.state.server_settings
    return settings


# ==============================================================================
# Health & Readiness Endpoints (Targeted for Render Health Checks)
# ==============================================================================


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness health check",
    tags=["System"],
)
async def health_check() -> HealthResponse:
    """Lightweight health check endpoint.

    Guarantees:
    - Never calls Qloo upstream
    - Does not depend on external database/network
    - Responds in < 5ms
    - Safe for Render Web Service health checks
    """
    return HealthResponse(status="ok", version="0.1.0")


@router.get(
    "/ready",
    response_model=ReadyResponse,
    summary="Readiness probe",
    tags=["System"],
)
async def readiness_check(
    request: Request,
    response: Response,
    settings: Annotated[ServerSettings, Depends(get_server_settings)],
) -> ReadyResponse:
    """Verifies backend readiness to handle traffic.

    Checks:
    - QLOO_API_KEY presence
    - Workflow persistence directory writability
    """
    qloo_configured = False
    try:
        raw_key = os.getenv("QLOO_API_KEY")
        if raw_key is not None:
            qloo_configured = bool(raw_key.strip())
        else:
            qloo_settings = QlooSettings()
            qloo_configured = bool(qloo_settings.raw_api_key)
    except Exception:
        qloo_configured = False

    storage_ready = False
    try:
        storage_path = Path(settings.storage_dir)
        storage_path.mkdir(parents=True, exist_ok=True)
        probe_file = storage_path / ".probe"
        probe_file.write_text("probe", encoding="utf-8")
        probe_file.unlink(missing_ok=True)
        storage_ready = True
    except Exception as exc:
        logger.warning(
            "Storage directory '%s' is not writable: %s", settings.storage_dir, exc
        )
        storage_ready = False

    is_ready = qloo_configured and storage_ready
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadyResponse(
            status="not_ready",
            version="0.1.0",
            qloo_configured=qloo_configured,
            storage_ready=storage_ready,
            details="Backend is starting up or missing credentials (e.g. QLOO_API_KEY).",
        )

    return ReadyResponse(
        status="ready",
        version="0.1.0",
        qloo_configured=True,
        storage_ready=True,
        details="All backend services and storage operational.",
    )


@router.get(
    "/api/v1/config",
    response_model=ConfigResponse,
    summary="Get public configuration",
    tags=["System"],
)
async def get_public_config(
    settings: Annotated[ServerSettings, Depends(get_server_settings)],
) -> ConfigResponse:
    """Returns safe, public runtime configuration. Never leaks API keys or secrets."""
    base_url = "https://hackathon.api.qloo.com"
    try:
        qloo_settings = QlooSettings()
        base_url = qloo_settings.base_url
    except Exception as exc:
        logger.debug("Using default base_url due to configuration resolution: %s", exc)

    return ConfigResponse(
        environment=settings.environment,
        qloo_base_url=base_url,
        version="0.1.0",
        mcp_tools_available=10,
    )


# ==============================================================================
# Workflow & Cultural Intelligence Pipeline Endpoints
# ==============================================================================


@router.post(
    "/api/v1/sessions",
    response_model=WorkflowContext,
    status_code=status.HTTP_201_CREATED,
    summary="Initialize cultural activation session",
    tags=["Sessions"],
)
async def create_session(
    payload: CreateSessionRequest,
    orchestrator: Annotated[TasteOpsOrchestrator, Depends(get_orchestrator)],
) -> WorkflowContext:
    """Initializes a new physical space cultural activation workflow session."""
    return orchestrator.create_session(
        user_input=payload.raw_intent,
        space_id=payload.space_id,
        hints=payload.hints,
    )


@router.get(
    "/api/v1/sessions/{session_id}",
    response_model=WorkflowContext,
    summary="Get session state",
    tags=["Sessions"],
)
async def get_session(
    session_id: str,
    orchestrator: Annotated[TasteOpsOrchestrator, Depends(get_orchestrator)],
) -> WorkflowContext:
    """Retrieves full typed state for an existing workflow session."""
    try:
        return orchestrator.get_session_state(session_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/api/v1/sessions/{session_id}/pipeline",
    response_model=WorkflowContext,
    summary="Run pipeline until human approval gate",
    tags=["Sessions"],
)
async def run_pipeline(
    session_id: str,
    payload: RunPipelineRequest,
    orchestrator: Annotated[TasteOpsOrchestrator, Depends(get_orchestrator)],
) -> WorkflowContext:
    """Drives the workflow pipeline forward until the Human Approval Gate is reached."""
    try:
        return await orchestrator.run_until_approval(
            session_id=session_id,
            hints=payload.hints,
            take_per_category=payload.take_per_category,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/api/v1/sessions/{session_id}/approve",
    response_model=WorkflowContext,
    summary="Approve cultural activation plan",
    tags=["Approval & Execution"],
)
async def approve_session(
    session_id: str,
    payload: ApproveRequest,
    orchestrator: Annotated[TasteOpsOrchestrator, Depends(get_orchestrator)],
) -> WorkflowContext:
    """Records human curator approval with cryptographic plan hash binding."""
    try:
        return await orchestrator.approve_session(
            session_id=session_id,
            approver=payload.approver,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (ValueError, InvalidStateTransitionError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/api/v1/sessions/{session_id}/reject",
    response_model=WorkflowContext,
    summary="Reject cultural activation plan",
    tags=["Approval & Execution"],
)
async def reject_session(
    session_id: str,
    payload: RejectRequest,
    orchestrator: Annotated[TasteOpsOrchestrator, Depends(get_orchestrator)],
) -> WorkflowContext:
    """Transitions workflow to FAILED following curator rejection and invalidates approvals."""
    try:
        return await orchestrator.reject_session(
            session_id=session_id,
            reason=payload.reason,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (ValueError, InvalidStateTransitionError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/api/v1/sessions/{session_id}/execute",
    response_model=WorkflowContext,
    summary="Execute approved cultural activation plan",
    tags=["Approval & Execution"],
)
async def execute_plan(
    session_id: str,
    orchestrator: Annotated[TasteOpsOrchestrator, Depends(get_orchestrator)],
) -> WorkflowContext:
    """Dispatches verified execution tasks with idempotency and provenance enforcement."""
    try:
        return await orchestrator.execute_approved_plan(session_id=session_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (
        ValueError,
        InvalidStateTransitionError,
        UnapprovedExecutionError,
        RuntimeError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/api/v1/sessions/{session_id}/audit",
    response_model=list[AuditEvent],
    summary="Get session audit events",
    tags=["Audit"],
)
async def get_audit_events(
    session_id: str,
    orchestrator: Annotated[TasteOpsOrchestrator, Depends(get_orchestrator)],
) -> list[AuditEvent]:
    """Retrieves all persisted immutable audit events for a workflow session."""
    events = orchestrator.get_audit_events(session_id)
    return events


# ==============================================================================
# Curatorial Execution Artifact Endpoints
# ==============================================================================


@router.get(
    "/api/v1/sessions/{session_id}/artifacts/procurement.csv",
    summary="Download validated procurement purchase order CSV",
    tags=["Artifacts"],
)
async def download_procurement_csv(
    session_id: str,
    orchestrator: Annotated[TasteOpsOrchestrator, Depends(get_orchestrator)],
) -> Response:
    """Exports validated 8-column purchase order CSV with verified Qloo entity provenance."""
    try:
        ctx = orchestrator.get_session_state(session_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    from tasteops.workflows.artifacts import generate_procurement_csv

    csv_content = generate_procurement_csv(ctx)
    filename = f"PO_{session_id[:8]}.csv"
    return Response(
        content=csv_content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/api/v1/sessions/{session_id}/artifacts/spotify_playlist.json",
    summary="Get Spotify-ready playlist specification artifact",
    tags=["Artifacts"],
)
async def get_spotify_playlist_artifact(
    session_id: str,
    orchestrator: Annotated[TasteOpsOrchestrator, Depends(get_orchestrator)],
) -> dict[str, Any]:
    """Retrieves structured, staged Spotify playlist artifact with track metadata and provenance."""
    try:
        ctx = orchestrator.get_session_state(session_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    from tasteops.workflows.artifacts import generate_spotify_playlist_artifact

    return generate_spotify_playlist_artifact(ctx)


@router.get(
    "/api/v1/sessions/{session_id}/artifacts/brand_dossiers.json",
    summary="Get brand partnership dossiers with outreach drafts",
    tags=["Artifacts"],
)
async def get_brand_dossiers_artifact(
    session_id: str,
    orchestrator: Annotated[TasteOpsOrchestrator, Depends(get_orchestrator)],
) -> list[dict[str, Any]]:
    """Retrieves structured partnership dossiers with draft communications and cultural alignment scores."""
    try:
        ctx = orchestrator.get_session_state(session_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    from tasteops.workflows.artifacts import generate_brand_dossiers_artifact

    return generate_brand_dossiers_artifact(ctx)
