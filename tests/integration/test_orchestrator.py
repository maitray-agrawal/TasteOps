"""TasteOps Integration Test Suite.

Verifies the 14 mandatory integration scenarios:
1. Complete workflow
2. Qloo failure
3. Qloo fallback
4. Agent failure
5. Validation failure
6. Curator rejection
7. Successful approval
8. Execution
9. Duplicate execution (idempotency)
10. Plan mutation after approval
11. Invalid Qloo entity (provenance check)
12. Missing evidence
13. Unsupported external action
14. Persistence recovery
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
import respx

from tasteops.agents.architect import ExperienceArchitect
from tasteops.agents.governance import (
    GovernanceAgent,
    ProvenanceValidationError,
    UnapprovedExecutionError,
)
from tasteops.connectors import create_configured_mock_registry
from tasteops.models.cultural_matrix import (
    CulturalMatrix,
    CulturalRecommendation,
    CulturalTwin,
)
from tasteops.workflows.engine import WorkflowEngine
from tasteops.workflows.orchestrator import TasteOpsOrchestrator
from tasteops.workflows.persistence import FileStateStore
from tasteops.workflows.schemas import (
    CulturalActivationPlan,
    CulturalPillar,
    CulturalStrategyOutput,
    ExecutionPlan,
    ExecutionPlanAction,
    ExecutionTask,
    ExperienceDesignInput,
    GovernanceValidationInput,
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


# ---------------------------------------------------------------------------
# 1. Complete Workflow
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_01_complete_workflow(mock_mcp_adapter, mock_mumbai_respx):
    """Test full sequential lifecycle from creation to approval, execution, and completion."""
    adapter, _, _, _ = mock_mcp_adapter
    orchestrator = TasteOpsOrchestrator(
        mcp_adapter=adapter,
        connector_registry=create_configured_mock_registry(),
    )

    # Step 1: Create session
    ctx = orchestrator.create_session(
        user_input=MUMBAI_DEMO_RAW_INTENT,
        space_id="space_mum_boutique_01",
        hints=MUMBAI_DEMO_HINTS,
    )
    assert ctx.current_state == WorkflowState.CREATED
    assert ctx.space_id == "space_mum_boutique_01"
    assert ctx.user_input == MUMBAI_DEMO_RAW_INTENT

    # Step 2: Run until approval gate
    ctx = await orchestrator.run_until_approval(ctx.session_id)
    assert ctx.current_state == WorkflowState.AWAITING_APPROVAL
    assert ctx.plan is not None
    assert ctx.agent_results is not None
    assert ctx.agent_results.strategy is not None
    assert ctx.agent_results.experience is not None
    assert ctx.agent_results.partnership is not None
    assert ctx.execution_plan is not None
    assert ctx.validation_result is not None
    assert ctx.validation_result.is_valid is True

    # Step 3: Approve session
    ctx = await orchestrator.approve_session(
        ctx.session_id, approver="Curator: Maitray Agrawal"
    )
    assert ctx.current_state == WorkflowState.APPROVED
    assert ctx.approval is not None
    assert ctx.approval.approver == "Curator: Maitray Agrawal"
    assert ctx.approval.plan_hash != ""

    # Step 4: Execute plan
    ctx = await orchestrator.execute_approved_plan(ctx.session_id)
    assert ctx.current_state == WorkflowState.COMPLETED
    assert len(ctx.execution_tasks) >= 2
    for task in ctx.execution_tasks:
        assert task.status == "EXECUTED"
        assert task.idempotency_key != ""
        assert task.provenance["session_id"] == ctx.session_id


# ---------------------------------------------------------------------------
# 2. Qloo Failure
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_02_qloo_failure(mock_mcp_adapter):
    """Test Qloo failure: Retries exhausted and fallback failure transitions to FAILED."""
    adapter, _, _, _ = mock_mcp_adapter

    mock_strategist = AsyncMock()
    mock_strategist.transform_brief.side_effect = RuntimeError(
        "Qloo API 500 Server Error"
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


# ---------------------------------------------------------------------------
# 3. Qloo Fallback
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_03_qloo_fallback(mock_mcp_adapter, mock_mumbai_respx):
    """Test Qloo fallback: Initial query fails, sanitized fallback succeeds, pipeline continues."""
    adapter, _, _, _ = mock_mcp_adapter

    mock_strategist = AsyncMock()
    # First 2 attempts fail; 3rd attempt (fallback) returns valid twin
    from tests.fixtures.demo_mumbai_boutique_hotel import get_mumbai_demo_twin

    mock_strategist.transform_brief.side_effect = [
        RuntimeError("Transient 504 Gateway Timeout"),
        RuntimeError("Transient 504 Gateway Timeout"),
        get_mumbai_demo_twin(),
    ]
    mock_strategist.execute.return_value = CulturalStrategyOutput(
        positioning_statement="Contemporary Indian Luxury",
        cultural_pillars=[CulturalPillar(name="Craft", description="Artisanal")],
        target_subcultures=[],
        affinity_themes=[],
        provenance_entity_ids=["test_fixture_ent_raw_mango"],
    )

    engine = WorkflowEngine(
        mcp_adapter=adapter,
        strategist=mock_strategist,
        max_qloo_retries=1,
    )
    orchestrator = TasteOpsOrchestrator(engine=engine)

    ctx = orchestrator.create_session(MUMBAI_DEMO_RAW_INTENT, hints=MUMBAI_DEMO_HINTS)
    ctx = await orchestrator.run_until_approval(ctx.session_id)

    # Fallback succeeded, workflow reached approval gate!
    assert ctx.current_state == WorkflowState.AWAITING_APPROVAL
    assert ctx.cultural_twin is not None


# ---------------------------------------------------------------------------
# 4. Agent Failure
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_04_agent_failure(mock_mcp_adapter):
    """Test Agent failure: Retries bounded, failure transitions to FAILED without infinite loop."""
    adapter, _, _, _ = mock_mcp_adapter

    mock_architect = AsyncMock()
    mock_architect.execute.side_effect = RuntimeError(
        "Architect memory overflow in spatial synthesis"
    )

    engine = WorkflowEngine(
        mcp_adapter=adapter,
        architect=mock_architect,
        max_agent_retries=2,
    )
    orchestrator = TasteOpsOrchestrator(engine=engine)

    ctx = orchestrator.create_session("Vinyl lounge", hints={})
    ctx.cultural_twin = CulturalTwin()
    ctx.cultural_matrix = CulturalMatrix()
    ctx.current_state = WorkflowState.CULTURAL_MATRIX_READY

    ctx = await orchestrator.run_until_approval(ctx)

    assert ctx.current_state == WorkflowState.FAILED
    assert "AGENT_FAILURE" in ctx.error_message
    assert ctx.agent_retry_count >= 2


# ---------------------------------------------------------------------------
# 5. Validation Failure
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_05_validation_failure(mock_mcp_adapter):
    """Test Validation failure loops back to PLAN_GENERATED and exhausts cycles to FAILED."""
    adapter, _, _, _ = mock_mcp_adapter

    mock_governance = AsyncMock()
    mock_governance.plan = MagicMock(
        return_value=ExecutionPlan(
            plan_id="plan_val_fail_01",
            actions=[],
            estimated_cost="$0",
        )
    )
    mock_governance.validate_plan.return_value = GovernanceValidationOutput(
        is_valid=False,
        provenance_verified=False,
        risk_flags=["Conflicting acoustic directives: 95dB in silent library"],
        readiness_score=0.1,
    )

    engine = WorkflowEngine(
        mcp_adapter=adapter,
        governance=mock_governance,
        max_validation_cycles=2,
    )
    orchestrator = TasteOpsOrchestrator(engine=engine)

    ctx = orchestrator.create_session("Library lounge", hints={})
    ctx.cultural_twin = CulturalTwin()
    ctx.cultural_matrix = CulturalMatrix()
    ctx.strategy_output = CulturalStrategyOutput(
        positioning_statement="Quiet focus",
        cultural_pillars=[CulturalPillar(name="Silence", description="Minimal sound")],
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

    ctx = await orchestrator.run_until_approval(ctx)

    assert ctx.current_state == WorkflowState.FAILED
    assert "VALIDATION_FAILURE" in ctx.error_message
    assert ctx.validation_cycle_count > 2


# ---------------------------------------------------------------------------
# 6. Curator Rejection
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_06_curator_rejection(mock_mcp_adapter, mock_mumbai_respx):
    """Test Curator rejection transitions AWAITING_APPROVAL -> FAILED and invalidates plan."""
    adapter, _, _, _ = mock_mcp_adapter
    orchestrator = TasteOpsOrchestrator(mcp_adapter=adapter)

    ctx = orchestrator.create_session(MUMBAI_DEMO_RAW_INTENT, hints=MUMBAI_DEMO_HINTS)
    await orchestrator.run_until_approval(ctx.session_id)
    assert ctx.current_state == WorkflowState.AWAITING_APPROVAL

    ctx = await orchestrator.reject_session(
        ctx.session_id, reason="Acoustic targets exceed residential zone caps"
    )
    assert ctx.current_state == WorkflowState.FAILED
    assert "Acoustic targets exceed" in ctx.error_message


# ---------------------------------------------------------------------------
# 7. Successful Approval
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_07_successful_approval(mock_mcp_adapter, mock_mumbai_respx):
    """Test Successful approval creates immutable cryptographic ApprovalRecord."""
    adapter, _, _, _ = mock_mcp_adapter
    orchestrator = TasteOpsOrchestrator(mcp_adapter=adapter)

    ctx = orchestrator.create_session(MUMBAI_DEMO_RAW_INTENT, hints=MUMBAI_DEMO_HINTS)
    await orchestrator.run_until_approval(ctx.session_id)

    ctx = await orchestrator.approve_session(
        ctx.session_id, approver="Head Curator: Maitray"
    )
    assert ctx.current_state == WorkflowState.APPROVED
    assert ctx.approval is not None
    assert ctx.approval.is_valid is True
    assert ctx.approval.approver == "Head Curator: Maitray"
    assert ctx.approval.plan_id == ctx.plan.plan_id
    assert ctx.approval.plan_version == ctx.plan.version
    assert ctx.approval.plan_hash == ctx.plan.compute_hash()


# ---------------------------------------------------------------------------
# 8. Execution
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_08_execution(mock_mcp_adapter, mock_mumbai_respx):
    """Test Execution dispatches tasks with full provenance and reaches COMPLETED."""
    adapter, _, _, _ = mock_mcp_adapter
    orchestrator = TasteOpsOrchestrator(
        mcp_adapter=adapter,
        connector_registry=create_configured_mock_registry(),
    )

    ctx = orchestrator.create_session(MUMBAI_DEMO_RAW_INTENT, hints=MUMBAI_DEMO_HINTS)
    await orchestrator.run_until_approval(ctx.session_id)
    await orchestrator.approve_session(ctx.session_id)
    ctx = await orchestrator.execute_approved_plan(ctx.session_id)

    assert ctx.current_state == WorkflowState.COMPLETED
    assert len(ctx.execution_tasks) >= 2
    for t in ctx.execution_tasks:
        assert t.status == "EXECUTED"
        assert t.provenance["plan_id"] == ctx.plan.plan_id
        assert t.provenance["source_id"]


# ---------------------------------------------------------------------------
# 9. Duplicate Execution (Idempotency)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_09_duplicate_execution(mock_mcp_adapter, mock_mumbai_respx):
    """Test Duplicate execution returns previous result and avoids duplicate dispatch."""
    adapter, _, _, _ = mock_mcp_adapter
    orchestrator = TasteOpsOrchestrator(
        mcp_adapter=adapter,
        connector_registry=create_configured_mock_registry(),
    )

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

    # Second execution (same plan and tasks)
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
        assert t1.timestamp == t2.timestamp  # Identical cached task instance


# ---------------------------------------------------------------------------
# 10. Plan Mutation After Approval
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_10_plan_mutation_after_approval(mock_mcp_adapter, mock_mumbai_respx):
    """Test Plan mutation after approval invalidates approval and blocks execution."""
    adapter, _, _, _ = mock_mcp_adapter
    orchestrator = TasteOpsOrchestrator(mcp_adapter=adapter)

    ctx = orchestrator.create_session(MUMBAI_DEMO_RAW_INTENT, hints=MUMBAI_DEMO_HINTS)
    await orchestrator.run_until_approval(ctx.session_id)
    await orchestrator.approve_session(ctx.session_id)

    # Mutate plan positioning statement
    ctx.plan.strategy.positioning_statement = (
        "MUTATED: Unapproved mass commercial nightclub"
    )

    with pytest.raises(
        UnapprovedExecutionError, match="Plan was mutated after approval"
    ):
        await orchestrator.execute_approved_plan(ctx.session_id)

    assert ctx.approval.is_valid is False
    assert "mutated after approval" in ctx.approval.invalidation_reason


# ---------------------------------------------------------------------------
# 11. Invalid Qloo Entity (Provenance Check)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_11_invalid_qloo_entity():
    """Test Invalid/unverified Qloo entity fails provenance validation and blocks execution."""
    gov = GovernanceAgent()
    task = ExecutionTask(
        task_id="task_fail_prov_01",
        action="Dispatch partner brief",
        provenance={
            "source": "qloo_insights_brand",
            "source_id": "invalid_hallucinated_id_999",
            "source_type": "brand",
            "query": "/v2/insights",
            "timestamp": "2026-10-24T00:00:00Z",
            "task_id": "task_fail_prov_01",
            "plan_id": "plan_01",
            "session_id": "sess_01",
            "approved_by": "curator",
            "approved_at": "2026-10-24T00:00:00Z",
            "execution_status": "EXECUTED",
        },
    )

    with pytest.raises(
        ProvenanceValidationError, match="references invalid/unverified Qloo ID"
    ):
        gov.validate_task_provenance(task)


# ---------------------------------------------------------------------------
# 12. Missing Evidence
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_12_missing_evidence():
    """Test Missing evidence fails governance validation."""
    gov = GovernanceAgent()
    empty_matrix = CulturalMatrix()  # No evidence, metadata, or entities
    twin = CulturalTwin()
    strat = CulturalStrategyOutput(
        positioning_statement="Pos",
        cultural_pillars=[CulturalPillar(name="P", description="D")],
        target_subcultures=[],
        affinity_themes=[],
        provenance_entity_ids=[],
    )
    arch = await ExperienceArchitect().execute(
        ExperienceDesignInput(
            cultural_twin=twin, strategy=strat, cultural_matrix=empty_matrix
        )
    )
    part = PartnershipOutput(partnerships=[], provenance_entity_ids=[])

    val = await gov.validate_plan(
        GovernanceValidationInput(
            cultural_twin=twin,
            cultural_matrix=empty_matrix,
            strategy=strat,
            experience_design=arch,
            partnerships=part,
        )
    )

    assert val.is_valid is False
    assert any(
        c.rule_name == "missing_evidence_audit" and not c.passed
        for c in val.compliance_checks
    )


# ---------------------------------------------------------------------------
# 13. Unsupported External Action
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_13_unsupported_external_action():
    """Test Unsupported external action (e.g. raw shell or bank transfer) is blocked."""
    gov = GovernanceAgent()
    twin = CulturalTwin()
    matrix = CulturalMatrix(
        artists=[
            CulturalRecommendation(
                id="ent_01",
                name="A",
                type="artist",
                affinity=0.9,
                source_query="/q",
            )
        ]
    )
    strat = CulturalStrategyOutput(
        positioning_statement="Pos",
        cultural_pillars=[CulturalPillar(name="P", description="D")],
        target_subcultures=[],
        affinity_themes=[],
        provenance_entity_ids=["ent_01"],
    )
    arch = await ExperienceArchitect().execute(
        ExperienceDesignInput(
            cultural_twin=twin, strategy=strat, cultural_matrix=matrix
        )
    )
    part = PartnershipOutput(partnerships=[], provenance_entity_ids=[])

    plan = ExecutionPlan(
        plan_id="plan_bad_act",
        actions=[
            ExecutionPlanAction(
                action_id="act_shell_exec_raw",
                title="Execute root shell command",
                description="Malicious action",
                owner="System",
            )
        ],
        estimated_cost="$0",
    )

    val = await gov.validate_plan(
        GovernanceValidationInput(
            cultural_twin=twin,
            cultural_matrix=matrix,
            strategy=strat,
            experience_design=arch,
            partnerships=part,
        ),
        execution_plan=plan,
    )

    assert val.is_valid is False
    assert any(
        c.rule_name == "unsupported_external_actions_audit" and not c.passed
        for c in val.compliance_checks
    )


# ---------------------------------------------------------------------------
# 14. Persistence Recovery
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_14_persistence_recovery(tmp_path, mock_mcp_adapter, mock_mumbai_respx):
    """Test Persistence recovery: Reconstructs state across orchestrator restarts."""
    adapter, _, _, _ = mock_mcp_adapter
    store_dir = tmp_path / "persistence_test"

    # Orchestrator Instance 1: Create and run until approval
    store_1 = FileStateStore(base_dir=store_dir)
    orch_1 = TasteOpsOrchestrator(mcp_adapter=adapter, store=store_1)

    ctx_1 = orch_1.create_session(
        MUMBAI_DEMO_RAW_INTENT,
        space_id="space_mum_boutique_01",
        hints=MUMBAI_DEMO_HINTS,
    )
    session_id = ctx_1.session_id
    await orch_1.run_until_approval(session_id)

    # Orchestrator Instance 2: Brand new instance pointing to same storage
    store_2 = FileStateStore(base_dir=store_dir)
    orch_2 = TasteOpsOrchestrator(mcp_adapter=adapter, store=store_2)

    # State restored from disk
    restored_ctx = orch_2.get_session_state(session_id)
    assert restored_ctx.session_id == session_id
    assert restored_ctx.space_id == "space_mum_boutique_01"
    assert restored_ctx.current_state == WorkflowState.AWAITING_APPROVAL
    assert restored_ctx.plan is not None

    # Audit events restored
    audit_events = orch_2.get_audit_events(session_id)
    assert len(audit_events) >= 8

    # Approve and complete on second instance
    await orch_2.approve_session(session_id, approver="Curator on Instance 2")
    final_ctx = await orch_2.execute_approved_plan(session_id)
    assert final_ctx.current_state == WorkflowState.COMPLETED
