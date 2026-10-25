"""Integration audit test for TasteOps Execution Connectors and API Boundary.

Validates:
1. Behavioral contrast between API route execution (currently simulated) and
   ConnectorRegistry execution (strictly fails when NOT_CONFIGURED).
2. Concurrency and idempotency behavior of ConnectorRegistry.
3. SSRF defense against cloud metadata, IPv4-mapped IPv6 addresses, and private subnets.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tasteops.api.main import create_app
from tasteops.config import ServerSettings
from tasteops.connectors import (
    ConnectorNotConfiguredError,
    DuplicateExecutionError,
    SpotifyConnector,
    create_default_registry,
)
from tasteops.security import validate_safe_url
from tasteops.workflows.orchestrator import TasteOpsOrchestrator
from tasteops.workflows.persistence import InMemoryStateStore
from tasteops.workflows.schemas import ExecutionTask


@pytest.fixture
def test_client(mock_mcp_adapter, tmp_path):
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


def test_api_route_simulated_execution_vs_connector_registry_truthfulness(
    test_client,
):
    """Audits the behavioral difference between current API route execution and ConnectorRegistry.

    Current Behavior (main):
        POST /api/v1/sessions/{id}/execute returns status='COMPLETED' with simulated 'EXECUTED'
        tasks even when SPOTIFY_CLIENT_ID or SENDGRID_API_KEY are absent from the environment.

    Connector Contract (PR #16):
        ConnectorRegistry.dispatch_task refuses to fake execution and raises
        ConnectorNotConfiguredError when credentials are missing.
    """
    # 1. Drive session to approval via UI test client
    init_resp = test_client.post(
        "/api/v1/sessions",
        json={"raw_intent": "Auditing execution truthfulness in listening lounge."},
    )
    session_id = init_resp.json()["session_id"]
    test_client.post(f"/api/v1/sessions/{session_id}/pipeline", json={})
    test_client.post(
        f"/api/v1/sessions/{session_id}/approve",
        json={"approver": "Lead Curator"},
    )

    # 2. Execute via API route
    exec_resp = test_client.post(f"/api/v1/sessions/{session_id}/execute")
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()
    assert exec_data["current_state"] == "COMPLETED"

    tasks = exec_data.get("execution_tasks", [])
    assert len(tasks) > 0

    # 3. Notice: API route currently reports tasks as 'EXECUTED' (simulated)
    spotify_tasks = [t for t in tasks if "spotify" in t.get("action", "").lower()]
    if spotify_tasks:
        assert spotify_tasks[0]["status"] == "EXECUTED"

        # 4. Now audit what ConnectorRegistry does with the exact same task
        registry = create_default_registry()
        task_model = ExecutionTask(**spotify_tasks[0])

        # When credentials are missing, ConnectorRegistry MUST raise ConnectorNotConfiguredError
        with pytest.raises(ConnectorNotConfiguredError):
            pytest.importorskip("asyncio").run(
                registry.dispatch_task(
                    task=task_model,
                    session_id=session_id,
                    plan_id=exec_data["plan"]["plan_id"],
                    plan_version=exec_data["plan"]["version"],
                )
            )


@pytest.mark.asyncio
async def test_connector_registry_idempotency_boundary():
    """Verifies that ConnectorRegistry rejects duplicate execution requests with identical keys."""
    registry = create_default_registry()
    # Configure spotify with dummy credentials for execution test
    spotify = SpotifyConnector(
        client_id="mock_client_id_12345", client_secret="mock_secret_12345"
    )
    registry.register(spotify)

    task = ExecutionTask(
        task_id="task_audit_idem_01",
        idempotency_key="idem_boundary_check_777",
        category="spotify_audio_seed",
        action="Export seed artist to Spotify",
        input={"artist_name": "Miles Davis", "daypart": "evening"},
    )

    # 1st Dispatch: Success
    res1 = await registry.dispatch_task(
        task=task,
        session_id="sess_idem_test",
        plan_id="plan_idem_test",
    )
    assert res1.status == "COMPLETED"
    assert registry.is_executed("idem_boundary_check_777") is True

    # 2nd Dispatch: Rejected with DuplicateExecutionError
    with pytest.raises(DuplicateExecutionError):
        await registry.dispatch_task(
            task=task,
            session_id="sess_idem_test",
            plan_id="plan_idem_test",
        )


def test_ssrf_edge_cases_in_request_boundary():
    """Verifies SSRF blocking on IPv4, IPv6, mapped addresses, and cloud metadata."""
    # Cloud metadata
    with pytest.raises(ValueError, match="SSRF Protection"):
        validate_safe_url("http://169.254.169.254/latest/meta-data/")
    with pytest.raises(ValueError, match="SSRF Protection"):
        validate_safe_url("http://metadata.google.internal/computeMetadata/v1/")

    # IPv4 loopback & private subnets
    with pytest.raises(ValueError, match="SSRF Protection"):
        validate_safe_url("http://127.0.0.1:8080/")
    with pytest.raises(ValueError, match="SSRF Protection"):
        validate_safe_url("http://10.254.1.1/internal")
    with pytest.raises(ValueError, match="SSRF Protection"):
        validate_safe_url("http://192.168.1.1/setup")

    # IPv4-mapped IPv6 bypass attempts
    with pytest.raises(ValueError, match="SSRF Protection"):
        validate_safe_url("http://[::ffff:169.254.169.254]/")
    with pytest.raises(ValueError, match="SSRF Protection"):
        validate_safe_url("http://[::ffff:127.0.0.1]/")

    # Allowed public URL
    assert validate_safe_url("https://api.spotify.com/v1/search") is True
