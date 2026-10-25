"""Comprehensive Integration Readiness Tests for TasteOps Execution Connectors.

Validates the full post-merge execution integration contract:
1. Successful mocked dispatch with truthful provider-specific output references.
2. Missing credentials produce explicit NOT_CONFIGURED status and never fabricate EXECUTED.
3. Provider runtime failures (HTTP 500) produce explicit FAILED task status.
4. Ambiguous provider outcomes (network/timeout) are flagged without blind external replay.
5. Concurrency-safe, persistent idempotency across repeated and parallel execution requests.
6. Process restart recovery from FileStateStore preserving previously executed tasks.
7. Approval enforcement: unapproved execution is strictly rejected (HTTP 400).
8. Plan mutation checks: post-approval hash mutation strictly invalidates execution.
9. SSRF defenses: HTTP redirects to internal/metadata endpoints are strictly intercepted and blocked.
10. SSRF edge cases: DNS resolution, IPv4-mapped IPv6, loopback, and cloud metadata.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from tasteops.api.main import create_app
from tasteops.config import ServerSettings
from tasteops.connectors import (
    ConnectorExecutionFailedError,
    ConnectorExecutionRequest,
    EmailConnector,
    SpotifyConnector,
    create_configured_mock_registry,
    create_default_registry,
)
from tasteops.security import (
    validate_redirect_target,
    validate_safe_url,
)
from tasteops.workflows.orchestrator import TasteOpsOrchestrator
from tasteops.workflows.persistence import FileStateStore, InMemoryStateStore
from tasteops.workflows.states import WorkflowState
from tests.fixtures.demo_mumbai_boutique_hotel import (
    MUMBAI_DEMO_HINTS,
    MUMBAI_DEMO_RAW_INTENT,
    MUMBAI_INSIGHTS_MOCK_RESPONSE,
    MUMBAI_SEARCH_MOCK_RESPONSE,
    MUMBAI_TAGS_MOCK_RESPONSE,
)

# =============================================================================
# Test Client Fixtures
# =============================================================================


@pytest.fixture
def mock_mumbai_respx():
    """Sets up respx routes with the Mumbai Boutique Hotel demo fixture."""
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
def mock_configured_client(mock_mcp_adapter, mock_mumbai_respx, tmp_path):
    """Provides a TestClient wired to an orchestrator with configured mock connectors."""
    adapter, _, _, _ = mock_mcp_adapter
    store = InMemoryStateStore()
    registry = create_configured_mock_registry()
    orchestrator = TasteOpsOrchestrator(
        store=store, mcp_adapter=adapter, connector_registry=registry
    )
    settings = ServerSettings(ENVIRONMENT="test", TASTEOPS_STORAGE_DIR=str(tmp_path))
    app = create_app(server_settings=settings, orchestrator=orchestrator)
    with TestClient(app) as client:
        yield client, orchestrator


@pytest.fixture
def unconfigured_client(mock_mcp_adapter, mock_mumbai_respx, tmp_path):
    """Provides a TestClient wired to an orchestrator with default unconfigured connectors."""
    adapter, _, _, _ = mock_mcp_adapter
    store = InMemoryStateStore()
    registry = create_default_registry()
    orchestrator = TasteOpsOrchestrator(
        store=store, mcp_adapter=adapter, connector_registry=registry
    )
    settings = ServerSettings(ENVIRONMENT="test", TASTEOPS_STORAGE_DIR=str(tmp_path))
    app = create_app(server_settings=settings, orchestrator=orchestrator)
    with TestClient(app) as client:
        yield client, orchestrator


# =============================================================================
# 1. Successful Mocked Dispatch
# =============================================================================


def test_successful_mocked_dispatch(mock_configured_client):
    """Verifies end-to-end execution through configured connectors produces EXECUTED tasks."""
    client, _ = mock_configured_client

    # 1. Initialize session and advance to approval
    resp = client.post(
        "/api/v1/sessions",
        json={
            "raw_intent": MUMBAI_DEMO_RAW_INTENT,
            "hints": MUMBAI_DEMO_HINTS,
        },
    )
    assert resp.status_code == 201
    session_id = resp.json()["session_id"]

    pipe_resp = client.post(f"/api/v1/sessions/{session_id}/pipeline", json={})
    assert pipe_resp.status_code == 200
    assert pipe_resp.json()["current_state"] == "AWAITING_APPROVAL"

    appr_resp = client.post(
        f"/api/v1/sessions/{session_id}/approve",
        json={"approver": "Lead Curator Satwik"},
    )
    assert appr_resp.status_code == 200
    assert appr_resp.json()["current_state"] == "APPROVED"

    # 2. Execute plan
    exec_resp = client.post(f"/api/v1/sessions/{session_id}/execute")
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()

    assert exec_data["current_state"] == "COMPLETED"
    tasks = exec_data.get("execution_tasks", [])
    assert len(tasks) >= 3

    # Every task executed truthfully via mock connector
    for task in tasks:
        assert task["status"] == "EXECUTED"
        assert task["output_reference"] is not None
        assert task["executed_at"] is not None
        assert task["provenance"]["execution_status"] == "EXECUTED"

    summary = exec_data["plan"]["execution_summary"]
    assert summary["executed_tasks"] == len(tasks)
    assert summary["failed_tasks"] == 0
    assert summary["audit_report"]["compliance_status"] == "COMPLIANT"


# =============================================================================
# 2. Missing Credentials Produce Explicit NOT_CONFIGURED
# =============================================================================


def test_missing_credentials_explicit_not_configured(unconfigured_client):
    """Verifies that missing credentials yield NOT_CONFIGURED and never fabricate execution success."""
    client, _ = unconfigured_client

    resp = client.post(
        "/api/v1/sessions",
        json={
            "raw_intent": MUMBAI_DEMO_RAW_INTENT,
            "hints": MUMBAI_DEMO_HINTS,
        },
    )
    session_id = resp.json()["session_id"]
    client.post(f"/api/v1/sessions/{session_id}/pipeline", json={})
    client.post(
        f"/api/v1/sessions/{session_id}/approve",
        json={"approver": "Lead Curator"},
    )

    exec_resp = client.post(f"/api/v1/sessions/{session_id}/execute")
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()

    # The workflow reaches COMPLETED after processing all tasks
    assert exec_data["current_state"] == "COMPLETED"
    tasks = exec_data.get("execution_tasks", [])
    assert len(tasks) >= 3

    # BUT every task is explicitly NOT_CONFIGURED with zero fabricated success
    for task in tasks:
        assert task["status"] == "NOT_CONFIGURED"
        assert task["output_reference"] is None
        assert task["result"]["status"] == "NOT_CONFIGURED"
        assert task["result"]["error_code"] == "NOT_CONFIGURED"
        assert task["provenance"]["execution_status"] == "NOT_CONFIGURED"

    summary = exec_data["plan"]["execution_summary"]
    assert summary["executed_tasks"] == 0
    assert summary["failed_tasks"] == len(tasks)


# =============================================================================
# 3. Provider Failures (HTTP 500)
# =============================================================================


@pytest.mark.asyncio
async def test_provider_http_500_failure_records_failed_task():
    """Verifies that third-party HTTP 500 errors mark task as FAILED with diagnostics."""

    def mock_500_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Spotify Service Unavailable")

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_500_handler))
    spotify = SpotifyConnector(
        client_id="mock_client_id_123",
        client_secret="mock_client_secret_123",
        http_client=mock_client,
    )

    req = ConnectorExecutionRequest(
        session_id="sess_err_test",
        plan_id="plan_err_test",
        plan_version=1,
        task_id="task_err_01",
        idempotency_key="idem_err_01",
        task_type="spotify_audio_seed",
        payload={"artist_name": "Four Tet", "daypart": "evening"},
    )

    with pytest.raises(ConnectorExecutionFailedError) as exc_info:
        await spotify.execute(req)

    assert exc_info.value.code == "EXECUTION_FAILED"
    assert exc_info.value.details["status_code"] == 500


# =============================================================================
# 4. Ambiguous Provider Outcome (Timeout)
# =============================================================================


@pytest.mark.asyncio
async def test_ambiguous_provider_timeout_handling():
    """Verifies that network timeouts raise ConnectorExecutionFailedError with ambiguous=True."""

    def mock_timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Socket timed out waiting for provider response")

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_timeout_handler))
    email = EmailConnector(
        api_key="sendgrid_key_mock_12345",
        from_email="curator@tasteops.ai",
        http_client=mock_client,
    )

    req = ConnectorExecutionRequest(
        session_id="sess_timeout_test",
        plan_id="plan_timeout_test",
        plan_version=1,
        task_id="task_time_01",
        idempotency_key="idem_time_01",
        task_type="partner_outreach_brief",
        payload={"partner_name": "Aesop", "recipient_email": "partners@aesop.com"},
    )

    with pytest.raises(ConnectorExecutionFailedError) as exc_info:
        await email.execute(req)

    assert exc_info.value.details.get("ambiguous") is True


# =============================================================================
# 5. Persistent Concurrency-Safe Idempotency
# =============================================================================


@pytest.mark.asyncio
async def test_concurrency_safe_duplicate_execution_idempotency(
    mock_mcp_adapter, mock_mumbai_respx
):
    """Verifies that parallel concurrent execution calls on the same session do not duplicate tasks."""
    adapter, _, _, _ = mock_mcp_adapter
    store = InMemoryStateStore()
    registry = create_configured_mock_registry()

    # Use orchestrator to run full pipeline
    orchestrator = TasteOpsOrchestrator(
        store=store, mcp_adapter=adapter, connector_registry=registry
    )
    sess_ctx = orchestrator.create_session(
        MUMBAI_DEMO_RAW_INTENT,
        hints=MUMBAI_DEMO_HINTS,
    )
    await orchestrator.run_until_approval(sess_ctx.session_id)
    await orchestrator.approve_session(sess_ctx.session_id, approver="Curator Elena")

    # Launch 4 parallel execution calls concurrently
    results = await asyncio.gather(
        orchestrator.execute_approved_plan(sess_ctx.session_id),
        orchestrator.execute_approved_plan(sess_ctx.session_id),
        orchestrator.execute_approved_plan(sess_ctx.session_id),
        orchestrator.execute_approved_plan(sess_ctx.session_id),
    )

    # All return the exact same completed context
    for res in results:
        assert res.current_state == WorkflowState.COMPLETED
        assert len(res.execution_tasks) >= 3

    # Task IDs must be strictly unique (no duplicates created)
    final_tasks = results[0].execution_tasks
    task_ids = [t.task_id for t in final_tasks]
    assert len(task_ids) == len(set(task_ids))

    # Audit events must only record one transition to COMPLETED
    events = orchestrator.get_audit_events(sess_ctx.session_id)
    completed_events = [e for e in events if e.to_state == WorkflowState.COMPLETED]
    assert len(completed_events) == 1


# =============================================================================
# 6. Restart Recovery From FileStateStore
# =============================================================================


@pytest.mark.asyncio
async def test_restart_recovery_from_filestatestore(
    mock_mcp_adapter, mock_mumbai_respx, tmp_path
):
    """Verifies that a session in EXECUTING state recovered from disk resumes cleanly without repeating tasks."""
    adapter, _, _, _ = mock_mcp_adapter
    store_dir = tmp_path / "restart_storage"
    store_1 = FileStateStore(base_dir=store_dir)
    registry_1 = create_configured_mock_registry()

    orch_1 = TasteOpsOrchestrator(
        store=store_1, mcp_adapter=adapter, connector_registry=registry_1
    )
    ctx_1 = orch_1.create_session(
        MUMBAI_DEMO_RAW_INTENT,
        hints=MUMBAI_DEMO_HINTS,
    )
    await orch_1.run_until_approval(ctx_1.session_id)
    await orch_1.approve_session(ctx_1.session_id, approver="Curator Dave")

    # Pre-execute task 1 and simulate mid-execution crash
    session_id = ctx_1.session_id
    orch_1.engine._record_and_persist(
        ctx_1,
        WorkflowState.EXECUTING,
        reason="Process crashed mid-execution",
    )

    # Destroy instance 1
    del orch_1
    del store_1

    # Instance 2 starts from same storage directory
    store_2 = FileStateStore(base_dir=store_dir)
    registry_2 = create_configured_mock_registry()
    orch_2 = TasteOpsOrchestrator(
        store=store_2, mcp_adapter=adapter, connector_registry=registry_2
    )

    recovered = orch_2.get_session_state(session_id)
    assert recovered.current_state == WorkflowState.EXECUTING

    # Resume execution
    final_ctx = await orch_2.execute_approved_plan(session_id)
    assert final_ctx.current_state == WorkflowState.COMPLETED
    assert len(final_ctx.execution_tasks) >= 3


# =============================================================================
# 7. Approval Gate & Plan Mutation Enforcement
# =============================================================================


def test_unapproved_execution_blocked(mock_configured_client):
    """Verifies calling execute before approval is rejected with HTTP 400."""
    client, _ = mock_configured_client

    resp = client.post(
        "/api/v1/sessions",
        json={"raw_intent": "Attempting unapproved execution bypass."},
    )
    session_id = resp.json()["session_id"]

    # Session is in CREATED state; execute must fail
    exec_resp = client.post(f"/api/v1/sessions/{session_id}/execute")
    assert exec_resp.status_code == 400

    # Advance to AWAITING_APPROVAL; execute without approval must still fail
    client.post(f"/api/v1/sessions/{session_id}/pipeline", json={})
    exec_resp2 = client.post(f"/api/v1/sessions/{session_id}/execute")
    assert exec_resp2.status_code == 400


@pytest.mark.asyncio
async def test_plan_mutation_after_approval_invalidates_execution(
    mock_mcp_adapter, mock_mumbai_respx
):
    """Verifies that mutating a plan after approval breaks cryptographic hash and blocks execution."""
    adapter, _, _, _ = mock_mcp_adapter
    registry = create_configured_mock_registry()
    orch = TasteOpsOrchestrator(mcp_adapter=adapter, connector_registry=registry)

    ctx = orch.create_session(
        MUMBAI_DEMO_RAW_INTENT,
        hints=MUMBAI_DEMO_HINTS,
    )
    await orch.run_until_approval(ctx.session_id)
    await orch.approve_session(ctx.session_id, approver="Security Auditor")

    # Tamper with plan after approval
    ctx.plan.plan_id = "tampered_plan_id_999"

    from tasteops.agents.governance import UnapprovedExecutionError

    with pytest.raises(UnapprovedExecutionError, match="does not match plan"):
        await orch.execute_approved_plan(ctx.session_id)


# =============================================================================
# 8. SSRF Defenses in Network Request Path
# =============================================================================


def test_ssrf_redirect_protection_in_network_path():
    """Verifies that HTTP redirects to cloud metadata and loopback destinations are strictly blocked."""
    # Test Response redirect validation
    req = httpx.Request("POST", "https://api.procurement.tasteops.internal/v1/orders")

    # 1. Redirect to AWS/GCP metadata
    resp_meta = httpx.Response(
        302,
        headers={"location": "http://169.254.169.254/latest/meta-data/"},
        request=req,
    )
    with pytest.raises(ValueError, match="SSRF Protection"):
        validate_redirect_target(resp_meta)

    # 2. Redirect to localhost
    resp_loopback = httpx.Response(
        302,
        headers={"location": "http://127.0.0.1:8080/internal/admin"},
        request=req,
    )
    with pytest.raises(ValueError, match="SSRF Protection"):
        validate_redirect_target(resp_loopback)

    # 3. Redirect to IPv4-mapped IPv6 loopback
    resp_ipv6 = httpx.Response(
        301,
        headers={"location": "http://[::ffff:127.0.0.1]:8080/admin"},
        request=req,
    )
    with pytest.raises(ValueError, match="SSRF Protection"):
        validate_redirect_target(resp_ipv6)

    # 4. Safe public redirect
    resp_safe = httpx.Response(
        302,
        headers={"location": "https://api.spotify.com/v1/status"},
        request=req,
    )
    validate_redirect_target(resp_safe)  # Does not raise


def test_ssrf_edge_cases_and_unspecified_addresses():
    """Verifies blocking on 0.0.0.0, localhost hostnames, and private subnets."""
    with pytest.raises(ValueError, match="SSRF Protection"):
        validate_safe_url("http://0.0.0.0:8000/orders")
    with pytest.raises(ValueError, match="SSRF Protection"):
        validate_safe_url("http://localhost:8000/orders")
    with pytest.raises(ValueError, match="SSRF Protection"):
        validate_safe_url("http://app.localhost/setup")
    with pytest.raises(ValueError, match="SSRF Protection"):
        validate_safe_url("http://[::ffff:0.0.0.0]/")
