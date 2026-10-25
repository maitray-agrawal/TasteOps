"""TasteOps Workflow Context.

Holds the end-to-end execution state, audit logs, and artifacts for a physical space activation.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from tasteops.models.cultural_matrix import CulturalMatrix, CulturalTwin
from tasteops.workflows.persistence import AuditEvent
from tasteops.workflows.schemas import (
    ApprovalRecord,
    CulturalActivationPlan,
    CulturalStrategyOutput,
    ExecutionPlan,
    ExecutionTask,
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


class AgentResults(BaseModel):
    """Encapsulates intermediate structured outputs from specialized domain agents."""

    strategy: CulturalStrategyOutput | None = Field(
        default=None, description="Output from Cultural Strategist"
    )
    experience: ExperienceDesignOutput | None = Field(
        default=None, description="Output from Experience Architect"
    )
    partnership: PartnershipOutput | None = Field(
        default=None, description="Output from Partnership Agent"
    )


class WorkflowContext(BaseModel):
    """Encapsulates all session state across the deterministic workflow lifecycle."""

    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    space_id: str | None = Field(
        default=None, description="Optional physical venue or space identifier"
    )
    user_input: str = Field(
        default="", description="Natural language physical space brief"
    )
    current_state: WorkflowState = WorkflowState.CREATED
    parsed_intent: dict[str, Any] = Field(default_factory=dict)

    cultural_twin: CulturalTwin | None = None
    cultural_matrix: CulturalMatrix | None = None

    agent_results: AgentResults | None = None
    strategy_output: CulturalStrategyOutput | None = None
    experience_output: ExperienceDesignOutput | None = None
    partnership_output: PartnershipOutput | None = None
    governance_output: GovernanceValidationOutput | None = None

    plan: CulturalActivationPlan | None = None
    execution_plan: ExecutionPlan | None = None
    validation_result: GovernanceValidationOutput | None = None
    approval: ApprovalRecord | None = None
    execution_tasks: list[ExecutionTask] = Field(default_factory=list)
    agent_telemetry: dict[str, Any] = Field(
        default_factory=dict,
        description="Per-agent execution timing, entity counts, status, and validation metrics",
    )

    history: list[StateTransitionRecord] = Field(default_factory=list)
    audit_events: list[AuditEvent] = Field(default_factory=list)
    error_message: str | None = None

    # Bounded cycle and retry tracking
    validation_cycle_count: int = 0
    qloo_retry_count: int = 0
    agent_retry_count: int = 0

    @model_validator(mode="before")
    @classmethod
    def handle_raw_intent(cls, data: Any) -> Any:
        if (
            isinstance(data, dict)
            and "raw_intent" in data
            and ("user_input" not in data or not data.get("user_input"))
        ):
            data["user_input"] = data.pop("raw_intent")
        return data

    @property
    def raw_intent(self) -> str:
        """Backward-compatible alias for user_input."""
        return self.user_input

    @raw_intent.setter
    def raw_intent(self, val: str) -> None:
        self.user_input = val

    def sync_outputs(self) -> None:
        """Synchronizes sub-models and helper references across the context."""
        if self.strategy_output or self.experience_output or self.partnership_output:
            if not self.agent_results:
                self.agent_results = AgentResults()
            if self.strategy_output:
                self.agent_results.strategy = self.strategy_output
            if self.experience_output:
                self.agent_results.experience = self.experience_output
            if self.partnership_output:
                self.agent_results.partnership = self.partnership_output
        elif self.agent_results:
            if self.agent_results.strategy and not self.strategy_output:
                self.strategy_output = self.agent_results.strategy
            if self.agent_results.experience and not self.experience_output:
                self.experience_output = self.agent_results.experience
            if self.agent_results.partnership and not self.partnership_output:
                self.partnership_output = self.agent_results.partnership

        if self.plan and self.plan.execution_plan:
            self.execution_plan = self.plan.execution_plan
        elif self.execution_plan and self.plan and not self.plan.execution_plan:
            self.plan.execution_plan = self.execution_plan

        if self.governance_output:
            self.validation_result = self.governance_output
        elif self.validation_result and not self.governance_output:
            self.governance_output = self.validation_result

        if (
            self.plan
            and self.plan.execution_summary
            and self.plan.execution_summary.tasks
        ):
            self.execution_tasks = self.plan.execution_summary.tasks

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
