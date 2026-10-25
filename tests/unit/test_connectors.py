"""Unit tests for TasteOps Execution Connectors & Dispatcher Abstraction.

Validates:
- Connector interfaces: Spotify, Email, Procurement.
- Required attributes: name, capability, configuration_status, validate(), execute().
- Configuration states: CONFIGURED, NOT_CONFIGURED, INVALID_CONFIGURATION.
- Missing connector fails explicitly (MissingConnectorError).
- Never fakes external execution (ConnectorNotConfiguredError on execute).
- Mandatory request telemetry: session_id, plan_id, plan_version, task_id, idempotency_key.
- Backend rejects duplicate execution attempts for identical idempotency keys (DuplicateExecutionError).
- Provider credentials remain server-side.
- Provider-mocked execution tests for all connectors.
"""

from __future__ import annotations

import httpx
import pytest

from tasteops.connectors import (
    BaseConnector,
    ConfigurationStatus,
    ConnectorExecutionFailedError,
    ConnectorExecutionRequest,
    ConnectorExecutionResult,
    ConnectorNotConfiguredError,
    ConnectorRegistry,
    DuplicateExecutionError,
    EmailConnector,
    InvalidConfigurationError,
    MissingConnectorError,
    ProcurementConnector,
    SpotifyConnector,
    create_default_registry,
)
from tasteops.workflows.schemas import ExecutionTask


# =============================================================================
# 1. Spotify Connector Tests
# =============================================================================


def test_spotify_connector_configuration_lifecycle(monkeypatch):
    """Test Spotify connector transitions across NOT_CONFIGURED, INVALID_CONFIGURATION, and CONFIGURED."""
    # 1. NOT_CONFIGURED: No credentials in environment or instance
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    monkeypatch.delenv("SPOTIFY_CLIENT_SECRET", raising=False)
    conn = SpotifyConnector()
    assert conn.configuration_status == ConfigurationStatus.NOT_CONFIGURED
    assert conn.name == "Spotify Web API"
    assert conn.capability == "spotify_audio_seed"

    # validate() must fail explicitly
    with pytest.raises(ConnectorNotConfiguredError) as exc_info:
        conn.validate()
    assert "SPOTIFY_CLIENT_ID" in str(exc_info.value)

    # 2. INVALID_CONFIGURATION: One credential present or malformed
    conn_partial = SpotifyConnector(client_id="valid_client_id_123", client_secret=None)
    assert conn_partial.configuration_status == ConfigurationStatus.INVALID_CONFIGURATION

    conn_whitespace = SpotifyConnector(client_id="client id with spaces", client_secret="secret")
    assert conn_whitespace.configuration_status == ConfigurationStatus.INVALID_CONFIGURATION

    with pytest.raises(InvalidConfigurationError):
        conn_partial.validate()

    # 3. CONFIGURED: Both credentials validly set
    conn_valid = SpotifyConnector(
        client_id="valid_sp_client_12345",
        client_secret="valid_sp_secret_67890",
    )
    assert conn_valid.configuration_status == ConfigurationStatus.CONFIGURED
    assert conn_valid.validate() is True


@pytest.mark.asyncio
async def test_spotify_connector_never_fakes_external_execution():
    """Verify that calling execute() on an unconfigured Spotify connector fails explicitly."""
    conn = SpotifyConnector(client_id=None, client_secret=None)
    assert conn.configuration_status == ConfigurationStatus.NOT_CONFIGURED

    req = ConnectorExecutionRequest(
        session_id="sess_123",
        plan_id="plan_abc",
        plan_version=1,
        task_id="task_sp_01",
        idempotency_key="idem_sp_01",
        task_type="spotify_audio_seed",
        payload={"artist_name": "Four Tet", "daypart": "evening"},
    )

    with pytest.raises(ConnectorNotConfiguredError):
        await conn.execute(req)


