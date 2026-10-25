"""TasteOps Approval Gate & Execution Security Boundary Audit Tests.

Proves that execution of external actions is mathematically and operationally impossible when:
1. Approval is absent (Engine unapproved state, missing ApprovalRecord, or Governance default)
2. Approval is rejected (Engine rejection, invalidated ApprovalRecord)
3. Validation failed (GovernanceValidationOutput is_valid=False, risk flags present)
4. Plan is stale (Mismatched plan_id, mismatched version, or SHA-256 mutation after sign-off)
5. Session is in the wrong state (All 11 non-APPROVED states blocked by finite state machine)
6. Execution has already occurred (COMPLETED state is terminal; task idempotency prevents duplicate execution)

Tests verify direct service-level and agent-level invocations to prove that the security boundary
resides firmly within backend application logic, independent of any UI/client controls.
"""

import pytest

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
from tasteops.workflows.persistence import InMemoryStateStore
from tasteops.workflows.schemas import (
    ApprovalRecord,
    CulturalActivationPlan,
    CulturalPillar,
    CulturalStrategyOutput,
    ExperienceDesignInput,
    GovernanceValidationInput,
    GovernanceValidationOutput,
    PartnershipOutput,
    TaskStatus,
)
from tasteops.workflows.states import (
    InvalidStateTransitionError,
    WorkflowState,
)


