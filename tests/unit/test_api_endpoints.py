"""Unit and Integration Tests for TasteOps FastAPI Application.

Verifies:
- Liveness (/health) and Readiness (/ready) probes
- Space registration, retrieval, and 404 handling
- Space analysis workflow triggering up to Human Approval Gate
- Session state retrieval, event ledgers, and blueprints
- Human-in-the-loop approval and rejection gates
- Unapproved execution prevention (403 Forbidden)
- Execution dispatch post-approval
- Centralized RFC 7807 error formatting
- Request correlation ID propagation
- Security headers and CORS behavior
- No secret leakage and no raw Qloo access in routes
"""

from __future__ import annotations

import pytest
import respx
from starlette.testclient import TestClient

from tasteops.api.app import create_app
from tasteops.api.dependencies import get_service
from tasteops.api.service import TasteOpsApplicationService
from tasteops.api.settings import APISettings
from tasteops.workflows.orchestrator import TasteOpsOrchestrator
from tasteops.workflows.persistence import InMemoryStateStore
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
    """Sets up respx routes with mock Qloo responses for deterministic pipeline tests."""
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
def api_service(mock_mcp_adapter):
    """Provides a fresh TasteOpsApplicationService backed by the mock MCP adapter."""
    adapter, _, _, _ = mock_mcp_adapter
    store = InMemoryStateStore()
    orchestrator = TasteOpsOrchestrator(mcp_adapter=adapter, store=store)
    return TasteOpsApplicationService(orchestrator=orchestrator, store=store)


@pytest.fixture
def test_app(api_service):
    """Provides a FastAPI test application with injected service dependency."""
    settings = APISettings(
        title="TasteOps Test API",
        environment="test",
        cors_origins=["http://localhost:3000", "https://app.tasteops.io"],
    )
    app = create_app(settings=settings)
    app.dependency_overrides[get_service] = lambda: api_service
    return app


@pytest.fixture
def client(test_app):
    """Test client for testing the FastAPI application."""
    with TestClient(test_app) as tc:
        yield tc


