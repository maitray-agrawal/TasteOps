"""TasteOps API Session Schemas.

Defines request and response schemas for workflow sessions, events, blueprints,
approvals, rejections, and execution dispatch.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class SessionResponse(BaseModel):
    """Minimal session response envelope."""

    session_id: str = Field(..., description="Unique workflow session UUID")
    space_id: str | None = Field(default=None, description="Associated space identifier")
    current_state: str = Field(..., description="Current deterministic workflow state")
    user_input: str = Field(..., description="Natural language activation brief")
    links: dict[str, str] = Field(
        default_factory=dict,
        description="HATEOAS navigational links for session operations",
    )


class SessionDetailResponse(BaseModel):
    """Comprehensive session detail envelope."""

    session_id: str = Field(..., description="Unique workflow session UUID")
    space_id: str | None = Field(default=None, description="Associated space identifier")
    current_state: str = Field(..., description="Current deterministic workflow state")
    user_input: str = Field(..., description="Natural language activation brief")
    parsed_intent: dict[str, Any] = Field(
        default_factory=dict, description="Structured parsed space brief"
    )
    cultural_twin: dict[str, Any] | None = Field(
        default=None, description="Synthesized Cultural Twin profile"
    )
    cultural_matrix: dict[str, Any] | None = Field(
        default=None, description="Qloo-grounded cultural affinity matrix"
    )
    plan: dict[str, Any] | None = Field(
        default=None, description="Generated activation plan"
    )
    validation_result: dict[str, Any] | None = Field(
        default=None, description="Governance compliance and provenance report"
    )
    approval: dict[str, Any] | None = Field(
        default=None, description="Human curator approval record"
    )
    execution_tasks_count: int = Field(
        default=0, description="Number of execution tasks created"
    )
    error_message: str | None = Field(
        default=None, description="Error message if workflow transitioned to FAILED"
    )
    links: dict[str, str] = Field(
        default_factory=dict, description="Operational navigation links"
    )


class SessionEventsResponse(BaseModel):
    """Audit events and state progression history for a session."""

    session_id: str = Field(..., description="Unique workflow session UUID")
    total_events: int = Field(..., description="Total count of audit log records")
    events: list[dict[str, Any]] = Field(
        default_factory=list, description="Ordered audit log records"
    )
    history: list[dict[str, Any]] = Field(
        default_factory=list, description="State transition progression history"
    )


class SessionBlueprintResponse(BaseModel):
    """Detailed architectural, sensory, and curatorial blueprint for a session."""

    session_id: str = Field(..., description="Unique workflow session UUID")
    space_id: str | None = Field(default=None, description="Associated space identifier")
    state: str = Field(..., description="Workflow state when blueprint was queried")
    plan_id: str | None = Field(default=None, description="Unique plan identifier")
    plan_hash: str | None = Field(
        default=None, description="Cryptographic SHA-256 hash of the activation plan"
    )
    estimated_cost: str | None = Field(
        default=None, description="Estimated budget and capital allocation"
    )
    experience_narrative: str | None = Field(
        default=None, description="Curatorial story and narrative arc"
    )
    spatial_zones: list[dict[str, Any]] = Field(
        default_factory=list, description="Zoned architectural layout specs"
    )
    soundscape_design: dict[str, Any] | None = Field(
        default=None, description="Acoustic hardware and playlist specifications"
    )
    lighting_design: dict[str, Any] | None = Field(
        default=None, description="Atmospheric lighting parameters"
    )
    cultural_pillars: list[dict[str, Any]] = Field(
        default_factory=list, description="Strategic cultural grounding pillars"
    )
    partnerships: list[dict[str, Any]] = Field(
        default_factory=list, description="Recommended brand & artist collaborations"
    )
    programming_calendar: list[dict[str, Any]] = Field(
        default_factory=list, description="Event programming calendar"
    )


class ApproveSessionRequest(BaseModel):
    """Payload to record human curator approval for an activation plan."""

    approver: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="Name or email of the approving curator/stakeholder",
        examples=["Curator: Satwik Jaiswal"],
    )
    role: str | None = Field(
        default="Cultural Curator",
        description="Organizational role or responsibility",
        examples=["Head of Cultural Experience"],
    )
    notes: str | None = Field(
        default=None,
        description="Optional approval notes or conditions",
        examples=["Approved for Phase 1 acoustic testing."],
    )
    plan_version: int | None = Field(
        default=1,
        ge=1,
        description="Expected version of the plan being approved",
    )


class RejectSessionRequest(BaseModel):
    """Payload to record human curator rejection of an activation plan."""

    reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Detailed rationale for rejection or requested changes",
        examples=["Audio levels exceed local municipal noise code limits."],
    )


class ExecutionResponse(BaseModel):
    """Response returned upon dispatching execution tasks for an approved plan."""

    session_id: str = Field(..., description="Unique workflow session UUID")
    current_state: str = Field(..., description="Workflow state post-execution")
    total_tasks: int = Field(..., description="Total execution tasks processed")
    executed_tasks: int = Field(..., description="Count of successfully executed tasks")
    failed_tasks: int = Field(default=0, description="Count of failed tasks")
    tasks: list[dict[str, Any]] = Field(
        default_factory=list, description="Individual execution task records"
    )
    audit_report: dict[str, Any] | None = Field(
        default=None, description="Post-execution compliance and provenance audit"
    )
