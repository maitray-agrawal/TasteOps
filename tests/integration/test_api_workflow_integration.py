"""TasteOps FastAPI & Workflow Engine Integration Tests.

Verifies end-to-end integration between:
FastAPI Application
    ↓
TasteOpsApplicationService
    ↓
TasteOpsOrchestrator / WorkflowEngine
    ↓
SQLite Relational Persistence Layer
    ↓
Mocked External Qloo / LLM Providers

Covers:
1. POST /api/v1/spaces/{space_id}/analyze full 10-step flow stopping at approval gate
2. Proof that tasks NEVER execute automatically after plan generation
3. Authoritative human approval gate enforcement
4. GET /api/v1/sessions/{session_id} safe, typed view of all 12 required components
5. Sanitization of errors (no stack traces or chain-of-thought exposed)
6. Curator rejection and audit ledger persistence
"""

from __future__ import annotations

import pytest
import respx
from fastapi.testclient import TestClient

from tasteops.api.app import create_app
from tasteops.api.dependencies import get_database, get_service, get_space_repository
from tasteops.api.service import TasteOpsApplicationService
from tasteops.api.settings import APISettings
from tasteops.persistence.database import Database
from tasteops.persistence.space_repository import SQLiteSpaceRepository
from tasteops.persistence.store import SQLiteStateStore
from tasteops.workflows.orchestrator import TasteOpsOrchestrator
from tasteops.workflows.states import WorkflowState
from tests.fixtures.demo_mumbai_boutique_hotel import (
    MUMBAI_DEMO_HINTS,
    MUMBAI_DEMO_RAW_INTENT,
    MUMBAI_INSIGHTS_MOCK_RESPONSE,
    MUMBAI_SEARCH_MOCK_RESPONSE,
    MUMBAI_TAGS_MOCK_RESPONSE,
)


@pytest.fixture
def mock_qloo_api():
    """Sets up respx mock router for all external Qloo HTTP endpoints."""
    with respx.mock(
        base_url="https://hackathon.api.qloo.com", assert_all_called=False
    ) as router:
        router.get("/search").respond(status_code=200, json=MUMBAI_SEARCH_MOCK_RESPONSE)
        router.get("/v2/tags").respond(status_code=200, json=MUMBAI_TAGS_MOCK_RESPONSE)
        router.get("/v2/insights").respond(
            status_code=200, json=MUMBAI_INSIGHTS_MOCK_RESPONSE
        )
        yield router


@pytest.fixture
def integrated_app(tmp_path, mock_mcp_adapter):
    """Provides a fully integrated FastAPI application with real SQLite persistence and mock MCP."""
    adapter, _, _, _ = mock_mcp_adapter
    db_path = tmp_path / "integration_tasteops.db"
    db = Database(str(db_path))
    space_repo = SQLiteSpaceRepository(db)
    state_store = SQLiteStateStore(db)

    orchestrator = TasteOpsOrchestrator(
        mcp_adapter=adapter,
        store=state_store,
    )
    service = TasteOpsApplicationService(
        orchestrator=orchestrator,
        store=state_store,
        space_repo=space_repo,
    )

    settings = APISettings(
        title="TasteOps Integration Test API",
        environment="test",
        database_path=str(db_path),
        cors_origins=["http://localhost:3000"],
    )
    app = create_app(settings=settings)

    # Dependency overrides to ensure service and DB are shared
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_space_repository] = lambda: space_repo
    app.dependency_overrides[get_service] = lambda: service

    return app, db, service


@pytest.fixture
def client(integrated_app):
    app, db, service = integrated_app
    with TestClient(app) as tc:
        yield tc, db, service


