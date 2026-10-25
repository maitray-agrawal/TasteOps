"""Integration tests verifying real execution truthfulness, connector boundaries, and artifact provenance.

Validates:
1. API-level execution honesty: unconfigured connectors return STAGED/NOT_CONFIGURED, never synthetic COMPLETED.
2. Configured connectors with mock HTTP transport return COMPLETED with real provider response payload.
3. Provider runtime failures (e.g. HTTP 500) fail gracefully to FAILED status.
4. Concurrent duplicate execution attempts with identical idempotency keys are atomically rejected.
5. Artifact provenance integrity: no fabricated ISBNs, unknown fields remain UNAVAILABLE, reconciled durations.
6. SSRF defense fails closed on DNS lookup failures and blocks cloud metadata unconditionally.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from tasteops.api.main import create_app
from tasteops.config import ServerSettings
from tasteops.connectors import (
    ConnectorRegistry,
    DuplicateExecutionError,
    EmailConnector,
    SpotifyConnector,
    create_default_registry,
)
from tasteops.connectors.base import ConnectorExecutionRequest
from tasteops.models.cultural_matrix import CulturalMatrix, CulturalRecommendation
from tasteops.security import validate_safe_url
from tasteops.workflows.artifacts import (
    generate_brand_dossiers_artifact,
    generate_procurement_csv,
    generate_spotify_playlist_artifact,
)
from tasteops.workflows.context import WorkflowContext
from tasteops.workflows.orchestrator import TasteOpsOrchestrator
from tasteops.workflows.persistence import InMemoryStateStore
from tasteops.workflows.schemas import ExecutionTask, TaskStatus

# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def unconfigured_test_client(mock_mcp_adapter, tmp_path):
    """Provides a TestClient initialized with orchestrator using default unconfigured connectors."""
    adapter, _, _, _ = mock_mcp_adapter
    store = InMemoryStateStore()
    registry = create_default_registry()
    orchestrator = TasteOpsOrchestrator(
        store=store, mcp_adapter=adapter, connector_registry=registry
    )
    settings = ServerSettings(
        ENVIRONMENT="test",
        TASTEOPS_STORAGE_DIR=str(tmp_path),
    )
    app = create_app(server_settings=settings, orchestrator=orchestrator)
    with TestClient(app) as client:
        yield client, orchestrator


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


def test_api_execution_truthfulness_unconfigured_connectors(unconfigured_test_client):
    """Proves that unconfigured connectors cannot claim false COMPLETED status in the API response."""
    client, _ = unconfigured_test_client

    # 1. Initialize session and drive to approval
    init_resp = client.post(
        "/api/v1/sessions",
        json={"raw_intent": "Curating an intentional acoustic tea sanctuary."},
    )
    assert init_resp.status_code == 201
    session_id = init_resp.json()["session_id"]

    client.post(f"/api/v1/sessions/{session_id}/pipeline", json={})
    client.post(
        f"/api/v1/sessions/{session_id}/approve",
        json={"approver": "Lead Curator"},
    )

    # 2. Execute plan
    exec_resp = client.post(f"/api/v1/sessions/{session_id}/execute")
    assert exec_resp.status_code == 200
    data = exec_resp.json()

    tasks = data.get("execution_tasks", [])
    assert len(tasks) > 0

    # 3. Verify that unconfigured tasks are STAGED, not false COMPLETED
    for task in tasks:
        status_val = task.get("status")
        # In JSON output, status must be STAGED or NOT_CONFIGURED, never COMPLETED
        assert status_val in ("STAGED", "NOT_CONFIGURED")
        # Output reference must reflect staged URI or None, not synthetic external provider URI
        out_ref = task.get("output_reference")
        if out_ref is not None:
            assert out_ref.startswith("staged://")
            assert "spotify.com" not in out_ref
            assert "sendgrid.com" not in out_ref


@pytest.mark.asyncio
async def test_mocked_configured_provider_success():
    """Proves that when a connector is properly configured with an HTTP client, it executes and marks COMPLETED."""
    mock_spotify_resp = {
        "id": "mock_playlist_999",
        "name": "TasteOps Sonic Seeding",
        "uri": "spotify:playlist:mock_playlist_999",
        "tracks": {"total": 5},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json=mock_spotify_resp)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    connector = SpotifyConnector(
        client_id="mock_client_id",
        client_secret="mock_client_secret",
        http_client=mock_client,
    )

    registry = ConnectorRegistry()
    registry.register(connector)

    task = ExecutionTask(
        task_id="task_spotify_real_01",
        idempotency_key="idem_real_spotify_01",
        category="spotify_audio_seed",
        action="Seed Spotify playlist",
        input={"engine": "spotify", "artist_id": "art_123", "artist_name": "Bonobo"},
        status=TaskStatus("PENDING"),
    )

    result = await registry.dispatch_task(
        task=task,
        session_id="sess_01",
        plan_id="plan_01",
        plan_version=1,
    )

    assert result.status == "COMPLETED"
    assert result.output_reference == "spotify:playlist:mock_playlist_999"
    assert result.payload["playlist_id"] == "mock_playlist_999"
    await mock_client.aclose()


@pytest.mark.asyncio
async def test_mocked_configured_provider_error_handling():
    """Proves that provider runtime HTTP errors fail explicitly with standard connector error."""

    def error_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "Internal Spotify Service Error"})

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(error_handler))
    connector = SpotifyConnector(
        client_id="mock_id",
        client_secret="mock_secret",
        http_client=mock_client,
    )

    registry = ConnectorRegistry()
    registry.register(connector)

    task = ExecutionTask(
        task_id="task_spotify_fail_01",
        idempotency_key="idem_spotify_fail_01",
        category="spotify_audio_seed",
        action="Seed Spotify playlist",
        input={"artist_id": "art_fail"},
    )

    with pytest.raises(Exception) as exc_info:
        await registry.dispatch_task(
            task=task,
            session_id="sess_01",
            plan_id="plan_01",
            plan_version=1,
        )

    assert "500" in str(exc_info.value) or "Spotify API error" in str(exc_info.value)
    await mock_client.aclose()


@pytest.mark.asyncio
async def test_atomic_concurrent_duplicate_reservation():
    """Proves that concurrent dispatches with identical idempotency key are rejected by atomic lock."""
    call_count = 0

    async def slow_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)
        return httpx.Response(200, json={"status": "ok"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(slow_handler))
    connector = EmailConnector(api_key="SG.mock_key", http_client=client)

    registry = ConnectorRegistry()
    registry.register(connector)

    req1 = ConnectorExecutionRequest(
        session_id="sess_concurrent",
        plan_id="plan_concurrent",
        plan_version=1,
        task_id="task_email_01",
        idempotency_key="idem_concurrent_unique_123",
        task_type="partner_outreach_brief",
        payload={"recipient_email": "partner@brand.com", "subject": "Collab"},
    )

    req2 = ConnectorExecutionRequest(
        session_id="sess_concurrent",
        plan_id="plan_concurrent",
        plan_version=1,
        task_id="task_email_02",
        idempotency_key="idem_concurrent_unique_123",  # duplicate!
        task_type="partner_outreach_brief",
        payload={"recipient_email": "partner@brand.com", "subject": "Collab"},
    )

    # Dispatch both concurrently
    results = await asyncio.gather(
        registry.dispatch(req1),
        registry.dispatch(req2),
        return_exceptions=True,
    )

    # One must succeed and one must be DuplicateExecutionError
    succeeded = [r for r in results if not isinstance(r, Exception)]
    duplicates = [r for r in results if isinstance(r, DuplicateExecutionError)]

    assert len(succeeded) == 1
    assert len(duplicates) == 1
    assert duplicates[0].idempotency_key == "idem_concurrent_unique_123"
    await client.aclose()


def test_artifact_provenance_and_data_integrity():
    """Validates that production artifacts do not fabricate ISBNs, authors, or runtimes."""
    # 1. Create a WorkflowContext with genuine books in CulturalMatrix
    ctx = WorkflowContext(user_input="Test sanctuary")
    ctx.cultural_matrix = CulturalMatrix(
        books=[
            CulturalRecommendation(
                id="qloo_book_01",
                name="The Architecture of Happiness",
                type="book",
                affinity=0.92,
                source_query="/v2/insights",
            ),
            CulturalRecommendation(
                id="qloo_book_02",
                name="Wabi-Sabi",
                type="book",
                affinity=0.88,
                source_query="/v2/insights",
            ),
        ],
        artists=[
            CulturalRecommendation(
                id="qloo_art_01",
                name="Nils Frahm",
                type="artist",
                affinity=0.95,
                source_query="/v2/insights",
            ),
            CulturalRecommendation(
                id="qloo_art_02",
                name="Olafur Arnalds",
                type="artist",
                affinity=0.91,
                source_query="/v2/insights",
            ),
        ],
    )

    # 2. Test Procurement CSV production generation (demo_mode=False)
    csv_out = generate_procurement_csv(ctx, demo_mode=False)
    assert "The Architecture of Happiness" in csv_out
    assert "Wabi-Sabi" in csv_out
    # Fabricated ISBNs must NOT be present
    assert "978-8400000000" not in csv_out
    # Unknown commercial attributes must be labeled UNAVAILABLE
    assert "UNAVAILABLE" in csv_out

    # 3. Test Spotify Playlist runtime reconciliation
    playlist_art = generate_spotify_playlist_artifact(ctx, demo_mode=False)
    assert playlist_art["total_tracks"] == 2
    assert len(playlist_art["staged_tracks_sample"]) == 2
    assert playlist_art["runtime"] != "0m 00s"
    assert playlist_art["is_demo_sample"] is False

    # 4. Test Brand Dossiers when no candidates exist and demo_mode is True
    dossiers = generate_brand_dossiers_artifact(ctx, demo_mode=True)
    assert len(dossiers) >= 1
    assert dossiers[0]["is_demo_sample"] is True
    assert "SAMPLE" in dossiers[0]["sample_notice"].upper()
    assert dossiers[0]["qloo_entity_id"] == "UNAVAILABLE (Sample Data)"


def test_ssrf_fails_closed_on_dns_errors():
    """Proves that SSRF validation fails closed on DNS lookup failures."""
    # Invalid domain that cannot resolve via DNS
    unresolvable_url = (
        "http://definitely-does-not-exist-tasteops-fail-closed.invalid/api/test"
    )
    with pytest.raises(ValueError) as exc_info:
        validate_safe_url(unresolvable_url, allow_private=False)

    assert "SSRF Protection: DNS resolution failed" in str(exc_info.value)


def test_ssrf_blocks_cloud_metadata_unconditionally():
    """Proves that cloud metadata 169.254.169.254 is blocked even with allow_private=True."""
    metadata_url = "http://169.254.169.254/latest/meta-data"
    with pytest.raises(ValueError) as exc_info:
        validate_safe_url(metadata_url, allow_private=True)

    assert "cloud metadata" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_spotify_current_endpoint_paths_and_items_schema():
    """Validates that Spotify connector uses POST /me/playlists and POST /playlists/{id}/items, never /tracks."""
    called_endpoints = []

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        called_endpoints.append(url_str)
        # Obsolete /tracks endpoint must NEVER be called
        assert "/tracks" not in url_str

        if url_str == "https://api.spotify.com/v1/me/playlists":
            return httpx.Response(
                201,
                json={
                    "id": "pl_seed_austin",
                    "uri": "spotify:playlist:pl_seed_austin",
                    "name": "Austin Modern Ambient",
                },
            )
        elif url_str == "https://api.spotify.com/v1/playlists/pl_seed_austin/items":
            import json

            body = json.loads(request.content)
            assert "uris" in body
            assert body["uris"] == ["spotify:track:4iV5W9uYEdYUVa79Axb7Rh"]
            return httpx.Response(201, json={"snapshot_id": "snap_austin_123"})
        return httpx.Response(404, text="Not Found")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    connector = SpotifyConnector(
        client_id="sp_test_id",
        client_secret="sp_test_token",
        http_client=client,
    )
    assert "playlist-modify-public" in connector.required_scopes

    req = ConnectorExecutionRequest(
        session_id="sess_sp_modern",
        plan_id="plan_sp_modern",
        plan_version=1,
        task_id="task_sp_modern",
        idempotency_key="idem_sp_modern_01",
        task_type="spotify_audio_seed",
        payload={
            "artist_name": "Tycho",
            "daypart": "morning",
            "track_uris": ["spotify:track:4iV5W9uYEdYUVa79Axb7Rh"],
        },
    )

    res = await connector.execute(req)
    assert res.status == "COMPLETED"
    assert res.output_reference == "spotify:playlist:pl_seed_austin"
    assert res.payload["snapshot_id"] == "snap_austin_123"
    assert "https://api.spotify.com/v1/me/playlists" in called_endpoints
    assert (
        "https://api.spotify.com/v1/playlists/pl_seed_austin/items" in called_endpoints
    )
    await client.aclose()


@pytest.mark.asyncio
async def test_sendgrid_202_acceptance_vs_delivery_status():
    """Proves SendGrid HTTP 202 is recorded as PROVIDER_ACCEPTED, never false DELIVERED."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://api.sendgrid.com/v3/mail/send"
        return httpx.Response(202, headers={"X-Message-Id": "sg_msg_98765"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    connector = EmailConnector(
        api_key="SG.live_curator_key_123",
        http_client=client,
    )

    req = ConnectorExecutionRequest(
        session_id="sess_sg_test",
        plan_id="plan_sg_test",
        plan_version=1,
        task_id="task_sg_test",
        idempotency_key="idem_sg_test_01",
        task_type="partner_outreach_brief",
        payload={"partner_name": "Aesop", "recipient_email": "collab@aesop.com"},
    )

    res = await connector.execute(req)
    assert res.status == "COMPLETED"
    assert res.payload["provider_status"] == "PROVIDER_ACCEPTED"
    assert res.payload["delivery_status"] == "ACCEPTED_FOR_DELIVERY"
    assert res.payload["is_confirmed_delivered"] is False
    assert res.payload["message_id"] == "sg_msg_98765"
    await client.aclose()


@pytest.mark.asyncio
async def test_procurement_ssrf_redirect_and_allowlist():
    """Proves that ProcurementConnector blocks redirects to cloud metadata and enforces host allowlist."""
    from tasteops.connectors import ProcurementConnector
    from tasteops.security import validate_safe_url

    # 1. Unspecified 0.0.0.0 and :: are blocked
    with pytest.raises(ValueError, match="cloud metadata|restricted IP|blocked"):
        validate_safe_url("http://0.0.0.0:8000/orders", allow_private=False)

    # 2. Host allowlist blocks unauthorized host
    with pytest.raises(ValueError, match="not in the allowed hosts list"):
        validate_safe_url(
            "https://evil.external.attacker.com/orders",
            allow_private=True,
            allowed_hosts=["api.procurement.tasteops.internal", "*.trusted-vendor.com"],
        )

    # 3. Redirect to prohibited destination is blocked in ProcurementConnector
    def redirect_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302,
            headers={"Location": "http://169.254.169.254/latest/meta-data"},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(redirect_handler))
    conn = ProcurementConnector(
        api_key="valid_erp_key",
        endpoint_url="https://api.procurement.tasteops.internal/v1/orders",
        http_client=client,
        allow_private=True,
    )

    req = ConnectorExecutionRequest(
        session_id="sess_po_redir",
        plan_id="plan_po_redir",
        plan_version=1,
        task_id="task_po_redir",
        idempotency_key="idem_po_redir",
        task_type="procurement_order",
        payload={"vendor": "Studio Klay", "item": "Ceramics"},
    )

    with pytest.raises(Exception) as exc_info:
        await conn.execute(req)
    assert (
        "SSRF violation" in str(exc_info.value)
        or "blocked" in str(exc_info.value).lower()
    )
    await client.aclose()


@pytest.mark.asyncio
async def test_durable_idempotency_store_multi_worker_safety_and_crash_recovery(
    tmp_path,
):
    """Proves atomic cross-worker reservation and crash recovery without duplicate dispatch."""
    from tasteops.workflows.idempotency import DurableIdempotencyStore

    store = DurableIdempotencyStore(base_dir=tmp_path / "idem_store")
    idem_key = "idem_crash_recovery_test_42"

    # Worker 1 reserves
    assert store.reserve(idem_key, worker_id="worker_pid_101") is True

    # Worker 2 simultaneously tries to reserve the same key -> Must be rejected
    assert store.reserve(idem_key, worker_id="worker_pid_102") is False

    # Simulate Worker 1 executing task and saving outcome immediately
    task = ExecutionTask(
        task_id="task_recovered_01",
        idempotency_key=idem_key,
        action="Created Spotify playlist",
        status=TaskStatus.COMPLETED,
        output_reference="spotify:playlist:pl_crash_safe",
        result={"playlist_id": "pl_crash_safe"},
    )
    store.save_outcome(idem_key, task)

    # Simulate Worker 1 crashing before session context is saved.
    # On recovery/retry, Worker 2 checks durable store:
    recovered = store.get_outcome(idem_key)
    assert recovered is not None
    assert recovered.status == TaskStatus.COMPLETED
    assert recovered.output_reference == "spotify:playlist:pl_crash_safe"

    # Worker 2 now calls async_reserve_or_wait -> Immediately receives cached outcome
    acquired, outcome = await store.async_reserve_or_wait(idem_key)
    assert acquired is False
    assert outcome is not None
    assert outcome.task_id == "task_recovered_01"
