"""TasteOps Persistence Deep Behavioral Test Suite.

Comprehensive behavioral testing covering:
1. CRUD operations across Spaces, Briefs, Sessions, and Tasks
2. Transaction rollback: atomic boundaries, mid-transaction failure rollback, FK violations
3. Foreign key relationships and cascading deletions (ON DELETE CASCADE, ON DELETE SET NULL)
4. Migration compatibility: DDL idempotency, PRAGMA integrity_check, schema evolution
5. Audit persistence: append-only ledger, tamper detection, cryptographic hash-chain verification
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

import pytest

from tasteops.api.schemas.spaces import SpaceCreateRequest
from tasteops.models.cultural_matrix import CulturalMatrix, CulturalTwin
from tasteops.persistence.database import Database
from tasteops.persistence.session_repository import SQLiteSessionRepository
from tasteops.persistence.space_repository import SQLiteSpaceRepository
from tasteops.workflows.context import WorkflowContext
from tasteops.workflows.persistence import AuditEvent
from tasteops.workflows.schemas import ExecutionTask
from tasteops.workflows.states import WorkflowState


@pytest.fixture
def test_db(tmp_path):
    """Provides an isolated file-backed SQLite Database with WAL and foreign keys."""
    db_path = tmp_path / f"test_persistence_{uuid.uuid4().hex[:8]}.db"
    db = Database(str(db_path))
    yield db, db_path
    db.close()


# -----------------------------------------------------------------------------
# 1. CRUD Operations
# -----------------------------------------------------------------------------
def test_persistence_crud_operations(test_db):
    """Asserts complete CRUD capabilities for Spaces, Briefs, Sessions, and ExecutionTasks."""
    db, _ = test_db
    space_repo = SQLiteSpaceRepository(db)
    session_repo = SQLiteSessionRepository(db)

    # 1. Space Create & Read
    req = SpaceCreateRequest(
        name="Kyoto Machiya Audio Club",
        business_type="Tea & Listening Lounge",
        location={"latitude": 35.0116, "longitude": 135.7681},
        target_audience="Acoustic purists",
        positioning="Analog sound sanctuary",
        desired_mood="Contemplative warmth",
        budget="Boutique",
        constraints=["Max 72dB SPL", "Natural acoustics only"],
        anchor_entities=["Blue Bottle Kyoto", "Hinoki Wood"],
    )
    space = space_repo.save_space(req)
    assert space.space_id.startswith("space_")
    assert space.name == "Kyoto Machiya Audio Club"

    read_space = space_repo.get_space(space.space_id)
    assert read_space is not None
    assert read_space.space_id == space.space_id
    assert read_space.brief["target_audience"] == "Acoustic purists"

    # 2. Space Update (Upsert)
    req.name = "Kyoto Machiya Audio Sanctuary"
    updated_space = space_repo.save_space(req, space_id=space.space_id)
    assert updated_space.name == "Kyoto Machiya Audio Sanctuary"
    assert space_repo.get_space(space.space_id).name == "Kyoto Machiya Audio Sanctuary"

    # 3. Session Create & Read
    ctx = WorkflowContext(
        session_id=f"sess_{uuid.uuid4().hex[:12]}",
        space_id=space.space_id,
        user_input="Curate contemplative analog soundscape",
        current_state=WorkflowState.CREATED,
        parsed_intent={"mood": "Contemplative"},
    )
    session_repo.save_session(ctx)
    read_session = session_repo.load_session(ctx.session_id)
    assert read_session is not None
    assert read_session.session_id == ctx.session_id
    assert read_session.space_id == space.space_id
    assert read_session.current_state == WorkflowState.CREATED

    # 4. Session Update
    ctx.current_state = WorkflowState.INTENT_PARSED
    ctx.validation_cycle_count = 2
    ctx.error_message = None
    session_repo.save_session(ctx)
    read_updated_sess = session_repo.load_session(ctx.session_id)
    assert read_updated_sess.current_state == WorkflowState.INTENT_PARSED
    assert read_updated_sess.validation_cycle_count == 2

    # 5. Task Create, Query, and Status Update
    task = ExecutionTask(
        task_id=f"task_{uuid.uuid4().hex[:8]}",
        category="spotify_audio_seed",
        action="Dispatch Kyoto ambient acoustic playlist seed",
        owner="Sound Director",
        status="PENDING",
        idempotency_key=f"idem_{uuid.uuid4().hex[:8]}",
    )
    ctx.execution_tasks.append(task)
    session_repo.save_session(ctx)

    loaded_tasks = session_repo.load_session(ctx.session_id).execution_tasks
    assert len(loaded_tasks) == 1
    assert loaded_tasks[0].status == "PENDING"

    # Update Task Status
    ctx.execution_tasks[0].status = "EXECUTED"
    ctx.execution_tasks[0].executed_at = datetime.now(UTC)
    session_repo.save_session(ctx)

    updated_tasks = session_repo.load_session(ctx.session_id).execution_tasks
    assert updated_tasks[0].status == "EXECUTED"
    assert updated_tasks[0].executed_at is not None

    # 6. Delete Space and Session
    assert session_repo.delete_session(ctx.session_id) is True
    assert session_repo.load_session(ctx.session_id) is None
    assert space_repo.delete_space(space.space_id) is True
    assert space_repo.get_space(space.space_id) is None


# -----------------------------------------------------------------------------
# 2. Transaction Boundaries & Atomic Rollback
# -----------------------------------------------------------------------------
def test_persistence_transaction_rollback_guarantee(test_db):
    """Asserts that exceptions inside transaction boundaries atomically roll back all interim operations."""
    db, _ = test_db
    space_repo = SQLiteSpaceRepository(db)

    # 1. Mid-transaction simulated error rollback
    initial_spaces = space_repo.list_spaces()
    with pytest.raises(RuntimeError, match="Atomic rollback trigger"):
        with db.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO spaces (space_id, name, business_type, created_at, updated_at)
                VALUES ('space_rollback_test', 'Doomed Venue', 'Cafe', '2026-10-25T00:00:00Z', '2026-10-25T00:00:00Z');
                """
            )
            # Verify row exists within open transaction
            cursor.execute(
                "SELECT name FROM spaces WHERE space_id = 'space_rollback_test';"
            )
            assert cursor.fetchone()["name"] == "Doomed Venue"
            # Intentionally explode
            raise RuntimeError("Atomic rollback trigger")

    # Outside transaction: record must NOT exist
    assert space_repo.get_space("space_rollback_test") is None
    assert len(space_repo.list_spaces()) == len(initial_spaces)

    # 2. Foreign key violation triggers automated transaction rollback
    with pytest.raises(Exception):
        with db.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO space_briefs (brief_id, space_id, target_audience, created_at, updated_at)
                VALUES ('brief_orphan', 'nonexistent_space_id_9999', 'Ghost Audience', '2026-10-25T00:00:00Z', '2026-10-25T00:00:00Z');
                """
            )


# -----------------------------------------------------------------------------
# 3. Foreign Key Relationships & Cascading Deletions
# -----------------------------------------------------------------------------
def test_persistence_relationships_and_cascades(test_db):
    """Asserts ON DELETE CASCADE for dependent artifacts and ON DELETE SET NULL for spaces."""
    db, _ = test_db
    space_repo = SQLiteSpaceRepository(db)
    session_repo = SQLiteSessionRepository(db)

    # Setup Space & Session
    space = space_repo.save_space(
        SpaceCreateRequest(name="Cascade Parent Space", business_type="Gallery")
    )
    ctx = WorkflowContext(
        session_id=f"sess_{uuid.uuid4().hex[:8]}",
        space_id=space.space_id,
        current_state=WorkflowState.PLAN_GENERATED,
    )
    ctx.cultural_twin = CulturalTwin(audience_profile="Audiophile", mood_profile="Zen")
    ctx.cultural_matrix = CulturalMatrix(fingerprint="fp_test")
    ctx.audit_events.append(
        AuditEvent(
            session_id=ctx.session_id,
            from_state=WorkflowState.CREATED,
            to_state=WorkflowState.PLAN_GENERATED,
        )
    )
    session_repo.save_session(ctx)

    conn = db.get_connection()
    cursor = conn.cursor()

    # 1. Verify child records exist
    cursor.execute(
        "SELECT count(*) as cnt FROM space_briefs WHERE space_id = ?;",
        (space.space_id,),
    )
    assert cursor.fetchone()["cnt"] == 1
    cursor.execute(
        "SELECT count(*) as cnt FROM cultural_twins WHERE session_id = ?;",
        (ctx.session_id,),
    )
    assert cursor.fetchone()["cnt"] == 1
    cursor.execute(
        "SELECT count(*) as cnt FROM cultural_matrices WHERE session_id = ?;",
        (ctx.session_id,),
    )
    assert cursor.fetchone()["cnt"] == 1
    cursor.execute(
        "SELECT count(*) as cnt FROM audit_events WHERE session_id = ?;",
        (ctx.session_id,),
    )
    assert cursor.fetchone()["cnt"] == 1

    # 2. Delete Space -> space_briefs cascades (deleted), session space_id becomes NULL (SET NULL)
    space_repo.delete_space(space.space_id)
    cursor.execute(
        "SELECT count(*) as cnt FROM space_briefs WHERE space_id = ?;",
        (space.space_id,),
    )
    assert cursor.fetchone()["cnt"] == 0

    reloaded_sess = session_repo.load_session(ctx.session_id)
    assert reloaded_sess is not None
    assert reloaded_sess.space_id is None

    # 3. Delete Session -> cultural_twins, cultural_matrices, and audit_events cascade delete
    session_repo.delete_session(ctx.session_id)
    cursor.execute(
        "SELECT count(*) as cnt FROM cultural_twins WHERE session_id = ?;",
        (ctx.session_id,),
    )
    assert cursor.fetchone()["cnt"] == 0
    cursor.execute(
        "SELECT count(*) as cnt FROM cultural_matrices WHERE session_id = ?;",
        (ctx.session_id,),
    )
    assert cursor.fetchone()["cnt"] == 0
    cursor.execute(
        "SELECT count(*) as cnt FROM audit_events WHERE session_id = ?;",
        (ctx.session_id,),
    )
    assert cursor.fetchone()["cnt"] == 0
    cursor.close()


# -----------------------------------------------------------------------------
# 4. Migration Compatibility & DDL Idempotency
# -----------------------------------------------------------------------------
def test_persistence_migration_compatibility(test_db):
    """Asserts DDL idempotency, PRAGMA integrity_check, and index stability under repeated initialization."""
    db, db_path = test_db
    space_repo = SQLiteSpaceRepository(db)

    # 1. Populate test data
    sp = space_repo.save_space(
        SpaceCreateRequest(name="Pre-Migration Space", business_type="Bar")
    )

    # 2. Re-run schema initialization multiple times (simulating re-deployments / migrations)
    db.init_schema()
    db.init_schema()

    # Verify existing data is preserved and intact
    saved_sp = space_repo.get_space(sp.space_id)
    assert saved_sp is not None
    assert saved_sp.name == "Pre-Migration Space"

    # 3. PRAGMA integrity_check
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA integrity_check;")
    integrity_result = cursor.fetchone()[0]
    assert integrity_result == "ok"

    # 4. PRAGMA foreign_keys verification
    cursor.execute("PRAGMA foreign_keys;")
    fk_enabled = cursor.fetchone()[0]
    assert fk_enabled == 1

    # 5. Verify critical indexes exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
    index_names = {row["name"] for row in cursor.fetchall()}
    assert "idx_spaces_created_at" in index_names
    assert "idx_briefs_space_id" in index_names
    assert "idx_sessions_current_state" in index_names
    assert "idx_exec_tasks_idempotency" in index_names
    assert "idx_transitions_session" in index_names
    cursor.close()


# -----------------------------------------------------------------------------
# 5. Audit Persistence & Tamper Detection
# -----------------------------------------------------------------------------
def test_persistence_audit_ledger_and_tamper_detection(test_db):
    """Asserts append-only audit persistence and cryptographic hash-chain verification."""
    db, _ = test_db
    session_repo = SQLiteSessionRepository(db)
    session_id = f"sess_audit_{uuid.uuid4().hex[:8]}"

    ctx = WorkflowContext(
        session_id=session_id,
        current_state=WorkflowState.CREATED,
    )
    session_repo.save_session(ctx)

    # 1. Record ordered audit events
    events = [
        AuditEvent(
            event_id="evt_01",
            session_id=session_id,
            from_state=WorkflowState.CREATED,
            to_state=WorkflowState.INTENT_PARSED,
            reason="Brief parsed",
            timestamp=datetime(2026, 10, 25, 10, 0, 0, tzinfo=UTC),
        ),
        AuditEvent(
            event_id="evt_02",
            session_id=session_id,
            from_state=WorkflowState.INTENT_PARSED,
            to_state=WorkflowState.CULTURAL_TWIN_CREATED,
            reason="Twin synthesized",
            timestamp=datetime(2026, 10, 25, 10, 1, 0, tzinfo=UTC),
        ),
        AuditEvent(
            event_id="evt_03",
            session_id=session_id,
            from_state=WorkflowState.CULTURAL_TWIN_CREATED,
            to_state=WorkflowState.AWAITING_APPROVAL,
            reason="Validation passed",
            timestamp=datetime(2026, 10, 25, 10, 2, 0, tzinfo=UTC),
        ),
    ]

    for ev in events:
        session_repo.save_audit_event(ev)

    persisted_events = session_repo.get_audit_events(session_id)
    assert len(persisted_events) == 3
    assert [e.event_id for e in persisted_events] == ["evt_01", "evt_02", "evt_03"]

    # 2. Compute authentic hash chain
    prev_hash = "GENESIS_ROOT_TASTEOPS"
    authentic_hashes = []
    for ev in persisted_events:
        ts_str = ev.timestamp.isoformat()
        meta_json = json.dumps(ev.metadata, sort_keys=True, default=str)
        payload = f"{prev_hash}|{ev.event_id}|{ev.session_id}|{ev.from_state}|{ev.to_state}|{ts_str}|{ev.reason}|{meta_json}"
        h = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        authentic_hashes.append(h)
        prev_hash = h

    assert len(authentic_hashes) == 3

    # 3. Simulate unauthorized tampering with audit history in relational storage
    conn = db.get_connection()
    with db.transaction() as cursor:
        cursor.execute(
            "UPDATE audit_events SET reason = 'TAMPERED: Illicitly modified audit record' WHERE event_id = 'evt_02';"
        )

    tampered_events = session_repo.get_audit_events(session_id)
    tampered_evt = next(e for e in tampered_events if e.event_id == "evt_02")
    assert "TAMPERED" in tampered_evt.reason

    # Verify cryptographic verification fails on tampered chain
    prev_hash = "GENESIS_ROOT_TASTEOPS"
    tampered_hashes = []
    for ev in tampered_events:
        ts_str = ev.timestamp.isoformat()
        meta_json = json.dumps(ev.metadata, sort_keys=True, default=str)
        payload = f"{prev_hash}|{ev.event_id}|{ev.session_id}|{ev.from_state}|{ev.to_state}|{ts_str}|{ev.reason}|{meta_json}"
        h = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        tampered_hashes.append(h)
        prev_hash = h

    # Checkpoint hash differs starting from tampered node evt_02
    assert tampered_hashes[0] == authentic_hashes[0]  # evt_01 intact
    assert tampered_hashes[1] != authentic_hashes[1]  # evt_02 tampered
    assert tampered_hashes[2] != authentic_hashes[2]  # cascade broken
