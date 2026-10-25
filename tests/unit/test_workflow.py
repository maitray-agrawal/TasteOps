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

from unittest.mock import AsyncMock, MagicMock

import pytest
import respx

from tasteops.workflows.engine import WorkflowEngine
from tasteops.workflows.persistence import (
    AuditEvent,
    FileStateStore,
)
from tasteops.workflows.schemas import GovernanceValidationOutput
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

        from tasteops.connectors import create_configured_mock_registry

        engine = WorkflowEngine(
            mcp_adapter=adapter,
            connector_registry=create_configured_mock_registry(),
        )

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


@pytest.mark.asyncio
async def test_workflow_persists_audit_events_and_transitions(
    tmp_path, mock_mcp_adapter
):
    """Test every state transition generates an AuditEvent and persists to FileStateStore."""
    adapter, mock_search, mock_tags, mock_insights = mock_mcp_adapter

    async with respx.mock(
        base_url="https://hackathon.api.qloo.com", assert_all_called=False
    ) as mock_router:
        mock_router.get("/search").respond(status_code=200, json=mock_search)
        mock_router.get("/v2/tags").respond(status_code=200, json=mock_tags)
        mock_router.get("/v2/insights").respond(status_code=200, json=mock_insights)

        store = FileStateStore(base_dir=tmp_path / "workflows")
        engine = WorkflowEngine(mcp_adapter=adapter, store=store)

        raw_intent = "Vinyl listening bar"
        hints = {"raw_anchor_entities": ["Blue Bottle"]}

        ctx = await engine.run_pipeline_to_approval_gate(raw_intent, hints)
        await engine.approve_plan(ctx, approver="alice")
        await engine.execute_plan(ctx)

        assert ctx.current_state == WorkflowState.COMPLETED

        # Verify in-memory audit events generated on every transition
        assert len(ctx.audit_events) >= 11
        for evt in ctx.audit_events:
            assert isinstance(evt, AuditEvent)
            assert evt.session_id == ctx.session_id
            assert evt.timestamp is not None
            assert evt.reason

        # Verify filesystem persistence
        persisted_events = store.get_audit_events(ctx.session_id)
        assert len(persisted_events) == len(ctx.audit_events)
        loaded_ctx = store.load_context(ctx.session_id)
        assert loaded_ctx is not None
        assert loaded_ctx.current_state == WorkflowState.COMPLETED


@pytest.mark.asyncio
async def test_qloo_failure_retry_fallback_to_failed():
    """Test QLOO failure: RETRY -> FALLBACK -> FAILED with bounded retries."""
    mock_mcp = AsyncMock()
    # Mock strategist failure
    mock_strategist = AsyncMock()
    mock_strategist.transform_brief.side_effect = RuntimeError(
        "Qloo API 500 Server Error"
    )

    engine = WorkflowEngine(
        mcp_adapter=mock_mcp,
        strategist=mock_strategist,
        max_qloo_retries=2,
    )

    ctx = engine.initialize_session(
        "Vinyl cafe", {"raw_anchor_entities": ["Nonexistent"]}
    )
    await engine.parse_intent(ctx)
    await engine.create_cultural_twin(ctx)
    await engine.resolve_qloo_anchors(ctx)

    # Must transition to FAILED after retries and fallback
    assert ctx.current_state == WorkflowState.FAILED
    assert "QLOO_FAILURE" in ctx.error_message
    assert ctx.qloo_retry_count >= 2


