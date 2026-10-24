"""TasteOps Deterministic Workflow States.

Defines the explicit finite state machine for physical space cultural activations.
Prevents unrestricted autonomous loops and enforces deterministic progression.
"""

from enum import Enum


class WorkflowState(str, Enum):
    """The 13 required deterministic workflow states."""

    CREATED = "CREATED"
    INTENT_PARSED = "INTENT_PARSED"
    CULTURAL_TWIN_CREATED = "CULTURAL_TWIN_CREATED"
    QLOO_RESOLVED = "QLOO_RESOLVED"
    CULTURAL_MATRIX_READY = "CULTURAL_MATRIX_READY"
    AGENTS_RUNNING = "AGENTS_RUNNING"
    PLAN_GENERATED = "PLAN_GENERATED"
    VALIDATED = "VALIDATED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# Valid deterministic state transitions graph
VALID_TRANSITIONS: dict[WorkflowState, set[WorkflowState]] = {
    WorkflowState.CREATED: {WorkflowState.INTENT_PARSED, WorkflowState.FAILED},
    WorkflowState.INTENT_PARSED: {
        WorkflowState.CULTURAL_TWIN_CREATED,
        WorkflowState.FAILED,
    },
    WorkflowState.CULTURAL_TWIN_CREATED: {
        WorkflowState.QLOO_RESOLVED,
        WorkflowState.FAILED,
    },
    WorkflowState.QLOO_RESOLVED: {
        WorkflowState.CULTURAL_MATRIX_READY,
        WorkflowState.FAILED,
    },
    WorkflowState.CULTURAL_MATRIX_READY: {
        WorkflowState.AGENTS_RUNNING,
        WorkflowState.FAILED,
    },
    WorkflowState.AGENTS_RUNNING: {WorkflowState.PLAN_GENERATED, WorkflowState.FAILED},
    WorkflowState.PLAN_GENERATED: {WorkflowState.VALIDATED, WorkflowState.FAILED},
    WorkflowState.VALIDATED: {
        WorkflowState.AWAITING_APPROVAL,
        WorkflowState.PLAN_GENERATED,
        WorkflowState.FAILED,
    },
    WorkflowState.AWAITING_APPROVAL: {WorkflowState.APPROVED, WorkflowState.FAILED},
    WorkflowState.APPROVED: {WorkflowState.EXECUTING, WorkflowState.FAILED},
    WorkflowState.EXECUTING: {WorkflowState.COMPLETED, WorkflowState.FAILED},
    WorkflowState.COMPLETED: set(),  # Terminal state
    WorkflowState.FAILED: set(),  # Terminal state
}


class InvalidStateTransitionError(Exception):
    """Raised when an illegal or out-of-order state transition is attempted."""

    def __init__(
        self, current_state: WorkflowState, target_state: WorkflowState
    ) -> None:
        super().__init__(
            f"Invalid workflow transition: cannot transition from '{current_state.value}' to '{target_state.value}'. "
            f"Allowed next states: {[s.value for s in VALID_TRANSITIONS.get(current_state, set())]}"
        )
        self.current_state = current_state
        self.target_state = target_state


def validate_transition(current: WorkflowState, target: WorkflowState) -> None:
    """Validates that target state is legally reachable from current state."""
    allowed = VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidStateTransitionError(current, target)