# ---------------------------------------------------------------------------
# 1. End-to-End POST /api/v1/spaces/{space_id}/analyze Flow
# ---------------------------------------------------------------------------
def test_analyze_space_full_flow_stops_at_approval_gate(client, mock_qloo_api):
    """Verify POST /api/v1/spaces/{space_id}/analyze executes the full 10-step pipeline:
    1. validate request
    2. create workflow session
    3. persist initial state
    4. invoke existing workflow engine
    5. persist state transitions
    6. persist agent outputs
    7. persist evidence/provenance
    8. persist generated plan
    9. persist validation result
    10. stop at approval gate (authoritative human gate)
    """
    tc, db, service = client

    # Step 1: Register space
    space_resp = tc.post(
        "/api/v1/spaces",
        json={
            "name": "The Haveli Contemporary Mumbai",
            "business_type": "Boutique Hotel",
            "desired_mood": "Sophisticated / intimate / creative",
            "target_audience": "Affluent design purists, alternative music lovers",
            "positioning": "Contemporary Indian cultural sanctuary",
            "anchor_entities": [
                "Independent cinema",
                "Alternative music",
                "Contemporary Indian design",
            ],
        },
    )
    assert space_resp.status_code == 201
    space_id = space_resp.json()["space_id"]

    # Step 2: Trigger analyze
    analyze_resp = tc.post(
        f"/api/v1/spaces/{space_id}/analyze",
        json={
            "user_input": MUMBAI_DEMO_RAW_INTENT,
            "hints": MUMBAI_DEMO_HINTS,
            "take_per_category": 10,
            "auto_run": True,
        },
    )
    assert analyze_resp.status_code == 200
    session_data = analyze_resp.json()
    session_id = session_data["session_id"]

    # Verify Stop at Approval Gate
    assert session_data["current_state"] == WorkflowState.AWAITING_APPROVAL.value
    assert session_data["status"] == "AWAITING_APPROVAL"

    # Verify Tasks were NOT executed automatically
    assert session_data["execution_state"]["status"] == "NOT_STARTED"
    assert session_data["execution_state"]["executed_tasks"] == 0
    assert session_data["approval_state"]["is_approved"] is False
    assert session_data["approval_state"]["status"] == "PENDING"

    # Step 3: Verify Persistence across SQLite Tables
    conn = db.get_connection()
    cursor = conn.cursor()

    # (a) Workflow session & validation result persisted
    cursor.execute(
        "SELECT current_state, status, validation_result_json FROM workflow_sessions WHERE session_id = ?;",
        (session_id,),
    )
    sess_row = cursor.fetchone()
    assert sess_row["current_state"] == "AWAITING_APPROVAL"
    assert sess_row["status"] == "AWAITING_APPROVAL"
    assert sess_row["validation_result_json"] != "{}"

    # (b) State transitions persisted
    cursor.execute(
        "SELECT count(*) as count FROM session_state_transitions WHERE session_id = ?;",
        (session_id,),
    )
    assert cursor.fetchone()["count"] >= 5

    # (c) Agent runs persisted
    cursor.execute(
        "SELECT agent_name, status FROM agent_runs WHERE session_id = ?;", (session_id,)
    )
    agent_rows = cursor.fetchall()
    agent_names = {r["agent_name"] for r in agent_rows}
    assert "CulturalStrategist" in agent_names
    assert "ExperienceArchitect" in agent_names
    assert "PartnershipAgent" in agent_names
    assert "GovernanceAgent" in agent_names

    # (d) Evidence / Provenance persisted
    cursor.execute(
        "SELECT count(*) as count FROM cultural_evidence WHERE session_id = ?;",
        (session_id,),
    )
    assert cursor.fetchone()["count"] > 0

    # (e) Execution plan persisted with version and hash
    cursor.execute(
        "SELECT plan_id, version, plan_hash, estimated_cost FROM execution_plans WHERE session_id = ?;",
        (session_id,),
    )
    plan_row = cursor.fetchone()
    assert plan_row is not None
    assert plan_row["version"] == 1
    assert plan_row["plan_hash"] is not None

    cursor.close()