async def _create_valid_plan() -> CulturalActivationPlan:
    """Generates a valid, cryptographically consistent CulturalActivationPlan."""
    gov = GovernanceAgent()
    twin = CulturalTwin(anchor_entities=["ent_clean"])
    matrix = CulturalMatrix(
        artists=[
            CulturalRecommendation(
                id="ent_clean",
                name="Clean",
                type="artist",
                affinity=0.9,
                source_query="/v2/insights",
            )
        ]
    )
    strat = CulturalStrategyOutput(
        positioning_statement="Clean acoustic listening space",
        cultural_pillars=[
            CulturalPillar(
                name="Sonic Purity",
                description="High fidelity acoustics",
                aligned_entity_ids=["ent_clean"],
            )
        ],
        target_subcultures=["Audiophile"],
        affinity_themes=["Analog warmth"],
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
        plan_id="plan_secure_audit_01",
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
    return plan


# =============================================================================
# 1. Proving Execution is Impossible when Approval is Absent
# =============================================================================
@pytest.mark.asyncio
async def test_execution_impossible_when_approval_absent_engine_level():
    """Prove WorkflowEngine rejects execution if session has not reached APPROVED."""
    engine = WorkflowEngine()
    ctx = WorkflowContext(current_state=WorkflowState.AWAITING_APPROVAL)

    # Direct call to engine.execute_plan when approval was never recorded
    with pytest.raises(
        InvalidStateTransitionError,
        match="cannot transition from 'AWAITING_APPROVAL' to 'EXECUTING'",
    ):
        await engine.execute_plan(ctx)

    assert ctx.current_state == WorkflowState.AWAITING_APPROVAL
    assert ctx.current_state != WorkflowState.EXECUTING
    assert ctx.current_state != WorkflowState.COMPLETED


@pytest.mark.asyncio
async def test_execution_impossible_when_approval_absent_missing_record():
    """Prove execution is blocked even if context state is artificially set to APPROVED without ApprovalRecord."""
    plan = await _create_valid_plan()
    engine = WorkflowEngine()
    # Attacker directly fabricates current_state = APPROVED without going through approve_plan()
    ctx = WorkflowContext(
        current_state=WorkflowState.APPROVED,
        plan=plan,
        approval=None,  # Approval record is absent
    )

    with pytest.raises(
        UnapprovedExecutionError,
        match="Execution blocked: Plan has not been approved",
    ):
        await engine.execute_plan(ctx)

    assert ctx.current_state != WorkflowState.COMPLETED


@pytest.mark.asyncio
async def test_execution_impossible_when_approval_absent_governance_service_level():
    """Prove GovernanceAgent defaults to is_approved=False and rejects unapproved calls."""
    plan = await _create_valid_plan()
    gov = GovernanceAgent()

    # Case A: Default invocation (is_approved defaults to False)
    with pytest.raises(
        UnapprovedExecutionError,
        match="The agent must NEVER execute external actions before explicit approval",
    ):
        await gov.execute_plan(plan)

    # Case B: Explicit is_approved=False
    with pytest.raises(
        UnapprovedExecutionError,
        match="The agent must NEVER execute external actions before explicit approval",
    ):
        await gov.execute_plan(plan, is_approved=False)


# =============================================================================
# 2. Proving Execution is Impossible when Approval is Rejected
# =============================================================================
@pytest.mark.asyncio
async def test_execution_impossible_when_approval_rejected_engine_level():
    """Prove engine rejection marks approval invalid, transitions to FAILED, and blocks execution."""
    store = InMemoryStateStore()
    engine = WorkflowEngine(store=store)
    ctx = engine.initialize_session("Vinyl Speakeasy", {})
    ctx.current_state = WorkflowState.AWAITING_APPROVAL
    ctx.approval = ApprovalRecord(
        session_id=ctx.session_id,
        plan_id="plan_rejected_123",
        approver="pending",
        is_valid=True,
    )

    # Curator explicitly rejects the plan
    await engine.reject_plan(
        ctx, reason="Zoning restriction: Venue cannot operate live music after 11 PM"
    )

    assert ctx.current_state == WorkflowState.FAILED
    assert ctx.approval.is_valid is False
    assert "Zoning restriction" in ctx.approval.invalidation_reason

    # Direct subsequent execution attempt must fail
    with pytest.raises(
        InvalidStateTransitionError,
        match="cannot transition from 'FAILED' to 'EXECUTING'",
    ):
        await engine.execute_plan(ctx)

    assert ctx.current_state == WorkflowState.FAILED
    assert ctx.current_state != WorkflowState.COMPLETED


@pytest.mark.asyncio
async def test_execution_impossible_when_approval_rejected_governance_service_level():
    """Prove GovernanceAgent directly rejects execution when ApprovalRecord has is_valid=False."""
    plan = await _create_valid_plan()
    gov = GovernanceAgent()

    rejected_approval = ApprovalRecord(
        session_id="sess_rej",
        plan_id=plan.plan_id,
        plan_version=plan.version,
        plan_hash=plan.compute_hash(),
        approver="chief_curator",
        is_valid=False,  # REJECTED / INVALIDATED
        invalidation_reason="Aesthetic misalignment with brand identity",
    )

    with pytest.raises(
        UnapprovedExecutionError,
        match="Approval is invalidated: Aesthetic misalignment with brand identity",
    ):
        await gov.execute_plan(
            plan,
            is_approved=True,
            approval=rejected_approval,
            approved_by="chief_curator",
        )


# =============================================================================
# 3. Proving Execution is Impossible when Validation Failed
# =============================================================================
@pytest.mark.asyncio
async def test_execution_impossible_when_validation_failed_service_level():
    """Prove GovernanceAgent directly rejects execution of any plan whose validation failed."""
    plan = await _create_valid_plan()
    gov = GovernanceAgent()

    # Tamper governance output to simulate a failed validation audit
    plan.governance = GovernanceValidationOutput(
        is_valid=False,
        provenance_verified=False,
        risk_flags=[
            "Provenance violation: Unverified external entity referenced",
            "Budget threshold exceeded by $12,000",
        ],
        readiness_score=0.2,
    )

    approval = ApprovalRecord(
        session_id="sess_val_fail",
        plan_id=plan.plan_id,
        plan_version=plan.version,
        plan_hash=plan.compute_hash(),
        approver="reckless_curator",
        is_valid=True,
    )

    with pytest.raises(
        UnapprovedExecutionError,
        match="Cannot execute unvalidated plan: .*Provenance violation",
    ):
        await gov.execute_plan(
            plan, is_approved=True, approval=approval, approved_by="reckless_curator"
        )


# =============================================================================
# 4. Proving Execution is Impossible when Plan is Stale
# =============================================================================
@pytest.mark.asyncio
async def test_execution_impossible_when_plan_is_stale_mismatched_id_or_version():
    """Prove GovernanceAgent rejects execution when approval points to mismatched plan ID or version."""
    plan = await _create_valid_plan()
    gov = GovernanceAgent()

    original_hash = plan.compute_hash()
    base_approval = ApprovalRecord(
        session_id="sess_stale_audit",
        plan_id=plan.plan_id,
        plan_version=1,
        plan_hash=original_hash,
        approver="lead_curator",
        is_valid=True,
    )

    # Sub-case A: Mismatched plan_id
    stale_id_approval = base_approval.model_copy(
        update={"plan_id": "different_plan_999"}
    )
    with pytest.raises(
        UnapprovedExecutionError,
        match="Approval plan_id 'different_plan_999' does not match plan",
    ):
        await gov.execute_plan(plan, is_approved=True, approval=stale_id_approval)

    # Sub-case B: Mismatched plan_version
    stale_version_approval = base_approval.model_copy(update={"plan_version": 2})
    with pytest.raises(
        UnapprovedExecutionError,
        match="Approval for plan version 2 does not authorize version 1",
    ):
        await gov.execute_plan(plan, is_approved=True, approval=stale_version_approval)


@pytest.mark.asyncio
async def test_execution_impossible_when_plan_is_stale_hash_tampered():
    """Prove GovernanceAgent detects post-approval mutation via SHA-256 hash mismatch."""
    plan = await _create_valid_plan()
    gov = GovernanceAgent()

    original_hash = plan.compute_hash()
    approval = ApprovalRecord(
        session_id="sess_tamper",
        plan_id=plan.plan_id,
        plan_version=1,
        plan_hash=original_hash,
        approver="lead_curator",
        is_valid=True,
    )

    # Attacker mutates the plan content after curator signed off
    plan.strategy.positioning_statement = (
        "MUTATED: Commercial electronic dance nightclub"
    )

    # Execution must fail and invalidate the approval
    with pytest.raises(
        UnapprovedExecutionError,
        match="Plan was mutated after approval. Previous approval is invalidated.",
    ):
        await gov.execute_plan(plan, is_approved=True, approval=approval)

    assert approval.is_valid is False
    assert "Plan was mutated after approval" in approval.invalidation_reason


# =============================================================================
# 5. Proving Execution is Impossible when Session is in Wrong State
# =============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "wrong_state",
    [
        WorkflowState.CREATED,
        WorkflowState.INTENT_PARSED,
        WorkflowState.CULTURAL_TWIN_CREATED,
        WorkflowState.QLOO_RESOLVED,
        WorkflowState.CULTURAL_MATRIX_READY,
        WorkflowState.AGENTS_RUNNING,
        WorkflowState.PLAN_GENERATED,
        WorkflowState.VALIDATED,
        WorkflowState.AWAITING_APPROVAL,
        WorkflowState.EXECUTING,
        WorkflowState.FAILED,
    ],
)
async def test_execution_impossible_from_wrong_state(wrong_state):
    """Prove that all 11 non-APPROVED workflow states strictly reject transition to EXECUTING."""
    engine = WorkflowEngine()
    ctx = WorkflowContext(current_state=wrong_state)

    with pytest.raises(
        InvalidStateTransitionError,
        match=f"cannot transition from '{wrong_state.value}' to 'EXECUTING'",
    ):
        await engine.execute_plan(ctx)

    assert ctx.current_state == wrong_state
    assert ctx.current_state != WorkflowState.COMPLETED


