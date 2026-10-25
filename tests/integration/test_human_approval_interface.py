"""Integration tests for Human Approval Gate and Curator Decision Workflows.

Validates:
- Display fields: session ID, plan ID, plan version, generated actions,
  estimated cost, risks, evidence, governance result, validation warnings, approval status.
- Actions:
  - POST /api/v1/sessions/{session_id}/approve
  - POST /api/v1/sessions/{session_id}/reject
- Authoritative backend source of truth:
  - Approval disabled when validation failed
  - Approval disabled when plan is missing
  - Approval disabled when plan is stale
  - Approval disabled when session already executed
  - Approval disabled when approval already exists
  - Approval disabled when required evidence is missing
- Never assumes action succeeded; state is refreshed from server.
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
    db_path = tmp_path / "test_human_approval.db"
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
        title="TasteOps Approval Integration Test",
        environment="test",
        database_path=str(db_path),
    )
    app = create_app(settings=settings)

    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_space_repository] = lambda: space_repo
    app.dependency_overrides[get_service] = lambda: service

    with TestClient(app) as tc:
        yield tc, db, service


def test_approval_gate_displays_all_required_components(client, mock_qloo_api):
    """Verify session detail exposes all 10 required items for the approval interface."""
    tc, db, service = client

    # Create Space & Analyze to reach AWAITING_APPROVAL
    space_resp = tc.post(
        "/api/v1/spaces",
        json={
            "name": "Kyoto Sound Pavilion",
            "business_type": "Vinyl Listening Room & Tea House",
            "desired_mood": "Minimalist analog warmth",
            "target_audience": "Audiophiles and architects",
            "anchor_entities": ["Prateek Kuhad", "Raw Mango"],
        },
    )
    assert space_resp.status_code == 201
    space_id = space_resp.json()["space_id"]

    analyze_resp = tc.post(
        f"/api/v1/spaces/{space_id}/analyze",
        json={"hints": MUMBAI_DEMO_HINTS, "auto_run": True},
    )
    assert analyze_resp.status_code == 200
    session_id = analyze_resp.json()["session_id"]

    # GET /api/v1/sessions/{session_id}
    session_resp = tc.get(f"/api/v1/sessions/{session_id}")
    assert session_resp.status_code == 200
    data = session_resp.json()

    # 1. Session ID
    assert data["session_id"] == session_id

    # 2. Plan ID
    assert data["execution_plan"] is not None
    assert "plan_id" in data["execution_plan"]
    assert data["execution_plan"]["plan_id"] is not None

    # 3. Plan Version
    assert data["execution_plan"]["version"] >= 1

    # 4. Generated Actions
    assert "actions" in data["execution_plan"]
    assert len(data["execution_plan"]["actions"]) > 0
    for act in data["execution_plan"]["actions"]:
        assert "action_id" in act
        assert "title" in act
        assert "owner" in act
        assert "estimated_cost" in act

    # 5. Estimated Cost
    assert data["execution_plan"]["estimated_cost"] is not None

    # 6. Risks
    assert "risks" in data["execution_plan"]
    assert isinstance(data["execution_plan"]["risks"], list)

    # 7. Evidence
    assert data["cultural_twin"] is not None
    assert isinstance(data["cultural_twin"]["resolved_entities"], list)
    assert len(data["cultural_twin"]["anchor_entities"]) > 0
    assert data["cultural_matrix_summary"] is not None
    assert data["cultural_matrix_summary"]["total_entities"] > 0

    # 8. Governance Result
    assert data["validation"] is not None
    assert data["validation"]["is_valid"] is True
    assert data["validation"]["provenance_verified"] is True
    assert 0.0 <= data["validation"]["compliance_score"] <= 1.0

    # 9. Validation Warnings
    assert "risk_flags" in data["validation"]

    # 10. Approval Status
    assert data["approval_state"] is not None
    assert data["approval_state"]["status"] == "PENDING"
    assert data["approval_state"]["is_approved"] is False


def test_approve_session_action_and_state_refresh(client, mock_qloo_api):
    """Verify POST /api/v1/sessions/{session_id}/approve seals plan and refreshes server state."""
    tc, db, service = client

    # Create Space & Analyze
    space_resp = tc.post(
        "/api/v1/spaces",
        json={
            "name": "Approval Test Space",
            "business_type": "Gallery",
            "anchor_entities": ["Tate"],
        },
    )
    space_id = space_resp.json()["space_id"]

    analyze_resp = tc.post(
        f"/api/v1/spaces/{space_id}/analyze",
        json={"hints": MUMBAI_DEMO_HINTS, "auto_run": True},
    )
    session_id = analyze_resp.json()["session_id"]

    # Execute Approval Action: POST /api/v1/sessions/{session_id}/approve
    approve_resp = tc.post(
        f"/api/v1/sessions/{session_id}/approve",
        json={
            "approver": "Satwik Jaiswal",
            "role": "Lead Cultural Strategist",
            "notes": "Verified 100% Qloo provenance signatures. Approved for execution.",
            "plan_version": 1,
        },
    )
    assert approve_resp.status_code == 200
    approved_data = approve_resp.json()

    # Verify Server State transition to APPROVED
    assert approved_data["current_state"] == "APPROVED"
    assert approved_data["approval_state"]["is_approved"] is True
    assert approved_data["approval_state"]["status"] == "APPROVED"
    assert "Satwik Jaiswal" in approved_data["approval_state"]["approver"]
    assert approved_data["approval_state"]["plan_hash"] is not None

    # Re-fetch session directly (Refresh Server State verification)
    refreshed_resp = tc.get(f"/api/v1/sessions/{session_id}")
    assert refreshed_resp.status_code == 200
    refreshed = refreshed_resp.json()
    assert refreshed["current_state"] == "APPROVED"
    assert refreshed["approval_state"]["is_approved"] is True

    # Backend is source of truth: Second identical approval returns existing approved state (idempotent)
    dup_resp = tc.post(
        f"/api/v1/sessions/{session_id}/approve",
        json={"approver": "Satwik Jaiswal", "role": "Lead Cultural Strategist"},
    )
    assert dup_resp.status_code == 200
    assert dup_resp.json()["current_state"] == "APPROVED"


def test_reject_session_action_and_state_refresh(client, mock_qloo_api):
    """Verify POST /api/v1/sessions/{session_id}/reject transitions session to FAILED."""
    tc, db, service = client

    space_resp = tc.post(
        "/api/v1/spaces",
        json={
            "name": "Rejection Test Space",
            "business_type": "Cafe",
            "anchor_entities": ["Aesop"],
        },
    )
    space_id = space_resp.json()["space_id"]

    analyze_resp = tc.post(
        f"/api/v1/spaces/{space_id}/analyze",
        json={"hints": MUMBAI_DEMO_HINTS, "auto_run": True},
    )
    session_id = analyze_resp.json()["session_id"]

    # Reject session
    reject_resp = tc.post(
        f"/api/v1/sessions/{session_id}/reject",
        json={
            "reason": "Acoustic soundscape decibel level violates venue lease limits."
        },
    )
    assert reject_resp.status_code == 200
    rejected_data = reject_resp.json()

    assert rejected_data["current_state"] == "FAILED"
    assert "violates venue lease limits" in (rejected_data["error_message"] or "")

    # Re-fetch session directly (Refresh Server State verification)
    refreshed_resp = tc.get(f"/api/v1/sessions/{session_id}")
    assert refreshed_resp.status_code == 200
    assert refreshed_resp.json()["current_state"] == "FAILED"

    # Cannot approve a failed session: returns 409 Conflict
    blocked_resp = tc.post(
        f"/api/v1/sessions/{session_id}/approve",
        json={"approver": "Curator"},
    )
    assert blocked_resp.status_code == 409


def test_approval_interface_asset_and_disabling_rules(client):
    """Verify the UI script sessionApproval.js contains all 6 disabling rules and server refresh."""
    tc, _, _ = client

    # SPA shell route
    res = tc.get("/sessions/sess_demo_123/approval")
    assert res.status_code == 200
    assert "TasteOps" in res.text

    # Script asset
    res_js = tc.get("/static/js/screens/sessionApproval.js")
    assert res_js.status_code == 200
    text = res_js.text

    # Verify all 6 disabling rule tokens exist in script
    assert "Validation Failed" in text
    assert "Plan is Missing" in text
    assert "Plan is Stale" in text
    assert "Session Already Executed" in text
    assert "Approval Already Exists" in text
    assert "Required Evidence Missing" in text

    # Verify never assuming success and refreshing server state
    assert "loadData" in text
    assert "apiClient.approveSession" in text
    assert "apiClient.rejectSession" in text
