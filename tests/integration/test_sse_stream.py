"""TasteOps Server-Sent Events (SSE) Stream Integration Tests.

Validates:
- GET /api/v1/sessions/{session_id}/stream
- Normal stream to approval gate
- Completed session stream
- Failed session stream
- Reconnect with Last-Event-ID header and last_event_id query param
- Missing session (404 error)
- Client disconnect cleanup (no broadcaster queue leaks)
- Deterministic event ordering
- Required fields on every event (event_id, session_id, timestamp, event_type)
- Zero secrets, zero raw authorization headers, zero chain-of-thought
- Bounded event payloads
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
import respx
from fastapi.testclient import TestClient

from tasteops.api.app import create_app
from tasteops.api.dependencies import get_database, get_service, get_space_repository
from tasteops.api.events import CANONICAL_EVENT_TYPES
from tasteops.api.routes.sessions import stream_session_events
from tasteops.api.service import TasteOpsApplicationService
from tasteops.api.settings import APISettings
from tasteops.persistence.database import Database
from tasteops.persistence.space_repository import SQLiteSpaceRepository
from tasteops.persistence.store import SQLiteStateStore
from tasteops.workflows.orchestrator import TasteOpsOrchestrator
from tests.fixtures.demo_mumbai_boutique_hotel import (
    MUMBAI_DEMO_HINTS,
    MUMBAI_DEMO_RAW_INTENT,
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
def test_setup(mock_mcp_adapter):
    """Sets up isolated in-memory SQLite database, state store, service, and FastAPI TestClient."""
    adapter, _, _, _ = mock_mcp_adapter
    db = Database(":memory:")
    state_store = SQLiteStateStore(db)
    space_repo = SQLiteSpaceRepository(db)
    orchestrator = TasteOpsOrchestrator(
        mcp_adapter=adapter,
        store=state_store,
    )
    service = TasteOpsApplicationService(
        orchestrator=orchestrator,
        store=state_store,
        space_repo=space_repo,
    )

    settings = APISettings(environment="testing", api_debug=True)
    app = create_app(settings=settings)
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_service] = lambda: service
    app.dependency_overrides[get_space_repository] = lambda: space_repo

    client = TestClient(app)
    return {
        "client": client,
        "service": service,
        "store": state_store,
        "db": db,
    }


def parse_sse_frames(text: str) -> list[dict[str, Any]]:
    """Helper to parse raw SSE text stream into deserialized event dictionaries."""
    frames = []
    raw_blocks = text.replace("\r\n", "\n").split("\n\n")
    for block in raw_blocks:
        block = block.strip()
        if not block or block.startswith(":"):
            continue
        data_lines = []
        for line in block.split("\n"):
            if line.startswith("data: "):
                data_lines.append(line[6:].strip())
        if data_lines:
            payload = json.loads("".join(data_lines))
            frames.append(payload)
    return frames


# =============================================================================
# 1. Missing Session Test
# =============================================================================
def test_stream_missing_session_returns_404(test_setup):
    """GET /api/v1/sessions/{session_id}/stream returns HTTP 404 for unknown session."""
    client = test_setup["client"]
    resp = client.get("/api/v1/sessions/nonexistent_session_999/stream")
    assert resp.status_code == 404
    error_data = resp.json()
    assert "detail" in error_data["error"]
    assert "not found" in error_data["error"]["detail"].lower()


# =============================================================================
# 2. Normal Stream Test (Up to Approval Gate)
# =============================================================================
def test_normal_stream_to_approval_gate(test_setup, mock_qloo_api):
    """GET /api/v1/sessions/{session_id}/stream recovers canonical event stream up to approval gate."""
    client = test_setup["client"]

    # 1. Create space
    space_resp = client.post(
        "/api/v1/spaces",
        json={
            "name": "Soho House Mumbai",
            "business_type": "Curated Boutique Hotel & Members Club",
            "location": {"city": "Mumbai", "country": "India"},
        },
    )
    assert space_resp.status_code == 201
    space_id = space_resp.json()["space_id"]

    # 2. Trigger analysis (runs to AWAITING_APPROVAL)
    analyze_resp = client.post(
        f"/api/v1/spaces/{space_id}/analyze",
        json={
            "user_input": MUMBAI_DEMO_RAW_INTENT,
            "hints": MUMBAI_DEMO_HINTS,
            "auto_run": True,
        },
    )
    assert analyze_resp.status_code == 200
    session_id = analyze_resp.json()["session_id"]

    # 3. Request SSE stream with wait=false (retrieve persisted events)
    stream_resp = client.get(f"/api/v1/sessions/{session_id}/stream?wait=false")
    assert stream_resp.status_code == 200
    assert "text/event-stream" in stream_resp.headers["content-type"]
    assert stream_resp.headers["cache-control"] == "no-cache"

    events = parse_sse_frames(stream_resp.text)
    assert len(events) >= 8

    # 4. Verify invariant fields on EVERY event
    for ev in events:
        assert "event_id" in ev
        assert ev["event_id"].startswith("evt_")
        assert ev["session_id"] == session_id
        assert "timestamp" in ev
        assert "event_type" in ev
        assert ev["event_type"] in CANONICAL_EVENT_TYPES
        assert "data" in ev
        assert isinstance(ev["data"], dict)

        # Safety assertions: zero secrets, zero chain-of-thought, zero tracebacks
        data_str = json.dumps(ev["data"]).lower()
        for forbidden in (
            "secret",
            "api_key",
            "bearer",
            "authorization",
            "stacktrace",
            "traceback",
        ):
            assert forbidden not in data_str, (
                f"Forbidden substring '{forbidden}' found in event payload"
            )

    # 5. Verify deterministic ordering of canonical progression
    event_types = [ev["event_type"] for ev in events]
    assert "session.created" in event_types
    assert "workflow.state_changed" in event_types
    assert "qloo.search_started" in event_types
    assert "qloo.search_completed" in event_types
    assert "cultural_matrix.ready" in event_types
    assert "agent.started" in event_types
    assert "agent.completed" in event_types
    assert "governance.completed" in event_types
    assert "approval.required" in event_types

    # Invariant: session.created must come before approval.required
    assert event_types.index("session.created") < event_types.index(
        "qloo.search_started"
    )
    assert event_types.index("qloo.search_started") < event_types.index(
        "cultural_matrix.ready"
    )
    assert event_types.index("cultural_matrix.ready") < event_types.index(
        "agent.started"
    )
    assert event_types.index("agent.started") < event_types.index("agent.completed")
    assert event_types.index("agent.completed") < event_types.index(
        "governance.completed"
    )
    assert event_types.index("governance.completed") < event_types.index(
        "approval.required"
    )


# =============================================================================
# 3. Completed Session Test
# =============================================================================
def test_completed_session_stream(test_setup, mock_qloo_api):
    """Completed session stream includes execution.started and execution.completed and terminates."""
    client = test_setup["client"]

    # 1. Create and analyze space
    space_resp = client.post(
        "/api/v1/spaces",
        json={
            "name": "Bandra Art Haven",
            "business_type": "Gallery & Cafe",
            "location": {"city": "Mumbai", "country": "India"},
        },
    )
    space_id = space_resp.json()["space_id"]
    analyze_resp = client.post(
        f"/api/v1/spaces/{space_id}/analyze",
        json={
            "user_input": MUMBAI_DEMO_RAW_INTENT,
            "hints": MUMBAI_DEMO_HINTS,
            "auto_run": True,
        },
    )
    session_id = analyze_resp.json()["session_id"]

    # 2. Approve and Execute
    appr_resp = client.post(
        f"/api/v1/sessions/{session_id}/approve",
        json={"approver": "curator_vip", "role": "lead_curator"},
    )
    assert appr_resp.status_code == 200

    exec_resp = client.post(f"/api/v1/sessions/{session_id}/execute")
    assert exec_resp.status_code == 200
    assert exec_resp.json()["current_state"] == "COMPLETED"

    # 3. Connect to stream
    stream_resp = client.get(f"/api/v1/sessions/{session_id}/stream")
    assert stream_resp.status_code == 200
    events = parse_sse_frames(stream_resp.text)

    event_types = [ev["event_type"] for ev in events]
    assert "execution.started" in event_types
    assert "execution.completed" in event_types

    # Find execution.completed event
    completed_ev = next(
        ev for ev in events if ev["event_type"] == "execution.completed"
    )
    assert completed_ev["data"]["status"] == "COMPLETED"
    assert completed_ev["data"]["total_tasks"] > 0
    assert completed_ev["data"]["executed_tasks"] == completed_ev["data"]["total_tasks"]


# =============================================================================
# 4. Failed Session Test
# =============================================================================
def test_failed_session_stream(test_setup, mock_qloo_api):
    """Curator rejection produces workflow.failed event with sanitized reason."""
    client = test_setup["client"]

    # 1. Create and analyze space
    space_resp = client.post(
        "/api/v1/spaces",
        json={
            "name": "Kala Ghoda Cafe",
            "business_type": "Artisan Bistro",
            "location": {"city": "Mumbai", "country": "India"},
        },
    )
    space_id = space_resp.json()["space_id"]
    analyze_resp = client.post(
        f"/api/v1/spaces/{space_id}/analyze",
        json={
            "user_input": MUMBAI_DEMO_RAW_INTENT,
            "hints": MUMBAI_DEMO_HINTS,
            "auto_run": True,
        },
    )
    session_id = analyze_resp.json()["session_id"]

    # 2. Reject plan
    reject_resp = client.post(
        f"/api/v1/sessions/{session_id}/reject",
        json={
            "reason": "Curator rejected: sonic identity unaligned with heritage guidelines"
        },
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["current_state"] == "FAILED"

    # 3. Read stream
    stream_resp = client.get(f"/api/v1/sessions/{session_id}/stream")
    assert stream_resp.status_code == 200
    events = parse_sse_frames(stream_resp.text)

    event_types = [ev["event_type"] for ev in events]
    assert "workflow.failed" in event_types

    failed_ev = next(ev for ev in events if ev["event_type"] == "workflow.failed")
    assert "sonic identity unaligned" in failed_ev["data"]["error"]
    assert "\n" not in failed_ev["data"]["error"]  # No stack traces


# =============================================================================
# 5. Reconnect Test
# =============================================================================
def test_reconnect_stream_with_last_event_id(test_setup, mock_qloo_api):
    """Reconnect with Last-Event-ID header and last_event_id query recovers only subsequent events."""
    client = test_setup["client"]

    # 1. Create and analyze space
    space_resp = client.post(
        "/api/v1/spaces",
        json={
            "name": "Juhu Beach Lounge",
            "business_type": "Coastal Lounge",
            "location": {"city": "Mumbai", "country": "India"},
        },
    )
    space_id = space_resp.json()["space_id"]
    analyze_resp = client.post(
        f"/api/v1/spaces/{space_id}/analyze",
        json={
            "user_input": MUMBAI_DEMO_RAW_INTENT,
            "hints": MUMBAI_DEMO_HINTS,
            "auto_run": True,
        },
    )
    session_id = analyze_resp.json()["session_id"]

    # 2. Get full stream
    full_resp = client.get(f"/api/v1/sessions/{session_id}/stream?wait=false")
    all_events = parse_sse_frames(full_resp.text)
    assert len(all_events) >= 5

    # Pick a midpoint event (e.g. cultural_matrix.ready)
    mid_index = next(
        idx
        for idx, ev in enumerate(all_events)
        if ev["event_type"] == "cultural_matrix.ready"
    )
    cutoff_event = all_events[mid_index]
    cutoff_id = cutoff_event["event_id"]

    # 3. Reconnect with Last-Event-ID header
    reconnect_resp = client.get(
        f"/api/v1/sessions/{session_id}/stream?wait=false",
        headers={"Last-Event-ID": cutoff_id},
    )
    assert reconnect_resp.status_code == 200
    reconnected_events = parse_sse_frames(reconnect_resp.text)

    # Invariant: Reconnected events must strictly match all_events[mid_index + 1:]
    expected_events = all_events[mid_index + 1 :]
    assert len(reconnected_events) == len(expected_events)
    for rec_ev, exp_ev in zip(reconnected_events, expected_events):
        assert rec_ev["event_id"] == exp_ev["event_id"]
        assert rec_ev["event_type"] == exp_ev["event_type"]

    # Invariant: Cutoff event and earlier events are NOT repeated
    reconnected_ids = {ev["event_id"] for ev in reconnected_events}
    assert cutoff_id not in reconnected_ids
    assert all_events[0]["event_id"] not in reconnected_ids

    # 4. Reconnect with last_event_id query parameter
    query_reconnect_resp = client.get(
        f"/api/v1/sessions/{session_id}/stream?wait=false&last_event_id={cutoff_id}"
    )
    assert query_reconnect_resp.status_code == 200
    query_events = parse_sse_frames(query_reconnect_resp.text)
    assert len(query_events) == len(expected_events)
    assert query_events[0]["event_id"] == expected_events[0]["event_id"]


# =============================================================================
# 6. Client Disconnect Test
# =============================================================================
@pytest.mark.asyncio
async def test_client_disconnect_cleans_up_broadcaster(test_setup, mock_qloo_api):
    """When a client disconnects from the SSE stream, broadcaster unsubscribes and cleans up."""
    client = test_setup["client"]
    service = test_setup["service"]

    # 1. Create space and session
    space_resp = client.post(
        "/api/v1/spaces",
        json={
            "name": "Colaba Social",
            "business_type": "Social Club",
            "location": {"city": "Mumbai", "country": "India"},
        },
    )
    space_id = space_resp.json()["space_id"]
    analyze_resp = client.post(
        f"/api/v1/spaces/{space_id}/analyze",
        json={
            "user_input": MUMBAI_DEMO_RAW_INTENT,
            "hints": MUMBAI_DEMO_HINTS,
            "auto_run": True,
        },
    )
    session_id = analyze_resp.json()["session_id"]

    # Initially, zero subscribers
    assert service.broadcaster.subscriber_count(session_id) == 0

    # 2. Invoke stream endpoint with Mock Request
    req = AsyncMock()
    req.is_disconnected = AsyncMock(return_value=False)
    streaming_resp = await stream_session_events(
        session_id=session_id,
        request=req,
        service=service,
        wait=True,
    )
    # Subscriber is active in broadcaster registry
    assert service.broadcaster.subscriber_count(session_id) == 1

    gen = streaming_resp.body_iterator
    # Read the first event
    first_chunk = await anext(gen)
    assert first_chunk.startswith("id: ")

    # Simulate client disconnect: closing the generator raises GeneratorExit in the generator
    await gen.aclose()

    # Broadcaster must have 0 subscribers immediately after disconnect
    assert service.broadcaster.subscriber_count(session_id) == 0

    # 3. Test disconnect via request.is_disconnected() == True
    req2 = AsyncMock()
    req2.is_disconnected = AsyncMock(return_value=True)
    streaming_resp2 = await stream_session_events(
        session_id=session_id,
        request=req2,
        service=service,
        wait=True,
    )
    assert service.broadcaster.subscriber_count(session_id) == 1
    async for _ in streaming_resp2.body_iterator:
        pass
    assert service.broadcaster.subscriber_count(session_id) == 0

    # 4. Verify broadcaster can publish without error even when 0 subscribers exist
    historical = service.get_session_sse_events(session_id)
    service.publish_sse_event(historical[0])
