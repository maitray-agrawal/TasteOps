"""Regression Test Suite for Storage Initialization, Idempotency and Execution Remediation.

Explicitly covers the 14 requirements:
1. Writable storage directory
2. Missing parent directory
3. Automatic storage directory creation
4. Unwritable storage directory
5. Failed exclusive lock creation
6. Reservation failure (concurrent active worker returns False)
7. Idempotency wait behavior when another worker owns the reservation
8. Idempotency timeout behavior
9. Storage failure does NOT wait unnecessarily (fails fast)
10. Execution API returns structured 503 for storage infrastructure failure
11. Execution failure does NOT produce false COMPLETED (truthful STAGED / NOT_CONFIGURED)
12. Execution failure produces truthful audit information (EXECUTING -> FAILED)
13. Existing approval SHA-256 binding remains valid
14. Existing artifact endpoints remain protected
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tasteops.agents.architect import ExperienceArchitect
from tasteops.agents.governance import GovernanceAgent, UnapprovedExecutionError
from tasteops.api.main import create_app
from tasteops.config import ServerSettings
from tasteops.models.cultural_matrix import (
    CulturalMatrix,
    CulturalRecommendation,
    CulturalTwin,
)
from tasteops.workflows.context import WorkflowContext
from tasteops.workflows.engine import WorkflowEngine
from tasteops.workflows.idempotency import (
    DurableIdempotencyStore,
    StorageUnavailableError,
)
from tasteops.workflows.persistence import FileStateStore, PersistenceStorageError
from tasteops.workflows.schemas import (
    ApprovalRecord,
    CulturalActivationPlan,
    CulturalPillar,
    CulturalStrategyOutput,
    ExecutionSummary,
    ExecutionTask,
    ExperienceDesignInput,
    GovernanceValidationInput,
    GovernanceValidationOutput,
    PartnershipOutput,
    TaskStatus,
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
            unverified_entity_ids=[],
        ),
    )


# ==============================================================================
# 1. Writable storage directory
# ==============================================================================


def test_writable_storage_directory(tmp_path: Path) -> None:
    """Store initializes, validates writability, and manages locks in a writable directory."""
    store_dir = tmp_path / "writable_workflows" / ".idempotency"
    store = DurableIdempotencyStore(base_dir=store_dir)
    store.check_storage_ready()
    assert store_dir.exists()
    assert store.reserve("test_key_writable") is True
    store.release_reservation("test_key_writable")


# ==============================================================================
# 2. Missing parent directory
# ==============================================================================


def test_missing_parent_directory(tmp_path: Path) -> None:
    """Store creates deeply nested missing parent directories without manual creation."""
    deep_path = tmp_path / "a" / "b" / "c" / "workflows" / ".idempotency"
    assert not deep_path.exists()
    store = DurableIdempotencyStore(base_dir=deep_path)
    store.check_storage_ready()
    assert deep_path.exists()


# ==============================================================================
# 3. Automatic storage directory creation
# ==============================================================================


def test_automatic_storage_directory_creation(tmp_path: Path) -> None:
    """Storage directory is automatically created upon first reservation or check."""
    target_dir = tmp_path / "auto_create" / ".idempotency"
    store = DurableIdempotencyStore(base_dir=target_dir)
    assert target_dir.exists()
    assert store.reserve("auto_key") is True
    store.release_reservation("auto_key")


# ==============================================================================
# 4. Unwritable storage directory
# ==============================================================================


def test_unwritable_storage_directory(tmp_path: Path) -> None:
    """When directory is unwritable, check_storage_ready and reserve fail closed with StorageUnavailableError."""
    store = DurableIdempotencyStore(base_dir=tmp_path / ".idempotency")
    with (
        patch("os.open", side_effect=PermissionError(13, "Permission denied")),
        pytest.raises(StorageUnavailableError) as exc_info,
    ):
        store.reserve("test_key_unwritable")

    assert "Storage unavailable" in str(exc_info.value) or "Permission denied" in str(
        exc_info.value
    )


# ==============================================================================
# 5. Failed exclusive lock creation
# ==============================================================================


def test_failed_exclusive_lock_creation(tmp_path: Path) -> None:
    """Any OS-level error during O_CREAT | O_EXCL raises StorageUnavailableError."""
    store = DurableIdempotencyStore(base_dir=tmp_path / ".idempotency")
    with (
        patch("os.open", side_effect=OSError(30, "Read-only file system")),
        pytest.raises(StorageUnavailableError),
    ):
        store.reserve("test_key_rofs")


# ==============================================================================
# 6. Reservation failure (concurrent active worker returns False)
# ==============================================================================


def test_reservation_failure(tmp_path: Path) -> None:
    """When an active non-stale lock exists by another worker, reserve returns False rather than crashing."""
    store1 = DurableIdempotencyStore(base_dir=tmp_path / ".idempotency")
    store2 = DurableIdempotencyStore(base_dir=tmp_path / ".idempotency")

    assert store1.reserve("active_key", worker_id="worker_alpha") is True
    # Second worker should be rejected cleanly
    assert store2.reserve("active_key", worker_id="worker_beta") is False


# ==============================================================================
# 7. Idempotency wait behavior when another worker owns the reservation
# ==============================================================================


@pytest.mark.asyncio
async def test_idempotency_wait_behavior_when_another_worker_owns_reservation(
    tmp_path: Path,
) -> None:
    """When another worker owns the reservation, async_reserve_or_wait polls and returns completed outcome."""
    store1 = DurableIdempotencyStore(base_dir=tmp_path / ".idempotency")
    store2 = DurableIdempotencyStore(base_dir=tmp_path / ".idempotency")

    assert store1.reserve("wait_key", worker_id="worker_1") is True

    # Simulate worker 1 producing an outcome after 100ms
    task = ExecutionTask(
        task_id="task_wait_01",
        idempotency_key="wait_key",
        action="Export audio seed",
        owner="Audio Curator",
        category="spotify_audio_seed",
        status=TaskStatus.STAGED,
    )

    async def _produce_outcome() -> None:
        await asyncio.sleep(0.1)
        store1.save_outcome("wait_key", task)

    producer = asyncio.create_task(_produce_outcome())

    acquired, outcome = await store2.async_reserve_or_wait("wait_key", timeout_sec=2.0)
    await producer

    assert acquired is False
    assert outcome is not None
    assert outcome.task_id == "task_wait_01"


# ==============================================================================
# 8. Idempotency timeout behavior
# ==============================================================================


@pytest.mark.asyncio
async def test_idempotency_timeout(tmp_path: Path) -> None:
    """When concurrent worker lock is never released or fulfilled, TimeoutError is raised."""
    store1 = DurableIdempotencyStore(base_dir=tmp_path / ".idempotency")
    store2 = DurableIdempotencyStore(base_dir=tmp_path / ".idempotency")

    assert store1.reserve("timeout_key", worker_id="worker_slow") is True

    with pytest.raises(TimeoutError) as exc_info:
        await store2.async_reserve_or_wait("timeout_key", timeout_sec=0.1)

    assert "timed out waiting for concurrent worker outcome" in str(exc_info.value)


# ==============================================================================
# 9. Storage failure does NOT wait unnecessarily (fails fast)
# ==============================================================================


@pytest.mark.asyncio
async def test_storage_failure_does_not_wait_unnecessarily(tmp_path: Path) -> None:
    """When storage fails during reservation, it fails fast without sleeping for timeout_sec."""
    store = DurableIdempotencyStore(base_dir=tmp_path / ".idempotency")

    start_time = asyncio.get_event_loop().time()
    with (
        patch("os.open", side_effect=PermissionError(13, "Permission denied")),
        pytest.raises(StorageUnavailableError),
    ):
        await store.async_reserve_or_wait("fail_fast_key", timeout_sec=5.0)

    elapsed = asyncio.get_event_loop().time() - start_time
    assert elapsed < 0.5, (
        f"Storage failure took {elapsed}s; expected immediate failure without spin-wait."
    )


# ==============================================================================
# 10. Execution API returns structured 503 for storage infrastructure failure
# ==============================================================================


@pytest.mark.asyncio
async def test_execution_api_returns_structured_503_for_storage_infrastructure_failure(
    tmp_path: Path,
) -> None:
    """POST /api/v1/sessions/{id}/execute returns HTTP 503 with structured JSON error on storage failure."""
    settings = ServerSettings(storage_dir=str(tmp_path / "workflows"))
    app = create_app(server_settings=settings)
    client = TestClient(app)

    plan = await _create_test_plan("plan_api_503")
    approval = ApprovalRecord(
        session_id="sess_api_503",
        plan_id=plan.plan_id,
        plan_version=plan.version,
        plan_hash=plan.compute_hash(),
        approver="lead_curator",
        is_valid=True,
    )
    ctx = WorkflowContext(
        session_id="sess_api_503",
        current_state=WorkflowState.APPROVED,
        plan=plan,
        approval=approval,
    )
    app.state.orchestrator.store.save_context(ctx)

    with patch.object(
        app.state.orchestrator.engine.governance.durable_store,
        "check_storage_ready",
        side_effect=StorageUnavailableError("Filesystem unwritable"),
    ):
        resp = client.post("/api/v1/sessions/sess_api_503/execute")
        assert resp.status_code == 503
        data = resp.json()
        assert data.get("error") == "storage_unavailable"
        assert "Execution storage is unavailable" in data.get("message", "")


# ==============================================================================
# 11. Execution failure does NOT produce false COMPLETED
# ==============================================================================


@pytest.mark.asyncio
async def test_execution_failure_does_not_produce_false_completed(
    tmp_path: Path,
) -> None:
    """Unconfigured connectors remain STAGED or NOT_CONFIGURED, never falsely COMPLETED."""
    gov = GovernanceAgent(
        durable_store=DurableIdempotencyStore(base_dir=tmp_path / ".idempotency")
    )
    plan = await _create_test_plan("plan_truthful_staging")
    approval = ApprovalRecord(
        session_id="sess_truthful_01",
        plan_id=plan.plan_id,
        plan_version=plan.version,
        plan_hash=plan.compute_hash(),
        approver="lead_curator",
        is_valid=True,
    )

    summary: ExecutionSummary = await gov.execute_plan(
        plan,
        is_approved=True,
        approved_by="lead_curator",
        approval=approval,
        session_id="sess_truthful_01",
    )

    assert summary.total_tasks > 0
    for task in summary.tasks:
        assert task.status in (TaskStatus.STAGED, TaskStatus.NOT_CONFIGURED)
        assert task.status != TaskStatus.COMPLETED


# ==============================================================================
# 12. Execution failure produces truthful audit information
# ==============================================================================


@pytest.mark.asyncio
async def test_execution_failure_produces_truthful_audit_information(
    tmp_path: Path,
) -> None:
    """When task execution crashes, engine transitions EXECUTING -> FAILED with audit entry."""
    store = FileStateStore(base_dir=tmp_path / "workflows")
    durable_store = DurableIdempotencyStore(
        base_dir=tmp_path / "workflows" / ".idempotency"
    )

    engine = WorkflowEngine(
        store=store,
        durable_idempotency_store=durable_store,
    )

    plan = await _create_test_plan("plan_engine_fail_01")
    approval = ApprovalRecord(
        session_id="sess_engine_fail",
        plan_id=plan.plan_id,
        plan_version=plan.version,
        plan_hash=plan.compute_hash(),
        approver="lead_curator",
        is_valid=True,
    )

    ctx = WorkflowContext(
        session_id="sess_engine_fail",
        current_state=WorkflowState.APPROVED,
        plan=plan,
        approval=approval,
    )
    store.save_context(ctx)

    with (
        patch.object(
            engine.governance,
            "execute_plan",
            side_effect=RuntimeError("Simulated provider crash"),
        ),
        pytest.raises(RuntimeError),
    ):
        await engine.execute_plan(ctx)

    assert ctx.current_state == WorkflowState.FAILED
    assert "Simulated provider crash" in (ctx.error_message or "")

    events = store.get_audit_events("sess_engine_fail")
    states = [(e.from_state, e.to_state) for e in events]
    assert (WorkflowState.APPROVED, WorkflowState.EXECUTING) in states
    assert (WorkflowState.EXECUTING, WorkflowState.FAILED) in states

    failed_event = next(e for e in events if e.to_state == WorkflowState.FAILED)
    assert failed_event.metadata.get("error_type") == "RuntimeError"


# ==============================================================================
# 13. Existing approval SHA-256 binding remains valid
# ==============================================================================


@pytest.mark.asyncio
async def test_existing_approval_sha256_binding_remains_valid(tmp_path: Path) -> None:
    """Plan mutation or unapproved execution is strictly rejected by governance gate."""
    gov = GovernanceAgent(
        durable_store=DurableIdempotencyStore(base_dir=tmp_path / ".idempotency")
    )
    plan = await _create_test_plan("plan_tamper_01")

    # Execution without approval is blocked
    with pytest.raises(UnapprovedExecutionError):
        await gov.execute_plan(plan, is_approved=False)

    # Execution with tampered hash is blocked
    tampered_approval = ApprovalRecord(
        session_id="sess_tamper",
        plan_id=plan.plan_id,
        plan_version=plan.version,
        plan_hash="corrupted_hash_00000000000000000000000000000000",
        approver="malicious_actor",
        is_valid=True,
    )
    with pytest.raises(UnapprovedExecutionError):
        await gov.execute_plan(
            plan,
            is_approved=True,
            approved_by="malicious_actor",
            approval=tampered_approval,
            session_id="sess_tamper",
        )


# ==============================================================================
# 14. Existing artifact endpoints remain protected
# ==============================================================================


def test_existing_artifact_endpoints_remain_protected(tmp_path: Path) -> None:
    """Artifact endpoints return 404 for unapproved/non-existent sessions."""
    settings = ServerSettings(storage_dir=str(tmp_path / "workflows"))
    app = create_app(server_settings=settings)
    client = TestClient(app)

    resp = client.get(
        "/api/v1/sessions/non_existent_session_id/artifacts/procurement.csv"
    )
    assert resp.status_code == 404


# ==============================================================================
# 15. Finding 1: Idempotency lock race (stat races with lock deletion)
# ==============================================================================


def test_idempotency_lock_race_when_stat_races_with_deletion(tmp_path: Path) -> None:
    """When lock exists but stat() raises FileNotFoundError due to concurrent deletion,

    reserve() does NOT raise StorageUnavailableError and returns False.
    """
    store = DurableIdempotencyStore(base_dir=tmp_path / ".idempotency")
    key = "race_key"
    lock_path = store._get_lock_path(store._sanitize_key(key))

    # Pre-create the lock file so os.open encounters FileExistsError
    lock_path.write_text("dummy", encoding="utf-8")

    # Patch lock_path.stat to simulate race where file was unlinked before stat()
    with patch.object(Path, "stat", side_effect=FileNotFoundError(2, "No such file")):
        acquired = store.reserve(key, worker_id="worker_racer")

    assert acquired is False  # Does not raise StorageUnavailableError!


@pytest.mark.asyncio
async def test_async_reserve_or_wait_handles_stat_race_and_returns_outcome(
    tmp_path: Path,
) -> None:
    """When stat() raises FileNotFoundError during reservation race,

    async_reserve_or_wait continues to wait for and return the completed outcome.
    """
    store = DurableIdempotencyStore(base_dir=tmp_path / ".idempotency")
    key = "race_outcome_key"
    lock_path = store._get_lock_path(store._sanitize_key(key))
    lock_path.write_text("dummy", encoding="utf-8")

    task = ExecutionTask(
        task_id="task_race_01",
        idempotency_key=key,
        action="Export audio seed",
        owner="Audio Curator",
        category="spotify_audio_seed",
        status=TaskStatus.STAGED,
    )

    orig_stat = Path.stat
    first_call = True

    def stat_with_transient_not_found(
        self: Path, *args: object, **kwargs: object
    ) -> os.stat_result:
        nonlocal first_call
        if self == lock_path and first_call:
            first_call = False
            # Simulate worker completing and saving outcome
            store.save_outcome(key, task)
            raise FileNotFoundError(2, "No such file")
        return orig_stat(self, *args, **kwargs)

    with patch.object(Path, "stat", stat_with_transient_not_found):
        acquired, outcome = await store.async_reserve_or_wait(key, timeout_sec=2.0)

    assert acquired is False
    assert outcome is not None
    assert outcome.task_id == "task_race_01"


# ==============================================================================
# 16. Finding 2: FileStateStore fails closed on state and audit write failures
# ==============================================================================


def test_filestatestore_state_write_failure_raises_storage_unavailable(
    tmp_path: Path,
) -> None:
    """FileStateStore.save_context fails closed and raises PersistenceStorageError on write failure."""
    store = FileStateStore(base_dir=tmp_path / "workflows")
    ctx = WorkflowContext(session_id="sess_write_fail", user_input="test space")

    with (
        patch("os.replace", side_effect=PermissionError(13, "Permission denied")),
        pytest.raises(PersistenceStorageError),
    ):
        store.save_context(ctx)


def test_filestatestore_audit_write_failure_raises_storage_unavailable(
    tmp_path: Path,
) -> None:
    """FileStateStore.save_transition fails closed and raises PersistenceStorageError on audit log write failure."""
    store = FileStateStore(base_dir=tmp_path / "workflows")
    ctx = WorkflowContext(session_id="sess_audit_fail", user_input="test space")

    from tasteops.workflows.persistence import AuditEvent

    event = AuditEvent(
        session_id=ctx.session_id,
        from_state=WorkflowState.CREATED,
        to_state=WorkflowState.INTENT_PARSED,
        reason="Test transition",
    )

    with (
        patch("builtins.open", side_effect=PermissionError(13, "Permission denied")),
        pytest.raises(PersistenceStorageError),
    ):
        store.save_transition(event, ctx)


@pytest.mark.asyncio
async def test_engine_execution_state_persistence_failure_fails_closed(
    tmp_path: Path,
) -> None:
    """When persisting COMPLETED state fails, engine transitions to FAILED and raises StorageUnavailableError."""
    store = FileStateStore(base_dir=tmp_path / "workflows")
    durable_store = DurableIdempotencyStore(
        base_dir=tmp_path / "workflows" / ".idempotency"
    )
    engine = WorkflowEngine(store=store, durable_idempotency_store=durable_store)

    plan = await _create_test_plan("plan_persist_fail")
    approval = ApprovalRecord(
        session_id="sess_persist_fail",
        plan_id=plan.plan_id,
        plan_version=plan.version,
        plan_hash=plan.compute_hash(),
        approver="lead_curator",
        is_valid=True,
    )
    ctx = WorkflowContext(
        session_id="sess_persist_fail",
        current_state=WorkflowState.APPROVED,
        plan=plan,
        approval=approval,
    )
    store.save_context(ctx)

    orig_save_transition = store.save_transition

    def failing_save_transition(event: object, context: WorkflowContext) -> None:
        if getattr(event, "to_state", None) == WorkflowState.COMPLETED:
            raise PersistenceStorageError("Disk full during COMPLETED persistence")
        orig_save_transition(event, context)  # type: ignore[arg-type]

    with (
        patch.object(store, "save_transition", side_effect=failing_save_transition),
        pytest.raises(StorageUnavailableError),
    ):
        await engine.execute_plan(ctx)

    # Must transition to FAILED, not falsely COMPLETED
    assert ctx.current_state == WorkflowState.FAILED
    assert ctx.current_state != WorkflowState.COMPLETED


@pytest.mark.asyncio
async def test_api_returns_structured_503_for_persistence_storage_failure(
    tmp_path: Path,
) -> None:
    """API endpoints return structured 503 when durable persistence fails."""
    settings = ServerSettings(storage_dir=str(tmp_path / "workflows"))
    app = create_app(server_settings=settings)
    client = TestClient(app)

    plan = await _create_test_plan("plan_persist_503")
    approval = ApprovalRecord(
        session_id="sess_persist_503",
        plan_id=plan.plan_id,
        plan_version=plan.version,
        plan_hash=plan.compute_hash(),
        approver="lead_curator",
        is_valid=True,
    )
    ctx = WorkflowContext(
        session_id="sess_persist_503",
        current_state=WorkflowState.AWAITING_APPROVAL,
        plan=plan,
        approval=approval,
    )
    app.state.orchestrator.store.save_context(ctx)

    with patch.object(
        app.state.orchestrator.store,
        "save_transition",
        side_effect=PersistenceStorageError("Read-only filesystem during approval"),
    ):
        resp = client.post(
            "/api/v1/sessions/sess_persist_503/approve",
            json={"approver": "lead_curator"},
        )
        assert resp.status_code == 503
        data = resp.json()
        assert data.get("error") == "storage_unavailable"
        assert "Storage unavailable" in data.get("message", "")


# ==============================================================================
# 17. Finding 3: HTTP 504 API contract for idempotency timeout
# ==============================================================================


@pytest.mark.asyncio
async def test_execution_api_returns_structured_504_for_idempotency_timeout(
    tmp_path: Path,
) -> None:
    """POST /api/v1/sessions/{id}/execute returns HTTP 504 when concurrent worker outcome times out."""
    settings = ServerSettings(storage_dir=str(tmp_path / "workflows"))
    app = create_app(server_settings=settings)
    client = TestClient(app)

    plan = await _create_test_plan("plan_api_504")
    approval = ApprovalRecord(
        session_id="sess_api_504",
        plan_id=plan.plan_id,
        plan_version=plan.version,
        plan_hash=plan.compute_hash(),
        approver="lead_curator",
        is_valid=True,
    )
    ctx = WorkflowContext(
        session_id="sess_api_504",
        current_state=WorkflowState.APPROVED,
        plan=plan,
        approval=approval,
    )
    app.state.orchestrator.store.save_context(ctx)

    with patch.object(
        app.state.orchestrator.engine.governance.durable_store,
        "async_reserve_or_wait",
        side_effect=TimeoutError("Timed out waiting for concurrent worker outcome"),
    ):
        resp = client.post("/api/v1/sessions/sess_api_504/execute")
        assert resp.status_code == 504
        data = resp.json()
        assert data.get("error") == "idempotency_timeout"
        assert (
            "timed out waiting for concurrent worker" in data.get("message", "").lower()
        )

    # Verify session transitioned EXECUTING -> FAILED and is NOT COMPLETED
    updated_ctx = app.state.orchestrator.get_session_state("sess_api_504")
    assert updated_ctx.current_state == WorkflowState.FAILED
    assert updated_ctx.current_state != WorkflowState.COMPLETED
    assert "Timed out" in (updated_ctx.error_message or "")

    # Verify audit events
    audit_events = app.state.orchestrator.get_audit_events("sess_api_504")
    transitions = [(e.from_state, e.to_state) for e in audit_events]
    assert (WorkflowState.APPROVED, WorkflowState.EXECUTING) in transitions
    assert (WorkflowState.EXECUTING, WorkflowState.FAILED) in transitions


# ==============================================================================
# 18. Additional Hardening: Quoted storage dir & QLOO_API_KEY quote normalization
# ==============================================================================


def test_storage_dir_resolves_quotes_and_whitespace(tmp_path: Path) -> None:
    """ServerSettings.effective_storage_path strips quotes and whitespace and resolves correctly."""
    target_sub = tmp_path / "quoted_workflows"
    quoted = f" '\"{target_sub}\"' "
    settings = ServerSettings(storage_dir=quoted)
    resolved = settings.effective_storage_path
    assert resolved == target_sub.resolve()
    assert "'" not in str(resolved)
    assert '"' not in str(resolved)

    relative_quoted = " 'storage/workflows' "
    settings_rel = ServerSettings(storage_dir=relative_quoted)
    resolved_rel = settings_rel.effective_storage_path
    assert resolved_rel.is_absolute()
    assert "'" not in str(resolved_rel)
    assert str(resolved_rel).endswith(os.path.join("storage", "workflows"))


def test_qloo_api_key_strips_quotes_in_ready_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /ready recognizes QLOO_API_KEY even if enclosed in surrounding quotes."""
    settings = ServerSettings(storage_dir=str(tmp_path / "workflows"))
    app = create_app(server_settings=settings)
    client = TestClient(app)

    monkeypatch.setenv("QLOO_API_KEY", " '\"test_quoted_api_key\"' ")
    resp = client.get("/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"
    assert data["qloo_configured"] is True
    assert data["storage_ready"] is True
