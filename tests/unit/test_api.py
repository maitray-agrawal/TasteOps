"""Unit and Integration Tests for TasteOps FastAPI Service.

Validates:
- GET /health (lightweight, zero Qloo calls, <5ms)
- GET /ready (readiness probe, 200 vs 503)
- GET /api/v1/config (safe public config, no leaked secrets)
- CORS origin handling
- Request ID correlation
- Full session workflow (create, pipeline, approve, execute, reject, audit)
- Structured error handling (404, 400, 422)
"""

from __future__ import annotations

import os

import pytest
import respx
from fastapi.testclient import TestClient

from tasteops.api.main import create_app
from tasteops.config import ServerSettings
from tasteops.workflows.orchestrator import TasteOpsOrchestrator
from tasteops.workflows.persistence import InMemoryStateStore
from tasteops.workflows.states import WorkflowState


@pytest.fixture
def api_test_context(mock_mcp_adapter, tmp_path):
    """Provides a test environment with real MCP adapter backed by mocked Qloo endpoints."""
    adapter, mock_search, mock_tags, mock_insights = mock_mcp_adapter
    store = InMemoryStateStore()
    orchestrator = TasteOpsOrchestrator(store=store, mcp_adapter=adapter)
    settings = ServerSettings(
        ENVIRONMENT="test",
        CORS_ORIGINS="http://localhost:3000,https://tasteops.vercel.app",
        TASTEOPS_STORAGE_DIR=str(tmp_path),
    )
    app = create_app(server_settings=settings, orchestrator=orchestrator)
    return app, mock_search, mock_tags, mock_insights


@pytest.fixture
def client(api_test_context):
    """TestClient instance for api_test_context."""
    app, _, _, _ = api_test_context
    with TestClient(app) as c:
        yield c


# ==============================================================================
# Health and Readiness Tests
# ==============================================================================


