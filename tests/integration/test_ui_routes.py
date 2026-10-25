"""Integration tests for TasteOps UI routes and static asset serving.

Verifies:
- All canonical workspace screens serve the single-page application shell:
  1. /
  2. /dashboard
  3. /spaces/new
  4. /spaces/[spaceId]
  5. /sessions/[sessionId]
  6. /sessions/[sessionId]/activity
  7. /sessions/[sessionId]/blueprint
  8. /sessions/[sessionId]/approval
  9. /sessions/[sessionId]/execution
  10. /sessions/[sessionId]/ledger
- Static CSS and JavaScript asset resolution (/static/css/index.css, /static/js/app.js, etc.)
- Missing static assets return 404
- Security check: No provider API keys or connection strings in frontend static files
- Full end-to-end API lifecycle:
  Create session → pipeline → approval gate → execute → audit trail
- Invalid/unapproved execution gate enforcement
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tasteops.api.main import create_app
from tasteops.config import ServerSettings
from tasteops.workflows.orchestrator import TasteOpsOrchestrator
from tasteops.workflows.persistence import InMemoryStateStore
from tasteops.workflows.states import WorkflowState


@pytest.fixture
def ui_test_client(mock_mcp_adapter, tmp_path):
    """Provides a TestClient initialized with orchestrator and mock MCP adapter."""
    adapter, _, _, _ = mock_mcp_adapter
    store = InMemoryStateStore()
    orchestrator = TasteOpsOrchestrator(store=store, mcp_adapter=adapter)
    settings = ServerSettings(
        ENVIRONMENT="test",
        TASTEOPS_STORAGE_DIR=str(tmp_path),
    )
    app = create_app(server_settings=settings, orchestrator=orchestrator)
    with TestClient(app) as client:
        yield client


# =============================================================================
# 1. Workspace Screen Route Tests
# =============================================================================
@pytest.mark.parametrize(
    "route_path",
    [
        "/",
        "/dashboard",
        "/spaces/new",
        "/spaces/space_demo_123",
        "/sessions/sess_demo_123",
        "/sessions/sess_demo_123/activity",
        "/sessions/sess_demo_123/blueprint",
        "/sessions/sess_demo_123/approval",
        "/sessions/sess_demo_123/execution",
        "/sessions/sess_demo_123/ledger",
    ],
)
def test_all_canonical_screens_served_by_fastapi(ui_test_client, route_path):
    """Verifies all required workspace screen routes return HTTP 200 and the HTML SPA shell."""
    resp = ui_test_client.get(route_path)
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "<title>TasteOps — AI Operations Workspace</title>" in resp.text
    assert 'id="app-nav"' in resp.text
    assert 'id="app-main"' in resp.text
    assert 'src="/static/js/app.js"' in resp.text


# =============================================================================
# 2. Static Asset Resolution Tests
# =============================================================================
@pytest.mark.parametrize(
    "asset_path,content_type_substr",
    [
        ("/static/css/index.css", "text/css"),
        ("/static/js/app.js", "javascript"),
        ("/static/js/apiClient.js", "javascript"),
        ("/static/js/router.js", "javascript"),
        ("/static/js/components/nav.js", "javascript"),
        ("/static/js/components/ui.js", "javascript"),
        ("/static/js/screens/dashboard.js", "javascript"),
        ("/static/js/screens/spaceNew.js", "javascript"),
        ("/static/js/screens/spaceDetail.js", "javascript"),
        ("/static/js/screens/sessionDetail.js", "javascript"),
        ("/static/js/screens/sessionActivity.js", "javascript"),
        ("/static/js/screens/sessionBlueprint.js", "javascript"),
        ("/static/js/screens/sessionApproval.js", "javascript"),
        ("/static/js/screens/sessionExecution.js", "javascript"),
        ("/static/js/screens/sessionLedger.js", "javascript"),
    ],
)
def test_static_assets_served_correctly(
    ui_test_client, asset_path, content_type_substr
):
    """Verifies all CSS stylesheets and ES module scripts resolve with valid mime types."""
    resp = ui_test_client.get(asset_path)
    assert resp.status_code == 200
    assert content_type_substr in resp.headers["content-type"]
    assert len(resp.text) > 50


def test_missing_static_asset_returns_404(ui_test_client):
    """Verifies requesting non-existent static file returns 404."""
    resp = ui_test_client.get("/static/js/nonexistent_file.js")
    assert resp.status_code == 404


# =============================================================================
# 3. Security Verification: No Secrets Exposed to Browser
# =============================================================================
def test_no_provider_secrets_exposed_in_frontend():
    """Verifies that provider API keys and database URLs are never written into static frontend assets."""
    static_root = (
        Path(__file__).resolve().parent.parent.parent
        / "src"
        / "tasteops"
        / "api"
        / "static"
    )
    assert static_root.exists(), f"Static root not found at {static_root}"

    forbidden_patterns = [
        "QLOO_API_KEY",
        "GROQ_API_KEY",
        "GEMINI_API_KEY",
        "DATABASE_URL",
        "sk-ant",
        "ghp_",
    ]

    for file_path in static_root.rglob("*"):
        if file_path.is_file():
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            for pattern in forbidden_patterns:
                assert pattern not in text, (
                    f"Found sensitive secret pattern '{pattern}' in {file_path}"
                )


# =============================================================================
# 4. End-to-End UI API Workflow Integration
# =============================================================================
def test_end_to_end_ui_api_flow(ui_test_client):
    """Verifies full create session -> pipeline -> approval -> execute -> audit flow."""
    # 1. Create Session
    create_payload = {
        "raw_intent": "Curate an analog vinyl listening lounge and tea room in Tokyo Shibuya.",
        "space_id": "shibuya_vinyl_01",
        "hints": {
            "desired_mood": "Reflective, acoustic, minimal",
            "business_type": "Listening Bar",
        },
    }
    resp = ui_test_client.post("/api/v1/sessions", json=create_payload)
    assert resp.status_code == 201
    session_data = resp.json()
    session_id = session_data["session_id"]
    assert session_data["current_state"] == WorkflowState.CREATED.value

    # 2. Run Pipeline to Approval Gate
    pipe_resp = ui_test_client.post(
        f"/api/v1/sessions/{session_id}/pipeline",
        json={"take_per_category": 10},
    )
    assert pipe_resp.status_code == 200
    pipe_data = pipe_resp.json()
    assert pipe_data["current_state"] == WorkflowState.AWAITING_APPROVAL.value
    assert pipe_data["plan"] is not None
    assert pipe_data["cultural_matrix"] is not None

    # 3. Verify premature execution is rejected with HTTP 400
    exec_premature = ui_test_client.post(
        f"/api/v1/sessions/{session_id}/execute", json={}
    )
    assert exec_premature.status_code == 400
    err_body = exec_premature.json()
    assert "error" in err_body
    assert "message" in err_body

    # 4. Approve session
    approve_resp = ui_test_client.post(
        f"/api/v1/sessions/{session_id}/approve",
        json={"approver": "Senior Curator Satwik"},
    )
    assert approve_resp.status_code == 200
    approved_data = approve_resp.json()
    assert approved_data["current_state"] == WorkflowState.APPROVED.value
    assert approved_data["approval"]["approver"] == "Senior Curator Satwik"

    # 5. Execute approved session
    exec_resp = ui_test_client.post(f"/api/v1/sessions/{session_id}/execute", json={})
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()
    assert exec_data["current_state"] == WorkflowState.COMPLETED.value
    assert len(exec_data["execution_tasks"]) > 0

    # 6. Audit ledger retrieval
    audit_resp = ui_test_client.get(f"/api/v1/sessions/{session_id}/audit")
    assert audit_resp.status_code == 200
    events = audit_resp.json()
    assert isinstance(events, list)
    assert len(events) >= 5

    states = [e["to_state"] for e in events]
    assert WorkflowState.CREATED.value in states
    assert WorkflowState.AWAITING_APPROVAL.value in states
    assert WorkflowState.APPROVED.value in states
    assert WorkflowState.COMPLETED.value in states


def test_reject_session_flow(ui_test_client):
    """Verifies plan rejection transitions workflow to FAILED state."""
    # 1. Create Session
    resp = ui_test_client.post(
        "/api/v1/sessions",
        json={"raw_intent": "Curate an underground experimental sound dome."},
    )
    assert resp.status_code == 201
    session_id = resp.json()["session_id"]

    # 2. Run Pipeline
    pipe_resp = ui_test_client.post(
        f"/api/v1/sessions/{session_id}/pipeline",
        json={"take_per_category": 5},
    )
    assert pipe_resp.status_code == 200
    assert pipe_resp.json()["current_state"] == WorkflowState.AWAITING_APPROVAL.value

    # 3. Reject Session
    reject_resp = ui_test_client.post(
        f"/api/v1/sessions/{session_id}/reject",
        json={"reason": "Sonic profile conflicts with neighborhood zoning laws."},
    )
    assert reject_resp.status_code == 200
    failed_data = reject_resp.json()
    assert failed_data["current_state"] == WorkflowState.FAILED.value
    assert "Sonic profile conflicts" in failed_data["error_message"]


# =============================================================================
# 5. Frontend & Backend Data Integrity Regression Tests (Phase 5)
# =============================================================================
def test_frontend_integrity_no_fabricated_verifications_or_merkle_claims():
    """Verifies frontend code does not fabricate audit verification or Merkle claims."""
    static_root = (
        Path(__file__).resolve().parent.parent.parent
        / "src"
        / "tasteops"
        / "api"
        / "static"
        / "js"
    )
    api_client_text = (static_root / "apiClient.js").read_text(encoding="utf-8")
    ledger_text = (static_root / "screens" / "sessionLedger.js").read_text(
        encoding="utf-8"
    )

    # 1. No unconditional is_verified: true or synthetic sha256:<event_id>
    assert "is_verified: true" not in api_client_text
    assert "sha256:${events[0]" not in api_client_text
    assert "SHA-256 (Merkle / Chained Digests)" not in api_client_text

    # 2. Must return explicit unavailable verification state
    assert "status: 'UNAVAILABLE'" in api_client_text
    assert "is_verified: false" in api_client_text

    # 3. Ledger UI must clearly state stored audit log when hash-chain is unavailable
    assert "STORED AUDIT LOG (HASH-CHAIN UNAVAILABLE)" in ledger_text
    assert (
        "Cryptographic hash-chain and Merkle ledger verification are not currently supported"
        in ledger_text
    )


def test_frontend_integrity_no_fabricated_confidence_or_affinity_defaults():
    """Verifies that missing confidence and affinity scores remain unavailable rather than defaulted."""
    static_root = (
        Path(__file__).resolve().parent.parent.parent
        / "src"
        / "tasteops"
        / "api"
        / "static"
        / "js"
    )

    blueprint_text = (static_root / "screens" / "sessionBlueprint.js").read_text(
        encoding="utf-8"
    )
    detail_text = (static_root / "screens" / "sessionDetail.js").read_text(
        encoding="utf-8"
    )
    api_client_text = (static_root / "apiClient.js").read_text(encoding="utf-8")

    # No fabricated confidence: 1.0 or 0.92/0.95 defaults
    assert "confidence: 1.0" not in api_client_text
    assert "affinity_score: 1.0" not in api_client_text
    assert "blueprint.confidence : 0.92" not in blueprint_text
    assert "ent.confidence || 1.0" not in detail_text
    assert "ct.confidence : 1.0" not in detail_text
    assert "qloo_sig_verified" not in blueprint_text


def test_frontend_integrity_no_fabricated_costs_or_mock_status():
    """Verifies missing costs are never represented as genuine $0 or fake budgets, and mock status is not hardcoded."""
    static_root = (
        Path(__file__).resolve().parent.parent.parent
        / "src"
        / "tasteops"
        / "api"
        / "static"
        / "js"
    )

    api_client_text = (static_root / "apiClient.js").read_text(encoding="utf-8")
    blueprint_text = (static_root / "screens" / "sessionBlueprint.js").read_text(
        encoding="utf-8"
    )
    approval_text = (static_root / "screens" / "sessionApproval.js").read_text(
        encoding="utf-8"
    )
    exec_text = (static_root / "screens" / "sessionExecution.js").read_text(
        encoding="utf-8"
    )

    # apiClient must not hardcode is_mock: false
    assert "is_mock: false" not in api_client_text

    # No fallback $150,000 USD or universal $0 fallback for unknown costs
    assert "blueprint.estimated_cost || '$150,000 USD'" not in blueprint_text
    assert "session.plan?.estimated_cost || '$150,000 USD'" not in approval_text
    assert "plan.estimated_cost || '$12,500 total'" not in exec_text
    assert "task.estimated_cost || '$0'" not in exec_text


def test_frontend_integrity_authoritative_approval_derivation(ui_test_client):
    """Verifies approval state derivation strictly depends on authoritative backend state."""
    static_root = (
        Path(__file__).resolve().parent.parent.parent
        / "src"
        / "tasteops"
        / "api"
        / "static"
        / "js"
    )
    api_client_text = (static_root / "apiClient.js").read_text(encoding="utf-8")

    # Authoritative derivation in _normalizeSession
    assert "isAuthoritativelyApproved" in api_client_text
    assert "context.approval.is_valid && context.approval.plan_hash" in api_client_text

    # Verify backend approval gate rejects premature execution
    resp = ui_test_client.post(
        "/api/v1/sessions",
        json={"raw_intent": "Auditing approval gate security boundary."},
    )
    session_id = resp.json()["session_id"]
    ui_test_client.post(f"/api/v1/sessions/{session_id}/pipeline", json={})

    # Cannot execute while in AWAITING_APPROVAL even if client simulates approval
    exec_attempt = ui_test_client.post(
        f"/api/v1/sessions/{session_id}/execute", json={}
    )
    assert exec_attempt.status_code == 400


def test_audit_events_are_stored_logs_not_fabricated_merkle_digests(ui_test_client):
    """Verifies audit events use real event IDs (evt_...) and do not fabricate cryptographic hash chaining."""
    resp = ui_test_client.post(
        "/api/v1/sessions",
        json={"raw_intent": "Verify audit log integrity without synthetic hashes."},
    )
    session_id = resp.json()["session_id"]
    ui_test_client.post(f"/api/v1/sessions/{session_id}/pipeline", json={})

    audit_resp = ui_test_client.get(f"/api/v1/sessions/{session_id}/audit")
    assert audit_resp.status_code == 200
    events = audit_resp.json()
    assert len(events) > 0

    for ev in events:
        event_id = ev["event_id"]
        # Event IDs are UUID-based prefixed identifiers, NOT SHA-256 digests
        assert event_id.startswith("evt_")
        assert len(event_id) != 64  # Not a 64-character SHA-256 hex string
        # Backend does not provide fake verification_hash or Merkle root
        assert "verification_hash" not in ev
        assert "merkle_root" not in ev
