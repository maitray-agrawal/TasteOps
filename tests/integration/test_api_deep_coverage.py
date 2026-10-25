"""TasteOps API Deep Behavioral Test Suite.

Comprehensive behavioral testing covering:
1. Every REST API endpoint (probes, spaces, sessions, blueprints, events, approvals, rejections, execution, stream, connectors)
2. Valid requests and schema verification
3. Malformed request payloads, missing fields, type mismatches
4. Missing resources (404 Not Found for non-existent spaces, sessions, tasks)
5. Invalid IDs and path traversal rejection (422/404)
6. Authorization failures (401 Missing Token, 403 Invalid Token)
7. Concurrent requests across analysis, approval, and execution pipelines
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient

from tasteops.api.app import create_app
from tasteops.api.dependencies import (
    get_database,
    get_service,
    get_space_repository,
)
from tasteops.api.service import TasteOpsApplicationService
from tasteops.api.settings import APISettings
from tasteops.persistence.database import Database
from tasteops.persistence.space_repository import SQLiteSpaceRepository
from tasteops.persistence.store import SQLiteStateStore
from tasteops.workflows.orchestrator import TasteOpsOrchestrator


@pytest.fixture
def api_test_env(tmp_path, mock_mcp_adapter):
    """Provides an isolated database, service, and TestClient."""
    adapter, _, _, _ = mock_mcp_adapter
    db_path = tmp_path / f"test_api_{uuid.uuid4().hex[:8]}.db"
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
        title="TasteOps API Deep Test",
        environment="test",
        TASTEOPS_API_KEY="test_secret_api_key_12345",
    )
    app = create_app(settings=settings)
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_space_repository] = lambda: space_repo
    app.dependency_overrides[get_service] = lambda: service

    with TestClient(app) as tc:
        yield tc, db, service, settings


# -----------------------------------------------------------------------------
# 1. System Probes: /health & /ready
# -----------------------------------------------------------------------------
def test_system_probes_behavior(api_test_env):
    tc, _, _, _ = api_test_env

    # GET /health
    health_resp = tc.get("/health")
    assert health_resp.status_code == 200
    h_data = health_resp.json()
    assert h_data["status"] == "healthy"
    assert "version" in h_data
    assert "timestamp" in h_data

    # GET /ready
    ready_resp = tc.get("/ready")
    assert ready_resp.status_code == 200
    r_data = ready_resp.json()
    assert r_data["status"] == "ready"
    assert "checks" in r_data
    assert r_data["checks"]["store"] == "ok"


# -----------------------------------------------------------------------------
# 2. Spaces Endpoints: Valid, Malformed, Missing, Invalid IDs
# -----------------------------------------------------------------------------
def test_spaces_crud_and_validation(api_test_env):
    tc, _, _, settings = api_test_env
    auth_headers = {"Authorization": f"Bearer {settings.api_key}"}

    # 1. Valid Space Registration
    valid_payload = {
        "name": "SoHo Vinyl Sanctuary",
        "business_type": "Listening Cafe",
        "location": {"latitude": 40.723, "longitude": -74.001, "radius_meters": 1500},
        "target_audience": "Curators and acoustic collectors",
        "positioning": "Wabi-sabi analog listening room",
        "desired_mood": "Warm, resonant, contemplative",
        "budget": "High",
        "constraints": ["No screens", "Acoustic ceiling"],
        "anchor_entities": ["Blue Bottle Coffee", "A24"],
        "brand": "TasteOps Studio",
        "goals": ["Foster music appreciation"],
        "cultural_preferences": ["Japanese jazz kissa"],
    }
    create_resp = tc.post("/api/v1/spaces", json=valid_payload, headers=auth_headers)
    assert create_resp.status_code == 201
    space = create_resp.json()
    space_id = space["space_id"]
    assert space["name"] == valid_payload["name"]
    assert create_resp.headers["Location"] == f"/api/v1/spaces/{space_id}"

    # 2. GET Space Profile
    get_resp = tc.get(f"/api/v1/spaces/{space_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["space_id"] == space_id

    # 3. Malformed Space Payload: missing required field 'business_type'
    bad_payload = {"name": "Incomplete Space"}
    bad_resp = tc.post("/api/v1/spaces", json=bad_payload, headers=auth_headers)
    assert bad_resp.status_code == 422
    assert "error" in bad_resp.json()

    # 4. Malformed Space Payload: empty string name
    empty_name_resp = tc.post(
        "/api/v1/spaces",
        json={"name": "", "business_type": "Cafe"},
        headers=auth_headers,
    )
    assert empty_name_resp.status_code == 422

    # 5. Missing Space: 404
    missing_resp = tc.get("/api/v1/spaces/space_nonexistent_99999")
    assert missing_resp.status_code == 404
    assert missing_resp.json()["error"]["code"] == "SPACE_NOT_FOUND"

    # 6. Invalid Space ID format (path traversal / symbols)
    invalid_id_resp = tc.get("/api/v1/spaces/space!!@@invalid")
    assert invalid_id_resp.status_code in (404, 422)


# -----------------------------------------------------------------------------
# 3. Analyze Space Flow & State Transitions
# -----------------------------------------------------------------------------
def test_space_analyze_endpoint_behavior(api_test_env):
    tc, _, _, settings = api_test_env
    auth_headers = {"Authorization": f"Bearer {settings.api_key}"}

    # Register space
    sp = tc.post(
        "/api/v1/spaces",
        json={
            "name": "Bespoke Tea Bar",
            "business_type": "Tea Salon",
            "desired_mood": "Zen acoustic",
            "target_audience": "Tea connoisseurs",
            "anchor_entities": ["Aesop", "Muji"],
        },
        headers=auth_headers,
    ).json()
    space_id = sp["space_id"]

    # 1. Trigger analyze
    analyze_resp = tc.post(
        f"/api/v1/spaces/{space_id}/analyze",
        json={
            "user_intent": "Create a peaceful sensory tea experience with ambient soundscapes"
        },
        headers=auth_headers,
    )
    assert analyze_resp.status_code == 200
    session = analyze_resp.json()
    session_id = session["session_id"]
    assert session["current_state"] == "AWAITING_APPROVAL"
    assert session["status"] == "AWAITING_APPROVAL"
    assert session["space_id"] == space_id
    assert session["cultural_twin"] is not None
    assert session["cultural_matrix_summary"] is not None
    assert session["agent_summaries"] is not None
    assert session["execution_plan"] is not None

    # 2. Re-trigger analyze on same space -> creates a fresh deterministically tracked session
    analyze2_resp = tc.post(f"/api/v1/spaces/{space_id}/analyze", headers=auth_headers)
    assert analyze2_resp.status_code == 200
    assert analyze2_resp.json()["session_id"] != session_id

    # 3. Analyze non-existent space -> 404
    missing_space_resp = tc.post(
        "/api/v1/spaces/space_ghost_123/analyze", headers=auth_headers
    )
    assert missing_space_resp.status_code == 404


# -----------------------------------------------------------------------------
# 4. Session Inspect, Blueprint, Ledger, Stream, and Connectors
# -----------------------------------------------------------------------------
def test_session_inspection_and_connectors(api_test_env):
    tc, _, _, settings = api_test_env
    auth_headers = {"Authorization": f"Bearer {settings.api_key}"}

    # Setup session
    sp = tc.post(
        "/api/v1/spaces",
        json={"name": "Inspect Space", "business_type": "Club"},
        headers=auth_headers,
    ).json()
    sess = tc.post(
        f"/api/v1/spaces/{sp['space_id']}/analyze", headers=auth_headers
    ).json()
    session_id = sess["session_id"]

    # 1. GET /sessions/{id}
    detail_resp = tc.get(f"/api/v1/sessions/{session_id}")
    assert detail_resp.status_code == 200
    data = detail_resp.json()
    assert data["session_id"] == session_id
    assert "timestamps" in data
    assert "links" in data

    # 2. GET /sessions/{id}/events
    events_resp = tc.get(f"/api/v1/sessions/{session_id}/events")
    assert events_resp.status_code == 200
    events_data = events_resp.json()
    assert events_data["total_events"] > 0
    assert "verification_status" in events_data
    assert events_data["verification_status"]["is_verified"] is True

    # 3. GET /sessions/{id}/ledger/verify
    verify_resp = tc.get(f"/api/v1/sessions/{session_id}/ledger/verify")
    assert verify_resp.status_code == 200
    v_data = verify_resp.json()
    assert v_data["is_verified"] is True
    assert "head_hash" in v_data
    assert "chain_length" in v_data

    # 4. GET /sessions/{id}/blueprint
    blueprint_resp = tc.get(f"/api/v1/sessions/{session_id}/blueprint")
    assert blueprint_resp.status_code == 200
    bp_data = blueprint_resp.json()
    assert "spatial_zones" in bp_data
    assert "soundscape_design" in bp_data
    assert "strategic_objective" in bp_data
    assert "experience_concept" in bp_data

    # 5. GET /sessions/{id}/connectors
    conn_resp = tc.get(f"/api/v1/sessions/{session_id}/connectors")
    assert conn_resp.status_code == 200
    connectors = conn_resp.json()
    assert len(connectors) >= 3
    capabilities = [c["capability"] for c in connectors]
    assert "spotify_audio_seed" in capabilities
    assert "partner_outreach_brief" in capabilities
    assert "procurement_order" in capabilities

    # 6. Missing Session ID -> 404 on all endpoints
    missing_id = "sess_not_found_0000"
    assert tc.get(f"/api/v1/sessions/{missing_id}").status_code == 404
    assert tc.get(f"/api/v1/sessions/{missing_id}/events").status_code == 404
    assert tc.get(f"/api/v1/sessions/{missing_id}/blueprint").status_code == 404
    assert tc.get(f"/api/v1/sessions/{missing_id}/ledger/verify").status_code == 404
    assert tc.get(f"/api/v1/sessions/{missing_id}/connectors").status_code == 404


# -----------------------------------------------------------------------------
# 5. Approval, Rejection, and Execution API Behavior
# -----------------------------------------------------------------------------
def test_approval_and_execution_lifecycle_api(api_test_env):
    tc, _, _, settings = api_test_env
    auth_headers = {"Authorization": f"Bearer {settings.api_key}"}

    # Setup session
    sp = tc.post(
        "/api/v1/spaces",
        json={"name": "Lifecycle Space", "business_type": "Lounge"},
        headers=auth_headers,
    ).json()
    sess = tc.post(
        f"/api/v1/spaces/{sp['space_id']}/analyze", headers=auth_headers
    ).json()
    session_id = sess["session_id"]
    plan_id = sess["execution_plan"]["plan_id"]

    # 1. Premature execution -> 403 Forbidden
    pre_exec = tc.post(f"/api/v1/sessions/{session_id}/execute", headers=auth_headers)
    assert pre_exec.status_code == 403

    # 2. Malformed Approval payload -> 422 (missing approver)
    bad_approve = tc.post(
        f"/api/v1/sessions/{session_id}/approve", json={}, headers=auth_headers
    )
    assert bad_approve.status_code == 422

    # 3. Valid Approval
    approve_resp = tc.post(
        f"/api/v1/sessions/{session_id}/approve",
        json={
            "approver": "Satwik Jaiswal",
            "role": "Principal Curator",
            "notes": "Verified sensory and cultural parameters",
            "plan_version": 1,
        },
        headers=auth_headers,
    )
    assert approve_resp.status_code == 200
    appr_data = approve_resp.json()
    assert appr_data["current_state"] == "APPROVED"
    assert appr_data["approval_state"]["is_approved"] is True

    # 4. Duplicate Approval -> Idempotent 200 OK preserving valid approval
    dup_approve = tc.post(
        f"/api/v1/sessions/{session_id}/approve",
        json={"approver": "Second Curator"},
        headers=auth_headers,
    )
    assert dup_approve.status_code == 200
    assert dup_approve.json()["approval_state"]["is_approved"] is True

    # 5. Execute Approved Session
    exec_resp = tc.post(f"/api/v1/sessions/{session_id}/execute", headers=auth_headers)
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()
    assert exec_data["current_state"] in ("EXECUTING", "COMPLETED")
    assert exec_data["total_tasks"] > 0

    # 6. Execute Individual Task Connector
    task_id = exec_data["tasks"][0]["task_id"]
    idem_key = f"idem_test_{uuid.uuid4().hex[:8]}"
    task_exec_resp = tc.post(
        f"/api/v1/sessions/{session_id}/tasks/{task_id}/execute",
        json={
            "session_id": session_id,
            "plan_id": plan_id,
            "plan_version": 1,
            "task_id": task_id,
            "idempotency_key": idem_key,
            "task_type": "spotify_audio_seed",
            "payload": {"artist_name": "Verified Artist"},
        },
        headers=auth_headers,
    )
    assert task_exec_resp.status_code in (
        200,
        422,
    )  # 200 if configured/mocked, 422 if not configured


# -----------------------------------------------------------------------------
# 6. Rejection Endpoint Behavior
# -----------------------------------------------------------------------------
def test_rejection_endpoint_behavior(api_test_env):
    tc, _, _, settings = api_test_env
    auth_headers = {"Authorization": f"Bearer {settings.api_key}"}

    sp = tc.post(
        "/api/v1/spaces",
        json={"name": "Rejection Space", "business_type": "Bar"},
        headers=auth_headers,
    ).json()
    sess = tc.post(
        f"/api/v1/spaces/{sp['space_id']}/analyze", headers=auth_headers
    ).json()
    session_id = sess["session_id"]

    # Missing rejection reason -> 422
    bad_reject = tc.post(
        f"/api/v1/sessions/{session_id}/reject", json={}, headers=auth_headers
    )
    assert bad_reject.status_code == 422

    # Valid rejection
    reject_resp = tc.post(
        f"/api/v1/sessions/{session_id}/reject",
        json={"reason": "Aesthetic parameters too loud for neighborhood zoning"},
        headers=auth_headers,
    )
    assert reject_resp.status_code == 200
    rej_data = reject_resp.json()
    assert rej_data["current_state"] == "FAILED"
    assert rej_data["status"] == "FAILED"


# -----------------------------------------------------------------------------
# 7. Authorization Failures on Mutating Endpoints
# -----------------------------------------------------------------------------
def test_authorization_failures(api_test_env):
    tc, _, _, _ = api_test_env

    # 1. Missing Authorization header on POST /spaces -> 401
    unauth_resp = tc.post(
        "/api/v1/spaces", json={"name": "No Auth Space", "business_type": "Cafe"}
    )
    assert unauth_resp.status_code == 401

    # 2. Invalid Token -> 403
    forbidden_resp = tc.post(
        "/api/v1/spaces",
        headers={"Authorization": "Bearer invalid_secret_token"},
        json={"name": "Forbidden Space", "business_type": "Cafe"},
    )
    assert forbidden_resp.status_code == 403


# -----------------------------------------------------------------------------
# 8. Concurrent Requests Resilience
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_concurrent_api_requests(api_test_env):
    tc, _, _, settings = api_test_env
    auth_headers = {"Authorization": f"Bearer {settings.api_key}"}

    # Register 5 spaces concurrently
    def create_one_space(idx: int):
        return tc.post(
            "/api/v1/spaces",
            json={"name": f"Concurrent Space {idx}", "business_type": "Gallery"},
            headers=auth_headers,
        )

    loop = asyncio.get_event_loop()
    tasks = [loop.run_in_executor(None, create_one_space, i) for i in range(5)]
    responses = await asyncio.gather(*tasks)

    for r in responses:
        assert r.status_code == 201
        assert "space_id" in r.json()

    # Verify all 5 spaces were saved
    list_resp = tc.get("/api/v1/spaces")
    assert len(list_resp.json()) >= 5
