"""Regression Test Suite for Workflow Idempotency and Duplicate Execution Prevention.

Covers:
1. Repeated approve request (Idempotent approval when plan hash is unchanged)
2. Repeated execute request (Idempotent return of ExecutionSummary on repeated execute calls)
3. Concurrent execute requests (Thread/coroutine safety via asyncio locks; zero duplicate tasks)
4. Retry after timeout (Stable idempotency keys prevent re-executing previously completed tasks)
5. Process restart after execution begins (Resumption from EXECUTING state without duplicate tasks)
6. Stable idempotency key verification (Deterministic keys across all executable tasks)
"""

import asyncio
from unittest.mock import patch

import pytest

from tasteops.agents.architect import ExperienceArchitect
from tasteops.agents.governance import GovernanceAgent
from tasteops.models.cultural_matrix import (
    CulturalMatrix,
    CulturalRecommendation,
    CulturalTwin,
)
from tasteops.workflows.context import WorkflowContext
from tasteops.workflows.engine import WorkflowEngine
from tasteops.workflows.persistence import FileStateStore
from tasteops.workflows.schemas import (
    ApprovalRecord,
    CulturalActivationPlan,
    CulturalPillar,
    CulturalStrategyOutput,
    ExecutionTask,
    ExperienceDesignInput,
    GovernanceValidationInput,
    GovernanceValidationOutput,
    PartnershipOutput,
)
from tasteops.workflows.states import WorkflowState


async def _create_test_plan(plan_id: str = "plan_idem_01") -> CulturalActivationPlan:
    """Creates a complete, verified CulturalActivationPlan with audio, brand, and spatial signals."""
    gov = GovernanceAgent()
    twin = CulturalTwin(anchor_entities=["ent_vinyl_lab"])
    matrix = CulturalMatrix(
        artists=[
            CulturalRecommendation(
                id="ent_artist_mono",
                name="Mono Poly",
                type="artist",
                affinity=0.92,
                source_query="/v2/insights",
            )
        ],
        places=[
            CulturalRecommendation(
                id="ent_place_tokyo",
                name="Bar Trench Tokyo",
                type="place",
                affinity=0.88,
                source_query="/v2/insights",
            )
        ],
    )
    strat = CulturalStrategyOutput(
        positioning_statement="Analog audiophile listening bar",
        cultural_pillars=[
            CulturalPillar(
                name="Acoustic Fidelity",
                description="Custom horn-loaded rotary sound system",
                aligned_entity_ids=["ent_artist_mono"],
            )
        ],
        target_subcultures=["Audiophile", "Vinyl Collectors"],
        affinity_themes=["Analog warmth"],
        provenance_entity_ids=["ent_artist_mono"],
    )
    arch = await ExperienceArchitect().execute(
        ExperienceDesignInput(
            cultural_twin=twin, strategy=strat, cultural_matrix=matrix
        )
    )
    part = PartnershipOutput(partnerships=[], provenance_entity_ids=["ent_artist_mono"])
    exec_plan = gov.plan(
        GovernanceValidationInput(
            cultural_twin=twin,
            cultural_matrix=matrix,
            strategy=strat,
            experience_design=arch,
            partnerships=part,
        )
    )

    return CulturalActivationPlan(
        plan_id=plan_id,
        version=1,
        cultural_twin=twin,
        cultural_matrix=matrix,
        strategy=strat,
        experience_design=arch,
        partnerships=part,
        execution_plan=exec_plan,
        governance=GovernanceValidationOutput(
            is_valid=True,
            provenance_verified=True,
            readiness_score=1.0,
            compliance_checks=[],
            risk_flags=[],
        ),
    )


# =============================================================================
# 1. Repeated Approve Request Tests
# =============================================================================
@pytest.mark.asyncio
async def test_repeated_approve_request_is_idempotent():
    """Verify that multiple approve requests on an already approved plan are idempotent."""
    plan = await _create_test_plan("plan_repeat_approve")
    engine = WorkflowEngine()
    ctx = WorkflowContext(
        current_state=WorkflowState.AWAITING_APPROVAL,
        plan=plan,
    )

    # 1st Approval
    await engine.approve_plan(ctx, approver="curator_alex")
    assert ctx.current_state == WorkflowState.APPROVED
    assert ctx.approval is not None
    assert ctx.approval.approver == "curator_alex"
    initial_approval_hash = ctx.approval.plan_hash

    # 2nd Approval (network retry / duplicate request)
    await engine.approve_plan(ctx, approver="curator_alex")
    assert ctx.current_state == WorkflowState.APPROVED
    assert ctx.approval.plan_hash == initial_approval_hash

    # 3rd Approval
    await engine.approve_plan(ctx, approver="curator_alex")
    assert ctx.current_state == WorkflowState.APPROVED

    # Audit history should only contain one APPROVED transition
    approved_events = [e for e in ctx.history if e.to_state == WorkflowState.APPROVED]
    assert len(approved_events) == 1


