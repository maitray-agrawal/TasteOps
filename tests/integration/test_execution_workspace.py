"""Integration tests for Execution Workspace & Downstream Task Dispatch.

Validates:
- Display fields for every ExecutionTask:
  - task_id
  - task_type
  - description
  - status (PENDING, APPROVED, RUNNING, COMPLETED, FAILED, SKIPPED)
  - estimated_cost
  - connector (NOT_CONFIGURED when unavailable)
  - approval_status
  - execution_timestamp
  - result
  - error
- Supported statuses: PENDING, APPROVED, RUNNING, COMPLETED, FAILED, SKIPPED.
- Strict 5 backend preconditions before execution is permitted:
  1. approved session
  2. current plan version
  3. successful governance validation
  4. required evidence
  5. executable tasks
- Never show success before backend confirmation.
- Unconfigured external connectors display NOT_CONFIGURED.
- Zero-simulation external execution guarantee.
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
from tests.fixtures.demo_mumbai_boutique_hotel import (
    MUMBAI_DEMO_HINTS,
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
def client(tmp_path, mock_mcp_adapter):
    """Provides a TestClient with SQLite persistence and mock MCP."""
    adapter, _, _, _ = mock_mcp_adapter
    db_path = tmp_path / "test_exec_workspace.db"
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
        title="TasteOps Execution Workspace Integration Test",
        environment="test",
        database_path=str(db_path),
    )
    app = create_app(settings=settings)

    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_space_repository] = lambda: space_repo
    app.dependency_overrides[get_service] = lambda: service

    with TestClient(app) as tc:
        yield tc, db, service


def _create_approved_session(tc: TestClient) -> tuple[str, str]:
    """Helper to run workflow up to AWAITING_APPROVAL and record human curator approval."""
    # 1. Create space
    sp_resp = tc.post(
        "/api/v1/spaces",
        json={
            "name": "Boutique Residency Mumbai",
            "business_type": "Boutique Hotel & Listening Lounge",
            "desired_mood": "Intimate listening lounge",
            "target_audience": "Designers and architects",
            "anchor_entities": ["Prateek Kuhad", "Raw Mango"],
        },
    )
    assert sp_resp.status_code == 201
    space_id = sp_resp.json()["space_id"]

    # 2. Analyze space
    hints = dict(MUMBAI_DEMO_HINTS)
    hints["anchor_entities"] = ["Prateek Kuhad", "Raw Mango"]
    hints["resolved_entities"] = ["ent_prateek_kuhad_01", "ent_raw_mango_01"]

    an_resp = tc.post(
        f"/api/v1/spaces/{space_id}/analyze",
        json={"hints": hints},
    )
    assert an_resp.status_code == 200
    session_id = an_resp.json()["session_id"]

    # 3. Approve session at human gate
    appr_resp = tc.post(
        f"/api/v1/sessions/{session_id}/approve",
        json={
            "approver": "Curator Maitray",
            "role": "Lead Cultural Strategist",
            "plan_version": 1,
            "notes": "Approved for external hardware and audio dispatch.",
        },
    )
    assert appr_resp.status_code == 200
    return space_id, session_id


# =============================================================================
# 1. Telemetry: All 10 Required Task Fields Displayed
# =============================================================================
def test_execution_tasks_display_all_10_required_fields(client, mock_qloo_api):
    """Verify that every execution task strictly exposes all 10 required fields."""
    tc, db, service = client
    _, session_id = _create_approved_session(tc)

    # Fetch session detail prior to execution
    detail_resp = tc.get(f"/api/v1/sessions/{session_id}")
    assert detail_resp.status_code == 200
    data = detail_resp.json()

    exec_state = data.get("execution_state", {})
    assert "tasks" in exec_state
    tasks = exec_state["tasks"]
    assert len(tasks) > 0, "Pre-execution plan must expose executable tasks"

    required_fields = [
        "task_id",
        "task_type",
        "description",
        "status",
        "estimated_cost",
        "connector",
        "approval_status",
        "execution_timestamp",
        "result",
        "error",
    ]

    valid_statuses = {
        "PENDING",
        "APPROVED",
        "RUNNING",
        "COMPLETED",
        "FAILED",
        "SKIPPED",
    }

    for task in tasks:
        for field in required_fields:
            assert field in task, (
                f"Task {task.get('task_id')} missing required field: {field}"
            )

        assert task["status"] in valid_statuses, f"Invalid status: {task['status']}"
        assert task["approval_status"] == "APPROVED"
        assert task["estimated_cost"] is not None
        assert len(task["description"]) > 0


# =============================================================================
# 2. Connector Availability & NOT_CONFIGURED Indicator
# =============================================================================
def test_connector_displays_not_configured_when_unconfigured(
    client, mock_qloo_api, monkeypatch
):
    """Verify that when connector environment credentials are absent, connector is NOT_CONFIGURED."""
    tc, db, service = client
    # Ensure Spotify credentials are NOT set
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    monkeypatch.delenv("PARTNER_OUTREACH_API_KEY", raising=False)

    _, session_id = _create_approved_session(tc)

    detail_resp = tc.get(f"/api/v1/sessions/{session_id}")
    assert detail_resp.status_code == 200
    tasks = detail_resp.json()["execution_state"]["tasks"]

    # All unconfigured external tasks must show NOT_CONFIGURED
    for task in tasks:
        assert task["connector"] == "NOT_CONFIGURED"


def test_connector_displays_configured_name_when_environment_credentials_present(
    client, mock_qloo_api, monkeypatch
):
    """Verify that when connector environment credentials are provided, connector displays its name."""
    tc, db, service = client
    # Set Spotify credentials in environment
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "spotify_client_id_live_test_123")
    monkeypatch.setenv("PARTNER_OUTREACH_API_KEY", "outreach_key_456")

    _, session_id = _create_approved_session(tc)

    detail_resp = tc.get(f"/api/v1/sessions/{session_id}")
    assert detail_resp.status_code == 200
    tasks = detail_resp.json()["execution_state"]["tasks"]

    spotify_tasks = [t for t in tasks if t["task_type"] == "spotify_audio_seed"]
    assert len(spotify_tasks) > 0
    for st in spotify_tasks:
        assert st["connector"] == "Spotify Web API"


# =============================================================================
# 3. Preconditions: Execute Only Possible When Confirmed by Backend
# =============================================================================
def test_execute_blocked_prior_to_session_approval(client, mock_qloo_api):
    """Precondition 1: Execute must be rejected (403) before session is approved."""
    tc, db, service = client

    # Create space & analyze to reach AWAITING_APPROVAL
    sp_resp = tc.post(
        "/api/v1/spaces",
        json={
            "name": "Unapproved Space",
            "business_type": "Test Venue",
            "desired_mood": "Reflective",
            "target_audience": "Designers",
            "anchor_entities": ["Prateek Kuhad", "Raw Mango"],
        },
    )
    assert sp_resp.status_code == 201
    space_id = sp_resp.json()["space_id"]

    hints = dict(MUMBAI_DEMO_HINTS)
    hints["anchor_entities"] = ["Prateek Kuhad", "Raw Mango"]
    hints["resolved_entities"] = ["ent_prateek_kuhad_01", "ent_raw_mango_01"]

    an_resp = tc.post(f"/api/v1/spaces/{space_id}/analyze", json={"hints": hints})
    session_id = an_resp.json()["session_id"]

    # Attempt to execute without curator approval
    exec_resp = tc.post(f"/api/v1/sessions/{session_id}/execute")
    assert exec_resp.status_code == 403
    err = exec_resp.json()["error"]
    assert err["code"] == "EXECUTION_UNAPPROVED"
    assert "must be explicitly approved" in err["detail"]


def test_execute_blocked_when_plan_version_mismatched(client, mock_qloo_api):
    """Precondition 2: Execute must be rejected (403) if approval plan version does not match plan."""
    tc, db, service = client
    _, session_id = _create_approved_session(tc)

    # Mutate plan version in context to simulate stale approval
    ctx = service.get_session(session_id)
    ctx.plan.version = 2

    exec_resp = tc.post(f"/api/v1/sessions/{session_id}/execute")
    assert exec_resp.status_code == 403
    err = exec_resp.json()["error"]
    assert "does not authorize current plan version" in err["detail"]


def test_execute_blocked_when_governance_validation_failed(client, mock_qloo_api):
    """Precondition 3: Execute must be rejected (403) if governance validation is invalid."""
    tc, db, service = client
    _, session_id = _create_approved_session(tc)

    # Invalidate governance in context
    ctx = service.get_session(session_id)
    ctx.plan.governance.is_valid = False
    ctx.plan.governance.risk_flags = [
        "Noise threshold exceeded: 85dB violates local municipal code"
    ]

    exec_resp = tc.post(f"/api/v1/sessions/{session_id}/execute")
    assert exec_resp.status_code == 403
    err = exec_resp.json()["error"]
    assert "Governance validation failed" in err["detail"]


def test_execute_blocked_when_required_evidence_missing(client, mock_qloo_api):
    """Precondition 4: Execute must be rejected (422) if required evidence provenance is unverified."""
    tc, db, service = client
    _, session_id = _create_approved_session(tc)

    # Strip evidence and mark provenance unverified
    ctx = service.get_session(session_id)
    ctx.plan.governance.provenance_verified = False

    exec_resp = tc.post(f"/api/v1/sessions/{session_id}/execute")
    assert exec_resp.status_code == 422
    err = exec_resp.json()["error"]
    assert "provenance verification failed" in err["detail"]


def test_execute_blocked_when_no_executable_tasks(client, mock_qloo_api):
    """Precondition 5: Execute must be rejected (409) if plan contains no executable tasks."""
    tc, db, service = client
    _, session_id = _create_approved_session(tc)

    # Clear tasks and plan components
    ctx = service.get_session(session_id)
    ctx.execution_tasks = []
    if ctx.plan.execution_plan:
        ctx.plan.execution_plan.actions = []
    ctx.plan.cultural_matrix.artists = []
    ctx.plan.partnerships.partnerships = []
    ctx.plan.experience_design.spatial_zones = []
    # Synchronize approval hash to specifically test precondition 5 (executable tasks)
    ctx.approval.plan_hash = ctx.plan.compute_hash()

    exec_resp = tc.post(f"/api/v1/sessions/{session_id}/execute")
    assert exec_resp.status_code == 409
    err = exec_resp.json()["error"]
    assert "Invalid workflow transition" in err["detail"]


# =============================================================================
# 4. Successful Execution Lifecycle & State Confirmation
# =============================================================================
def test_successful_execution_confirms_backend_state(client, mock_qloo_api):
    """Verify complete execution flow: 200 response, status COMPLETED, and timestamps."""
    tc, db, service = client
    _, session_id = _create_approved_session(tc)

    # Execute approved plan
    exec_resp = tc.post(f"/api/v1/sessions/{session_id}/execute")
    assert exec_resp.status_code == 200
    res_data = exec_resp.json()

    assert res_data["session_id"] == session_id
    assert res_data["current_state"] == "COMPLETED"
    assert res_data["executed_tasks"] >= 2
    assert res_data["failed_tasks"] == 0

    # Inspect tasks returned in execution response
    tasks = res_data["tasks"]
    for t in tasks:
        assert t["status"] == "COMPLETED"
        assert t["execution_timestamp"] is not None
        assert t["result"] is not None
        assert t["error"] is None

    # Inspect refreshed session detail
    detail_resp = tc.get(f"/api/v1/sessions/{session_id}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()

    assert detail_data["current_state"] == "COMPLETED"
    assert detail_data["status"] == "COMPLETED"
    exec_state = detail_data["execution_state"]
    assert exec_state["status"] == "COMPLETED"
    assert exec_state["executed_tasks"] == res_data["executed_tasks"]


# =============================================================================
# 5. UI Route & Static Asset Verification
# =============================================================================
def test_execution_workspace_ui_and_static_asset(client):
    """Verify that the SPA route /sessions/{id}/execution and JavaScript asset are served."""
    tc, _, _ = client

    # SPA route
    page_resp = tc.get("/sessions/sess_exec_mock_01/execution")
    assert page_resp.status_code == 200
    assert "text/html" in page_resp.headers["content-type"]

    # Static script
    js_resp = tc.get("/static/js/screens/sessionExecution.js")
    assert js_resp.status_code == 200
    content = js_resp.text

    # Must contain all 10 task fields
    required_keywords = [
        "task_id",
        "task_type",
        "description",
        "status",
        "estimated_cost",
        "connector",
        "approval_status",
        "execution_timestamp",
        "result",
        "error",
        "NOT_CONFIGURED",
        "btn-dispatch-tasks",
    ]
    for kw in required_keywords:
        assert kw in content, f"Missing expected keyword in sessionExecution.js: {kw}"


# =============================================================================
# 6. Execution Connector Abstraction API Integration
# =============================================================================
def test_list_session_connectors_api(client, mock_qloo_api, monkeypatch):
    """Verify GET /api/v1/sessions/{session_id}/connectors returns registered connectors and statuses."""
    tc, _, service = client
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "spotify_client_id_live_test_123")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "spotify_client_secret_live_test_456")

    _, session_id = _create_approved_session(tc)

    resp = tc.get(f"/api/v1/sessions/{session_id}/connectors")
    assert resp.status_code == 200
    connectors = resp.json()
    assert isinstance(connectors, list)
    names = {c["name"]: c for c in connectors}

    assert "Spotify Web API" in names
    assert names["Spotify Web API"]["configuration_status"] == "CONFIGURED"
    assert names["Spotify Web API"]["capability"] == "spotify_audio_seed"

    assert "Transactional Email Engine" in names
    assert names["Transactional Email Engine"]["capability"] == "partner_outreach_brief"

    assert "Procurement Order System" in names
    assert names["Procurement Order System"]["capability"] == "procurement_order"

    # Credentials must NOT be exposed in output
    for c in connectors:
        assert "client_secret" not in c
        assert "api_key" not in c
        assert "secret" not in c


def test_execute_task_connector_lifecycle(client, mock_qloo_api, monkeypatch):
    """Verify POST /api/v1/sessions/{session_id}/tasks/{task_id}/execute dispatches with idempotency."""
    tc, _, service = client
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "valid_client_id_1234")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "valid_client_secret_5678")

    # Refresh connectors in registry with credentials
    from tasteops.connectors import create_default_registry

    service.connector_registry = create_default_registry()

    _, session_id = _create_approved_session(tc)
    detail_resp = tc.get(f"/api/v1/sessions/{session_id}")
    plan_id = detail_resp.json()["execution_plan"]["plan_id"]
    plan_version = 1

    # 1. Execute task with valid credentials
    req_body = {
        "session_id": session_id,
        "plan_id": plan_id,
        "plan_version": plan_version,
        "task_id": "task_sp_unique_01",
        "idempotency_key": "idem_unique_sp_999",
        "task_type": "spotify_audio_seed",
        "payload": {
            "artist_name": "Four Tet",
            "artist_id": "art_four_tet",
            "daypart": "evening",
        },
    }

    exec_resp = tc.post(
        f"/api/v1/sessions/{session_id}/tasks/task_sp_unique_01/execute",
        json=req_body,
    )
    assert exec_resp.status_code == 200
    res_data = exec_resp.json()
    assert res_data["task_id"] == "task_sp_unique_01"
    assert res_data["connector_name"] == "Spotify Web API"
    assert res_data["status"] == "COMPLETED"
    assert "spotify://seed_artist" in res_data["output_reference"]
    assert res_data["provenance"]["idempotency_key"] == "idem_unique_sp_999"

    # 2. Duplicate execution attempt for the same idempotency key must be rejected (409 Conflict)
    dup_resp = tc.post(
        f"/api/v1/sessions/{session_id}/tasks/task_sp_unique_01/execute",
        json=req_body,
    )
    assert dup_resp.status_code == 409
    dup_data = dup_resp.json().get("error", dup_resp.json())
    assert (
        dup_data.get("code") == "DUPLICATE_IDEMPOTENCY_KEY"
        or "duplicate" in str(dup_data).lower()
    )


def test_execute_task_connector_missing_connector_fails_explicitly(
    client, mock_qloo_api
):
    """Verify that an execution task with an unknown capability fails explicitly with 422."""
    tc, _, _ = client
    _, session_id = _create_approved_session(tc)
    detail_resp = tc.get(f"/api/v1/sessions/{session_id}")
    plan_id = detail_resp.json()["execution_plan"]["plan_id"]

    req_body = {
        "session_id": session_id,
        "plan_id": plan_id,
        "plan_version": 1,
        "task_id": "task_unknown_01",
        "idempotency_key": "idem_unknown_01",
        "task_type": "completely_unsupported_quantum_teleportation",
        "payload": {},
    }

    resp = tc.post(
        f"/api/v1/sessions/{session_id}/tasks/task_unknown_01/execute",
        json=req_body,
    )
    assert resp.status_code == 422
    data = resp.json().get("error", resp.json())
    assert data.get("code") == "MISSING_CONNECTOR" or "missing" in str(data).lower()


def test_execute_task_connector_never_fakes_unconfigured_execution(
    client, mock_qloo_api, monkeypatch
):
    """Verify that execute on an unconfigured connector fails explicitly with 422 (never fakes execution)."""
    tc, _, service = client
    # Clear Spotify credentials
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    monkeypatch.delenv("SPOTIFY_CLIENT_SECRET", raising=False)

    from tasteops.connectors import create_default_registry

    service.connector_registry = create_default_registry()

    _, session_id = _create_approved_session(tc)
    detail_resp = tc.get(f"/api/v1/sessions/{session_id}")
    plan_id = detail_resp.json()["execution_plan"]["plan_id"]

    req_body = {
        "session_id": session_id,
        "plan_id": plan_id,
        "plan_version": 1,
        "task_id": "task_sp_unconf_01",
        "idempotency_key": "idem_sp_unconf_01",
        "task_type": "spotify_audio_seed",
        "payload": {"artist_name": "Bonobo"},
    }

    resp = tc.post(
        f"/api/v1/sessions/{session_id}/tasks/task_sp_unconf_01/execute",
        json=req_body,
    )
    assert resp.status_code == 422
    data = resp.json().get("error", resp.json())
    assert data.get("code") == "NOT_CONFIGURED" or "not_configured" in str(data).lower()