# ---------------------------------------------------------------------------
# 2. GET /api/v1/sessions/{session_id} Safe, Typed View
# ---------------------------------------------------------------------------
def test_get_session_exposes_all_12_safe_typed_components(client, mock_qloo_api):
    """Verify GET /api/v1/sessions/{session_id} exposes a clean, typed view of:
    - session
    - current state
    - status
    - Cultural Twin
    - Cultural Matrix summary
    - agent summaries
    - validation
    - execution plan
    - approval state
    - execution state
    - errors
    - timestamps
    and does NOT expose stack traces or chain-of-thought.
    """
    tc, db, service = client

    # Create space and analyze
    s_resp = tc.post(
        "/api/v1/spaces",
        json={"name": "Kala Ghoda Listening Lab", "business_type": "Listening Bar"},
    )
    space_id = s_resp.json()["space_id"]

    a_resp = tc.post(
        f"/api/v1/spaces/{space_id}/analyze", json={"hints": MUMBAI_DEMO_HINTS}
    )
    session_id = a_resp.json()["session_id"]

    # Query GET session
    resp = tc.get(f"/api/v1/sessions/{session_id}")
    assert resp.status_code == 200
    data = resp.json()

    # 1. Session
    assert data["session_id"] == session_id
    assert data["space_id"] == space_id
    assert data["user_input"] is not None
    assert (
        "venue_name" in data["parsed_intent"]
        or "space" in data["parsed_intent"]
        or isinstance(data["parsed_intent"], dict)
    )

    # 2. Current State
    assert data["current_state"] == "AWAITING_APPROVAL"

    # 3. Status
    assert data["status"] == "AWAITING_APPROVAL"

    # 4. Cultural Twin (safe typed view without prompt/chain-of-thought)
    assert data["cultural_twin"] is not None
    assert "audience_profile" in data["cultural_twin"]
    assert "cultural_themes" in data["cultural_twin"]
    assert "mood_profile" in data["cultural_twin"]
    assert "resolved_entities" in data["cultural_twin"]
    assert "chain_of_thought" not in data["cultural_twin"]
    assert "raw_prompt" not in data["cultural_twin"]

    # 5. Cultural Matrix Summary (safe metrics, no uncontrolled raw provider dumps)
    assert data["cultural_matrix_summary"] is not None
    mat_sum = data["cultural_matrix_summary"]
    assert mat_sum["total_entities"] > 0
    assert "domains_present" in mat_sum
    assert "category_counts" in mat_sum
    assert "top_affinities" in mat_sum
    assert mat_sum["evidence_count"] >= 0

    # 6. Agent Summaries
    assert data["agent_summaries"] is not None
    agents = data["agent_summaries"]
    assert "cultural_strategist" in agents
    assert "experience_architect" in agents
    assert "partnership_agent" in agents
    assert "governance_agent" in agents
    assert agents["governance_agent"]["is_valid"] is True

    # 7. Validation
    assert data["validation"] is not None
    val = data["validation"]
    assert val["is_valid"] is True
    assert val["provenance_verified"] is True
    assert isinstance(val["compliance_score"], float)

    # 8. Execution Plan
    assert data["execution_plan"] is not None
    plan = data["execution_plan"]
    assert "plan" in plan["plan_id"]
    assert plan["version"] == 1
    assert plan["plan_hash"] is not None
    assert plan["actions_count"] > 0
    assert len(plan["actions"]) > 0

    # 9. Approval State
    assert data["approval_state"] is not None
    appr = data["approval_state"]
    assert appr["is_approved"] is False
    assert appr["status"] == "PENDING"
    assert appr["approver"] is None

    # 10. Execution State
    assert data["execution_state"] is not None
    exec_state = data["execution_state"]
    assert exec_state["status"] == "NOT_STARTED"
    assert exec_state["executed_tasks"] == 0

    # 11. Errors (clean, no stack traces)
    assert data["errors"] == []
    assert data["error_message"] is None

    # 12. Timestamps
    assert data["timestamps"] is not None
    ts = data["timestamps"]
    assert "created_at" in ts
    assert "updated_at" in ts
    assert ts["completed_at"] is None


