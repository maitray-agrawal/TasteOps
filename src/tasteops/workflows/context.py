"""TasteOps Workflow Context.

Holds the end-to-end execution state, audit logs, and artifacts for a physical space activation.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from tasteops.models.cultural_matrix import CulturalMatrix, CulturalTwin
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
    error_message: str | None = None

    def record_transition(
        self,
        to_state: WorkflowState,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Records a verified transition in the audit history."""
        record = StateTransitionRecord(
            from_state=self.current_state,
            to_state=to_state,
            reason=reason,
            metadata=metadata or {},
        )
        self.history.append(record)
        self.current_state = to_state
