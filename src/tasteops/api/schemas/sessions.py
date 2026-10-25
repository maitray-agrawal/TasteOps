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


class CulturalMatrixSummary(BaseModel):
    """Safe, summarized cultural intelligence matrix metrics without raw provider dumps."""

    total_entities: int = Field(default=0, description="Total verified entities retrieved from Qloo")
    fingerprint: str | None = Field(default=None, description="Deterministic matrix fingerprint")
    domains_present: list[str] = Field(default_factory=list, description="Cultural domains analyzed")
    category_counts: dict[str, int] = Field(default_factory=dict, description="Counts of items per category")
    top_affinities: dict[str, list[dict[str, Any]]] = Field(
        default_factory=dict, description="Top cultural recommendations per category"
    )
    evidence_count: int = Field(default=0, description="Total provenance evidence records")


class AgentSummaries(BaseModel):
    """Sanitized summaries of agent outputs without chain-of-thought or raw prompts."""

    cultural_strategist: dict[str, Any] | None = Field(
        default=None, description="Strategic positioning and cultural pillars summary"
    )
    experience_architect: dict[str, Any] | None = Field(
        default=None, description="Spatial zones and sensory design summary"
    )
    partnership_agent: dict[str, Any] | None = Field(
        default=None, description="Curated brand and artist collaboration summary"
    )
    governance_agent: dict[str, Any] | None = Field(
        default=None, description="Provenance and compliance verification summary"
    )


class ValidationSummary(BaseModel):
    """Typed summary of governance validation checks and provenance verification."""

    is_valid: bool = Field(..., description="Whether plan passed all compliance and provenance checks")
    provenance_verified: bool = Field(default=True, description="Whether all entities trace to verified Qloo signals")
    compliance_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Aggregate compliance confidence score")
    risk_flags: list[str] = Field(default_factory=list, description="Identified operational or cultural risk flags")
    recommendations: list[str] = Field(default_factory=list, description="Governance curatorial recommendations")


class ExecutionPlanSummary(BaseModel):
    """Structured execution plan summary for human curator review."""

    plan_id: str = Field(..., description="Unique execution plan ID")
    version: int = Field(default=1, description="Plan version")
    plan_hash: str | None = Field(default=None, description="Cryptographic content hash")
    estimated_cost: str = Field(..., description="Estimated cost and resource allocation")
    actions_count: int = Field(default=0, description="Total planned actions")
    actions: list[dict[str, Any]] = Field(default_factory=list, description="Action items")
    risks: list[str] = Field(default_factory=list, description="Identified risks")
    approvals_required: list[str] = Field(default_factory=list, description="Required sign-off roles")


class ApprovalStateSummary(BaseModel):
    """Authoritative human curator approval state."""

    is_approved: bool = Field(default=False, description="Whether plan has received valid curator sign-off")
    status: str = Field(default="PENDING", description="Approval status (PENDING / APPROVED / REJECTED / REVOKED)")
    approver: str | None = Field(default=None, description="Approving curator identity")
    role: str | None = Field(default=None, description="Curator organizational role")
    approved_at: datetime | str | None = Field(default=None, description="Timestamp of approval")
    plan_hash: str | None = Field(default=None, description="Cryptographic hash of approved plan")
    notes: str | None = Field(default=None, description="Review notes or feedback")


class ExecutionStateSummary(BaseModel):
    """Execution status and task dispatch progress."""

    status: str = Field(default="NOT_STARTED", description="Execution status (NOT_STARTED / EXECUTING / COMPLETED / FAILED)")
    total_tasks: int = Field(default=0, description="Total execution tasks")
    executed_tasks: int = Field(default=0, description="Number of executed tasks")
    failed_tasks: int = Field(default=0, description="Number of failed tasks")
    tasks: list[dict[str, Any]] = Field(default_factory=list, description="Task details")


class SessionDetailResponse(BaseModel):
    """Comprehensive, safe, typed workflow session detail envelope."""

    session_id: str = Field(..., description="Unique workflow session UUID")
    space_id: str | None = Field(default=None, description="Associated space identifier")
    current_state: str = Field(..., description="Current deterministic workflow state")
    status: str = Field(
        default="IN_PROGRESS",
        description="High-level workflow status (IN_PROGRESS, AWAITING_APPROVAL, APPROVED, EXECUTING, COMPLETED, FAILED)",
    )
    user_input: str = Field(..., description="Natural language activation brief")
    parsed_intent: dict[str, Any] = Field(
        default_factory=dict, description="Structured parsed space brief"
    )
    cultural_twin: dict[str, Any] | None = Field(
        default=None, description="Synthesized Cultural Twin profile"
    )
    cultural_matrix_summary: CulturalMatrixSummary | dict[str, Any] | None = Field(
        default=None, description="Safe summary of Qloo cultural affinities"
    )
    agent_summaries: AgentSummaries | dict[str, Any] = Field(
        default_factory=dict, description="Safe summaries of domain agent outputs"
    )
    validation: ValidationSummary | dict[str, Any] | None = Field(
        default=None, description="Governance compliance and provenance report"
    )
    execution_plan: ExecutionPlanSummary | dict[str, Any] | None = Field(
        default=None, description="Structured execution plan"
    )
    approval_state: ApprovalStateSummary | dict[str, Any] = Field(
        default_factory=dict, description="Human curator approval state"
    )
    execution_state: ExecutionStateSummary | dict[str, Any] = Field(
        default_factory=dict, description="Execution tasks and dispatch state"
    )
    errors: list[str] = Field(
        default_factory=list, description="Sanitized error messages without stack traces"
    )
    timestamps: dict[str, Any] = Field(
        default_factory=dict, description="Key lifecycle timestamps"
    )

    # Backward-compatibility fields
    plan: dict[str, Any] | None = Field(
        default=None, description="Generated activation plan"
    )
    cultural_matrix: dict[str, Any] | None = Field(
        default=None, description="Qloo-grounded cultural affinity matrix"
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