# =============================================================================
# 2. Repeated Execute Request Tests
# =============================================================================
@pytest.mark.asyncio
async def test_repeated_execute_request_is_idempotent():
    """Verify that calling execute_plan repeatedly on a completed session is idempotent."""
    plan = await _create_test_plan("plan_repeat_execute")
    engine = WorkflowEngine()
    ctx = WorkflowContext(
        current_state=WorkflowState.AWAITING_APPROVAL,
        plan=plan,
    )
    await engine.approve_plan(ctx, approver="curator_elena")

    # 1st Execution
    await engine.execute_plan(ctx)
    assert ctx.current_state == WorkflowState.COMPLETED
    assert ctx.plan.execution_summary is not None
    original_summary = ctx.plan.execution_summary
    initial_task_count = len(ctx.execution_tasks)
    initial_completed_time = original_summary.completed_at

    # 2nd Execution (repeated request)
    await engine.execute_plan(ctx)
    assert ctx.current_state == WorkflowState.COMPLETED
    assert len(ctx.execution_tasks) == initial_task_count
    assert ctx.plan.execution_summary.completed_at == initial_completed_time

    # 3rd Execution
    await engine.execute_plan(ctx)
    assert ctx.current_state == WorkflowState.COMPLETED
    assert len(ctx.execution_tasks) == initial_task_count

    # State transitions should only have one COMPLETED record
    completed_events = [e for e in ctx.history if e.to_state == WorkflowState.COMPLETED]
    assert len(completed_events) == 1


# =============================================================================
# 3. Concurrent Execute Requests Tests
# =============================================================================
@pytest.mark.asyncio
async def test_concurrent_execute_requests_run_safely():
    """Verify that parallel concurrent execution calls on the same session do not duplicate tasks."""
    plan = await _create_test_plan("plan_concurrent_exec")
    engine = WorkflowEngine()
    ctx = WorkflowContext(
        current_state=WorkflowState.AWAITING_APPROVAL,
        plan=plan,
    )
    await engine.approve_plan(ctx, approver="curator_concurrent")

    # Launch 5 concurrent execution requests simultaneously
    results = await asyncio.gather(
        engine.execute_plan(ctx),
        engine.execute_plan(ctx),
        engine.execute_plan(ctx),
        engine.execute_plan(ctx),
        engine.execute_plan(ctx),
    )

    # Every concurrent call must return the completed context
    for res in results:
        assert res.current_state == WorkflowState.COMPLETED
        assert res.plan.execution_summary is not None

    # Tasks should be exactly the expected number (2 tasks: 1 audio seed + 1 spatial spec)
    assert len(ctx.execution_tasks) == 2
    task_ids = [t.task_id for t in ctx.execution_tasks]
    assert len(task_ids) == len(set(task_ids)), (
        "Task IDs must be strictly unique (no duplicates)"
    )