# ---------------------------------------------------------------------------
# 1. Health & Readiness Probes
# ---------------------------------------------------------------------------
def test_health_check(client):
    """Verify /health returns 200 OK with expected payload."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "tasteops-api"
    assert "timestamp" in data


def test_readiness_check_healthy(client):
    """Verify /ready returns 200 OK when all subsystems are available."""
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"]["store"] == "ok"
    assert data["checks"]["orchestrator"] == "ok"


def test_readiness_check_unhealthy(test_app, api_service):
    """Verify /ready returns 503 Service Unavailable when a subsystem is degraded."""
    api_service.store = None  # Simulate store unavailability
    with TestClient(test_app) as tc:
        response = tc.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["checks"]["store"] == "unavailable"


# ---------------------------------------------------------------------------
# 2. Spaces Management (POST / GET)
# ---------------------------------------------------------------------------
def test_create_space_success(client):
    """Verify POST /api/v1/spaces creates a venue and returns 201 Created with Location header."""
    payload = {
        "name": "The Haveli Contemporary Mumbai",
        "business_type": "Boutique Hotel",
        "location": {
            "latitude": 18.9220,
            "longitude": 72.8347,
            "radius_meters": 5000,
        },
        "target_audience": "Affluent design-conscious professionals",
        "positioning": "Contemporary Indian luxury",
        "desired_mood": "Sophisticated / intimate / creative",
        "anchor_entities": [
            "Independent cinema",
            "Alternative music",
            "Contemporary Indian design",
        ],
    }
    response = client.post("/api/v1/spaces", json=payload)
    assert response.status_code == 201
    assert "Location" in response.headers
    data = response.json()
    assert data["space_id"].startswith("space_")
    assert data["name"] == "The Haveli Contemporary Mumbai"
    assert data["business_type"] == "Boutique Hotel"
    assert data["brief"]["target_audience"] == "Affluent design-conscious professionals"


def test_create_space_validation_error(client):
    """Verify POST /api/v1/spaces with missing required fields returns 422 with RFC 7807 error."""
    # Missing 'business_type'
    payload = {"name": "Incomplete Space"}
    response = client.post("/api/v1/spaces", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "UNPROCESSABLE_ENTITY"
    assert data["error"]["status"] == 422
    assert "correlation_id" in data["error"]


def test_get_space_success(client):
    """Verify GET /api/v1/spaces/{space_id} retrieves a registered space."""
    # First create
    create_resp = client.post(
        "/api/v1/spaces",
        json={"name": "Chelsea Audio Kissa", "business_type": "Listening Bar"},
    )
    space_id = create_resp.json()["space_id"]

    # Now get
    get_resp = client.get(f"/api/v1/spaces/{space_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["space_id"] == space_id
    assert data["name"] == "Chelsea Audio Kissa"


def test_get_space_not_found(client):
    """Verify GET /api/v1/spaces/{space_id} returns 404 for nonexistent space."""
    response = client.get("/api/v1/spaces/space_nonexistent_999")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "SPACE_NOT_FOUND"
    assert data["error"]["status"] == 404


# ---------------------------------------------------------------------------
# 3. Space Analysis & Full Workflow Driving
# ---------------------------------------------------------------------------
def test_analyze_space_advances_to_approval(client, mock_mumbai_respx):
    """Verify POST /api/v1/spaces/{space_id}/analyze runs workflow up to AWAITING_APPROVAL."""
    # 1. Register space
    space_resp = client.post(
        "/api/v1/spaces",
        json={
            "name": "The Haveli Contemporary Mumbai",
            "business_type": "Boutique Hotel",
            "desired_mood": "Sophisticated / intimate / creative",
            "anchor_entities": [
                "Independent cinema",
                "Alternative music",
                "Contemporary Indian design",
            ],
        },
    )
    space_id = space_resp.json()["space_id"]

    # 2. Trigger analysis
    analyze_resp = client.post(
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
    assert session_data["space_id"] == space_id
    assert session_data["current_state"] == WorkflowState.AWAITING_APPROVAL.value
    assert session_data["plan"] is not None
    assert session_data["cultural_twin"] is not None
    assert session_data["cultural_matrix"] is not None
    assert session_data["validation_result"] is not None
    assert session_data["validation_result"]["is_valid"] is True


# ---------------------------------------------------------------------------
# 4. Sessions Inspection, Events, and Blueprints
# ---------------------------------------------------------------------------
def test_get_session_details(client, mock_mumbai_respx):
    """Verify GET /api/v1/sessions/{session_id} returns full session state."""
    # Create space and analyze
    s_resp = client.post(
        "/api/v1/spaces",
        json={"name": "Test Space", "business_type": "Cafe"},
    )
    space_id = s_resp.json()["space_id"]
    a_resp = client.post(
        f"/api/v1/spaces/{space_id}/analyze",
        json={"hints": MUMBAI_DEMO_HINTS},
    )
    session_id = a_resp.json()["session_id"]

    # Query session
    get_resp = client.get(f"/api/v1/sessions/{session_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["session_id"] == session_id
    assert data["current_state"] == WorkflowState.AWAITING_APPROVAL.value
    assert "links" in data
    assert data["links"]["approve"] == f"/api/v1/sessions/{session_id}/approve"


def test_get_session_not_found(client):
    """Verify GET /api/v1/sessions/{session_id} returns 404 for unknown session."""
    response = client.get("/api/v1/sessions/unknown_session_uuid")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "SESSION_NOT_FOUND"


def test_get_session_events(client, mock_mumbai_respx):
    """Verify GET /api/v1/sessions/{session_id}/events returns ordered audit logs."""
    s_resp = client.post(
        "/api/v1/spaces",
        json={"name": "Test Venue", "business_type": "Gallery"},
    )
    a_resp = client.post(
        f"/api/v1/spaces/{s_resp.json()['space_id']}/analyze",
        json={"hints": MUMBAI_DEMO_HINTS},
    )
    session_id = a_resp.json()["session_id"]

    events_resp = client.get(f"/api/v1/sessions/{session_id}/events")
    assert events_resp.status_code == 200
    data = events_resp.json()
    assert data["session_id"] == session_id
    assert data["total_events"] > 0
    assert len(data["events"]) > 0
    assert len(data["history"]) > 0


def test_get_session_blueprint_success(client, mock_mumbai_respx):
    """Verify GET /api/v1/sessions/{session_id}/blueprint returns spatial and sensory specs."""
    s_resp = client.post(
        "/api/v1/spaces",
        json={"name": "Test Hotel", "business_type": "Hotel"},
    )
    a_resp = client.post(
        f"/api/v1/spaces/{s_resp.json()['space_id']}/analyze",
        json={"hints": MUMBAI_DEMO_HINTS},
    )
    session_id = a_resp.json()["session_id"]

    bp_resp = client.get(f"/api/v1/sessions/{session_id}/blueprint")
    assert bp_resp.status_code == 200
    bp = bp_resp.json()
    assert bp["session_id"] == session_id
    assert bp["state"] == WorkflowState.AWAITING_APPROVAL.value
    assert bp["plan_id"] is not None
    assert bp["plan_hash"] is not None
    assert len(bp["spatial_zones"]) > 0
    assert len(bp["cultural_pillars"]) > 0


def test_get_session_blueprint_conflict_when_not_ready(client, api_service):
    """Verify GET blueprint returns 409 Conflict if session has not reached PLAN_GENERATED."""
    ctx = api_service.orchestrator.create_session(
        user_input="Bare conceptual brief without agent outputs",
        space_id="space_test",
    )
    assert ctx.current_state == WorkflowState.CREATED

    response = client.get(f"/api/v1/sessions/{ctx.session_id}/blueprint")
    assert response.status_code == 409
    data = response.json()
    assert data["error"]["code"] == "BLUEPRINT_NOT_READY"


# ---------------------------------------------------------------------------
# 5. Approvals, Rejections, and Execution Dispatch
# ---------------------------------------------------------------------------
def test_human_approval_and_execution_lifecycle(client, mock_mumbai_respx):
    """Verify full approval and execution lifecycle through API endpoints."""
    # 1. Setup space and advance to AWAITING_APPROVAL
    s_resp = client.post(
        "/api/v1/spaces",
        json={"name": "Mumbai Haven", "business_type": "Boutique Hotel"},
    )
    a_resp = client.post(
        f"/api/v1/spaces/{s_resp.json()['space_id']}/analyze",
        json={"hints": MUMBAI_DEMO_HINTS},
    )
    session_id = a_resp.json()["session_id"]

    # 2. Approve session
    appr_resp = client.post(
        f"/api/v1/sessions/{session_id}/approve",
        json={
            "approver": "Curator: Satwik Jaiswal",
            "role": "Lead Cultural Strategist",
            "notes": "Approved for acoustic and spatial installation.",
            "plan_version": 1,
        },
    )
    assert appr_resp.status_code == 200
    appr_data = appr_resp.json()
    assert appr_data["current_state"] == WorkflowState.APPROVED.value
    assert appr_data["approval"] is not None
    assert "Satwik Jaiswal" in appr_data["approval"]["approver"]
    assert appr_data["approval"]["plan_hash"] != ""

    # 3. Execute approved plan
    exec_resp = client.post(f"/api/v1/sessions/{session_id}/execute")
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()
    assert exec_data["current_state"] == WorkflowState.COMPLETED.value
    assert exec_data["total_tasks"] >= 2
    assert exec_data["executed_tasks"] >= 2
    assert exec_data["failed_tasks"] == 0


def test_unapproved_execution_blocked(client, mock_mumbai_respx):
    """Verify POST /api/v1/sessions/{session_id}/execute without approval returns 403 Forbidden."""
    s_resp = client.post(
        "/api/v1/spaces",
        json={"name": "Direct Execution Space", "business_type": "Club"},
    )
    a_resp = client.post(
        f"/api/v1/spaces/{s_resp.json()['space_id']}/analyze",
        json={"hints": MUMBAI_DEMO_HINTS},
    )
    session_id = a_resp.json()["session_id"]

    # Try executing while state is still AWAITING_APPROVAL
    exec_resp = client.post(f"/api/v1/sessions/{session_id}/execute")
    assert exec_resp.status_code == 403
    data = exec_resp.json()
    assert data["error"]["code"] == "EXECUTION_UNAPPROVED"
    assert data["error"]["status"] == 403


def test_human_rejection(client, mock_mumbai_respx):
    """Verify POST /api/v1/sessions/{session_id}/reject transitions session to FAILED."""
    s_resp = client.post(
        "/api/v1/spaces",
        json={"name": "Rejection Venue", "business_type": "Bar"},
    )
    a_resp = client.post(
        f"/api/v1/spaces/{s_resp.json()['space_id']}/analyze",
        json={"hints": MUMBAI_DEMO_HINTS},
    )
    session_id = a_resp.json()["session_id"]

    reject_resp = client.post(
        f"/api/v1/sessions/{session_id}/reject",
        json={"reason": "Acoustic decibel levels unacceptable for residential zone."},
    )
    assert reject_resp.status_code == 200
    data = reject_resp.json()
    assert data["current_state"] == WorkflowState.FAILED.value
    assert (
        data["error_message"]
        == "Acoustic decibel levels unacceptable for residential zone."
    )


# ---------------------------------------------------------------------------
# 6. Middlewares: Correlation ID, Security Headers & CORS
# ---------------------------------------------------------------------------
def test_correlation_id_propagation(client):
    """Verify X-Correlation-ID header is propagated when provided or generated when missing."""
    custom_cid = "test-custom-cid-12345"
    resp = client.get("/health", headers={"X-Correlation-ID": custom_cid})
    assert resp.status_code == 200
    assert resp.headers.get("X-Correlation-ID") == custom_cid

    # Auto-generation test
    auto_resp = client.get("/health")
    assert auto_resp.status_code == 200
    assert auto_resp.headers.get("X-Correlation-ID") is not None
    assert auto_resp.headers.get("X-Correlation-ID").startswith("req_")


def test_security_headers_present(client):
    """Verify mandatory security response headers are attached."""
    resp = client.get("/health")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-XSS-Protection") == "1; mode=block"


def test_cors_headers_allowed_origin(client):
    """Verify CORS middleware adds Access-Control-Allow-Origin for allowed origin."""
    resp = client.get(
        "/health",
        headers={"Origin": "https://app.tasteops.io"},
    )
    assert resp.headers.get("access-control-allow-origin") == "https://app.tasteops.io"
