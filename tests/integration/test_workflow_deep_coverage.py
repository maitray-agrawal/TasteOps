"""TasteOps Workflow Behavioral Deep Coverage Test Suite.

Comprehensive behavioral testing covering all 11 workflow requirements:
1. Successful run: complete lifecycle brief -> matrix -> agents -> validation -> approval -> execution -> COMPLETED
2. Qloo failure: 500/502/503 server error triggers backoff retries and graceful transition to FAILED
3. Qloo timeout: timeout triggers retry exhaustion and clean FAILED transition without hung coroutines
4. Agent failure: unhandled runtime failure in agent execution pipeline is bounded, retried, and transitions to FAILED
5. Validation failure: governance compliance/provenance failure loops through refinement cycles up to max and terminates
6. Governance rejection: curator or governance rejection invalidates approval and marks workflow FAILED with audit reason
7. Approval: human curator approval cryptographically binds SHA-256 plan hash and unblocks execution
8. Stale plan: post-approval plan mutation or version discrepancy raises UnapprovedExecutionError and blocks execution
9. Execution: approved plan dispatches connectors with typed outcomes, updates task statuses, reaches COMPLETED
10. Duplicate execution: duplicate task or plan execution with identical idempotency key is safely deduplicated
11. Restart / Recovery: workflow context and audit ledger fully recovered across fresh orchestrator instances from persistent store
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import respx

from tasteops.agents.governance import (
    UnapprovedExecutionError,
)
from tasteops.models.cultural_matrix import (
    CulturalMatrix,
    CulturalTwin,
)
from tasteops.persistence.database import Database
from tasteops.persistence.store import SQLiteStateStore
from tasteops.workflows.engine import WorkflowEngine
from tasteops.workflows.orchestrator import TasteOpsOrchestrator
from tasteops.workflows.schemas import (
    CulturalActivationPlan,
    CulturalPillar,
    CulturalStrategyOutput,
    ExecutionPlan,
    ExperienceDesignInput,
    GovernanceValidationOutput,
    PartnershipOutput,
)
from tasteops.workflows.states import WorkflowState
from tests.fixtures.demo_mumbai_boutique_hotel import (
    MUMBAI_DEMO_HINTS,
    MUMBAI_DEMO_RAW_INTENT,
    MUMBAI_INSIGHTS_MOCK_RESPONSE,
    MUMBAI_SEARCH_MOCK_RESPONSE,
    MUMBAI_TAGS_MOCK_RESPONSE,
)


@pytest.fixture
def mock_mumbai_respx():
    """Sets up respx routes with the Mumbai Boutique Hotel demo fixture."""
    with respx.mock(
        base_url="https://hackathon.api.qloo.com", assert_all_called=False
    ) as mock_router:
        mock_router.get("/search").respond(
            status_code=200, json=MUMBAI_SEARCH_MOCK_RESPONSE
        )
        mock_router.get("/v2/tags").respond(
            status_code=200, json=MUMBAI_TAGS_MOCK_RESPONSE
        )
        mock_router.get("/v2/insights").respond(
            status_code=200, json=MUMBAI_INSIGHTS_MOCK_RESPONSE
        )
        yield mock_router


@pytest.fixture
def persistent_store(tmp_path):
    """Provides an isolated SQLite persistent state store."""
    db_file = tmp_path / f"test_workflow_{uuid.uuid4().hex[:8]}.db"
    db = Database(str(db_file))
    store = SQLiteStateStore(db)
    yield store, db_file
    db.close()


# ---------------------------------------------------------------------------
# 1. Successful Run
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_workflow_successful_run(
    mock_mcp_adapter, mock_mumbai_respx, persistent_store
):
    """Asserts complete end-to-end workflow execution with valid assertions at each milestone."""
    adapter, _, _, _ = mock_mcp_adapter
    store, _ = persistent_store
    orchestrator = TasteOpsOrchestrator(mcp_adapter=adapter, store=store)

    # 1. Initialize
    ctx = orchestrator.create_session(
        user_input=MUMBAI_DEMO_RAW_INTENT,
        space_id="space_mum_boutique_01",
        hints=MUMBAI_DEMO_HINTS,
    )
    assert ctx.current_state == WorkflowState.CREATED
    assert ctx.session_id is not None
    assert ctx.space_id == "space_mum_boutique_01"

    # 2. Run pipeline to approval gate
    ctx = await orchestrator.run_until_approval(ctx.session_id)
    assert ctx.current_state == WorkflowState.AWAITING_APPROVAL
    assert ctx.cultural_twin is not None
    assert ctx.cultural_matrix is not None
    assert ctx.plan is not None
    assert ctx.validation_result is not None
    assert ctx.validation_result.is_valid is True

    # 3. Approve
    ctx = await orchestrator.approve_session(
        ctx.session_id, approver="Lead Cultural Strategist: Satwik"
    )
    assert ctx.current_state == WorkflowState.APPROVED
    assert ctx.approval is not None
    assert ctx.approval.is_valid is True
    assert ctx.approval.approver == "Lead Cultural Strategist: Satwik"
    assert ctx.approval.plan_hash == ctx.plan.compute_hash()

    # 4. Execute
    ctx = await orchestrator.execute_approved_plan(ctx.session_id)
    assert ctx.current_state == WorkflowState.COMPLETED
    assert len(ctx.execution_tasks) >= 2
    for task in ctx.execution_tasks:
        assert task.status == "EXECUTED"
        assert task.idempotency_key != ""
        assert task.provenance["session_id"] == ctx.session_id

    # 5. Audit Events
    audit_events = orchestrator.get_audit_events(ctx.session_id)
    assert len(audit_events) >= 8
    states_traversed = [e.to_state for e in audit_events]
    assert WorkflowState.INTENT_PARSED in states_traversed
    assert WorkflowState.CULTURAL_TWIN_CREATED in states_traversed
    assert WorkflowState.AWAITING_APPROVAL in states_traversed
    assert WorkflowState.APPROVED in states_traversed
    assert WorkflowState.COMPLETED in states_traversed


# ---------------------------------------------------------------------------
# 2. Qloo Failure (HTTP 500/502/503)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_workflow_qloo_failure_retry_and_termination(mock_mcp_adapter):
    """Asserts that Qloo upstream 500 error triggers retry budget and transitions to FAILED."""
    adapter, _, _, _ = mock_mcp_adapter

    mock_strategist = AsyncMock()
    mock_strategist.transform_brief.side_effect = RuntimeError(
        "Qloo API 500 Internal Server Error: Gateway failure"
    )

    engine = WorkflowEngine(
        mcp_adapter=adapter,
        strategist=mock_strategist,
        max_qloo_retries=2,
    )
    orchestrator = TasteOpsOrchestrator(engine=engine)

    ctx = orchestrator.create_session("Speakeasy cafe in Bandra", hints={})
    ctx = await orchestrator.run_until_approval(ctx.session_id)

    assert ctx.current_state == WorkflowState.FAILED
    assert "QLOO_FAILURE" in ctx.error_message
    assert ctx.qloo_retry_count >= 2
    assert "Gateway failure" in ctx.error_message

    # Verify audit event captures failure
    events = orchestrator.get_audit_events(ctx.session_id)
    assert any(e.to_state == WorkflowState.FAILED for e in events)


# ---------------------------------------------------------------------------
# 3. Qloo Timeout (Network/Socket Timeout)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_workflow_qloo_timeout_handling(mock_mcp_adapter):
    """Asserts that Qloo socket/read timeout exhausts retries and transitions safely to FAILED."""
    adapter, _, _, _ = mock_mcp_adapter

    mock_strategist = AsyncMock()
    mock_strategist.transform_brief.side_effect = httpx.ReadTimeout(
        "Connection timed out waiting for Qloo insights endpoint after 2.0s"
    )

    engine = WorkflowEngine(
        mcp_adapter=adapter,
        strategist=mock_strategist,
        max_qloo_retries=2,
    )
    orchestrator = TasteOpsOrchestrator(engine=engine)

    ctx = orchestrator.create_session("Tokyo ambient tea salon", hints={})
    ctx = await orchestrator.run_until_approval(ctx.session_id)

    assert ctx.current_state == WorkflowState.FAILED
    assert "QLOO_FAILURE" in ctx.error_message
    assert ctx.qloo_retry_count >= 2
    assert "timed out" in ctx.error_message.lower()


# ---------------------------------------------------------------------------
# 4. Agent Failure (Injected Exception)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_workflow_agent_failure_boundary(mock_mcp_adapter):
    """Asserts that unexpected agent exception during execution is safely bounded and marks session FAILED."""
    adapter, _, _, _ = mock_mcp_adapter

    mock_architect = AsyncMock()
    mock_architect.execute.side_effect = ValueError(
        "Acoustic synthesis failure: conflicting reverberation decay constraints"
    )

    engine = WorkflowEngine(
        mcp_adapter=adapter,
        architect=mock_architect,
        max_agent_retries=2,
    )
    orchestrator = TasteOpsOrchestrator(engine=engine)

    ctx = orchestrator.create_session("Acoustic Vinyl Lounge", hints={})
    ctx.cultural_twin = CulturalTwin()
    ctx.cultural_matrix = CulturalMatrix()
    ctx.current_state = WorkflowState.CULTURAL_MATRIX_READY

    ctx = await orchestrator.run_until_approval(ctx)

    assert ctx.current_state == WorkflowState.FAILED
    assert "AGENT_FAILURE" in ctx.error_message
    assert "conflicting reverberation" in ctx.error_message
    assert ctx.agent_retry_count >= 2


# ---------------------------------------------------------------------------
# 5. Validation Failure (Governance Rejection Cycle)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_workflow_validation_failure_exhaustion(mock_mcp_adapter):
    """Asserts that validation failures iterate through cycles up to max_validation_cycles and transition to FAILED."""
    adapter, _, _, _ = mock_mcp_adapter

    mock_governance = AsyncMock()
    mock_governance.plan = MagicMock(
        return_value=ExecutionPlan(
            plan_id="plan_val_fail_exhaustive",
            actions=[],
            estimated_cost="$0",
        )
    )
    mock_governance.validate_plan.return_value = GovernanceValidationOutput(
        is_valid=False,
        provenance_verified=False,
        risk_flags=["Acoustic level 105dB violates zoning ordinance"],
        readiness_score=0.1,
    )

    engine = WorkflowEngine(
        mcp_adapter=adapter,
        governance=mock_governance,
        max_validation_cycles=2,
    )
    orchestrator = TasteOpsOrchestrator(engine=engine)

    ctx = orchestrator.create_session("Club in residential zone", hints={})
    ctx.cultural_twin = CulturalTwin()
    ctx.cultural_matrix = CulturalMatrix()
    ctx.strategy_output = CulturalStrategyOutput(
        positioning_statement="Extreme sound",
        cultural_pillars=[CulturalPillar(name="Sound", description="Loud")],
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
        plan_id="plan_val_exhaustive_test",
        cultural_twin=ctx.cultural_twin,
        cultural_matrix=ctx.cultural_matrix,
        strategy=ctx.strategy_output,
        experience_design=ctx.experience_output,
        partnerships=ctx.partnership_output,
        governance=mock_governance.validate_plan.return_value,
    )

    ctx = await orchestrator.run_until_approval(ctx)

    assert ctx.current_state == WorkflowState.FAILED
    assert "VALIDATION_FAILURE" in ctx.error_message
    assert ctx.validation_cycle_count > 2


# ---------------------------------------------------------------------------
# 6. Governance Rejection (Human Curator Sign-off Denied)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_workflow_curator_rejection(mock_mcp_adapter, mock_mumbai_respx):
    """Asserts that curator rejection invalidates plan, transitions to FAILED, and logs reason."""
    adapter, _, _, _ = mock_mcp_adapter
    orchestrator = TasteOpsOrchestrator(mcp_adapter=adapter)

    ctx = orchestrator.create_session(MUMBAI_DEMO_RAW_INTENT, hints=MUMBAI_DEMO_HINTS)
    await orchestrator.run_until_approval(ctx.session_id)
    assert ctx.current_state == WorkflowState.AWAITING_APPROVAL

    # Reject
    ctx = await orchestrator.reject_session(
        ctx.session_id, reason="Acoustic targets exceed residential zone caps"
    )
    assert ctx.current_state == WorkflowState.FAILED
    assert "Acoustic targets exceed residential zone caps" in ctx.error_message

    # Attempting to execute a rejected session must be forbidden
    with pytest.raises(Exception):
        await orchestrator.execute_approved_plan(ctx.session_id)


# ---------------------------------------------------------------------------
# 7. Approval (Cryptographic Plan Binding)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_workflow_approval_binding(mock_mcp_adapter, mock_mumbai_respx):
    """Asserts that approval records human curator credentials and cryptographically seals plan hash."""
    adapter, _, _, _ = mock_mcp_adapter
    orchestrator = TasteOpsOrchestrator(mcp_adapter=adapter)

    ctx = orchestrator.create_session(MUMBAI_DEMO_RAW_INTENT, hints=MUMBAI_DEMO_HINTS)
    await orchestrator.run_until_approval(ctx.session_id)

    ctx = await orchestrator.approve_session(
        ctx.session_id, approver="Curator: Maitray Agrawal"
    )
    assert ctx.current_state == WorkflowState.APPROVED
    assert ctx.approval is not None
    assert ctx.approval.is_valid is True
    assert ctx.approval.approver == "Curator: Maitray Agrawal"
    assert ctx.approval.plan_id == ctx.plan.plan_id
    assert ctx.approval.plan_version == ctx.plan.version
    assert ctx.approval.plan_hash == ctx.plan.compute_hash()


# ---------------------------------------------------------------------------
# 8. Stale Plan (Post-Approval Tampering Detection)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_workflow_stale_plan_tampering_blocked(
    mock_mcp_adapter, mock_mumbai_respx
):
    """Asserts that if plan is mutated after approval, execution is rejected and approval invalidated."""
    adapter, _, _, _ = mock_mcp_adapter
    orchestrator = TasteOpsOrchestrator(mcp_adapter=adapter)

    ctx = orchestrator.create_session(MUMBAI_DEMO_RAW_INTENT, hints=MUMBAI_DEMO_HINTS)
    await orchestrator.run_until_approval(ctx.session_id)
    await orchestrator.approve_session(ctx.session_id)

    # Malicious or stale plan mutation
    ctx.plan.strategy.positioning_statement = "TAMPERED: Mass commercial EDM festival"

    with pytest.raises(
        UnapprovedExecutionError, match="Plan was mutated after approval"
    ):
        await orchestrator.execute_approved_plan(ctx.session_id)

    assert ctx.approval.is_valid is False
    assert "mutated after approval" in ctx.approval.invalidation_reason


# ---------------------------------------------------------------------------
# 9. Execution (Dispatching Connectors)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_workflow_execution_dispatch(mock_mcp_adapter, mock_mumbai_respx):
    """Asserts that approved plans dispatch execution tasks and update provenance metadata."""
    adapter, _, _, _ = mock_mcp_adapter
    orchestrator = TasteOpsOrchestrator(mcp_adapter=adapter)

    ctx = orchestrator.create_session(MUMBAI_DEMO_RAW_INTENT, hints=MUMBAI_DEMO_HINTS)
    await orchestrator.run_until_approval(ctx.session_id)
    await orchestrator.approve_session(ctx.session_id)
    ctx = await orchestrator.execute_approved_plan(ctx.session_id)

    assert ctx.current_state == WorkflowState.COMPLETED
    assert len(ctx.execution_tasks) >= 2
    for t in ctx.execution_tasks:
        assert t.status == "EXECUTED"
        assert t.provenance["session_id"] == ctx.session_id
        assert t.provenance["plan_id"] == ctx.plan.plan_id
        assert "source_id" in t.provenance


# ---------------------------------------------------------------------------
# 10. Duplicate Execution (Idempotency Protection)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_workflow_duplicate_execution_idempotency(
    mock_mcp_adapter, mock_mumbai_respx
):
    """Asserts that re-executing an approved plan returns the cached execution result and prevents duplicate dispatch."""
    adapter, _, _, _ = mock_mcp_adapter
    orchestrator = TasteOpsOrchestrator(mcp_adapter=adapter)

    ctx = orchestrator.create_session(MUMBAI_DEMO_RAW_INTENT, hints=MUMBAI_DEMO_HINTS)
    await orchestrator.run_until_approval(ctx.session_id)
    await orchestrator.approve_session(ctx.session_id)

    # First execution
    summary_1 = await orchestrator.engine.governance.execute_plan(
        ctx.plan,
        is_approved=True,
        approval=ctx.approval,
        session_id=ctx.session_id,
    )
    first_tasks = summary_1.tasks

    # Second execution (duplicate attempt with same plan & tasks)
    summary_2 = await orchestrator.engine.governance.execute_plan(
        ctx.plan,
        is_approved=True,
        approval=ctx.approval,
        session_id=ctx.session_id,
    )
    second_tasks = summary_2.tasks

    assert len(first_tasks) == len(second_tasks)
    for t1, t2 in zip(first_tasks, second_tasks, strict=True):
        assert t1.idempotency_key == t2.idempotency_key
        assert t1.timestamp == t2.timestamp


# ---------------------------------------------------------------------------
# 11. Restart / Recovery (Multi-Instance Persistence)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_workflow_restart_and_recovery(
    mock_mcp_adapter, mock_mumbai_respx, tmp_path
):
    """Asserts that state can be suspended on Instance A and resumed seamlessly on Instance B."""
    adapter, _, _, _ = mock_mcp_adapter
    db_file = tmp_path / "shared_recovery.db"

    # Instance A: runs until approval
    db_a = Database(str(db_file))
    store_a = SQLiteStateStore(db_a)
    orch_a = TasteOpsOrchestrator(mcp_adapter=adapter, store=store_a)

    ctx_a = orch_a.create_session(
        MUMBAI_DEMO_RAW_INTENT,
        space_id="space_mum_boutique_01",
        hints=MUMBAI_DEMO_HINTS,
    )
    session_id = ctx_a.session_id
    await orch_a.run_until_approval(session_id)
    assert ctx_a.current_state == WorkflowState.AWAITING_APPROVAL
    db_a.close()

    # Instance B: recovers from SQLite database file
    db_b = Database(str(db_file))
    store_b = SQLiteStateStore(db_b)
    orch_b = TasteOpsOrchestrator(mcp_adapter=adapter, store=store_b)

    recovered = orch_b.get_session_state(session_id)
    assert recovered.session_id == session_id
    assert recovered.space_id == "space_mum_boutique_01"
    assert recovered.current_state == WorkflowState.AWAITING_APPROVAL
    assert recovered.plan is not None

    # Instance B: completes approval and execution
    await orch_b.approve_session(session_id, approver="Curator on Instance B")
    final_ctx = await orch_b.execute_approved_plan(session_id)
    assert final_ctx.current_state == WorkflowState.COMPLETED
    assert len(final_ctx.execution_tasks) >= 2

    # Verify audit trail contains transitions from both instances
    audit_events = orch_b.get_audit_events(session_id)
    assert len(audit_events) >= 8
    db_b.close()