@pytest.mark.asyncio
async def test_agent_failure_bounded_retries_to_failed(mock_mcp_adapter):
    """Test Agent failure: retry bounded number of times -> FAILED."""
    adapter, _, _, _ = mock_mcp_adapter

    mock_architect = AsyncMock()
    mock_architect.execute.side_effect = RuntimeError(
        "Experience Architect memory overflow"
    )

    engine = WorkflowEngine(
        mcp_adapter=adapter,
        architect=mock_architect,
        max_agent_retries=2,
    )

    ctx = engine.initialize_session("Vinyl bar", {})
    await engine.parse_intent(ctx)
    await engine.create_cultural_twin(ctx)
    # Set mock matrix to proceed to AGENTS_RUNNING
    from tasteops.models.cultural_matrix import CulturalMatrix

    ctx.cultural_matrix = CulturalMatrix()
    ctx.current_state = WorkflowState.CULTURAL_MATRIX_READY

    await engine.run_agents_and_generate_plan(ctx)

    # Must transition to FAILED without infinite loop
    assert ctx.current_state == WorkflowState.FAILED
    assert "AGENT_FAILURE" in ctx.error_message
    assert ctx.agent_retry_count >= 2


@pytest.mark.asyncio
async def test_validation_failure_loops_to_plan_generated_and_bounds_cycles(
    mock_mcp_adapter,
):
    """Test Validation failure transitions to PLAN_GENERATED and bounds maximum cycles to FAILED."""
    adapter, _, _, _ = mock_mcp_adapter

    # Mock governance to fail validation
    mock_governance = AsyncMock()
    from tasteops.workflows.schemas import ExecutionPlan

    mock_governance.plan = MagicMock(
        return_value=ExecutionPlan(
            plan_id="plan_mock_01",
            actions=[],
            estimated_cost="$0",
        )
    )
    mock_governance.validate_plan.return_value = GovernanceValidationOutput(
        is_valid=False,
        provenance_verified=False,
        risk_flags=["Conflicting acoustic directives detected: 90dB in quiet zone"],
        readiness_score=0.2,
    )

    engine = WorkflowEngine(
        mcp_adapter=adapter,
        governance=mock_governance,
        max_validation_cycles=2,
    )

    ctx = engine.initialize_session("Quiet lounge", {})
    from tasteops.models.cultural_matrix import CulturalMatrix, CulturalTwin
    from tasteops.workflows.schemas import (
        CulturalActivationPlan,
        CulturalPillar,
        CulturalStrategyOutput,
        ExperienceDesignInput,
        PartnershipOutput,
    )

    ctx.cultural_twin = CulturalTwin()
    ctx.cultural_matrix = CulturalMatrix()
    ctx.strategy_output = CulturalStrategyOutput(
        positioning_statement="Quiet focus",
        cultural_pillars=[
            CulturalPillar(name="Acoustic Focus", description="Calm audio landscape")
        ],
        target_subcultures=[],
        affinity_themes=[],
        provenance_entity_ids=[],
    )
    ctx.experience_output = await engine.architect.execute(
        ExperienceDesignInput(
            cultural_twin=ctx.cultural_twin,
            strategy=ctx.strategy_output,
            cultural_matrix=ctx.cultural_matrix,
        )
    )
    ctx.partnership_output = PartnershipOutput(
        partnerships=[], provenance_entity_ids=[]
    )
    ctx.current_state = WorkflowState.PLAN_GENERATED
    ctx.plan = CulturalActivationPlan(
        plan_id="plan_val_test",
        cultural_twin=ctx.cultural_twin,
        cultural_matrix=ctx.cultural_matrix,
        strategy=ctx.strategy_output,
        experience_design=ctx.experience_output,
        partnerships=ctx.partnership_output,
        governance=mock_governance.validate_plan.return_value,
    )

    # Cycle 1: Validation fails -> transitions back to PLAN_GENERATED
    await engine.validate_and_await_approval(ctx)
    assert ctx.current_state == WorkflowState.PLAN_GENERATED
    assert ctx.validation_cycle_count == 1

    # Cycle 2: Validation fails -> transitions back to PLAN_GENERATED
    await engine.validate_and_await_approval(ctx)
    assert ctx.current_state == WorkflowState.PLAN_GENERATED
    assert ctx.validation_cycle_count == 2

    # Cycle 3: Bounded limit exceeded -> transitions to FAILED
    await engine.validate_and_await_approval(ctx)
    assert ctx.current_state == WorkflowState.FAILED
    assert "cycles exhausted" in ctx.error_message