# =============================================================================
# 4. Retry After Timeout Tests
# =============================================================================
@pytest.mark.asyncio
async def test_retry_after_timeout_preserves_idempotency():
    """Verify that when an execution attempt times out, retrying re-uses already executed tasks."""
    plan = await _create_test_plan("plan_timeout_retry")
    gov = GovernanceAgent()
    approval = ApprovalRecord(
        session_id="sess_timeout",
        plan_id=plan.plan_id,
        plan_version=plan.version,
        plan_hash=plan.compute_hash(),
        approver="curator_sam",
        is_valid=True,
    )

    # 1st Execution: Pre-populate task 1 as already executed, simulate failure/timeout midway
    task_1 = ExecutionTask(
        task_id="task_ent_artist_mono_plan_t",
        idempotency_key=f"idem_{plan.plan_id}_spotify_ent_artist_mono",
        action="Export seed artist",
        status="EXECUTED",
        provenance={
            "source": "qloo_insights_artist",
            "source_id": "ent_artist_mono",
            "source_type": "artist",
            "query": "/v2/insights",
            "timestamp": "2026-10-25T00:00:00Z",
            "task_id": "task_ent_artist_mono_plan_t",
            "plan_id": plan.plan_id,
            "session_id": "sess_timeout",
            "approved_by": "curator_sam",
            "approved_at": "2026-10-25T00:00:00Z",
            "execution_status": "EXECUTED",
        },
    )
    gov._idempotency_store[task_1.idempotency_key] = task_1

    # Simulate timeout on 1st run
    with (
        patch.object(
            gov, "audit", side_effect=TimeoutError("Downstream network timeout")
        ),
        pytest.raises(TimeoutError),
    ):
        await gov.execute_plan(plan, is_approved=True, approval=approval)

    # Verify task 1 remains safely recorded
    assert task_1.idempotency_key in gov._idempotency_store

    # 2nd Execution (Retry after timeout): Must succeed without re-executing task 1
    summary = await gov.execute_plan(plan, is_approved=True, approval=approval)
    assert summary.executed_tasks >= 2

    # Verify task 1 was retrieved from idempotency store
    retrieved_task_1 = next(
        t for t in summary.tasks if t.idempotency_key == task_1.idempotency_key
    )
    assert retrieved_task_1.task_id == task_1.task_id


# =============================================================================
# 5. Process Restart After Execution Begins
# =============================================================================
@pytest.mark.asyncio
async def test_process_restart_after_execution_begins(tmp_path):
    """Verify clean recovery when process restarts while in EXECUTING state."""
    store_dir = tmp_path / "restart_during_exec"
    plan = await _create_test_plan("plan_crash_exec")

    # Instance 1: Starts execution, persists EXECUTING state, then crashes
    store_1 = FileStateStore(base_dir=store_dir)
    engine_1 = WorkflowEngine(store=store_1)
    ctx_1 = engine_1.initialize_session("Crash Test Lounge", {})
    ctx_1.plan = plan
    ctx_1.current_state = WorkflowState.AWAITING_APPROVAL
    await engine_1.approve_plan(ctx_1, approver="curator_dave")

    # Manually simulate crash right after entering EXECUTING
    engine_1._record_and_persist(
        ctx_1,
        WorkflowState.EXECUTING,
        reason="Process crashed mid-execution",
    )
    session_id = ctx_1.session_id

    # Destroy Instance 1
    del engine_1
    del store_1

    # Instance 2: Boots afresh from disk
    store_2 = FileStateStore(base_dir=store_dir)
    recovered_ctx = store_2.load_context(session_id)
    assert recovered_ctx is not None
    assert recovered_ctx.current_state == WorkflowState.EXECUTING

    # Resume execution on Instance 2
    engine_2 = WorkflowEngine(store=store_2)
    final_ctx = await engine_2.execute_plan(recovered_ctx)

    assert final_ctx.current_state == WorkflowState.COMPLETED
    assert final_ctx.plan.execution_summary is not None
    assert len(final_ctx.execution_tasks) == 2


# =============================================================================
# 6. Stable Idempotency Key Verification
# =============================================================================
@pytest.mark.asyncio
async def test_stable_idempotency_keys_are_deterministic():
    """Verify that every executable task generated has a deterministic, non-empty idempotency key."""
    plan = await _create_test_plan("plan_stable_keys")
    gov = GovernanceAgent()
    approval = ApprovalRecord(
        session_id="sess_keys",
        plan_id=plan.plan_id,
        plan_version=plan.version,
        plan_hash=plan.compute_hash(),
        approver="curator_keys",
        is_valid=True,
    )

    summary_1 = await gov.execute_plan(plan, is_approved=True, approval=approval)

    # Create an identical plan with the same ID
    plan_clone = await _create_test_plan("plan_stable_keys")
    gov_2 = GovernanceAgent()
    summary_2 = await gov_2.execute_plan(
        plan_clone, is_approved=True, approval=approval
    )

    assert len(summary_1.tasks) == len(summary_2.tasks)
    for t1, t2 in zip(summary_1.tasks, summary_2.tasks, strict=True):
        # Must have non-empty, stable idempotency key
        assert t1.idempotency_key
        assert t2.idempotency_key
        assert t1.idempotency_key == t2.idempotency_key
        assert t1.idempotency_key.startswith(f"idem_{plan.plan_id}_")