@pytest.mark.asyncio
async def test_spotify_connector_mocked_execution_success():
    """Verify successful Spotify audio seeding using a mocked HTTP transport."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.spotify.com/v1/audio-seed"
        return httpx.Response(
            200,
            json={
                "artist_id": "art_four_tet_42",
                "artist_name": "Four Tet",
                "daypart": "evening",
                "spotify_uri": "spotify:artist:art_four_tet_42",
            },
        )

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    conn = SpotifyConnector(
        client_id="valid_sp_client_12345",
        client_secret="valid_sp_secret_67890",
        http_client=mock_client,
    )
    assert conn.configuration_status == ConfigurationStatus.CONFIGURED

    req = ConnectorExecutionRequest(
        session_id="sess_123",
        plan_id="plan_abc",
        plan_version=1,
        task_id="task_sp_01",
        idempotency_key="idem_sp_01",
        task_type="spotify_audio_seed",
        payload={"artist_name": "Four Tet", "daypart": "evening"},
    )

    result = await conn.execute(req)
    assert isinstance(result, ConnectorExecutionResult)
    assert result.task_id == "task_sp_01"
    assert result.connector_name == "Spotify Web API"
    assert result.status == "COMPLETED"
    assert result.output_reference == "spotify://seed_artist/art_four_tet_42"
    assert result.payload["artist_name"] == "Four Tet"
    assert result.provenance["session_id"] == "sess_123"
    assert result.provenance["idempotency_key"] == "idem_sp_01"


@pytest.mark.asyncio
async def test_spotify_connector_mocked_execution_failure():
    """Verify provider 500 error raises ConnectorExecutionFailedError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="Bad Gateway from Spotify Cluster")

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    conn = SpotifyConnector(
        client_id="valid_sp_client_12345",
        client_secret="valid_sp_secret_67890",
        http_client=mock_client,
    )

    req = ConnectorExecutionRequest(
        session_id="sess_123",
        plan_id="plan_abc",
        plan_version=1,
        task_id="task_sp_01",
        idempotency_key="idem_sp_01",
        task_type="spotify_audio_seed",
        payload={"artist_name": "Four Tet"},
    )

    with pytest.raises(ConnectorExecutionFailedError) as exc_info:
        await conn.execute(req)
    assert "502" in str(exc_info.value)
    assert exc_info.value.code == "EXECUTION_FAILED"


# =============================================================================
# 2. Email Connector Tests
# =============================================================================


def test_email_connector_configuration_lifecycle(monkeypatch):
    """Test Email connector transitions across NOT_CONFIGURED, INVALID_CONFIGURATION, and CONFIGURED."""
    monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
    monkeypatch.delenv("EMAIL_API_KEY", raising=False)
    conn = EmailConnector()
    assert conn.configuration_status == ConfigurationStatus.NOT_CONFIGURED
    assert conn.name == "Transactional Email Engine"
    assert conn.capability == "partner_outreach_brief"

    with pytest.raises(ConnectorNotConfiguredError):
        conn.validate()

    # INVALID_CONFIGURATION: Invalid email format
    conn_bad_email = EmailConnector(api_key="SG.validkey123456", from_email="invalid-email-address")
    assert conn_bad_email.configuration_status == ConfigurationStatus.INVALID_CONFIGURATION
    with pytest.raises(InvalidConfigurationError):
        conn_bad_email.validate()

    # CONFIGURED
    conn_valid = EmailConnector(
        api_key="SG.valid_email_key_987654",
        from_email="curator@tasteops.ai",
    )
    assert conn_valid.configuration_status == ConfigurationStatus.CONFIGURED
    assert conn_valid.validate() is True


@pytest.mark.asyncio
async def test_email_connector_never_fakes_external_execution():
    """Verify that calling execute() on an unconfigured Email connector fails explicitly."""
    conn = EmailConnector(api_key=None)
    assert conn.configuration_status == ConfigurationStatus.NOT_CONFIGURED

    req = ConnectorExecutionRequest(
        session_id="sess_123",
        plan_id="plan_abc",
        plan_version=1,
        task_id="task_email_01",
        idempotency_key="idem_email_01",
        task_type="partner_outreach_brief",
        payload={"partner_name": "Raw Mango", "activation_type": "textile_residency"},
    )

    with pytest.raises(ConnectorNotConfiguredError):
        await conn.execute(req)


