"""TasteOps API Session Management Routes.

Provides endpoints for inspecting session states, audit logs, blueprints,
recording curator approvals/rejections, and dispatching execution tasks.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response, status

from tasteops.api.dependencies import ServiceDep
from tasteops.api.schemas.sessions import (
    ApproveSessionRequest,
    ExecutionResponse,
    RejectSessionRequest,
    SessionBlueprintResponse,
    SessionDetailResponse,
    SessionEventsResponse,
)
from tasteops.workflows.context import WorkflowContext

router = APIRouter(prefix="/sessions", tags=["Sessions"])


def format_session_detail(ctx: WorkflowContext) -> SessionDetailResponse:
    """Serializes a WorkflowContext into a typed SessionDetailResponse envelope."""
    cultural_twin_dict: dict[str, Any] | None = None
    if ctx.cultural_twin:
        cultural_twin_dict = (
            ctx.cultural_twin.model_dump()
            if hasattr(ctx.cultural_twin, "model_dump")
            else dict(ctx.cultural_twin)
        )

    cultural_matrix_dict: dict[str, Any] | None = None
    if ctx.cultural_matrix:
        cultural_matrix_dict = (
            ctx.cultural_matrix.model_dump()
            if hasattr(ctx.cultural_matrix, "model_dump")
            else dict(ctx.cultural_matrix)
        )

    plan_dict: dict[str, Any] | None = None
    if ctx.plan:
        plan_dict = (
            ctx.plan.model_dump()
            if hasattr(ctx.plan, "model_dump")
            else dict(ctx.plan)
        )

    validation_dict: dict[str, Any] | None = None
    if ctx.validation_result:
        validation_dict = (
            ctx.validation_result.model_dump()
            if hasattr(ctx.validation_result, "model_dump")
            else dict(ctx.validation_result)
        )

    approval_dict: dict[str, Any] | None = None
    if ctx.approval:
        approval_dict = (
            ctx.approval.model_dump()
            if hasattr(ctx.approval, "model_dump")
            else dict(ctx.approval)
        )

    links = {
        "self": f"/api/v1/sessions/{ctx.session_id}",
        "events": f"/api/v1/sessions/{ctx.session_id}/events",
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
        user_input=ctx.user_input,
        parsed_intent=ctx.parsed_intent,
        cultural_twin=cultural_twin_dict,
        cultural_matrix=cultural_matrix_dict,
        plan=plan_dict,
        validation_result=validation_dict,
        approval=approval_dict,
        execution_tasks_count=len(ctx.execution_tasks),
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
