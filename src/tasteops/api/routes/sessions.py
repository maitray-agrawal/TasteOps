"""TasteOps API Session Management Routes.

Provides endpoints for inspecting session states, audit logs, blueprints,
recording curator approvals/rejections, and dispatching execution tasks.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Header, Query, Request, Response, status
from fastapi.responses import StreamingResponse

from tasteops.api.dependencies import ServiceDep
from tasteops.api.events import format_sse
from tasteops.api.schemas.sessions import (
    ApproveSessionRequest,
    ExecutionResponse,
    RejectSessionRequest,
    SessionBlueprintResponse,
    SessionDetailResponse,
    SessionEventsResponse,
)
from tasteops.workflows.context import WorkflowContext
from tasteops.workflows.states import WorkflowState

logger = logging.getLogger("tasteops.api.routes.sessions")
router = APIRouter(prefix="/sessions", tags=["Sessions"])


def format_session_detail(ctx: WorkflowContext) -> SessionDetailResponse:
    """Serializes a WorkflowContext into a typed, safe SessionDetailResponse envelope."""
    # 1. High-level status
    status_str = "IN_PROGRESS"
    if ctx.current_state == WorkflowState.AWAITING_APPROVAL:
        status_str = "AWAITING_APPROVAL"
    elif ctx.current_state == WorkflowState.APPROVED:
        status_str = "APPROVED"
    elif ctx.current_state == WorkflowState.EXECUTING:
        status_str = "EXECUTING"
    elif ctx.current_state == WorkflowState.COMPLETED:
        status_str = "COMPLETED"
    elif ctx.current_state == WorkflowState.FAILED:
        status_str = "FAILED"

    # 2. Cultural Twin (Safe typed view without chain-of-thought)
    cultural_twin_dict: dict[str, Any] | None = None
    if ctx.cultural_twin:
        ct = ctx.cultural_twin
        cultural_twin_dict = {
            "audience_profile": getattr(ct, "audience_profile", ""),
            "cultural_themes": getattr(ct, "cultural_themes", []),
            "mood_profile": getattr(ct, "mood_profile", ""),
            "anchor_entities": getattr(ct, "anchor_entities", []),
            "resolved_entities": [
                {
                    "id": getattr(e, "id", ""),
                    "name": getattr(e, "name", ""),
                    "type": getattr(e, "type", ""),
                    "confidence": getattr(e, "confidence", 1.0),
                    "why_it_matters": getattr(e, "why_it_matters", ""),
                }
                for e in getattr(ct, "resolved_entities", [])
            ],
            "resolved_tags": getattr(ct, "resolved_tags", []),
            "cultural_constraints": getattr(ct, "cultural_constraints", []),
            "confidence": getattr(ct, "confidence", 1.0),
        }

    # 3. Cultural Matrix Summary (Metrics without raw provider dumps)
    cultural_matrix_dict: dict[str, Any] | None = None
    cultural_matrix_summary: dict[str, Any] | None = None
    if ctx.cultural_matrix:
        mat = ctx.cultural_matrix
        cultural_matrix_dict = (
            mat.model_dump() if hasattr(mat, "model_dump") else dict(mat)
        )
        cat_counts = {
            "artists": len(getattr(mat, "artists", [])),
            "books": len(getattr(mat, "books", [])),
            "brands": len(getattr(mat, "brands", [])),
            "places": len(getattr(mat, "places", [])),
            "movies": len(getattr(mat, "movies", [])),
            "destinations": len(getattr(mat, "destinations", [])),
        }
        top_affinities: dict[str, list[dict[str, Any]]] = {}
        for cat in ["artists", "books", "brands", "places", "movies", "destinations"]:
            recs = getattr(mat, cat, [])
            if recs:
                top_affinities[cat] = [
                    {
                        "id": getattr(r, "id", ""),
                        "name": getattr(r, "name", ""),
                        "affinity": getattr(r, "affinity", 0.0),
                        "source_query": getattr(r, "source_query", ""),
                    }
                    for r in recs[:5]
                ]
        cultural_matrix_summary = {
            "total_entities": sum(cat_counts.values()),
            "fingerprint": getattr(mat, "fingerprint", None),
            "domains_present": [k for k, v in cat_counts.items() if v > 0],
            "category_counts": cat_counts,
            "top_affinities": top_affinities,
            "evidence_count": len(getattr(mat, "evidence", [])),
        }

    # 4. Agent Summaries
    strat = ctx.strategy_output or (ctx.plan.strategy if ctx.plan else None)
    exp = ctx.experience_output or (ctx.plan.experience_design if ctx.plan else None)
    part = ctx.partnership_output or (ctx.plan.partnerships if ctx.plan else None)
    gov = ctx.validation_result or ctx.governance_output or (ctx.plan.governance if ctx.plan else None)

    agent_summaries: dict[str, Any] = {}
    if strat:
        pillars = getattr(strat, "cultural_pillars", [])
        agent_summaries["cultural_strategist"] = {
            "positioning": getattr(strat, "positioning_statement", ""),
            "pillars_count": len(pillars),
            "pillars": [getattr(p, "name", str(p)) for p in pillars],
            "target_audience": getattr(strat, "target_audience", ""),
        }
    if exp:
        zones = getattr(exp, "spatial_zones", [])
        sonic = getattr(exp, "sonic_identity", None)
        reading = getattr(exp, "reading_library_identity", None)
        brand = getattr(exp, "brand_ecosystem", None)
        agent_summaries["experience_architect"] = {
            "spatial_zones_count": len(zones),
            "sonic_profile": getattr(sonic, "acoustic_profile", "") if sonic else None,
            "reading_library": getattr(reading, "overview", "") if reading else None,
            "material_palette": getattr(brand, "material_palette", []) if brand else [],
        }
    if part:
        partnerships = getattr(part, "partnerships", [])
        agent_summaries["partnership_agent"] = {
            "partnerships_count": len(partnerships),
            "partners": [
                {
                    "name": getattr(p, "partner_name", ""),
                    "type": getattr(p, "partnership_type", ""),
                    "tier": getattr(p, "tier", ""),
                }
                for p in partnerships
            ],
        }
    if gov:
        agent_summaries["governance_agent"] = {
            "is_valid": gov.is_valid,
            "provenance_verified": getattr(gov, "provenance_verified", True),
            "compliance_score": getattr(gov, "compliance_score", 1.0),
            "risk_flags_count": len(getattr(gov, "risk_flags", [])),
        }

    # 5. Validation Summary
    validation_dict: dict[str, Any] | None = None
    if gov:
        validation_dict = {
            "is_valid": gov.is_valid,
            "provenance_verified": getattr(gov, "provenance_verified", True),
            "compliance_score": getattr(gov, "compliance_score", 1.0),
            "risk_flags": getattr(gov, "risk_flags", []),
            "recommendations": getattr(gov, "recommendations", []),
        }

    # 6. Execution Plan
    plan_dict: dict[str, Any] | None = None
    if ctx.plan:
        plan_dict = ctx.plan.model_dump() if hasattr(ctx.plan, "model_dump") else dict(ctx.plan)

    exec_plan = ctx.execution_plan or (ctx.plan.execution_plan if ctx.plan else None)
    execution_plan_dict: dict[str, Any] | None = None
    if exec_plan:
        actions = [
            {
                "action_id": a.action_id,
                "title": getattr(a, "title", a.action_id),
                "category": getattr(a, "category", "general"),
                "description": a.description,
                "owner": a.owner,
            }
            for a in getattr(exec_plan, "actions", [])
        ]
        plan_hash = getattr(exec_plan, "plan_hash", None) or (ctx.plan.compute_hash() if ctx.plan else None)
        execution_plan_dict = {
            "plan_id": exec_plan.plan_id,
            "version": exec_plan.version,
            "plan_hash": plan_hash,
            "estimated_cost": exec_plan.estimated_cost,
            "actions_count": len(actions),
            "actions": actions,
            "risks": getattr(exec_plan, "risks", []),
            "approvals_required": getattr(exec_plan, "approvals_required", []),
        }

    # 7. Approval State
    approval_dict: dict[str, Any] | None = None
    if ctx.approval:
        approval_dict = ctx.approval.model_dump() if hasattr(ctx.approval, "model_dump") else dict(ctx.approval)

    approval_state: dict[str, Any] = {
        "is_approved": False,
        "status": "PENDING",
        "approver": None,
        "role": None,
        "approved_at": None,
        "plan_hash": None,
        "notes": None,
    }
    if ctx.approval:
        approval_state["is_approved"] = bool(ctx.approval.is_valid)
        approval_state["status"] = "APPROVED" if ctx.approval.is_valid else "INVALIDATED"
        approval_state["approver"] = ctx.approval.approver
        approval_state["role"] = getattr(ctx.approval, "role", "Lead Cultural Strategist")
        approval_state["approved_at"] = (
            ctx.approval.approved_at.isoformat()
            if hasattr(ctx.approval.approved_at, "isoformat")
            else str(ctx.approval.approved_at)
        )
        approval_state["plan_hash"] = ctx.approval.plan_hash
        approval_state["notes"] = getattr(ctx.approval, "notes", getattr(ctx.approval, "invalidation_reason", None))

    # 8. Execution State
    executed_tasks = sum(1 for t in ctx.execution_tasks if t.status == "EXECUTED")
    failed_tasks = sum(1 for t in ctx.execution_tasks if t.status == "FAILED")
    total_tasks = len(ctx.execution_tasks)
    exec_status = "NOT_STARTED"
    if total_tasks > 0:
        if executed_tasks == total_tasks:
            exec_status = "COMPLETED"
        elif executed_tasks > 0 or failed_tasks > 0:
            exec_status = "EXECUTING"
    execution_state = {
        "status": exec_status,
        "total_tasks": total_tasks,
        "executed_tasks": executed_tasks,
        "failed_tasks": failed_tasks,
        "tasks": [
            {
                "task_id": t.task_id,
                "action": t.action,
                "owner": t.owner,
                "status": t.status,
                "output_reference": t.output_reference,
            }
            for t in ctx.execution_tasks
        ],
    }

    # 9. Errors (Sanitized, no stack traces or chain of thought)
    errors: list[str] = []
    if ctx.error_message:
        clean_lines = []
        for line in ctx.error_message.splitlines():
            s = line.strip()
            if s and not s.startswith("Traceback") and not s.startswith('File "'):
                clean_lines.append(s)
        errors = [clean_lines[-1]] if clean_lines else [ctx.error_message.strip()]

    # 10. Timestamps
    now_iso = datetime.now(UTC).isoformat()
    created_at = ctx.history[0].timestamp.isoformat() if ctx.history else now_iso
    updated_at = ctx.history[-1].timestamp.isoformat() if ctx.history else now_iso
    completed_at = (
        ctx.history[-1].timestamp.isoformat()
        if ctx.current_state in {WorkflowState.COMPLETED, WorkflowState.FAILED}
        else None
    )
    timestamps = {
        "created_at": created_at,
        "updated_at": updated_at,
        "approved_at": approval_state["approved_at"],
        "completed_at": completed_at,
    }

    links = {
        "self": f"/api/v1/sessions/{ctx.session_id}",
        "events": f"/api/v1/sessions/{ctx.session_id}/events",
        "stream": f"/api/v1/sessions/{ctx.session_id}/stream",
        "blueprint": f"/api/v1/sessions/{ctx.session_id}/blueprint",
        "approve": f"/api/v1/sessions/{ctx.session_id}/approve",
        "reject": f"/api/v1/sessions/{ctx.session_id}/reject",
        "execute": f"/api/v1/sessions/{ctx.session_id}/execute",
    }
    if ctx.space_id:
        links["space"] = f"/api/v1/spaces/{ctx.space_id}"

    return SessionDetailResponse(
        session_id=ctx.session_id,
        space_id=ctx.space_id,
        current_state=ctx.current_state.value,
        status=status_str,
        user_input=ctx.user_input,
        parsed_intent=ctx.parsed_intent,
        cultural_twin=cultural_twin_dict,
        cultural_matrix_summary=cultural_matrix_summary,
        agent_summaries=agent_summaries,
        validation=validation_dict,
        execution_plan=execution_plan_dict,
        approval_state=approval_state,
        execution_state=execution_state,
        errors=errors,
        timestamps=timestamps,
        # Backward-compatibility fields
        plan=plan_dict,
        cultural_matrix=cultural_matrix_dict,
        validation_result=validation_dict,
        approval=approval_dict,
        execution_tasks_count=total_tasks,
        error_message=ctx.error_message,
        links=links,
    )


@router.get(
    "/{session_id}",
    response_model=SessionDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Workflow Session",
    description="Retrieves the complete state, cultural twin, matrix, plan, and validation result of a session.",
    responses={404: {"description": "Session not found"}},
)
async def get_session(session_id: str, service: ServiceDep) -> SessionDetailResponse:
    ctx = service.get_session(session_id)
    return format_session_detail(ctx)


@router.get(
    "/{session_id}/events",
    response_model=SessionEventsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Session Audit Events",
    description="Returns the immutable audit log event ledger and state transition progression.",
    responses={404: {"description": "Session not found"}},
)
async def get_session_events(
    session_id: str, service: ServiceDep
) -> SessionEventsResponse:
    audit_events, history = service.get_session_events(session_id)
    serialized_events = [
        evt.model_dump() if hasattr(evt, "model_dump") else dict(evt)
        for evt in audit_events
    ]
    serialized_history = [
        h.model_dump() if hasattr(h, "model_dump") else dict(h) for h in history
    ]

    return SessionEventsResponse(
        session_id=session_id,
        total_events=len(serialized_events),
        events=serialized_events,
        history=serialized_history,
    )


@router.get(
    "/{session_id}/blueprint",
    response_model=SessionBlueprintResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Session Blueprint",
    description="Returns the synthesized architectural, sensory, sonic, and curatorial blueprint.",
    responses={
        404: {"description": "Session not found"},
        409: {"description": "Blueprint not yet generated for this session"},
    },
)
async def get_session_blueprint(
    session_id: str, service: ServiceDep
) -> SessionBlueprintResponse:
    blueprint = service.get_session_blueprint(session_id)
    return SessionBlueprintResponse(**blueprint)


@router.get(
    "/{session_id}/stream",
    response_class=StreamingResponse,
    summary="Server-Sent Events Stream",
    description="Streams real-time structured workflow events for a session with deterministic ordering, reconnect safety, and event recovery.",
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": "Stream of safe structured SSE events.",
        },
        404: {"description": "Session not found"},
    },
)
async def stream_session_events(
    session_id: str,
    request: Request,
    service: ServiceDep,
    last_event_id_header: str | None = Header(None, alias="Last-Event-ID"),
    last_event_id_query: str | None = Query(None, alias="last_event_id"),
    wait: bool = Query(True, description="Keep stream open for live events if session is active"),
) -> StreamingResponse:
    # 1. Authoritative verification that session exists (raises 404 if not found)
    service.get_session(session_id)

    # 2. Extract reconnect identifier
    last_event_id = last_event_id_header or last_event_id_query

    # 3. Subscribe to real-time broadcaster before snapshot to prevent race conditions
    queue = service.broadcaster.subscribe(session_id)

    async def event_generator():
        seen_event_ids: set[str] = set()
        try:
            # 4. Recover persisted historical events
            historical_events = service.get_session_sse_events(session_id)

            # Reconnect-safe slicing: only send events subsequent to last_event_id
            start_idx = 0
            if last_event_id:
                for idx, ev in enumerate(historical_events):
                    if ev.event_id == last_event_id:
                        start_idx = idx + 1
                        break

            for ev in historical_events[start_idx:]:
                seen_event_ids.add(ev.event_id)
                yield format_sse(ev)

            # If session is already terminal or wait=False, close stream cleanly
            current_ctx = service.get_session(session_id)
            if (
                current_ctx.current_state in (WorkflowState.COMPLETED, WorkflowState.FAILED)
                or not wait
            ):
                return

            # 5. Live event streaming loop with keep-alive pings and client disconnect detection
            while True:
                if await request.is_disconnected():
                    logger.info("SSE client disconnected for session %s", session_id)
                    break
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=1.0)
                    if ev.event_id in seen_event_ids:
                        continue
                    seen_event_ids.add(ev.event_id)
                    yield format_sse(ev)

                    if ev.event_type in ("execution.completed", "workflow.failed"):
                        break
                except asyncio.TimeoutError:
                    if await request.is_disconnected():
                        break
                    yield ": ping\n\n"
                    # Check if session transitioned to terminal state
                    check_ctx = service.get_session(session_id)
                    if check_ctx.current_state in (
                        WorkflowState.COMPLETED,
                        WorkflowState.FAILED,
                    ):
                        break
        finally:
            service.broadcaster.unsubscribe(session_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/{session_id}/approve",
    response_model=SessionDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve Activation Plan",
    description="Records human curator approval, binds the plan hash cryptographically, and unblocks execution.",
    responses={
        400: {"description": "Invalid approver payload"},
        404: {"description": "Session not found"},
        409: {"description": "Session is not awaiting approval"},
    },
)
async def approve_session(
    session_id: str,
    request: ApproveSessionRequest,
    service: ServiceDep,
) -> SessionDetailResponse:
    ctx = await service.approve_session(
        session_id=session_id,
        approver=request.approver,
        role=request.role,
        notes=request.notes,
        plan_version=request.plan_version,
    )
    return format_session_detail(ctx)


@router.post(
    "/{session_id}/reject",
    response_model=SessionDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject Activation Plan",
    description="Records human curator rejection, invalidates any pending approval, and transitions workflow to FAILED.",
    responses={
        404: {"description": "Session not found"},
        409: {"description": "Session cannot be rejected from its current state"},
    },
)
async def reject_session(
    session_id: str,
    request: RejectSessionRequest,
    service: ServiceDep,
) -> SessionDetailResponse:
    ctx = await service.reject_session(
        session_id=session_id,
        reason=request.reason,
    )
    return format_session_detail(ctx)


@router.post(
    "/{session_id}/execute",
    response_model=ExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Approved Plan",
    description="Dispatches external integration tasks with strict idempotency and provenance enforcement.",
    responses={
        403: {"description": "Execution attempted prior to explicit curator approval"},
        404: {"description": "Session not found"},
        409: {"description": "Session state invalid for execution"},
        422: {"description": "Provenance validation failed"},
    },
)
async def execute_session(
    session_id: str,
    service: ServiceDep,
) -> ExecutionResponse:
    ctx = await service.execute_session(session_id)
    tasks = [
        task.model_dump() if hasattr(task, "model_dump") else dict(task)
        for task in ctx.execution_tasks
    ]
    executed = sum(1 for t in ctx.execution_tasks if t.status == "EXECUTED")
    failed = sum(1 for t in ctx.execution_tasks if t.status == "FAILED")

    audit_report = None
    if ctx.agent_results and ctx.agent_results.strategy:
        pass
    # Extract audit report if stored in context
    if hasattr(ctx, "governance_output") and ctx.governance_output:
        audit_report = (
            ctx.governance_output.model_dump()
            if hasattr(ctx.governance_output, "model_dump")
            else dict(ctx.governance_output)
        )

    return ExecutionResponse(
        session_id=ctx.session_id,
        current_state=ctx.current_state.value,
        total_tasks=len(tasks),
        executed_tasks=executed,
        failed_tasks=failed,
        tasks=tasks,
        audit_report=audit_report,
    )
