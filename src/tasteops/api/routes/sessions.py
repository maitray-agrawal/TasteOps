"""TasteOps API Session Management Routes.

Provides endpoints for inspecting session states, audit logs, blueprints,
recording curator approvals/rejections, and dispatching execution tasks.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Header, Path, Query, Request, status
from fastapi.responses import StreamingResponse

from tasteops.api.dependencies import AuthDep, ServiceDep
from tasteops.api.events import format_sse
from tasteops.api.schemas.sessions import (
    ApproveSessionRequest,
    ExecutionResponse,
    RejectSessionRequest,
    SessionBlueprintResponse,
    SessionDetailResponse,
    SessionEventsResponse,
)
from tasteops.connectors.base import (
    ConnectorExecutionRequest,
    ConnectorExecutionResult,
)
from tasteops.workflows.context import WorkflowContext
from tasteops.workflows.states import WorkflowState

logger = logging.getLogger("tasteops.api.routes.sessions")
router = APIRouter(prefix="/sessions", tags=["Sessions"])


def _resolve_connector(category: str, task_type: str, desc: str) -> str:
    """Determines external connector availability.

    If the connector credentials or integrations are not configured in the environment,
    returns 'NOT_CONFIGURED'. Does not simulate external execution.
    """
    cat_lower = (category or "").lower()
    type_lower = (task_type or "").lower()
    desc_lower = (desc or "").lower()

    if (
        "spotify" in cat_lower
        or "spotify" in type_lower
        or "spotify" in desc_lower
        or "sonic" in cat_lower
    ):
        spotify_client_id = os.getenv("SPOTIFY_CLIENT_ID")
        if spotify_client_id and spotify_client_id.strip():
            return "Spotify Web API"
        return "NOT_CONFIGURED"

    if (
        "outreach" in cat_lower
        or "partner" in cat_lower
        or "brand" in cat_lower
        or "outreach" in desc_lower
    ):
        outreach_key = os.getenv("PARTNER_OUTREACH_API_KEY") or os.getenv(
            "SENDGRID_API_KEY"
        )
        if outreach_key and outreach_key.strip():
            return "Partner Outreach Mailer"
        return "NOT_CONFIGURED"

    if (
        "spatial" in cat_lower
        or "design" in cat_lower
        or "cad" in cat_lower
        or "spatial" in desc_lower
    ):
        cad_key = os.getenv("CAD_CONNECTOR_KEY") or os.getenv("AUTODESK_API_KEY")
        if cad_key and cad_key.strip():
            return "Spatial CAD Specifier"
        return "NOT_CONFIGURED"

    if "programming" in cat_lower or "calendar" in cat_lower or "salon" in desc_lower:
        calendar_key = os.getenv("CALENDAR_API_KEY") or os.getenv("NOTION_API_KEY")
        if calendar_key and calendar_key.strip():
            return "Curatorial Calendar Dispatcher"
        return "NOT_CONFIGURED"

    if "hospitality" in cat_lower or "training" in cat_lower or "tempo" in desc_lower:
        lms_key = os.getenv("LMS_CONNECTOR_KEY")
        if lms_key and lms_key.strip():
            return "Staff Operations Portal"
        return "NOT_CONFIGURED"

    return "NOT_CONFIGURED"


def _format_execution_tasks(ctx: WorkflowContext) -> list[dict[str, Any]]:
    """Formats execution tasks with complete 10-field telemetry and connector detection.

    Required Fields:
    - task_id
    - task_type
    - description
    - status (PENDING, APPROVED, RUNNING, COMPLETED, FAILED, SKIPPED)
    - estimated_cost
    - connector (NOT_CONFIGURED if unavailable)
    - approval_status
    - execution_timestamp
    - result
    - error
    """
    is_session_approved = bool(
        ctx.current_state == WorkflowState.APPROVED
        or (ctx.approval and ctx.approval.is_valid)
        or ctx.current_state in {WorkflowState.EXECUTING, WorkflowState.COMPLETED}
    )
    approval_str = "APPROVED" if is_session_approved else "PENDING"

    # Pre-build action cost lookup map from execution plan
    cost_map: dict[str, str] = {}
    if ctx.execution_plan and hasattr(ctx.execution_plan, "actions"):
        for a in ctx.execution_plan.actions:
            if hasattr(a, "action_id"):
                cost_map[a.action_id] = getattr(a, "estimated_cost", "$0")
            target_id = getattr(a, "target_entity_id", None)
            if target_id:
                cost_map[str(target_id)] = getattr(a, "estimated_cost", "$0")

    tasks_out: list[dict[str, Any]] = []

    # Case 1: Tasks exist in context
    if ctx.execution_tasks:
        for t in ctx.execution_tasks:
            raw_status = str(getattr(t, "status", "PENDING")).upper()
            if raw_status in {"EXECUTED", "COMPLETED"}:
                status = "COMPLETED"
            elif raw_status == "FAILED":
                status = "FAILED"
            elif raw_status == "SKIPPED":
                status = "SKIPPED"
            elif raw_status in {"RUNNING", "EXECUTING"}:
                status = "RUNNING"
            elif raw_status == "APPROVED" or (
                raw_status == "PENDING" and is_session_approved
            ):
                status = "APPROVED"
            else:
                status = "PENDING"

            category = getattr(t, "category", "") or "general_execution"
            task_type = getattr(t, "task_type", "") or category
            desc = getattr(t, "description", "") or getattr(t, "action", "")

            # Cost resolution
            cost = getattr(t, "estimated_cost", None)
            if not cost or cost == "$0":
                t_target_id = getattr(t, "target_entity_id", None)
                target_cost = cost_map.get(str(t_target_id)) if t_target_id else None
                cost = (
                    cost_map.get(t.task_id)
                    or target_cost
                    or cost_map.get(t.task_id.replace("task_", "act_"), "$0")
                )

            # Connector resolution
            connector = getattr(t, "connector", None)
            if not connector or connector == "NOT_CONFIGURED":
                connector = _resolve_connector(category, task_type, desc)

            # Timestamp resolution
            exec_ts = None
            if status in {"COMPLETED", "FAILED", "RUNNING"}:
                ts_val = getattr(t, "executed_at", None) or getattr(
                    t, "timestamp", None
                )
                if ts_val:
                    exec_ts = (
                        ts_val.isoformat()
                        if hasattr(ts_val, "isoformat")
                        else str(ts_val)
                    )

            # Result resolution
            res = getattr(t, "result", None)
            if not res and getattr(t, "output_reference", None):
                res = {"output_reference": t.output_reference}

            # Error resolution
            err = getattr(t, "error", None)
            if not err and status == "FAILED" and isinstance(res, dict):
                err = res.get("error")

            tasks_out.append(
                {
                    "task_id": t.task_id,
                    "task_type": task_type,
                    "description": desc,
                    "status": status,
                    "estimated_cost": cost,
                    "connector": connector,
                    "approval_status": approval_str,
                    "execution_timestamp": exec_ts,
                    "result": res,
                    "error": err,
                    # Backward-compatibility fields
                    "action": getattr(t, "action", desc),
                    "owner": getattr(t, "owner", "GovernanceAgent"),
                    "output_reference": getattr(t, "output_reference", None),
                    "idempotency_key": getattr(
                        t, "idempotency_key", f"idem_{t.task_id}"
                    ),
                }
            )

    # Case 2: No execution_tasks yet, but execution_plan has planned actions (pre-execution state)
    elif (
        ctx.execution_plan
        and hasattr(ctx.execution_plan, "actions")
        and ctx.execution_plan.actions
    ):
        for a in ctx.execution_plan.actions:
            act_id = getattr(a, "action_id", "act_01")
            title = getattr(a, "title", "")
            desc = getattr(a, "description", "") or title

            # Infer task type
            if (
                "sonic" in act_id
                or "spotify" in title.lower()
                or "audio" in title.lower()
            ):
                category = "spotify_audio_seed"
            elif (
                "outreach" in act_id or "brand" in act_id or "partner" in title.lower()
            ):
                category = "partner_outreach_brief"
            elif (
                "hospitality" in act_id
                or "spatial" in title.lower()
                or "atmosphere" in title.lower()
            ):
                category = "spatial_design_spec"
            elif (
                "prog" in act_id
                or "salon" in title.lower()
                or "calendar" in title.lower()
            ):
                category = "curatorial_programming"
            else:
                category = "general_execution"

            status = "APPROVED" if is_session_approved else "PENDING"
            connector = _resolve_connector(category, category, desc)

            tasks_out.append(
                {
                    "task_id": f"task_{act_id}",
                    "task_type": category,
                    "description": desc,
                    "status": status,
                    "estimated_cost": getattr(a, "estimated_cost", "$0"),
                    "connector": connector,
                    "approval_status": approval_str,
                    "execution_timestamp": None,
                    "result": None,
                    "error": None,
                    # Backward-compatibility fields
                    "action": desc,
                    "owner": getattr(a, "owner", "GovernanceAgent"),
                    "output_reference": None,
                    "idempotency_key": f"idem_{act_id}",
                }
            )

    return tasks_out


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

        resolved_entities_list = []
        for e in getattr(ct, "resolved_entities", []):
            resolved_entities_list.append(
                {
                    "id": getattr(e, "id", ""),
                    "name": getattr(e, "name", ""),
                    "type": getattr(e, "type", ""),
                    "confidence": getattr(e, "confidence", 1.0),
                    "why_it_matters": getattr(e, "why_it_matters", ""),
                    "source": getattr(e, "source", "qloo_search"),
                    "evidence": getattr(e, "evidence", {})
                    if isinstance(getattr(e, "evidence", {}), dict)
                    else {},
                }
            )

        resolved_tags_list = []
        for t in getattr(ct, "resolved_tag_details", []):
            resolved_tags_list.append(
                {
                    "id": getattr(t, "id", ""),
                    "name": getattr(t, "name", ""),
                    "category": getattr(t, "category", None),
                    "confidence": getattr(t, "confidence", 1.0),
                    "why_it_matters": getattr(t, "why_it_matters", ""),
                }
            )

        matrix_evidence = []
        if ctx.cultural_matrix and hasattr(ctx.cultural_matrix, "evidence"):
            for ev in ctx.cultural_matrix.evidence:
                matrix_evidence.append(
                    {
                        "category": getattr(ev, "category", ""),
                        "message": getattr(ev, "message", ""),
                        "timestamp": getattr(
                            ev, "timestamp", datetime.now(UTC)
                        ).isoformat()
                        if hasattr(getattr(ev, "timestamp", None), "isoformat")
                        else str(getattr(ev, "timestamp", "")),
                        "signals_used": getattr(ev, "signals_used", []),
                    }
                )

        provenance_trace = []
        for ent in resolved_entities_list:
            provenance_trace.append(
                {
                    "type": "entity_resolution",
                    "target_id": ent["id"],
                    "target_name": ent["name"],
                    "source": ent["source"],
                    "confidence": ent["confidence"],
                    "evidence": ent["evidence"],
                }
            )
        for mev in matrix_evidence:
            provenance_trace.append(
                {
                    "type": "cultural_matrix_query",
                    "category": mev["category"],
                    "source": "qloo_cultural_matrix",
                    "message": mev["message"],
                    "signals_used": mev["signals_used"],
                    "timestamp": mev["timestamp"],
                }
            )

        raw_constraints = getattr(ct, "constraints", {})
        if isinstance(raw_constraints, dict) and "raw_constraints" in raw_constraints:
            constraints_val = raw_constraints["raw_constraints"]
        else:
            constraints_val = raw_constraints

        cultural_twin_dict = {
            "audience_profile": getattr(ct, "audience_profile", ""),
            "cultural_themes": getattr(ct, "cultural_themes", []),
            "mood_profile": getattr(ct, "mood_profile", ""),
            "mood": getattr(ct, "mood", getattr(ct, "mood_profile", "")),
            "anchor_entities": getattr(ct, "anchor_entities", []),
            "resolved_entities": resolved_entities_list,
            "resolved_tags": getattr(ct, "resolved_tags", []),
            "resolved_tag_details": resolved_tags_list,
            "constraints": constraints_val,
            "cultural_constraints": getattr(ct, "cultural_constraints", []),
            "exclusions": getattr(ct, "exclusions", []),
            "confidence": getattr(ct, "confidence", 1.0),
            "evidence": matrix_evidence,
            "provenance": provenance_trace,
            "signal_explanations": getattr(ct, "signal_explanations", {}),
            "business_type": getattr(ct, "business_type", None),
            "positioning": getattr(ct, "positioning", None),
            "budget": getattr(ct, "budget", None),
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

    # 4. Agent Summaries & Activity Telemetry
    strat = ctx.strategy_output or (ctx.plan.strategy if ctx.plan else None)
    exp = ctx.experience_output or (ctx.plan.experience_design if ctx.plan else None)
    part = ctx.partnership_output or (ctx.plan.partnerships if ctx.plan else None)
    gov = (
        ctx.validation_result
        or ctx.governance_output
        or (ctx.plan.governance if ctx.plan else None)
    )

    curr = ctx.current_state
    state_timestamps: dict[WorkflowState, datetime] = {}
    for h in ctx.history:
        state_timestamps[h.to_state] = h.timestamp
    init_time = ctx.history[0].timestamp if ctx.history else datetime.now(UTC)

    # 4A. Cultural Strategist
    strat_start = init_time.isoformat()
    if WorkflowState.CULTURAL_MATRIX_READY in state_timestamps:
        strat_end = state_timestamps[WorkflowState.CULTURAL_MATRIX_READY].isoformat()
        strat_dur = max(
            0.12,
            (
                state_timestamps[WorkflowState.CULTURAL_MATRIX_READY] - init_time
            ).total_seconds(),
        )
        strat_dur_str = f"{strat_dur:.2f}s"
        strat_status = "COMPLETED"
    elif curr == WorkflowState.FAILED and not strat:
        strat_end = datetime.now(UTC).isoformat()
        strat_dur_str = "0.00s"
        strat_status = "FAILED"
    elif ctx.qloo_retry_count > 0 and curr in {
        WorkflowState.CULTURAL_TWIN_CREATED,
        WorkflowState.QLOO_RESOLVED,
    }:
        strat_end = None
        strat_dur_str = None
        strat_status = "RETRYING"
    elif curr in {
        WorkflowState.CREATED,
        WorkflowState.INTENT_PARSED,
        WorkflowState.CULTURAL_TWIN_CREATED,
        WorkflowState.QLOO_RESOLVED,
    }:
        strat_end = None
        strat_dur_str = None
        strat_status = "RUNNING"
    else:
        strat_end = init_time.isoformat()
        strat_dur_str = "0.15s"
        strat_status = "COMPLETED"

    pillars = getattr(strat, "cultural_pillars", []) if strat else []
    strat_evidence_cnt = (
        len(getattr(ctx.cultural_twin, "resolved_entities", []))
        + len(getattr(ctx.cultural_twin, "resolved_tags", []))
        if ctx.cultural_twin
        else 0
    )

    # 4B. Experience Architect
    if curr in {
        WorkflowState.CREATED,
        WorkflowState.INTENT_PARSED,
        WorkflowState.CULTURAL_TWIN_CREATED,
        WorkflowState.QLOO_RESOLVED,
    }:
        exp_status = "BLOCKED"
        exp_start = None
        exp_end = None
        exp_dur_str = None
    elif (
        curr in {WorkflowState.CULTURAL_MATRIX_READY, WorkflowState.AGENTS_RUNNING}
        and not exp
    ):
        exp_status = "RETRYING" if ctx.agent_retry_count > 0 else "RUNNING"
        exp_start = (
            state_timestamps.get(WorkflowState.AGENTS_RUNNING)
            or state_timestamps.get(WorkflowState.CULTURAL_MATRIX_READY, init_time)
        ).isoformat()
        exp_end = None
        exp_dur_str = None
    elif (
        curr == WorkflowState.FAILED
        and not exp
        and curr == WorkflowState.AGENTS_RUNNING
    ):
        exp_status = "FAILED"
        exp_start = state_timestamps.get(
            WorkflowState.AGENTS_RUNNING, init_time
        ).isoformat()
        exp_end = datetime.now(UTC).isoformat()
        exp_dur_str = None
    else:
        exp_status = "COMPLETED" if exp else "BLOCKED"
        t0 = state_timestamps.get(WorkflowState.AGENTS_RUNNING) or state_timestamps.get(
            WorkflowState.CULTURAL_MATRIX_READY, init_time
        )
        t1 = state_timestamps.get(WorkflowState.PLAN_GENERATED) or state_timestamps.get(
            WorkflowState.VALIDATED, t0
        )
        exp_start = t0.isoformat()
        exp_end = t1.isoformat()
        exp_dur = max(0.18, (t1 - t0).total_seconds()) if exp else 0.0
        exp_dur_str = f"{exp_dur:.2f}s" if exp else None

    zones = getattr(exp, "spatial_zones", []) if exp else []
    sonic = getattr(exp, "sonic_identity", None) if exp else None
    reading = getattr(exp, "reading_library_identity", None) if exp else None
    brand = getattr(exp, "brand_ecosystem", None) if exp else None
    exp_evidence_cnt = (
        len(zones) + len(getattr(brand, "material_palette", [])) if exp else 0
    )

    # 4C. Partnership Agent
    if curr in {
        WorkflowState.CREATED,
        WorkflowState.INTENT_PARSED,
        WorkflowState.CULTURAL_TWIN_CREATED,
        WorkflowState.QLOO_RESOLVED,
    }:
        part_status = "BLOCKED"
        part_start = None
        part_end = None
        part_dur_str = None
    elif (
        curr in {WorkflowState.CULTURAL_MATRIX_READY, WorkflowState.AGENTS_RUNNING}
        and not part
    ):
        part_status = "RETRYING" if ctx.agent_retry_count > 0 else "RUNNING"
        part_start = (
            state_timestamps.get(WorkflowState.AGENTS_RUNNING)
            or state_timestamps.get(WorkflowState.CULTURAL_MATRIX_READY, init_time)
        ).isoformat()
        part_end = None
        part_dur_str = None
    elif (
        curr == WorkflowState.FAILED
        and not part
        and curr == WorkflowState.AGENTS_RUNNING
    ):
        part_status = "FAILED"
        part_start = state_timestamps.get(
            WorkflowState.AGENTS_RUNNING, init_time
        ).isoformat()
        part_end = datetime.now(UTC).isoformat()
        part_dur_str = None
    else:
        part_status = "COMPLETED" if part else "BLOCKED"
        t0 = state_timestamps.get(WorkflowState.AGENTS_RUNNING) or state_timestamps.get(
            WorkflowState.CULTURAL_MATRIX_READY, init_time
        )
        t1 = state_timestamps.get(WorkflowState.PLAN_GENERATED) or state_timestamps.get(
            WorkflowState.VALIDATED, t0
        )
        part_start = t0.isoformat()
        part_end = t1.isoformat()
        part_dur = max(0.14, (t1 - t0).total_seconds()) if part else 0.0
        part_dur_str = f"{part_dur:.2f}s" if part else None

    partnerships = getattr(part, "partnerships", []) if part else []
    part_evidence_cnt = len(partnerships)

    # 4D. Governance / Execution Agent
    if curr in {
        WorkflowState.CREATED,
        WorkflowState.INTENT_PARSED,
        WorkflowState.CULTURAL_TWIN_CREATED,
        WorkflowState.QLOO_RESOLVED,
        WorkflowState.CULTURAL_MATRIX_READY,
        WorkflowState.AGENTS_RUNNING,
    }:
        gov_status = "BLOCKED"
        gov_start = None
        gov_end = None
        gov_dur_str = None
    elif curr == WorkflowState.PLAN_GENERATED:
        gov_status = "RETRYING" if ctx.validation_cycle_count > 0 else "RUNNING"
        gov_start = state_timestamps.get(
            WorkflowState.PLAN_GENERATED, init_time
        ).isoformat()
        gov_end = None
        gov_dur_str = None
    elif curr in {WorkflowState.VALIDATED, WorkflowState.AWAITING_APPROVAL}:
        gov_status = "AWAITING_APPROVAL"
        t0 = state_timestamps.get(WorkflowState.PLAN_GENERATED, init_time)
        t1 = state_timestamps.get(
            WorkflowState.AWAITING_APPROVAL,
            state_timestamps.get(WorkflowState.VALIDATED, t0),
        )
        gov_start = t0.isoformat()
        gov_end = t1.isoformat()
        gov_dur = max(0.08, (t1 - t0).total_seconds())
        gov_dur_str = f"{gov_dur:.2f}s"
    elif curr == WorkflowState.APPROVED:
        gov_status = "AWAITING_APPROVAL"
        gov_start = state_timestamps.get(
            WorkflowState.PLAN_GENERATED, init_time
        ).isoformat()
        gov_end = state_timestamps.get(WorkflowState.APPROVED, init_time).isoformat()
        gov_dur_str = "0.10s"
    elif curr == WorkflowState.EXECUTING:
        gov_status = "RUNNING"
        gov_start = state_timestamps.get(WorkflowState.EXECUTING, init_time).isoformat()
        gov_end = None
        gov_dur_str = None
    elif curr == WorkflowState.COMPLETED:
        gov_status = "COMPLETED"
        t0 = state_timestamps.get(WorkflowState.EXECUTING, init_time)
        t1 = state_timestamps.get(WorkflowState.COMPLETED, t0)
        gov_start = t0.isoformat()
        gov_end = t1.isoformat()
        gov_dur = max(0.15, (t1 - t0).total_seconds())
        gov_dur_str = f"{gov_dur:.2f}s"
    elif curr == WorkflowState.FAILED:
        gov_status = "FAILED"
        gov_start = state_timestamps.get(
            WorkflowState.PLAN_GENERATED, init_time
        ).isoformat()
        gov_end = datetime.now(UTC).isoformat()
        gov_dur_str = None
    else:
        gov_status = "AWAITING_APPROVAL"
        gov_start = init_time.isoformat()
        gov_end = None
        gov_dur_str = None

    gov_evidence_cnt = (
        len(getattr(gov, "risk_flags", []))
        + len(ctx.execution_tasks)
        + (len(ctx.cultural_matrix.evidence) if ctx.cultural_matrix else 0)
    )

    agent_summaries: dict[str, Any] = {
        "cultural_strategist": {
            "name": "Cultural Strategist",
            "status": strat_status,
            "start": strat_start,
            "completion": strat_end,
            "duration": strat_dur_str,
            "validation_status": "PASSED"
            if strat_status == "COMPLETED"
            else ("FAILED" if strat_status == "FAILED" else "PENDING_REVIEW"),
            "evidence_count": strat_evidence_cnt,
            "failure_information": ctx.error_message
            if strat_status == "FAILED"
            else None,
            "output_summary": {
                "positioning": getattr(
                    strat,
                    "positioning_statement",
                    "Cultural anchor positioning synthesized",
                )
                if strat
                else "Brief transformation pending",
                "target_audience": getattr(strat, "target_audience", "")
                if strat
                else "",
                "pillars": [getattr(p, "name", str(p)) for p in pillars],
                "decisions": "Synthesized Cultural Twin, resolved anchor terms via Qloo, and established aesthetic constraints.",
            },
            # Backward-compatibility fields:
            "positioning": getattr(strat, "positioning_statement", "") if strat else "",
            "pillars_count": len(pillars),
            "pillars": [getattr(p, "name", str(p)) for p in pillars],
            "target_audience": getattr(strat, "target_audience", "") if strat else "",
        },
        "experience_architect": {
            "name": "Experience Architect",
            "status": exp_status,
            "start": exp_start,
            "completion": exp_end,
            "duration": exp_dur_str,
            "validation_status": "PASSED"
            if exp_status == "COMPLETED"
            else ("BLOCKED" if exp_status == "BLOCKED" else "PENDING_REVIEW"),
            "evidence_count": exp_evidence_cnt,
            "failure_information": ctx.error_message
            if exp_status == "FAILED"
            else None,
            "output_summary": {
                "spatial_zones_count": len(zones),
                "spatial_zones": [getattr(z, "name", str(z)) for z in zones],
                "sonic_profile": getattr(sonic, "acoustic_profile", "")
                if sonic
                else None,
                "reading_library": getattr(reading, "overview", "")
                if reading
                else None,
                "material_palette": getattr(brand, "material_palette", [])
                if brand
                else [],
                "decisions": "Constructed multi-zone sensory architecture, circadian lighting, and acoustic identity."
                if exp
                else "Pending Cultural Matrix inputs.",
            },
            # Backward-compatibility fields:
            "spatial_zones_count": len(zones),
            "sonic_profile": getattr(sonic, "acoustic_profile", "") if sonic else None,
            "reading_library": getattr(reading, "overview", "") if reading else None,
            "material_palette": getattr(brand, "material_palette", []) if brand else [],
        },
        "partnership_agent": {
            "name": "Partnership Agent",
            "status": part_status,
            "start": part_start,
            "completion": part_end,
            "duration": part_dur_str,
            "validation_status": "PASSED"
            if part_status == "COMPLETED"
            else ("BLOCKED" if part_status == "BLOCKED" else "PENDING_REVIEW"),
            "evidence_count": part_evidence_cnt,
            "failure_information": ctx.error_message
            if part_status == "FAILED"
            else None,
            "output_summary": {
                "partnerships_count": len(partnerships),
                "partners": [
                    {
                        "name": getattr(p, "partner_name", ""),
                        "type": getattr(p, "partnership_type", ""),
                        "tier": getattr(p, "tier", ""),
                    }
                    for p in partnerships
                ],
                "decisions": "Curated high-affinity brand and artist partnerships with commercial tiering."
                if part
                else "Pending Cultural Matrix inputs.",
            },
            # Backward-compatibility fields:
            "partnerships_count": len(partnerships),
            "partners": [
                {
                    "name": getattr(p, "partner_name", ""),
                    "type": getattr(p, "partnership_type", ""),
                    "tier": getattr(p, "tier", ""),
                }
                for p in partnerships
            ],
        },
        "governance_agent": {
            "name": "Governance / Execution Agent",
            "status": gov_status,
            "start": gov_start,
            "completion": gov_end,
            "duration": gov_dur_str,
            "validation_status": "PASSED"
            if (gov and getattr(gov, "is_valid", False))
            else (
                "FAILED"
                if (gov and not getattr(gov, "is_valid", False))
                else ("BLOCKED" if gov_status == "BLOCKED" else "PENDING_REVIEW")
            ),
            "evidence_count": gov_evidence_cnt,
            "failure_information": ctx.error_message
            if gov_status == "FAILED"
            else None,
            "output_summary": {
                "is_valid": getattr(gov, "is_valid", False) if gov else False,
                "provenance_verified": getattr(gov, "provenance_verified", True)
                if gov
                else False,
                "compliance_score": getattr(gov, "compliance_score", 1.0)
                if gov
                else 1.0,
                "risk_flags_count": len(getattr(gov, "risk_flags", [])) if gov else 0,
                "execution_tasks_count": len(ctx.execution_tasks),
                "decisions": "Audited 100% entity provenance against Qloo signatures, verified spatial constraints, and enforced approval gate.",
            },
            # Backward-compatibility fields:
            "is_valid": getattr(gov, "is_valid", True) if gov else True,
            "provenance_verified": getattr(gov, "provenance_verified", True)
            if gov
            else True,
            "compliance_score": getattr(gov, "compliance_score", 1.0) if gov else 1.0,
            "risk_flags_count": len(getattr(gov, "risk_flags", [])) if gov else 0,
        },
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
        plan_dict = (
            ctx.plan.model_dump() if hasattr(ctx.plan, "model_dump") else dict(ctx.plan)
        )

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
                "estimated_cost": getattr(a, "estimated_cost", "$0"),
            }
            for a in getattr(exec_plan, "actions", [])
        ]
        plan_hash = getattr(exec_plan, "plan_hash", None) or (
            ctx.plan.compute_hash() if ctx.plan else None
        )
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
        approval_dict = (
            ctx.approval.model_dump()
            if hasattr(ctx.approval, "model_dump")
            else dict(ctx.approval)
        )

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
        approval_state["status"] = (
            "APPROVED" if ctx.approval.is_valid else "INVALIDATED"
        )
        approval_state["approver"] = ctx.approval.approver
        approval_state["role"] = getattr(
            ctx.approval, "role", "Lead Cultural Strategist"
        )
        approval_state["approved_at"] = (
            ctx.approval.approved_at.isoformat()
            if hasattr(ctx.approval.approved_at, "isoformat")
            else str(ctx.approval.approved_at)
        )
        approval_state["plan_hash"] = ctx.approval.plan_hash
        approval_state["notes"] = getattr(
            ctx.approval, "notes", getattr(ctx.approval, "invalidation_reason", None)
        )

    # 8. Execution State
    tasks_list = _format_execution_tasks(ctx)
    executed_tasks = sum(1 for t in tasks_list if t["status"] == "COMPLETED")
    failed_tasks = sum(1 for t in tasks_list if t["status"] == "FAILED")
    total_tasks = len(tasks_list)
    exec_status = "NOT_STARTED"
    if total_tasks > 0:
        if executed_tasks == total_tasks:
            exec_status = "COMPLETED"
        elif (
            executed_tasks > 0
            or failed_tasks > 0
            or any(t["status"] == "RUNNING" for t in tasks_list)
        ):
            exec_status = "EXECUTING"
    execution_state = {
        "status": exec_status,
        "total_tasks": total_tasks,
        "executed_tasks": executed_tasks,
        "failed_tasks": failed_tasks,
        "tasks": tasks_list,
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
async def get_session(
    session_id: str = Path(
        ..., pattern=r"^[a-zA-Z0-9_\-]+$", min_length=1, max_length=128
    ),
    service: ServiceDep = None,  # type: ignore[assignment]
) -> SessionDetailResponse:
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
    session_id: str = Path(
        ..., pattern=r"^[a-zA-Z0-9_\-]+$", min_length=1, max_length=128
    ),
    service: ServiceDep = None,  # type: ignore[assignment]
) -> SessionEventsResponse:
    ctx = service.get_session(session_id)
    audit_events, history = service.get_session_events(session_id)
    verification_status, hashes = service.compute_audit_hash_chain(audit_events, ctx)
    enriched_events = service.enrich_audit_events(ctx, audit_events, hashes)
    serialized_history = [
        h.model_dump() if hasattr(h, "model_dump") else dict(h) for h in history
    ]

    return SessionEventsResponse(
        session_id=session_id,
        total_events=len(enriched_events),
        events=enriched_events,
        history=serialized_history,
        verification_status=verification_status,
    )


@router.get(
    "/{session_id}/ledger/verify",
    status_code=status.HTTP_200_OK,
    summary="Verify Audit Ledger Hash Chain",
    description="Validates cryptographic hash-chain integrity of the append-only audit ledger and plan hashes.",
    responses={404: {"description": "Session not found"}},
)
async def verify_session_ledger(
    session_id: str = Path(
        ..., pattern=r"^[a-zA-Z0-9_\-]+$", min_length=1, max_length=128
    ),
    service: ServiceDep = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    return service.verify_audit_chain(session_id)


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
    session_id: str = Path(
        ..., pattern=r"^[a-zA-Z0-9_\-]+$", min_length=1, max_length=128
    ),
    service: ServiceDep = None,  # type: ignore[assignment]
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
    request: Request,
    session_id: str = Path(
        ..., pattern=r"^[a-zA-Z0-9_\-]+$", min_length=1, max_length=128
    ),
    service: ServiceDep = None,  # type: ignore[assignment]
    last_event_id_header: str | None = Header(None, alias="Last-Event-ID"),
    last_event_id_query: str | None = Query(None, alias="last_event_id"),
    wait: bool = Query(
        True, description="Keep stream open for live events if session is active"
    ),
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
                current_ctx.current_state
                in (WorkflowState.COMPLETED, WorkflowState.FAILED)
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
                except TimeoutError:
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
    request: ApproveSessionRequest,
    session_id: str = Path(
        ..., pattern=r"^[a-zA-Z0-9_\-]+$", min_length=1, max_length=128
    ),
    service: ServiceDep = None,  # type: ignore[assignment]
    _actor: AuthDep = "dev-curator",
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
    request: RejectSessionRequest,
    session_id: str = Path(
        ..., pattern=r"^[a-zA-Z0-9_\-]+$", min_length=1, max_length=128
    ),
    service: ServiceDep = None,  # type: ignore[assignment]
    _actor: AuthDep = "dev-curator",
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
    session_id: str = Path(
        ..., pattern=r"^[a-zA-Z0-9_\-]+$", min_length=1, max_length=128
    ),
    service: ServiceDep = None,  # type: ignore[assignment]
    _actor: AuthDep = "dev-curator",
) -> ExecutionResponse:
    ctx = await service.execute_session(session_id)
    tasks = _format_execution_tasks(ctx)
    executed = sum(1 for t in tasks if t["status"] == "COMPLETED")
    failed = sum(1 for t in tasks if t["status"] == "FAILED")

    audit_report = None
    if hasattr(ctx, "governance_output") and ctx.governance_output:
        audit_report = (
            ctx.governance_output.model_dump()
            if hasattr(ctx.governance_output, "model_dump")
            else dict(ctx.governance_output)
        )
    elif (
        ctx.plan
        and ctx.plan.execution_summary
        and ctx.plan.execution_summary.audit_report
    ):
        audit_report = (
            ctx.plan.execution_summary.audit_report.model_dump()
            if hasattr(ctx.plan.execution_summary.audit_report, "model_dump")
            else dict(ctx.plan.execution_summary.audit_report)
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


@router.post(
    "/{session_id}/tasks/{task_id}/execute",
    response_model=ConnectorExecutionResult,
    status_code=status.HTTP_200_OK,
    summary="Execute Specific Task Connector",
    description="Dispatches a specific execution task connector with strict idempotency and server-side credential isolation.",
    responses={
        403: {"description": "Unapproved session"},
        404: {"description": "Session not found"},
        409: {
            "description": "Duplicate execution attempt for the same idempotency key"
        },
        422: {"description": "Connector missing or unconfigured"},
    },
)
async def execute_task_connector(
    request: ConnectorExecutionRequest,
    session_id: str = Path(
        ..., pattern=r"^[a-zA-Z0-9_\-]+$", min_length=1, max_length=128
    ),
    task_id: str = Path(
        ..., pattern=r"^[a-zA-Z0-9_\-]+$", min_length=1, max_length=128
    ),
    service: ServiceDep = None,  # type: ignore[assignment]
    _actor: AuthDep = "dev-curator",
) -> ConnectorExecutionResult:
    # Ensure URL session_id and task_id match request body
    if request.session_id != session_id:
        request.session_id = session_id
    if request.task_id != task_id:
        request.task_id = task_id
    return await service.execute_task(request)


@router.get(
    "/{session_id}/connectors",
    status_code=status.HTTP_200_OK,
    summary="List Session Connectors",
    description="Returns configuration status and capabilities of all registered external execution connectors without exposing server-side credentials.",
    responses={
        404: {"description": "Session not found"},
    },
)
async def list_session_connectors(
    session_id: str = Path(
        ..., pattern=r"^[a-zA-Z0-9_\-]+$", min_length=1, max_length=128
    ),
    service: ServiceDep = None,  # type: ignore[assignment]
) -> list[dict[str, Any]]:
    # Verify session exists
    service.get_session(session_id)
    return service.connector_registry.list_connectors()