# ---------------------------------------------------------------------------
# 3. Authoritative Human Approval Gate Lifecycle
# ---------------------------------------------------------------------------
def test_authoritative_approval_gate_blocks_and_permits_execution(
    client, mock_qloo_api
):
    """Verify:
    1. Direct execution attempt while AWAITING_APPROVAL is blocked (HTTP 403 / 409).
    2. Human curator approval binds cryptographic plan hash and transitions to APPROVED.
    3. Execution is only permitted once approved, dispatching tasks to COMPLETED.
    """
    tc, db, service = client

    # Setup session
    s_resp = tc.post(
        "/api/v1/spaces", json={"name": "Kala Ghoda Cafe", "business_type": "Cafe"}
    )
    a_resp = tc.post(
        f"/api/v1/spaces/{s_resp.json()['space_id']}/analyze",
        json={"hints": MUMBAI_DEMO_HINTS},
    )
    session_id = a_resp.json()["session_id"]

    # 1. Attempt unapproved execution -> Must be blocked
    exec_unapproved = tc.post(f"/api/v1/sessions/{session_id}/execute")
    assert exec_unapproved.status_code in {403, 409}
    error_data = exec_unapproved.json()
    assert "error" in error_data
    assert (
        "APPROVAL" in error_data["error"]["detail"].upper()
        or "UNAPPROVED" in error_data["error"]["code"]
    )

    # Verify session remains in AWAITING_APPROVAL
    get_unapproved = tc.get(f"/api/v1/sessions/{session_id}")
    assert get_unapproved.json()["current_state"] == "AWAITING_APPROVAL"

    # 2. Human Curator approves the plan
    approve_resp = tc.post(
        f"/api/v1/sessions/{session_id}/approve",
        json={
            "approver": "Curator: Satwik Jaiswal",
            "role": "Head of Cultural Experience",
            "notes": "Plan approved for Phase 1 acoustic installation.",
            "plan_version": 1,
        },
    )
    assert approve_resp.status_code == 200
    approved_data = approve_resp.json()
    assert approved_data["current_state"] == "APPROVED"
    assert approved_data["approval_state"]["is_approved"] is True
    assert approved_data["approval_state"]["status"] == "APPROVED"
    assert (
        approved_data["approval_state"]["approver"]
        == "Curator: Satwik Jaiswal (Head of Cultural Experience)"
    )
    assert approved_data["approval_state"]["plan_hash"] is not None

    # 3. Execution dispatched after approval
    exec_resp = tc.post(f"/api/v1/sessions/{session_id}/execute")
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()
    assert exec_data["current_state"] == "COMPLETED"
    assert exec_data["executed_tasks"] > 0

    # 4. Final state check
    final_resp = tc.get(f"/api/v1/sessions/{session_id}")
    final_data = final_resp.json()
    assert final_data["current_state"] == "COMPLETED"
    assert final_data["status"] == "COMPLETED"
    assert final_data["execution_state"]["status"] == "COMPLETED"
    assert final_data["execution_state"]["executed_tasks"] > 0
    assert final_data["timestamps"]["completed_at"] is not None


# ---------------------------------------------------------------------------
# 4. Curator Rejection Flow & Sanitized Error Logging
# ---------------------------------------------------------------------------
def test_curator_rejection_flow_records_audit_and_sanitizes_errors(
    client, mock_qloo_api
):
    """Verify:
    1. Human curator can reject plan with rationale.
    2. Workflow transitions to FAILED.
    3. Errors are exposed cleanly without Python tracebacks.
    4. Audit log event is persisted in relational database.
    """
    tc, db, service = client

    s_resp = tc.post(
        "/api/v1/spaces", json={"name": "Rejection Test Space", "business_type": "Bar"}
    )
    a_resp = tc.post(
        f"/api/v1/spaces/{s_resp.json()['space_id']}/analyze",
        json={"hints": MUMBAI_DEMO_HINTS},
    )
    session_id = a_resp.json()["session_id"]

    # Reject session
    reject_resp = tc.post(
        f"/api/v1/sessions/{session_id}/reject",
        json={
            "reason": "Acoustic volume specifications exceed municipal limits for residential district."
        },
    )
    assert reject_resp.status_code == 200
    rej_data = reject_resp.json()
    assert rej_data["current_state"] == "FAILED"
    assert rej_data["status"] == "FAILED"
    assert rej_data["errors"] is not None
    assert len(rej_data["errors"]) > 0
    # Must NOT expose python internal stack trace
    assert "Traceback (most recent call last)" not in rej_data["errors"][0]
    assert "exceed municipal limits" in rej_data["errors"][0]

    # Verify audit events ledger has the rejection event
    events_resp = tc.get(f"/api/v1/sessions/{session_id}/events")
    assert events_resp.status_code == 200
    events_data = events_resp.json()
    reasons = [e["reason"] for e in events_data["events"]]
    assert any("exceed municipal limits" in r for r in reasons)
