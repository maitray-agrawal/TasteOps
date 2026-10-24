"""TasteOps Workflow Context.

Holds the end-to-end execution state, audit logs, and artifacts for a physical space activation.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from tasteops.models.cultural_matrix import CulturalMatrix, CulturalTwin
from tasteops.workflows.persistence import AuditEvent
from tasteops.workflows.schemas import (
    CulturalActivationPlan,
    CulturalStrategyOutput,
    ExperienceDesignOutput,
    GovernanceValidationOutput,
    PartnershipOutput,
)
from tasteops.workflows.states import WorkflowState


class StateTransitionRecord(BaseModel):
    """Audit log entry for an executed state transition."""

    from_state: WorkflowState
    to_state: WorkflowState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reason: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowContext(BaseModel):
    """Encapsulates all session state across the deterministic workflow lifecycle."""

    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    current_state: WorkflowState = WorkflowState.CREATED
    raw_intent: str = ""
    parsed_intent: dict[str, Any] = Field(default_factory=dict)

    cultural_twin: CulturalTwin | None = None
    cultural_matrix: CulturalMatrix | None = None

    strategy_output: CulturalStrategyOutput | None = None
    experience_output: ExperienceDesignOutput | None = None
    partnership_output: PartnershipOutput | None = None
    governance_output: GovernanceValidationOutput | None = None

    plan: CulturalActivationPlan | None = None
    history: list[StateTransitionRecord] = Field(default_factory=list)
    audit_events: list[AuditEvent] = Field(default_factory=list)
    error_message: str | None = None

    # Bounded cycle and retry tracking
    validation_cycle_count: int = 0
    qloo_retry_count: int = 0
    agent_retry_count: int = 0

    def record_transition(
        self,
        to_state: WorkflowState,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> AuditEvent:
        """Records a verified transition in the audit history and creates an AuditEvent."""
        from_state = self.current_state

        record = StateTransitionRecord(
            from_state=from_state,
            to_state=to_state,
            reason=reason,
            metadata=metadata or {},
        )
        self.history.append(record)

        event = AuditEvent(
            session_id=self.session_id,
            from_state=from_state,
            to_state=to_state,
            reason=reason,
            metadata=metadata or {},
            error=error,
        )
        self.audit_events.append(event)
        self.current_state = to_state
        return event
