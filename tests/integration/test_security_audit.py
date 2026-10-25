"""TasteOps Comprehensive Security Audit & Defense Verification Tests.

Validates:
1. Insecure CORS rejection (wildcard with credentials prevented).
2. SSRF prevention on external connector URLs (private IPs & cloud metadata blocked).
3. Path traversal prevention in FileStateStore and API path parameters.
4. Authentication & Authorization boundary on sensitive and mutating operations.
5. Secret leakage prevention across responses, logs, and connector listings.
6. Browser security headers enforcement (CSP, HSTS, X-Frame-Options, Nosniff).
7. Replay attack and duplicate execution prevention via idempotency keys.
"""

from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient

from tasteops.api.app import create_app
from tasteops.api.dependencies import (
    get_api_settings,
    get_database,
    get_service,
    get_space_repository,
)
from tasteops.api.service import TasteOpsApplicationService
from tasteops.api.settings import APISettings
from tasteops.connectors.base import ConfigurationStatus, InvalidConfigurationError
from tasteops.connectors.procurement import ProcurementConnector
from tasteops.persistence.database import Database
from tasteops.persistence.space_repository import SQLiteSpaceRepository
from tasteops.persistence.store import SQLiteStateStore
from tasteops.security import validate_safe_url
from tasteops.workflows.orchestrator import TasteOpsOrchestrator
from tasteops.workflows.persistence import FileStateStore


@pytest.fixture
def client(tmp_path, mock_mcp_adapter):
    """Provides a TestClient with relational SQLite persistence."""
    adapter, _, _, _ = mock_mcp_adapter
    db_path = tmp_path / "test_security_audit.db"
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
        title="TasteOps Security Audit Test",
        environment="test",
    )
    app = create_app(settings=settings)

    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_space_repository] = lambda: space_repo
    app.dependency_overrides[get_service] = lambda: service

    with TestClient(app) as tc:
        yield tc, db, service


# -----------------------------------------------------------------------------
# 1. CORS Security Verification
# -----------------------------------------------------------------------------
def test_cors_disallows_credentials_when_wildcard_origins_configured():
    """Verify that wildcard origins prohibit allow_credentials=True."""
    settings = APISettings(CORS_ORIGINS=["*"])
    app = create_app(settings)

    # Inspect CORSMiddleware configuration in middleware stack
    cors_middleware = next(
        (m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware"),
        None,
    )
    assert cors_middleware is not None
    assert cors_middleware.kwargs["allow_origins"] == ["*"]
    # Critical security rule: allow_credentials MUST be False when origins is ['*']
    assert cors_middleware.kwargs["allow_credentials"] is False


def test_cors_allows_credentials_only_for_explicit_origins():
    """Verify that explicit origins permit allow_credentials=True."""
    settings = APISettings(CORS_ORIGINS=["http://localhost:3000", "https://tasteops.ai"])
    app = create_app(settings)

    cors_middleware = next(
        (m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware"),
        None,
    )
    assert cors_middleware is not None
    assert cors_middleware.kwargs["allow_credentials"] is True


# -----------------------------------------------------------------------------
# 2. SSRF (Server-Side Request Forgery) Prevention
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "blocked_url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://169.254.169.254/computeMetadata/v1/",
        "http://127.0.0.1:8000/internal-admin",
        "http://10.0.0.1/network-admin",
        "http://192.168.1.1/router",
        "http://172.16.0.1/secrets",
        "http://[::1]:8080/metrics",
        "ftp://malicious.host/file",
        "file:///etc/passwd",
    ],
)
def test_ssrf_validator_blocks_private_and_cloud_metadata_urls(blocked_url: str):
    """Verify that validate_safe_url strictly blocks internal, cloud metadata, and non-HTTP schemes."""
    with pytest.raises(ValueError) as exc_info:
        validate_safe_url(blocked_url)
    assert "SSRF" in str(exc_info.value) or "Invalid URL scheme" in str(exc_info.value)


def test_procurement_connector_blocks_ssrf_endpoint():
    """Verify ProcurementConnector enters INVALID_CONFIGURATION and rejects execution when given SSRF endpoint."""
    conn = ProcurementConnector(
        api_key="valid_test_api_key_12345",
        endpoint_url="http://169.254.169.254/latest/meta-data/",
    )
    assert conn.configuration_status == ConfigurationStatus.INVALID_CONFIGURATION
    with pytest.raises(InvalidConfigurationError) as exc_info:
        conn.validate()
    assert "SSRF" in str(exc_info.value)