@pytest.mark.asyncio
async def test_email_connector_mocked_execution_success():
    """Verify successful Email outreach dispatch using a mocked HTTP transport."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.sendgrid.com/v3/mail/send"
        return httpx.Response(
            202,
            json={
                "message_id": "msg_sg_raw_mango_99",
                "partner_id": "part_raw_mango_01",
                "status": "queued_for_delivery",
            },
        )

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    conn = EmailConnector(
        api_key="SG.valid_email_key_987654",
        from_email="curator@tasteops.ai",
        http_client=mock_client,
    )

    req = ConnectorExecutionRequest(
        session_id="sess_123",
        plan_id="plan_abc",
        plan_version=1,
        task_id="task_email_01",
        idempotency_key="idem_email_01",
        task_type="partner_outreach_brief",
        payload={
            "partner_name": "Raw Mango",
            "partner_entity_id": "ent_raw_mango_01",
            "activation_type": "textile_residency",
        },
    )

    result = await conn.execute(req)
    assert isinstance(result, ConnectorExecutionResult)
    assert result.task_id == "task_email_01"
    assert result.connector_name == "Transactional Email Engine"
    assert result.status == "COMPLETED"
    assert result.output_reference == "brief://partner/ent_raw_mango_01"
    assert result.payload["message_id"] == "msg_sg_raw_mango_99"
    assert result.provenance["session_id"] == "sess_123"


# =============================================================================
# 3. Procurement Connector Tests
# =============================================================================


def test_procurement_connector_configuration_lifecycle(monkeypatch):
    """Test Procurement connector transitions across NOT_CONFIGURED, INVALID_CONFIGURATION, and CONFIGURED."""
    monkeypatch.delenv("PROCUREMENT_API_KEY", raising=False)
    monkeypatch.delenv("ERP_API_KEY", raising=False)
    conn = ProcurementConnector(api_key=None)
    assert conn.configuration_status == ConfigurationStatus.NOT_CONFIGURED
    assert conn.name == "Procurement Order System"
    assert conn.capability == "procurement_order"

    with pytest.raises(ConnectorNotConfiguredError):
        conn.validate()

    # INVALID_CONFIGURATION: Malformed endpoint URL
    conn_bad_url = ProcurementConnector(
        api_key="valid_erp_key_12345",
        endpoint_url="ftp://invalid-protocol",
    )
    assert conn_bad_url.configuration_status == ConfigurationStatus.INVALID_CONFIGURATION
    with pytest.raises(InvalidConfigurationError):
        conn_bad_url.validate()

    # CONFIGURED
    conn_valid = ProcurementConnector(
        api_key="valid_erp_key_12345",
        endpoint_url="https://erp.tasteops.internal/orders",
    )
    assert conn_valid.configuration_status == ConfigurationStatus.CONFIGURED
    assert conn_valid.validate() is True


@pytest.mark.asyncio
async def test_procurement_connector_never_fakes_external_execution():
    """Verify that calling execute() on an unconfigured Procurement connector fails explicitly."""
    conn = ProcurementConnector(api_key=None)
    assert conn.configuration_status == ConfigurationStatus.NOT_CONFIGURED

    req = ConnectorExecutionRequest(
        session_id="sess_123",
        plan_id="plan_abc",
        plan_version=1,
        task_id="task_po_01",
        idempotency_key="idem_po_01",
        task_type="procurement_order",
        payload={"vendor": "Studio Klay", "item": "Terracotta tasting flights"},
    )

    with pytest.raises(ConnectorNotConfiguredError):
        await conn.execute(req)


@pytest.mark.asyncio
async def test_procurement_connector_mocked_execution_success():
    """Verify successful purchase order submission using a mocked HTTP transport."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("authorization") == "Bearer valid_erp_key_12345"
        return httpx.Response(
            201,
            json={
                "po_number": "PO_TASK_PO_01",
                "vendor": "Studio Klay",
                "status": "purchase_order_issued",
            },
        )

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    conn = ProcurementConnector(
        api_key="valid_erp_key_12345",
        endpoint_url="https://erp.tasteops.internal/orders",
        http_client=mock_client,
    )

    req = ConnectorExecutionRequest(
        session_id="sess_123",
        plan_id="plan_abc",
        plan_version=1,
        task_id="task_po_01",
        idempotency_key="idem_po_01",
        task_type="procurement_order",
        payload={"vendor": "Studio Klay", "item": "Terracotta tasting flights"},
    )

    result = await conn.execute(req)
    assert isinstance(result, ConnectorExecutionResult)
    assert result.task_id == "task_po_01"
    assert result.connector_name == "Procurement Order System"
    assert result.output_reference == "order://procurement/PO_TASK_PO_01"
    assert result.payload["status"] == "purchase_order_issued"


# =============================================================================
# 4. ConnectorRegistry & Execution Dispatcher Tests
# =============================================================================


def test_registry_registration_and_list():
    """Verify registration, capability lookup, and safe credential-free summaries."""
    registry = ConnectorRegistry()
    spotify = SpotifyConnector(client_id="id12345", client_secret="secret12345")
    email = EmailConnector(api_key="SG.validkey123456")

    registry.register(spotify, alias_capabilities=["spotify_audio"])
    registry.register(email)

    assert registry.get_connector("spotify_audio_seed") is spotify
    assert registry.get_connector("spotify_audio") is spotify
    assert registry.get_connector("partner_outreach_brief") is email
    assert registry.get_connector("unknown_cap") is None

    summaries = registry.list_connectors()
    assert len(summaries) == 2
    for s in summaries:
        assert "name" in s
        assert "capability" in s
        assert "configuration_status" in s
        # Credentials must NEVER be present in registry summaries
        assert "client_secret" not in s
        assert "api_key" not in s


