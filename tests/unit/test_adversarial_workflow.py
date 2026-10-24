"""Adversarial Test Suite for the Deterministic Workflow Engine and State Machine.

Tests:
1. Invalid state transitions (illegal jumps, transitions from terminal states)
2. Agent failure (bounded retries, transitions to FAILED, never jumps to COMPLETED)
3. Retry exhaustion (bounded retry caps, deterministic FAILED terminal state)
4. Qloo failure (network/provider failure, fallback exhaustion, persisted FAILED state)
5. Validation failure (corrective cycle exhaustion, terminal FAILED state)
6. Governance rejection (unvalidated plan execution blocked, invalid entities flagged)
7. Approval rejection (curator rejection, approval invalidation, persisted failure)
8. Restart during workflow (process restart, disk restoration, state consistency)
9. Duplicate workflow request (idempotency enforcement, duplicate execution prevention)
10. Execution after failure (illegal transition from FAILED blocked)
11. Execution before approval (unapproved execution strictly blocked)
12. Stale workflow state (mutated plan hash, mismatched approval ID rejected)

Guarantees:
- The workflow must NEVER silently jump to COMPLETED.
- Every terminal failure must be persisted and observable.
- Working behavior is not modified merely to satisfy tests.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
import respx

from tasteops.agents.architect import ExperienceArchitect
from tasteops.agents.governance import (
    GovernanceAgent,
    UnapprovedExecutionError,
)
from tasteops.models.cultural_matrix import (
    CulturalMatrix,
    CulturalRecommendation,
    CulturalTwin,
)
from tasteops.workflows.context import WorkflowContext
from tasteops.workflows.engine import WorkflowEngine
from tasteops.workflows.orchestrator import TasteOpsOrchestrator
from tasteops.workflows.persistence import (
    FileStateStore,
    InMemoryStateStore,
)
from tasteops.workflows.schemas import (
    ApprovalRecord,
    CulturalActivationPlan,
    CulturalPillar,
    CulturalStrategyOutput,
    ExecutionPlan,
    ExperienceDesignInput,
    GovernanceValidationInput,
    GovernanceValidationOutput,
    PartnershipOutput,
)
from tasteops.workflows.states import (
    InvalidStateTransitionError,
    WorkflowState,
    validate_transition,
)


# =============================================================================
# 1. Invalid State Transition Tests
# =============================================================================
def test_adversarial_invalid_state_transitions():
    """Verify that illegal transitions and bypass attempts are strictly rejected."""
    # Attempting to jump directly from CREATED to COMPLETED (never silently jump!)
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(WorkflowState.CREATED, WorkflowState.COMPLETED)

    # Attempting to jump directly from CREATED to EXECUTING
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(WorkflowState.CREATED, WorkflowState.EXECUTING)

    # Attempting to jump directly from INTENT_PARSED to COMPLETED
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(WorkflowState.INTENT_PARSED, WorkflowState.COMPLETED)

    # Attempting to jump directly from QLOO_RESOLVED to APPROVED (skipping matrix and agents)
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(WorkflowState.QLOO_RESOLVED, WorkflowState.APPROVED)

    # Attempting to jump from AWAITING_APPROVAL directly to EXECUTING (skipping APPROVED)
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(WorkflowState.AWAITING_APPROVAL, WorkflowState.EXECUTING)

    # Terminal state COMPLETED cannot transition to any other state
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(WorkflowState.COMPLETED, WorkflowState.EXECUTING)
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(WorkflowState.COMPLETED, WorkflowState.CREATED)

    # Terminal state FAILED cannot transition to COMPLETED or EXECUTING
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(WorkflowState.FAILED, WorkflowState.COMPLETED)
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(WorkflowState.FAILED, WorkflowState.EXECUTING)


# =============================================================================
# 2. Agent Failure Tests
# =============================================================================
@pytest.mark.asyncio
async def test_adversarial_agent_failure_persisted_and_observable(mock_mcp_adapter):
    """Verify agent failure retries up to bound, transitions to FAILED, and never reaches COMPLETED."""
    adapter, _, _, _ = mock_mcp_adapter
    store = InMemoryStateStore()

    mock_architect = AsyncMock()
    mock_architect.execute.side_effect = RuntimeError(
        "Fatal GPU memory corruption in architect"
    )

    engine = WorkflowEngine(
        mcp_adapter=adapter,
        architect=mock_architect,
        store=store,
        max_agent_retries=2,
    )

    ctx = engine.initialize_session("Vinyl lounge", {})
    await engine.parse_intent(ctx)
    await engine.create_cultural_twin(ctx)
    ctx.cultural_matrix = CulturalMatrix()
    ctx.current_state = WorkflowState.CULTURAL_MATRIX_READY

    # Run agents
    await engine.run_agents_and_generate_plan(ctx)

    # Must be FAILED, NOT COMPLETED
    assert ctx.current_state == WorkflowState.FAILED
    assert ctx.current_state != WorkflowState.COMPLETED
    assert "AGENT_FAILURE" in ctx.error_message
    assert ctx.agent_retry_count >= 2

    # Verify failure is persisted in store and observable
    events = store.get_audit_events(ctx.session_id)
    failed_events = [e for e in events if e.to_state == WorkflowState.FAILED]
    assert len(failed_events) == 1
    assert "Fatal GPU memory corruption" in failed_events[0].error


# =============================================================================
# 3. Retry Exhaustion Tests
# =============================================================================
@pytest.mark.asyncio
async def test_adversarial_retry_exhaustion():
    """Verify that bounded retries terminate strictly in FAILED without infinite spinning."""
    store = InMemoryStateStore()
    mock_strategist = AsyncMock()
    # Continuous failure
    mock_strategist.transform_brief.side_effect = RuntimeError(
        "Upstream API 503 Unavailable"
    )

    engine = WorkflowEngine(
        strategist=mock_strategist,
        store=store,
        max_qloo_retries=3,
    )

    ctx = engine.initialize_session("Coffee bar", {"raw_anchor_entities": ["SeedCafe"]})
    await engine.parse_intent(ctx)
    await engine.create_cultural_twin(ctx)
    await engine.resolve_qloo_anchors(ctx)

    assert ctx.current_state == WorkflowState.FAILED
    assert ctx.current_state != WorkflowState.COMPLETED
    assert ctx.qloo_retry_count >= 3
    assert "QLOO_FAILURE_TERMINAL" in ctx.history[-1].reason


# =============================================================================
# 4. Qloo Failure Tests
# =============================================================================
@pytest.mark.asyncio
async def test_adversarial_qloo_failure():
    """Verify that Qloo matrix query failure across retries and fallback transitions to FAILED."""
    mock_mcp = AsyncMock()
    # get_cultural_matrix always raises exception
    mock_mcp.get_cultural_matrix.side_effect = RuntimeError("Qloo timeout error 504")

    store = InMemoryStateStore()
    engine = WorkflowEngine(
        mcp_adapter=mock_mcp,
        store=store,
        max_qloo_retries=1,
    )

    ctx = engine.initialize_session("HiFi Bar", {})
    ctx.cultural_twin = CulturalTwin()
    ctx.current_state = WorkflowState.QLOO_RESOLVED

    await engine.fetch_cultural_matrix(ctx)

    assert ctx.current_state == WorkflowState.FAILED
    assert ctx.current_state != WorkflowState.COMPLETED
    assert "QLOO_FAILURE_TERMINAL" in ctx.history[-1].reason
    assert "timeout error 504" in ctx.error_message


# =============================================================================
# 5. Validation Failure Tests
# =============================================================================
@pytest.mark.asyncio
async def test_adversarial_validation_failure_exhaustion():
    """Verify that unresolvable plan validation failure exhausts cycles and terminates in FAILED."""
    mock_governance = AsyncMock()
    mock_governance.plan = MagicMock(
        return_value=ExecutionPlan(plan_id="p1", actions=[], estimated_cost="$0")
    )
    mock_governance.validate_plan.return_value = GovernanceValidationOutput(
        is_valid=False,
        provenance_verified=False,
        risk_flags=["Acoustic conflict: 100dB club sound in residential quiet zone"],
        readiness_score=0.1,
    )

    store = InMemoryStateStore()
    engine = WorkflowEngine(
        governance=mock_governance, store=store, max_validation_cycles=2
    )

    ctx = engine.initialize_session("Quiet lounge", {})
    ctx.cultural_twin = CulturalTwin()
    ctx.cultural_matrix = CulturalMatrix()
    ctx.strategy_output = CulturalStrategyOutput(
        positioning_statement="Quiet",
        cultural_pillars=[CulturalPillar(name="P", description="D")],
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
        plan_id="plan_fail_cycles",
        cultural_twin=ctx.cultural_twin,
        cultural_matrix=ctx.cultural_matrix,
        strategy=ctx.strategy_output,
        experience_design=ctx.experience_output,
        partnerships=ctx.partnership_output,
        governance=mock_governance.validate_plan.return_value,
    )

    # Cycle 1 -> loops back to PLAN_GENERATED
    await engine.validate_and_await_approval(ctx)
    assert ctx.current_state == WorkflowState.PLAN_GENERATED
    assert ctx.validation_cycle_count == 1

    # Cycle 2 -> loops back to PLAN_GENERATED
    await engine.validate_and_await_approval(ctx)
    assert ctx.current_state == WorkflowState.PLAN_GENERATED
    assert ctx.validation_cycle_count == 2

    # Cycle 3 -> exhausted -> FAILED
    await engine.validate_and_await_approval(ctx)
    assert ctx.current_state == WorkflowState.FAILED
    assert ctx.current_state != WorkflowState.COMPLETED
    assert "VALIDATION_FAILURE" in ctx.error_message


# =============================================================================
# 6. Governance Rejection Tests
# =============================================================================
@pytest.mark.asyncio
async def test_adversarial_governance_rejection():
    """Verify that executing a plan flagged as invalid by governance is blocked."""
    gov = GovernanceAgent()
    invalid_plan = CulturalActivationPlan(
        plan_id="plan_unvalidated",
        cultural_twin=CulturalTwin(),
        cultural_matrix=CulturalMatrix(),
        strategy=CulturalStrategyOutput(
            positioning_statement="Pos",
            cultural_pillars=[CulturalPillar(name="P", description="D")],
            target_subcultures=[],
            affinity_themes=[],
            provenance_entity_ids=[],
        ),
        experience_design=await ExperienceArchitect().execute(
            ExperienceDesignInput(
                cultural_twin=CulturalTwin(), cultural_matrix=CulturalMatrix()
            )
        ),
        partnerships=PartnershipOutput(partnerships=[], provenance_entity_ids=[]),
        governance=GovernanceValidationOutput(
            is_valid=False,  # Unvalidated / Failed
            provenance_verified=False,
            risk_flags=[
                "Critical provenance violation: Hallucinated entity IDs detected"
            ],
            readiness_score=0.0,
        ),
    )

    with pytest.raises(
        UnapprovedExecutionError, match="Cannot execute unvalidated plan"
    ):
        await gov.execute_plan(invalid_plan, is_approved=True)


# =============================================================================
# 7. Approval Rejection Tests
# =============================================================================
@pytest.mark.asyncio
async def test_adversarial_approval_rejection():
    """Verify curator rejection invalidates plan, transitions to FAILED, and records audit trail."""
    store = InMemoryStateStore()
    engine = WorkflowEngine(store=store)

    ctx = engine.initialize_session("Speakeasy", {})
    ctx.current_state = WorkflowState.AWAITING_APPROVAL
    ctx.approval = ApprovalRecord(
        session_id=ctx.session_id,
        plan_id="plan_123",
        approver="pending",
        is_valid=True,
    )

    # Curator rejects
    await engine.reject_plan(
        ctx, reason="Acoustics violation: Exceeds local zoning noise code"
    )

    assert ctx.current_state == WorkflowState.FAILED
    assert ctx.current_state != WorkflowState.COMPLETED
    assert ctx.approval.is_valid is False
    assert "Exceeds local zoning noise code" in ctx.approval.invalidation_reason
    assert "Exceeds local zoning noise code" in ctx.error_message

    # Verify audit event persisted
    events = store.get_audit_events(ctx.session_id)
    assert events[-1].to_state == WorkflowState.FAILED
    assert "Exceeds local zoning noise code" in events[-1].error


# =============================================================================
# 8. Restart During Workflow Tests
# =============================================================================
@pytest.mark.asyncio
async def test_adversarial_restart_during_workflow(tmp_path, mock_mcp_adapter):
    """Verify that process restart at intermediate state recovers state cleanly without skipping steps."""
    adapter, mock_search, mock_tags, mock_insights = mock_mcp_adapter
    store_dir = tmp_path / "crash_recovery_test"

    async with respx.mock(
        base_url="https://hackathon.api.qloo.com", assert_all_called=False
    ) as mock_router:
        mock_router.get("/search").respond(status_code=200, json=mock_search)
        mock_router.get("/v2/tags").respond(status_code=200, json=mock_tags)
        mock_router.get("/v2/insights").respond(status_code=200, json=mock_insights)

        # Instance 1: Starts and runs until AWAITING_APPROVAL
        store_1 = FileStateStore(base_dir=store_dir)
        orch_1 = TasteOpsOrchestrator(mcp_adapter=adapter, store=store_1)
        ctx_1 = orch_1.create_session(
            "Japanese Vinyl Lounge", hints={"raw_anchor_entities": ["Blue Bottle"]}
        )
        session_id = ctx_1.session_id
        await orch_1.run_until_approval(session_id)
        assert ctx_1.current_state == WorkflowState.AWAITING_APPROVAL

        # "Crash" Instance 1 by deleting orchestrator reference
        del orch_1
        del store_1

        # Instance 2: Boots afresh from disk storage
        store_2 = FileStateStore(base_dir=store_dir)
        orch_2 = TasteOpsOrchestrator(mcp_adapter=adapter, store=store_2)

        # Recover session state from disk
        recovered = orch_2.get_session_state(session_id)
        assert recovered.session_id == session_id
        assert recovered.current_state == WorkflowState.AWAITING_APPROVAL
        assert recovered.current_state != WorkflowState.COMPLETED
        assert recovered.plan is not None

        # Verify history is preserved
        audit_events = orch_2.get_audit_events(session_id)
        assert len(audit_events) >= 8

        # Continue lawfully to completion on instance 2
        await orch_2.approve_session(session_id, approver="alice")
        final_ctx = await orch_2.execute_approved_plan(session_id)
        assert final_ctx.current_state == WorkflowState.COMPLETED


# =============================================================================
# 9. Duplicate Workflow Request Tests (Idempotency)
# =============================================================================
@pytest.mark.asyncio
async def test_adversarial_duplicate_workflow_request(mock_mcp_adapter):
    """Verify that duplicate execution dispatches do not duplicate tasks or create duplicate actions."""
    adapter, mock_search, mock_tags, mock_insights = mock_mcp_adapter

    async with respx.mock(
        base_url="https://hackathon.api.qloo.com", assert_all_called=False
    ) as mock_router:
        mock_router.get("/search").respond(status_code=200, json=mock_search)
        mock_router.get("/v2/tags").respond(status_code=200, json=mock_tags)
        mock_router.get("/v2/insights").respond(status_code=200, json=mock_insights)

        orch = TasteOpsOrchestrator(mcp_adapter=adapter)
        ctx = orch.create_session(
            "Listening Bar", hints={"raw_anchor_entities": ["Blue Bottle"]}
        )
        await orch.run_until_approval(ctx.session_id)
        await orch.approve_session(ctx.session_id)

        # 1st Execution
        exec_1 = await orch.engine.governance.execute_plan(
            ctx.plan, is_approved=True, approval=ctx.approval, session_id=ctx.session_id
        )
        task_count_1 = len(exec_1.tasks)

        # 2nd Execution (duplicate request)
        exec_2 = await orch.engine.governance.execute_plan(
            ctx.plan, is_approved=True, approval=ctx.approval, session_id=ctx.session_id
        )
        task_count_2 = len(exec_2.tasks)

        # Same number of tasks, identical idempotency keys, zero duplicates created
        assert task_count_1 == task_count_2
        for t1, t2 in zip(exec_1.tasks, exec_2.tasks, strict=True):
            assert t1.idempotency_key == t2.idempotency_key
            assert t1.task_id == t2.task_id


# =============================================================================
# 10. Execution After Failure Tests
# =============================================================================
@pytest.mark.asyncio
async def test_adversarial_execution_after_failure():
    """Verify that attempting to execute an activation plan after workflow FAILED is strictly rejected."""
    engine = WorkflowEngine()
    ctx = WorkflowContext(
        current_state=WorkflowState.FAILED, error_message="Previous fatal error"
    )

    # Attempting to call execute_plan on failed context
    with pytest.raises(
        InvalidStateTransitionError,
        match="cannot transition from 'FAILED' to 'EXECUTING'",
    ):
        await engine.execute_plan(ctx)

    # Workflow must remain FAILED, never jump to COMPLETED
    assert ctx.current_state == WorkflowState.FAILED
    assert ctx.current_state != WorkflowState.COMPLETED


# =============================================================================
# 11. Execution Before Approval Tests
# =============================================================================
@pytest.mark.asyncio
async def test_adversarial_execution_before_approval():
    """Verify that attempting to execute an activation plan before approval is strictly rejected."""
    engine = WorkflowEngine()

    # Case A: Engine at AWAITING_APPROVAL attempted execute_plan without approve_plan
    ctx = WorkflowContext(current_state=WorkflowState.AWAITING_APPROVAL)
    with pytest.raises(
        InvalidStateTransitionError,
        match="cannot transition from 'AWAITING_APPROVAL' to 'EXECUTING'",
    ):
        await engine.execute_plan(ctx)

    assert ctx.current_state == WorkflowState.AWAITING_APPROVAL
    assert ctx.current_state != WorkflowState.COMPLETED

    # Case B: Governance execute_plan called with is_approved=False
    gov = GovernanceAgent()
    plan = CulturalActivationPlan(
        plan_id="plan_unapproved",
        cultural_twin=CulturalTwin(),
        cultural_matrix=CulturalMatrix(),
        strategy=CulturalStrategyOutput(
            positioning_statement="Pos",
            cultural_pillars=[CulturalPillar(name="P", description="D")],
            target_subcultures=[],
            affinity_themes=[],
            provenance_entity_ids=[],
        ),
        experience_design=await ExperienceArchitect().execute(
            ExperienceDesignInput(
                cultural_twin=CulturalTwin(), cultural_matrix=CulturalMatrix()
            )
        ),
        partnerships=PartnershipOutput(partnerships=[], provenance_entity_ids=[]),
        governance=GovernanceValidationOutput(
            is_valid=True, provenance_verified=True, readiness_score=1.0
        ),
    )

    with pytest.raises(
        UnapprovedExecutionError,
        match="The agent must NEVER execute external actions before explicit approval",
    ):
        await gov.execute_plan(plan, is_approved=False)


# =============================================================================
# 12. Stale Workflow State Tests
# =============================================================================
@pytest.mark.asyncio
async def test_adversarial_stale_workflow_state():
    """Verify that stale approvals, mutated plans, and mismatched versions are rejected."""
    gov = GovernanceAgent()

    # Construct clean plan
    twin = CulturalTwin(anchor_entities=["ent_clean"])
    matrix = CulturalMatrix(
        artists=[
            CulturalRecommendation(
                id="ent_clean",
                name="Clean",
                type="artist",
                affinity=0.9,
                source_query="/q",
            )
        ]
    )
    strat = CulturalStrategyOutput(
        positioning_statement="Clean original plan",
        cultural_pillars=[
            CulturalPillar(
                name="Clean Pillar",
                description="Original",
                aligned_entity_ids=["ent_clean"],
            )
        ],
        target_subcultures=[],
        affinity_themes=[],
        provenance_entity_ids=["ent_clean"],
    )
    arch = await ExperienceArchitect().execute(
        ExperienceDesignInput(
            cultural_twin=twin, strategy=strat, cultural_matrix=matrix
        )
    )
    part = PartnershipOutput(partnerships=[], provenance_entity_ids=["ent_clean"])
    exec_plan = gov.plan(
        GovernanceValidationInput(
            cultural_twin=twin,
            cultural_matrix=matrix,
            strategy=strat,
            experience_design=arch,
            partnerships=part,
        )
    )

    plan = CulturalActivationPlan(
        plan_id="plan_stale_test",
        version=1,
        cultural_twin=twin,
        cultural_matrix=matrix,
        strategy=strat,
        experience_design=arch,
        partnerships=part,
        execution_plan=exec_plan,
        governance=GovernanceValidationOutput(
            is_valid=True, provenance_verified=True, readiness_score=1.0
        ),
    )

    original_hash = plan.compute_hash()
    approval = ApprovalRecord(
        session_id="sess_stale",
        plan_id=plan.plan_id,
        plan_version=1,
        plan_hash=original_hash,
        approver="curator_bob",
        is_valid=True,
    )

    # Case 1: Mismatched plan_id
    stale_approval_id = approval.model_copy(update={"plan_id": "different_plan_999"})
    with pytest.raises(UnapprovedExecutionError, match="does not match plan"):
        await gov.execute_plan(plan, is_approved=True, approval=stale_approval_id)

    # Case 2: Mismatched plan_version
    stale_approval_version = approval.model_copy(update={"plan_version": 2})
    with pytest.raises(UnapprovedExecutionError, match="does not authorize version"):
        await gov.execute_plan(plan, is_approved=True, approval=stale_approval_version)

    # Case 3: Plan mutated after approval (tampered content)
    plan.strategy.positioning_statement = "TAMPERED: Secret commercial nightclub"
    with pytest.raises(
        UnapprovedExecutionError, match="Plan was mutated after approval"
    ):
        await gov.execute_plan(plan, is_approved=True, approval=approval)

    # Verify approval was invalidated
    assert approval.is_valid is False
    assert "mutated after approval" in approval.invalidation_reason
