"""Unit tests for the Deterministic Workflow Engine and State Machine.

Verifies:
- All 13 states: CREATED -> INTENT_PARSED -> CULTURAL_TWIN_CREATED -> QLOO_RESOLVED ->
  CULTURAL_MATRIX_READY -> AGENTS_RUNNING -> PLAN_GENERATED -> VALIDATED ->
  AWAITING_APPROVAL -> APPROVED -> EXECUTING -> COMPLETED (and FAILED).
- Invalid state transition rejection.
- Human-in-the-loop approval gate.
- Rejection transition to FAILED.
- Post-approval execution tasks.
"""

import pytest
import respx

from tasteops.workflows.engine import WorkflowEngine
from tasteops.workflows.states import (
    InvalidStateTransitionError,
    WorkflowState,
    validate_transition,
)


def test_state_transition_validation():
    """Ensure illegal transitions raise InvalidStateTransitionError."""
    # Legal transition
    validate_transition(WorkflowState.CREATED, WorkflowState.INTENT_PARSED)
    validate_transition(WorkflowState.VALIDATED, WorkflowState.AWAITING_APPROVAL)
    validate_transition(WorkflowState.AWAITING_APPROVAL, WorkflowState.APPROVED)
    validate_transition(WorkflowState.APPROVED, WorkflowState.EXECUTING)
    validate_transition(WorkflowState.EXECUTING, WorkflowState.COMPLETED)

    # Illegal transitions
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(WorkflowState.CREATED, WorkflowState.COMPLETED)

    with pytest.raises(InvalidStateTransitionError):
        validate_transition(WorkflowState.CREATED, WorkflowState.APPROVED)

    with pytest.raises(InvalidStateTransitionError):
        validate_transition(WorkflowState.AWAITING_APPROVAL, WorkflowState.EXECUTING)


@pytest.mark.asyncio
async def test_full_workflow_to_completion(mock_settings, mock_mcp_adapter):
    """Test full sequential workflow execution through human approval to COMPLETED."""
    adapter, mock_search, mock_tags, mock_insights = mock_mcp_adapter

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/search").respond(status_code=200, json=mock_search)
        mock_router.get("/v2/tags").respond(status_code=200, json=mock_tags)
        mock_router.get("/v2/insights").respond(status_code=200, json=mock_insights)

        engine = WorkflowEngine(mcp_adapter=adapter)

        raw_intent = (
            "Open an analog vinyl listening cafe with Japanese minimalism in Chelsea"
        )
        hints = {
            "business_type": "Japanese Listening Cafe",
            "mood": "Warm analog intimate minimalism",
            "target_audience": "Audiophiles, design professionals, coffee purists",
            "raw_anchor_entities": ["Blue Bottle"],
            "raw_tags": ["Japanese minimalism"],
            "location": {
                "latitude": 40.7484,
                "longitude": -73.9857,
                "radius_meters": 2000,
            },
        }

        # Step 1: Run pipeline up to human approval gate
        ctx = await engine.run_pipeline_to_approval_gate(raw_intent, hints)

        # Must halt at AWAITING_APPROVAL
        assert ctx.current_state == WorkflowState.AWAITING_APPROVAL
        assert ctx.plan is not None
        assert ctx.plan.governance.is_valid is True
        assert ctx.plan.governance.provenance_verified is True

        # Verify audit history passed through all required pre-approval states
        recorded_states = [r.to_state for r in ctx.history]
        assert WorkflowState.CREATED in recorded_states
        assert WorkflowState.INTENT_PARSED in recorded_states
        assert WorkflowState.CULTURAL_TWIN_CREATED in recorded_states
        assert WorkflowState.QLOO_RESOLVED in recorded_states
        assert WorkflowState.CULTURAL_MATRIX_READY in recorded_states
        assert WorkflowState.AGENTS_RUNNING in recorded_states
        assert WorkflowState.PLAN_GENERATED in recorded_states
        assert WorkflowState.VALIDATED in recorded_states
        assert WorkflowState.AWAITING_APPROVAL in recorded_states

        # Step 2: Human curator signs off
        await engine.approve_plan(ctx, approver="senior_curator_alice")
        assert ctx.current_state == WorkflowState.APPROVED

        # Step 3: Execute approved activations
        await engine.execute_plan(ctx)
        assert ctx.current_state == WorkflowState.COMPLETED
        assert ctx.plan.execution_summary is not None
        assert ctx.plan.execution_summary.executed_tasks >= 2


@pytest.mark.asyncio
async def test_human_rejection_at_approval_gate(mock_settings, mock_mcp_adapter):
    """Test human rejecting the plan transitions state to FAILED."""
    adapter, mock_search, mock_tags, mock_insights = mock_mcp_adapter

    async with respx.mock(
        base_url="https://hackathon.api.qloo.com", assert_all_called=False
    ) as mock_router:
        mock_router.get("/search").respond(status_code=200, json=mock_search)
        mock_router.get("/v2/tags").respond(status_code=200, json=mock_tags)
        mock_router.get("/v2/insights").respond(status_code=200, json=mock_insights)

        engine = WorkflowEngine(mcp_adapter=adapter)

        raw_intent = "Boutique venue"
        hints = {"raw_anchor_entities": ["Blue Bottle"]}

        ctx = await engine.run_pipeline_to_approval_gate(raw_intent, hints)
        assert ctx.current_state == WorkflowState.AWAITING_APPROVAL

        # Human curator rejects
        await engine.reject_plan(
            ctx, reason="Budget exceeded for physical audio hardware installation"
        )
        assert ctx.current_state == WorkflowState.FAILED
        assert "Budget exceeded" in ctx.error_message