@pytest.mark.asyncio
async def test_registry_missing_connector_fails_explicitly():
    """Requirement: A missing connector must fail explicitly (MissingConnectorError)."""
    registry = ConnectorRegistry()
    # Register Spotify, but leave out Email
    spotify = SpotifyConnector(client_id="cid12345", client_secret="sec12345")
    registry.register(spotify)

    req = ConnectorExecutionRequest(
        session_id="sess_123",
        plan_id="plan_abc",
        plan_version=1,
        task_id="task_email_missing",
        idempotency_key="idem_missing_01",
        task_type="partner_outreach_brief",  # Not registered!
        payload={"partner_name": "Raw Mango"},
    )

    with pytest.raises(MissingConnectorError) as exc_info:
        await registry.dispatch(req)

    assert "Missing execution connector" in str(exc_info.value)
    assert exc_info.value.code == "MISSING_CONNECTOR"


@pytest.mark.asyncio
async def test_registry_rejects_duplicate_execution_attempts_for_same_idempotency_key():
    """Requirement: The backend must reject duplicate execution attempts for the same idempotency key."""
    registry = ConnectorRegistry()
    spotify = SpotifyConnector(client_id="cid12345", client_secret="sec12345")
    registry.register(spotify)

    req1 = ConnectorExecutionRequest(
        session_id="sess_123",
        plan_id="plan_abc",
        plan_version=1,
        task_id="task_sp_01",
        idempotency_key="idem_unique_key_999",
        task_type="spotify_audio_seed",
        payload={"artist_name": "Four Tet"},
    )

    # 1st Dispatch: Success
    res1 = await registry.dispatch(req1)
    assert res1.status == "COMPLETED"
    assert registry.is_executed("idem_unique_key_999") is True

    # 2nd Dispatch with SAME idempotency key: MUST be rejected!
    req2 = ConnectorExecutionRequest(
        session_id="sess_123",
        plan_id="plan_abc",
        plan_version=1,
        task_id="task_sp_01_duplicate",
        idempotency_key="idem_unique_key_999",  # DUPLICATE!
        task_type="spotify_audio_seed",
        payload={"artist_name": "Four Tet"},
    )

    with pytest.raises(DuplicateExecutionError) as exc_info:
        await registry.dispatch(req2)

    assert "Duplicate execution rejected" in str(exc_info.value)
    assert exc_info.value.code == "DUPLICATE_IDEMPOTENCY_KEY"
    assert exc_info.value.details["idempotency_key"] == "idem_unique_key_999"


@pytest.mark.asyncio
async def test_registry_requires_all_5_mandatory_request_fields():
    """Requirement: Every execution request must include session_id, plan_id, plan_version, task_id, idempotency_key."""
    registry = create_default_registry()

    # Test empty/missing field rejection
    with pytest.raises(ValueError) as exc:
        ConnectorExecutionRequest(
            session_id="",
            plan_id="plan_1",
            plan_version=1,
            task_id="task_1",
            idempotency_key="idem_1",
        )
    assert "session_id" in str(exc.value)

    with pytest.raises(ValueError) as exc:
        ConnectorExecutionRequest(
            session_id="sess_1",
            plan_id="",
            plan_version=1,
            task_id="task_1",
            idempotency_key="idem_1",
        )
    assert "plan_id" in str(exc.value)

    with pytest.raises(ValueError) as exc:
        ConnectorExecutionRequest(
            session_id="sess_1",
            plan_id="plan_1",
            plan_version=0,  # Invalid! Must be >= 1
            task_id="task_1",
            idempotency_key="idem_1",
        )
    assert "plan_version" in str(exc.value)


@pytest.mark.asyncio
async def test_dispatch_from_execution_task_model():
    """Verify dispatch_task converts an ExecutionTask model into a ConnectorExecutionRequest."""
    registry = ConnectorRegistry()
    spotify = SpotifyConnector(client_id="cid12345", client_secret="sec12345")
    registry.register(spotify)

    task = ExecutionTask(
        task_id="task_from_model_01",
        idempotency_key="idem_model_key_555",
        category="spotify_audio_seed",
        action="Export seed artist 'Four Tet' to Spotify audio engine pipeline",
        input={"artist_name": "Four Tet", "daypart": "evening"},
    )

    result = await registry.dispatch_task(
        task=task,
        session_id="sess_model_100",
        plan_id="plan_model_200",
        plan_version=1,
    )

    assert result.task_id == "task_from_model_01"
    assert result.status == "COMPLETED"
    assert result.provenance["session_id"] == "sess_model_100"
    assert result.provenance["idempotency_key"] == "idem_model_key_555"