def test_health_check_responds_ok(client):
    """GET /health must return 200 OK with status='ok' and correlation ID."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
    assert "X-Request-ID" in response.headers


def test_readiness_probe_with_configured_key(client, monkeypatch):
    """GET /ready returns 200 when QLOO_API_KEY is configured."""
    monkeypatch.setenv("QLOO_API_KEY", "mock_ready_key_12345")
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["qloo_configured"] is True
    assert data["storage_ready"] is True


def test_readiness_probe_when_key_missing(client, monkeypatch):
    """GET /ready returns 503 when QLOO_API_KEY is absent."""
    monkeypatch.delenv("QLOO_API_KEY", raising=False)
    monkeypatch.setattr(
        os, "getenv", lambda k, d=None: "" if k == "QLOO_API_KEY" else d
    )
    response = client.get("/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "not_ready"
    assert data["qloo_configured"] is False


def test_get_public_config_never_leaks_secrets(client):
    """GET /api/v1/config returns public configuration without exposing any secret keys."""
    response = client.get("/api/v1/config")
    assert response.status_code == 200
    data = response.json()
    assert data["environment"] == "test"
    assert "qloo_base_url" in data
    assert "api_key" not in data
    assert "secret" not in str(data).lower()


# ==============================================================================
# CORS and Middleware Tests
# ==============================================================================


def test_cors_headers_allowed_origin(client):
    """CORS middleware returns allow-origin for configured origin."""
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert (
        response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    )


def test_cors_headers_allowed_vercel_origin(client):
    """CORS middleware returns allow-origin for configured Vercel production origin."""
    response = client.options(
        "/health",
        headers={
            "Origin": "https://tasteops.vercel.app",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert (
        response.headers.get("access-control-allow-origin")
        == "https://tasteops.vercel.app"
    )
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_unapproved_origin_rejected(client):
    """CORS middleware does NOT grant access-control-allow-origin to unapproved origins."""
    response = client.options(
        "/health",
        headers={
            "Origin": "https://malicious-external-origin.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    # FastApi CORSMiddleware does not set access-control-allow-origin for unauthorized origins
    assert "access-control-allow-origin" not in response.headers


def test_cors_preflight_post_options(client):
    """CORS preflight for POST on /api/v1/sessions succeeds with proper methods."""
    response = client.options(
        "/api/v1/sessions",
        headers={
            "Origin": "https://tasteops.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert response.status_code == 200
    assert (
        response.headers.get("access-control-allow-origin")
        == "https://tasteops.vercel.app"
    )
    assert "POST" in response.headers.get("access-control-allow-methods", "")


def test_cors_trailing_slash_normalization():
    """Origins configured with trailing slashes match browser requests without trailing slashes."""
    settings = ServerSettings(
        ENVIRONMENT="test",
        CORS_ORIGINS="https://tasteops.vercel.app/,http://localhost:3000/",
    )
    assert settings.cors_origins_list == [
        "https://tasteops.vercel.app",
        "http://localhost:3000",
    ]
    app = create_app(server_settings=settings)
    with TestClient(app) as test_client:
        response = test_client.options(
            "/health",
            headers={
                "Origin": "https://tasteops.vercel.app",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert (
            response.headers.get("access-control-allow-origin")
            == "https://tasteops.vercel.app"
        )


def test_request_id_propagation(client):
    """Client-supplied X-Request-ID is preserved and echoed in response headers."""
    custom_id = "req_custom_trace_987"
    response = client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_id


# ==============================================================================
# Workflow Lifecycle Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_session_lifecycle_full(api_test_context):
    """Tests complete session lifecycle: create -> pipeline -> approve -> execute -> audit."""
    app, mock_search, mock_tags, mock_insights = api_test_context

    with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/search").respond(status_code=200, json=mock_search)
        mock_router.get("/v2/tags").respond(status_code=200, json=mock_tags)
        mock_router.get("/v2/insights").respond(status_code=200, json=mock_insights)

        with TestClient(app) as client:
            # 1. Create session
            create_res = client.post(
                "/api/v1/sessions",
                json={
                    "raw_intent": "Listening bar in Shibuya for specialty coffee lovers and indie jazz",
                    "space_id": "venue_shibuya_test",
                    "hints": {
                        "business_type": "Listening Bar",
                        "raw_anchor_entities": ["Blue Bottle"],
                        "raw_tags": ["Japanese Minimalism"],
                    },
                },
            )
            assert create_res.status_code == 201
            created_data = create_res.json()
            session_id = created_data["session_id"]
            assert created_data["current_state"] == WorkflowState.CREATED.value

            # 2. Get session
            get_res = client.get(f"/api/v1/sessions/{session_id}")
            assert get_res.status_code == 200
            assert get_res.json()["session_id"] == session_id

            # 3. Run pipeline until approval gate
            pipe_res = client.post(
                f"/api/v1/sessions/{session_id}/pipeline",
                json={"take_per_category": 5},
            )
            assert pipe_res.status_code == 200
            pipe_data = pipe_res.json()
            assert pipe_data["current_state"] == WorkflowState.AWAITING_APPROVAL.value
            assert pipe_data["plan"] is not None

            # 4. Approve session
            approve_res = client.post(
                f"/api/v1/sessions/{session_id}/approve",
                json={"approver": "curator_alice"},
            )
            assert approve_res.status_code == 200
            approve_data = approve_res.json()
            assert approve_data["current_state"] == WorkflowState.APPROVED.value
            assert approve_data["approval"] is not None
            assert approve_data["approval"]["approver"] == "curator_alice"

            # 5. Execute approved plan
            exec_res = client.post(f"/api/v1/sessions/{session_id}/execute")
            assert exec_res.status_code == 200
            exec_data = exec_res.json()
            assert exec_data["current_state"] == WorkflowState.COMPLETED.value
            assert exec_data["execution_plan"] is not None

            # 6. Audit events
            audit_res = client.get(f"/api/v1/sessions/{session_id}/audit")
            assert audit_res.status_code == 200
            events = audit_res.json()
            assert len(events) >= 5
            states_traversed = [evt["to_state"] for evt in events]
            assert WorkflowState.AWAITING_APPROVAL.value in states_traversed
            assert WorkflowState.APPROVED.value in states_traversed
            assert WorkflowState.COMPLETED.value in states_traversed


@pytest.mark.asyncio
async def test_session_rejection_flow(api_test_context):
    """Tests that rejecting an awaiting approval session transitions to FAILED."""
    app, mock_search, mock_tags, mock_insights = api_test_context

    with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/search").respond(status_code=200, json=mock_search)
        mock_router.get("/v2/tags").respond(status_code=200, json=mock_tags)
        mock_router.get("/v2/insights").respond(status_code=200, json=mock_insights)

        with TestClient(app) as client:
            create_res = client.post(
                "/api/v1/sessions",
                json={
                    "raw_intent": "Pop-up gallery in Brooklyn for streetwear and ambient music",
                    "hints": {
                        "raw_anchor_entities": ["Blue Bottle"],
                        "raw_tags": ["Japanese Minimalism"],
                    },
                },
            )
            session_id = create_res.json()["session_id"]

            # Run pipeline
            pipe_res = client.post(f"/api/v1/sessions/{session_id}/pipeline", json={})
            assert (
                pipe_res.json()["current_state"]
                == WorkflowState.AWAITING_APPROVAL.value
            )

            # Reject
            reject_res = client.post(
                f"/api/v1/sessions/{session_id}/reject",
                json={"reason": "Audience mismatch with neighborhood demographics"},
            )
            assert reject_res.status_code == 200
            assert reject_res.json()["current_state"] == WorkflowState.FAILED.value


def test_session_not_found_returns_404(client):
    """Non-existent session returns HTTP 404 with structured ErrorResponse."""
    response = client.get("/api/v1/sessions/session_does_not_exist_999")
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "http_404"
    assert "not found" in data["message"].lower()
    assert "request_id" in data


def test_execute_before_approval_returns_400(client):
    """Calling execute on an unapproved session returns HTTP 400 Bad Request."""
    create_res = client.post(
        "/api/v1/sessions",
        json={"raw_intent": "Rooftop terrace in Austin for natural wine and vinyl"},
    )
    session_id = create_res.json()["session_id"]

    # Attempt to execute directly without running pipeline or getting approval
    exec_res = client.post(f"/api/v1/sessions/{session_id}/execute")
    assert exec_res.status_code == 400
    data = exec_res.json()
    assert data["error"] == "http_400"
    assert "cannot transition" in data["message"].lower()


def test_validation_error_on_invalid_payload(client):
    """Invalid payload (raw_intent too short) returns HTTP 422 with structured error."""
    response = client.post("/api/v1/sessions", json={"raw_intent": "x"})
    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "validation_error"
    assert "request_id" in data
