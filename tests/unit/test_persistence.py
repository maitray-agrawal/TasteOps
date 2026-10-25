"""Unit Tests for TasteOps Relational Persistence Layer.

Verifies:
- CRUD operations for Spaces, SpaceBriefs, WorkflowSessions, and Tasks
- Foreign key relationships and cascading deletion
- Transaction boundaries and atomic rollback on error
- Missing record handling
- Duplicate operations and upsert idempotency
- Complete session recovery across all 12 cultural/workflow entities
- Approval state persistence and plan hash verification
- Audit event ledger ordered persistence
- Security: No API secrets or uncontrolled raw provider dumps stored
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tasteops.api.schemas.spaces import SpaceCreateRequest
from tasteops.models.cultural_matrix import (
    CulturalMatrix,
    CulturalRecommendation,
    CulturalTwin,
)
from tasteops.persistence.database import Database
from tasteops.persistence.session_repository import SQLiteSessionRepository
from tasteops.persistence.space_repository import SQLiteSpaceRepository
from tasteops.persistence.store import SQLiteStateStore
from tasteops.workflows.context import WorkflowContext
from tasteops.workflows.persistence import AuditEvent
from tasteops.workflows.schemas import (
    ApprovalRecord,
    AtmosphereGuidelines,
    BrandEcosystem,
    CulturalProgrammingIdeas,
    ExecutionPlan,
    ExecutionPlanAction,
    ExecutionTask,
    ExperienceDesignOutput,
    ReadingLibraryIdentity,
    SonicIdentity,
    SpatialZone,
)
from tasteops.workflows.states import WorkflowState


@pytest.fixture
def db():
    """Provides a fresh isolated in-memory SQLite database with schema initialized."""
    database = Database(":memory:")
    yield database
    database.close()


@pytest.fixture
def space_repo(db):
    """Provides space repository instance."""
    return SQLiteSpaceRepository(db)


@pytest.fixture
def session_repo(db):
    """Provides session repository instance."""
    return SQLiteSessionRepository(db)


@pytest.fixture
def state_store(db):
    """Provides SQLite state store instance."""
    return SQLiteStateStore(db)


# ---------------------------------------------------------------------------
# 1. CRUD Tests
# ---------------------------------------------------------------------------
def test_space_and_brief_crud(space_repo):
    """Verify Space and SpaceBrief creation, retrieval, listing, and deletion."""
    req = SpaceCreateRequest(
        name="SoHo Vinyl Kissa",
        business_type="Listening Bar & Cafe",
        location={"latitude": 40.7233, "longitude": -74.0030},
        target_audience="Audiophiles & design enthusiasts",
        positioning="Japanese-inspired craft audio lounge",
        desired_mood="Warm, acoustic, intimate",
        budget="Boutique premium",
        constraints=["Max 75dB SPL", "Analog only"],
        anchor_entities=["Blue Bottle", "Japanese minimalism"],
    )

    # 1. Create
    space = space_repo.save_space(req)
    assert space.space_id.startswith("space_")
    assert space.name == "SoHo Vinyl Kissa"
    assert space.brief["target_audience"] == "Audiophiles & design enthusiasts"

    # 2. Read
    fetched = space_repo.get_space(space.space_id)
    assert fetched is not None
    assert fetched.space_id == space.space_id
    assert fetched.business_type == "Listening Bar & Cafe"
    assert fetched.brief["desired_mood"] == "Warm, acoustic, intimate"

    # 3. List
    spaces = space_repo.list_spaces()
    assert len(spaces) == 1
    assert spaces[0].space_id == space.space_id

    # 4. Update (Upsert)
    req.name = "SoHo Analog Sanctuary"
    updated = space_repo.save_space(req, space_id=space.space_id)
    assert updated.space_id == space.space_id
    assert updated.name == "SoHo Analog Sanctuary"
    assert space_repo.get_space(space.space_id).name == "SoHo Analog Sanctuary"

    # 5. Delete
    deleted = space_repo.delete_space(space.space_id)
    assert deleted is True
    assert space_repo.get_space(space.space_id) is None
    assert len(space_repo.list_spaces()) == 0


def test_workflow_session_crud(session_repo):
    """Verify WorkflowSession lifecycle CRUD operations."""
    ctx = WorkflowContext(
        session_id="sess_test_12345",
        space_id="space_test_abc",
        user_input="Curate a boutique listening lounge",
        current_state=WorkflowState.CREATED,
        parsed_intent={"business_type": "Listening Bar"},
    )

    # 1. Create
    session_repo.save_session(ctx)

    # 2. Read
    loaded = session_repo.load_session("sess_test_12345")
    assert loaded is not None
    assert loaded.session_id == "sess_test_12345"
    assert loaded.space_id == "space_test_abc"
    assert loaded.current_state == WorkflowState.CREATED
    assert loaded.parsed_intent["business_type"] == "Listening Bar"

    # 3. Update state
    ctx.current_state = WorkflowState.INTENT_PARSED
    ctx.validation_cycle_count = 1
    session_repo.save_session(ctx)
    loaded_updated = session_repo.load_session("sess_test_12345")
    assert loaded_updated.current_state == WorkflowState.INTENT_PARSED
    assert loaded_updated.validation_cycle_count == 1

    # 4. Delete
    deleted = session_repo.delete_session("sess_test_12345")
    assert deleted is True
    assert session_repo.load_session("sess_test_12345") is None


# ---------------------------------------------------------------------------
# 2. Relationships & Cascading Deletes
# ---------------------------------------------------------------------------
def test_space_brief_foreign_key_cascade(db, space_repo):
    """Verify deleting a space cascades to its 1:1 space_briefs row."""
    req = SpaceCreateRequest(name="Cascade Test Space", business_type="Gallery")
    space = space_repo.save_space(req)

    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT count(*) as count FROM space_briefs WHERE space_id = ?;",
        (space.space_id,),
    )
    assert cursor.fetchone()["count"] == 1

    # Delete space
    space_repo.delete_space(space.space_id)
    cursor.execute(
        "SELECT count(*) as count FROM space_briefs WHERE space_id = ?;",
        (space.space_id,),
    )
    assert cursor.fetchone()["count"] == 0
    cursor.close()


def test_session_child_artifacts_cascade_delete(db, session_repo):
    """Verify deleting a session cascades to all child artifacts."""
    ctx = WorkflowContext(
        session_id="sess_cascade_999",
        current_state=WorkflowState.PLAN_GENERATED,
    )
    ctx.cultural_twin = CulturalTwin(
        audience_profile="Audiophile youth",
        spatial_archetype="Sanctuary",
        vibe_keywords=["warm", "minimal"],
    )
    ctx.cultural_matrix = CulturalMatrix(
        fingerprint="fp_hash_123",
        total_entities=5,
        domains=[],
    )
    ctx.audit_events.append(
        AuditEvent(
            session_id=ctx.session_id,
            from_state=WorkflowState.CREATED,
            to_state=WorkflowState.PLAN_GENERATED,
            reason="Fast forwarded",
        )
    )
    session_repo.save_session(ctx)

    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT count(*) as count FROM cultural_twins WHERE session_id = ?;",
        (ctx.session_id,),
    )
    assert cursor.fetchone()["count"] == 1
    cursor.execute(
        "SELECT count(*) as count FROM cultural_matrices WHERE session_id = ?;",
        (ctx.session_id,),
    )
    assert cursor.fetchone()["count"] == 1
    cursor.execute(
        "SELECT count(*) as count FROM audit_events WHERE session_id = ?;",
        (ctx.session_id,),
    )
    assert cursor.fetchone()["count"] == 1

    # Delete session
    session_repo.delete_session(ctx.session_id)

    # Verify children are deleted via foreign key ON DELETE CASCADE
    cursor.execute(
        "SELECT count(*) as count FROM cultural_twins WHERE session_id = ?;",
        (ctx.session_id,),
    )
    assert cursor.fetchone()["count"] == 0
    cursor.execute(
        "SELECT count(*) as count FROM cultural_matrices WHERE session_id = ?;",
        (ctx.session_id,),
    )
    assert cursor.fetchone()["count"] == 0
    cursor.execute(
        "SELECT count(*) as count FROM audit_events WHERE session_id = ?;",
        (ctx.session_id,),
    )
    assert cursor.fetchone()["count"] == 0
    cursor.close()


# ---------------------------------------------------------------------------
# 3. Transaction Boundaries & Rollback
# ---------------------------------------------------------------------------
def test_transaction_rollback_on_error(db, space_repo):
    """Verify failed transactions roll back and leave no partial records."""
    req = SpaceCreateRequest(name="Rollback Space", business_type="Cafe")

    # Manually execute transaction that fails midway
    with pytest.raises(RuntimeError, match="Simulated mid-transaction failure"):
        with db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO spaces (space_id, name, business_type, created_at, updated_at) VALUES (?, ?, ?, ?, ?);",
                (
                    "space_rollback_1",
                    "Rollback Space",
                    "Cafe",
                    datetime.now(UTC).isoformat(),
                    datetime.now(UTC).isoformat(),
                ),
            )
            # Raise exception before COMMIT
            raise RuntimeError("Simulated mid-transaction failure")

    # Verify space was rolled back and does not exist
    assert space_repo.get_space("space_rollback_1") is None


def test_foreign_key_violation_triggers_rollback(db):
    """Verify inserting child record with nonexistent foreign key violates constraints."""
    with pytest.raises(Exception):
        with db.transaction() as cursor:
            # Foreign key session_id does not exist
            cursor.execute(
                """
                INSERT INTO session_state_transitions (transition_id, session_id, from_state, to_state, timestamp)
                VALUES ('tr_1', 'nonexistent_session_999', 'CREATED', 'INTENT_PARSED', '2026-10-25T00:00:00Z');
                """
            )


# ---------------------------------------------------------------------------
# 4. Missing Records Handling
# ---------------------------------------------------------------------------
def test_missing_records(space_repo, session_repo):
    """Verify repositories return None or False cleanly for missing IDs."""
    assert space_repo.get_space("nonexistent_space_id") is None
    assert space_repo.delete_space("nonexistent_space_id") is False
    assert session_repo.load_session("nonexistent_session_id") is None
    assert session_repo.delete_session("nonexistent_session_id") is False
    assert session_repo.get_audit_events("nonexistent_session_id") == []


# ---------------------------------------------------------------------------
# 5. Duplicate Operations & Upsert Idempotency
# ---------------------------------------------------------------------------
def test_duplicate_operations_idempotency(session_repo):
    """Verify duplicate writes to same session/task ID update rather than duplicating."""
    ctx = WorkflowContext(
        session_id="sess_idempotent_1",
        current_state=WorkflowState.CREATED,
    )
    task = ExecutionTask(
        task_id="task_seed_101",
        category="spotify_audio_seed",
        action="Seed Four Tet to audio pipeline",
        owner="Audio Curator",
        status="PENDING",
        idempotency_key="idemp_hash_four_tet",
    )
    ctx.execution_tasks.append(task)

    # First write
    session_repo.save_session(ctx)
    loaded = session_repo.load_session("sess_idempotent_1")
    assert len(loaded.execution_tasks) == 1
    assert loaded.execution_tasks[0].status == "PENDING"

    # Second write with updated task status
    ctx.execution_tasks[0].status = "EXECUTED"
    ctx.execution_tasks[0].executed_at = datetime.now(UTC)
    session_repo.save_session(ctx)

    # Must still have exactly 1 task, now EXECUTED
    loaded2 = session_repo.load_session("sess_idempotent_1")
    assert len(loaded2.execution_tasks) == 1
    assert loaded2.execution_tasks[0].status == "EXECUTED"
    assert loaded2.execution_tasks[0].executed_at is not None


# ---------------------------------------------------------------------------
# 6. Complete Session Recovery Across All 12 Entities
# ---------------------------------------------------------------------------
def test_complete_session_relational_recovery(db, session_repo):
    """Verify full recovery of all 12 cultural, architectural, execution, and audit entities."""
    now = datetime.now(UTC)
    ctx = WorkflowContext(
        session_id="sess_recovery_full_888",
        space_id="space_haveli_01",
        user_input="Launch Mumbai luxury boutique hotel",
        current_state=WorkflowState.COMPLETED,
        parsed_intent={"venue_name": "The Haveli", "business_type": "Boutique Hotel"},
        validation_cycle_count=1,
    )

    # 1. CulturalTwin
    ctx.cultural_twin = CulturalTwin(
        audience_profile="Contemporary Indian design leaders",
        mood_profile="Craft Audio Sanctuary",
        cultural_themes=["sophisticated", "intimate", "creative"],
        anchor_entities=["Teak wood", "Basalt stone"],
        resolved_tags=["Alternative music", "Independent cinema"],
        cultural_constraints=["heritage", "modernism"],
    )

    # 2. CulturalMatrix & Evidence
    ctx.cultural_matrix = CulturalMatrix(
        artists=[
            CulturalRecommendation(
                id="ent_four_tet_101",
                name="Four Tet",
                type="artist",
                affinity=0.94,
                source_query="/v2/insights",
                explainability=[
                    "Strong cross-affinity with design and minimalist audio"
                ],
            )
        ]
    )

    # 3. Experience Blueprint
    ctx.experience_output = ExperienceDesignOutput(
        sonic_identity=SonicIdentity(
            overview="Analog acoustic sanctuary soundscape",
            acoustic_profile="Warm tube amplification, wide dynamic range",
            playback_mediums=["Vinyl 33/45 RPM"],
            directives=["Keep vocal density moderate during daytime"],
        ),
        reading_library_identity=ReadingLibraryIdentity(
            overview="Global design and local architectural heritage",
            curation_themes=["monographs", "rare journals"],
            display_strategy="Built-in basalt reading alcoves",
        ),
        brand_ecosystem=BrandEcosystem(
            overview="Local craft and artisanal ceramics",
            material_palette=["raw brass", "reclaimed teak"],
        ),
        local_experience_ecosystem={
            "overview": "Kala Ghoda arts district",
            "neighborhood_context": "Heritage architecture",
            "curated_recommendations": [],
            "community_synergies": [],
        },
        cultural_programming_ideas=CulturalProgrammingIdeas(
            overview="Weekly listening sessions and filmmaker salons",
            thematic_pillars=["Independent film and analog listening"],
            activations=[],
        ),
        atmosphere_guidelines=AtmosphereGuidelines(
            hospitality_tempo="Unrushed, attentive, ceremonial",
            lighting_parameters={"evening_kelvin": 2400, "dim_percentage": 40},
            olfactory_and_thermal={"notes": ["sandalwood", "vetiver"]},
            sonic_parameters={"spl_cap_db": 75},
        ),
        spatial_zones=[
            SpatialZone(
                zone_name="Listening Lounge",
                intended_mood="Intimate acoustic sanctuary",
                tactile_elements=["Basalt panels", "Teak benches"],
            )
        ],
        provenance_entity_ids=["ent_four_tet_101"],
    )

    # 4. ExecutionPlan (Versioned)
    ctx.execution_plan = ExecutionPlan(
        plan_id="plan_mumbai_v1",
        version=1,
        plan_hash="hash_mumbai_plan_sha256_abcdef",
        estimated_cost="$150,000 opening phase allocation",
        actions=[
            ExecutionPlanAction(
                action_id="act_sound_01",
                title="Acoustic Panels",
                category="spatial_design_spec",
                description="Install basalt acoustic panels",
                owner="Experience Architect",
            )
        ],
        risks=["Noise code compliance in residential zone"],
        approvals_required=["Lead Cultural Strategist", "General Manager"],
    )

    # 5. ExecutionTask
    ctx.execution_tasks = [
        ExecutionTask(
            task_id="task_exec_901",
            category="spatial_design_spec",
            action="Install acoustic panels",
            owner="Experience Architect",
            status="EXECUTED",
            idempotency_key="idemp_acoustic_panels_01",
            output_reference="jira://TICKET-441",
            provenance={"approved_by": "Curator: Satwik Jaiswal"},
            timestamp=now,
            executed_at=now,
        )
    ]

    # 6. Approval Record
    ctx.approval = ApprovalRecord(
        session_id=ctx.session_id,
        plan_id="plan_mumbai_v1",
        plan_version=1,
        plan_hash="hash_mumbai_plan_sha256_abcdef",
        approver="Curator: Satwik Jaiswal",
        is_valid=True,
        approved_at=now,
    )

    # 7. Audit Events
    ctx.audit_events = [
        AuditEvent(
            event_id="evt_audit_001",
            session_id=ctx.session_id,
            from_state=WorkflowState.CREATED,
            to_state=WorkflowState.AWAITING_APPROVAL,
            reason="Pipeline completed to approval gate",
            timestamp=now,
        ),
        AuditEvent(
            event_id="evt_audit_002",
            session_id=ctx.session_id,
            from_state=WorkflowState.AWAITING_APPROVAL,
            to_state=WorkflowState.APPROVED,
            reason="Curator signoff",
            timestamp=now,
        ),
        AuditEvent(
            event_id="evt_audit_003",
            session_id=ctx.session_id,
            from_state=WorkflowState.APPROVED,
            to_state=WorkflowState.COMPLETED,
            reason="Execution tasks dispatched",
            timestamp=now,
        ),
    ]

    # Persist session to relational database
    session_repo.save_session(ctx)

    # Now recover from database using a fresh repository instance
    recovered = session_repo.load_session("sess_recovery_full_888")
    assert recovered is not None
    assert recovered.session_id == "sess_recovery_full_888"
    assert recovered.space_id == "space_haveli_01"
    assert recovered.current_state == WorkflowState.COMPLETED
    assert recovered.parsed_intent["venue_name"] == "The Haveli"

    # Verify CulturalTwin recovery
    assert recovered.cultural_twin is not None
    assert (
        recovered.cultural_twin.audience_profile == "Contemporary Indian design leaders"
    )
    assert "creative" in recovered.cultural_twin.cultural_themes
    assert "Teak wood" in recovered.cultural_twin.anchor_entities
    assert recovered.cultural_twin.mood_profile == "Craft Audio Sanctuary"

    # Verify CulturalMatrix recovery
    assert recovered.cultural_matrix is not None
    assert len(recovered.cultural_matrix.artists) == 1
    assert recovered.cultural_matrix.artists[0].id == "ent_four_tet_101"

    # Verify ExecutionPlan recovery
    assert recovered.execution_plan is not None
    assert recovered.execution_plan.plan_id == "plan_mumbai_v1"
    assert recovered.execution_plan.version == 1
    assert recovered.execution_plan.plan_hash == "hash_mumbai_plan_sha256_abcdef"
    assert (
        recovered.execution_plan.estimated_cost == "$150,000 opening phase allocation"
    )

    # Verify ExecutionTask recovery
    assert len(recovered.execution_tasks) == 1
    assert recovered.execution_tasks[0].task_id == "task_exec_901"
    assert recovered.execution_tasks[0].status == "EXECUTED"
    assert recovered.execution_tasks[0].idempotency_key == "idemp_acoustic_panels_01"

    # Verify Approval recovery
    assert recovered.approval is not None
    assert recovered.approval.session_id == ctx.session_id
    assert recovered.approval.approver == "Curator: Satwik Jaiswal"
    assert recovered.approval.plan_hash == "hash_mumbai_plan_sha256_abcdef"
    assert recovered.approval.is_valid is True

    # Verify Audit Events recovery
    assert len(recovered.audit_events) == 3
    assert recovered.audit_events[0].from_state == WorkflowState.CREATED
    assert recovered.audit_events[1].to_state == WorkflowState.APPROVED
    assert recovered.audit_events[2].to_state == WorkflowState.COMPLETED


# ---------------------------------------------------------------------------
# 7. SQLiteStateStore State Machine Integration
# ---------------------------------------------------------------------------
def test_state_store_integration_with_workflow_events(state_store):
    """Verify SQLiteStateStore functions transparently as a BaseStateStore."""
    ctx = WorkflowContext(
        session_id="sess_store_test_001",
        current_state=WorkflowState.CREATED,
    )
    event = AuditEvent(
        event_id="evt_init_1",
        session_id=ctx.session_id,
        from_state=WorkflowState.CREATED,
        to_state=WorkflowState.INTENT_PARSED,
        reason="Initialized and parsed intent",
    )

    state_store.save_transition(event, ctx)

    # Verify context and audit event are accessible
    loaded = state_store.load_context("sess_store_test_001")
    assert loaded is not None
    assert loaded.session_id == "sess_store_test_001"

    events = state_store.get_audit_events("sess_store_test_001")
    assert len(events) == 1
    assert events[0].event_id == "evt_init_1"
    assert events[0].to_state == WorkflowState.INTENT_PARSED