# =============================================================================
# 6. Proving Execution is Impossible when Execution has Already Occurred
# =============================================================================
@pytest.mark.asyncio
async def test_execution_impossible_when_already_completed():
    """Prove that once workflow reaches COMPLETED, re-execution is rejected by the state machine."""
    engine = WorkflowEngine()
    ctx = WorkflowContext(current_state=WorkflowState.COMPLETED)

    # COMPLETED is terminal (no valid transitions)
    with pytest.raises(
        InvalidStateTransitionError,
        match="cannot transition from 'COMPLETED' to 'EXECUTING'",
    ):
        await engine.execute_plan(ctx)

    assert ctx.current_state == WorkflowState.COMPLETED


@pytest.mark.asyncio
async def test_duplicate_execution_is_idempotent_no_duplicate_tasks():
    """Prove that direct service-level re-invocation respects idempotency and never duplicates external actions."""
    plan = await _create_valid_plan()
    gov = GovernanceAgent()

    approval = ApprovalRecord(
        session_id="sess_idem_gate",
        plan_id=plan.plan_id,
        plan_version=1,
        plan_hash=plan.compute_hash(),
        approver="lead_curator",
        is_valid=True,
    )

    # 1st Execution
    summary_1 = await gov.execute_plan(
        plan, is_approved=True, approval=approval, approved_by="lead_curator"
    )
    task_count_1 = len(summary_1.tasks)
    assert task_count_1 >= 2

    # 2nd Execution attempt
    summary_2 = await gov.execute_plan(
        plan, is_approved=True, approval=approval, approved_by="lead_curator"
    )
    task_count_2 = len(summary_2.tasks)

    # Idempotency guarantees: zero duplicate tasks dispatched
    assert task_count_1 == task_count_2
    for t1, t2 in zip(summary_1.tasks, summary_2.tasks, strict=True):
        assert t1.idempotency_key == t2.idempotency_key
        assert t1.task_id == t2.task_id
        assert t1.status == TaskStatus.STAGED