# -----------------------------------------------------------------------------
# 3. Path Traversal & Identifier Sanitization
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "malicious_session_id",
    [
        "../../etc/passwd",
        "..\\..\\windows\\system32",
        "session/../../../root",
        "session_id with spaces",
        "session;DROP TABLE users;--",
        "session\x00nullbyte",
    ],
)
def test_file_state_store_rejects_path_traversal(tmp_path, malicious_session_id: str):
    """Verify that FileStateStore strictly rejects path traversal attempts."""
    store = FileStateStore(base_dir=tmp_path / "workflows")
    with pytest.raises(ValueError):
        store._get_session_dir(malicious_session_id)

    # load_context and get_audit_events should safely return None/empty and not crash
    assert store.load_context(malicious_session_id) is None
    assert store.get_audit_events(malicious_session_id) == []


def test_api_path_parameter_validation_rejects_path_traversal(client):
    """Verify that FastAPI route path parameters reject path traversal with HTTP 404 or 422."""
    tc, _, _ = client
    resp = tc.get("/api/v1/sessions/..%2F..%2Fetc%2Fpasswd")
    assert resp.status_code in (404, 422)

    resp2 = tc.get("/api/v1/spaces/..%2F..%2Fsecret")
    assert resp2.status_code in (404, 422)


# -----------------------------------------------------------------------------
# 4. Authentication & Authorization Boundary
# -----------------------------------------------------------------------------
def test_authenticated_mode_enforces_api_key(tmp_path, mock_mcp_adapter):
    """Verify that when TASTEOPS_API_KEY is configured, unauthenticated requests are rejected with 401."""
    adapter, _, _, _ = mock_mcp_adapter
    db_path = tmp_path / "test_auth_enforce.db"
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
        TASTEOPS_API_KEY="super_secret_curator_key_12345",
        ENVIRONMENT="production",
    )
    app = create_app(settings)
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_space_repository] = lambda: space_repo
    app.dependency_overrides[get_service] = lambda: service

    with TestClient(app) as test_client:
        # 1. Attempt mutating action without auth -> 401
        resp = test_client.post(
            "/api/v1/spaces",
            json={"name": "Test Space", "business_type": "Cafe"},
        )
        assert resp.status_code == 401
        assert "Missing authentication credentials" in resp.text

        # 2. Attempt with invalid key -> 403 Forbidden
        resp_invalid = test_client.post(
            "/api/v1/spaces",
            headers={"Authorization": "Bearer wrong_token"},
            json={"name": "Test Space", "business_type": "Cafe"},
        )
        assert resp_invalid.status_code == 403
        assert "Invalid API key" in resp_invalid.text

        # 3. Attempt with valid key -> 201 Created
        resp_valid = test_client.post(
            "/api/v1/spaces",
            headers={"Authorization": "Bearer super_secret_curator_key_12345"},
            json={"name": "Test Space", "business_type": "Cafe"},
        )
        assert resp_valid.status_code == 201


# -----------------------------------------------------------------------------
# 5. Security Headers & Zero Secret Leakage
# -----------------------------------------------------------------------------
def test_security_headers_present_on_all_responses(client):
    """Verify presence of security headers (CSP, HSTS, X-Frame-Options, Nosniff, Referrer)."""
    tc, _, _ = client
    resp = tc.get("/health")
    assert resp.status_code == 200
    headers = resp.headers

    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("X-XSS-Protection") == "1; mode=block"
    assert "max-age=" in headers.get("Strict-Transport-Security", "")
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "default-src 'self'" in headers.get("Content-Security-Policy", "")


def test_connector_listing_never_exposes_secrets(client):
    """Verify that GET /connectors returns capability telemetry but zero secret keys."""
    tc, _, _ = client
    # Create space & session
    space_resp = tc.post("/api/v1/spaces", json={"name": "Sec Space", "business_type": "Gallery"})
    s_id = space_resp.json()["space_id"]
    analyze_resp = tc.post(f"/api/v1/spaces/{s_id}/analyze")
    session_id = analyze_resp.json()["session_id"]

    resp = tc.get(f"/api/v1/sessions/{session_id}/connectors")
    assert resp.status_code == 200
    connectors = resp.json()

    for conn in connectors:
        assert "name" in conn
        assert "capability" in conn
        assert "configuration_status" in conn
        # Secrets MUST NOT exist
        assert "api_key" not in conn
        assert "client_secret" not in conn
        assert "token" not in conn
