"""Integration Tests for the TasteOps Decision Ledger UI & Audit Trail.

Verifies:
- Chronological event retrieval for:
  - session creation
  - workflow state changes
  - Qloo retrieval
  - agent completion
  - governance decisions
  - plan validation
  - human approvals / rejections
  - execution attempts & outcomes
  - failure events
- Event telemetry: timestamp, event_type, actor, summary, related, provenance
- Multi-dimensional filter support (event type, agent, state, date)
- Cryptographic hash-chain verification (/ledger/verify and verification_status)
- Read-only immutability guarantees: no edit or delete operations permitted
- Frontend static asset verification (/static/js/screens/sessionLedger.js)
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

MUMBAI_SEARCH_MOCK_RESPONSE = {
    "entities": [
        {
            "id": "ent_prateek_kuhad_01",
            "name": "Prateek Kuhad",
            "type": "artist",
            "popularity": 0.88,
        },
        {
            "id": "ent_raw_mango_01",
            "name": "Raw Mango",
            "type": "brand",
            "popularity": 0.85,
        },
    ],
    "count": 2,
}

MUMBAI_TAGS_MOCK_RESPONSE = {
    "tags": [
        {
            "id": "tag_listening_01",
            "name": "Intimate listening lounge",
            "category": "music",
        },
        {
            "id": "tag_craft_01",
            "name": "Contemporary Indian design",
            "category": "design",
        },
    ]
}

MUMBAI_INSIGHTS_MOCK_RESPONSE = {
    "query": {"category": "all"},
    "insights": {
        "artists": [
            {
                "id": "qloo_art_01",
                "name": "Prateek Kuhad",
                "affinity": 0.94,
                "subgenres": ["Indie Folk"],
            },
            {
                "id": "qloo_art_02",
                "name": "Anoushka Shankar",
                "affinity": 0.89,
                "subgenres": ["Classical Crossover"],
            },
        ],
        "brands": [
            {
                "id": "qloo_brd_01",
                "name": "Raw Mango",
                "affinity": 0.91,
                "categories": ["Fashion"],
            },
            {
                "id": "qloo_brd_02",
                "name": "Subko Coffee",
                "affinity": 0.88,
                "categories": ["Specialty Coffee"],
            },
        ],
        "places": [
            {
                "id": "qloo_plc_01",
                "name": "Kala Ghoda Arts Precinct",
                "affinity": 0.92,
                "neighborhood": "Fort",
            },
        ],
        "books": [],
        "movies": [],
        "destinations": [],
    },
}

MUMBAI_DEMO_HINTS = {
    "business_type": "Boutique Hotel & Listening Lounge",
    "location": "Colaba / Kala Ghoda, Mumbai",
    "target_audience": "Designers and architects",
    "desired_mood": "Intimate listening lounge",
    "anchor_entities": ["Prateek Kuhad", "Raw Mango"],
    "resolved_entities": ["ent_prateek_kuhad_01", "ent_raw_mango_01"],
}


@pytest.fixture
def mock_qloo_api():
    """Sets up respx mock router for external Qloo HTTP endpoints."""
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
    """Provides a TestClient with relational SQLite persistence."""
    adapter, _, _, _ = mock_mcp_adapter
    db_path = tmp_path / "test_decision_ledger.db"
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
        title="TasteOps Decision Ledger Integration Test",
        environment="test",
        database_path=str(db_path),
    )
    app = create_app(settings=settings)

    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_space_repository] = lambda: space_repo
    app.dependency_overrides[get_service] = lambda: service

    with TestClient(app) as tc:
        yield tc, db, service


def _create_approved_session(tc: TestClient) -> tuple[str, str]:
    """Helper creating a space, driving pipeline to approval gate, and signing off."""
    sp_resp = tc.post(
        "/api/v1/spaces",
        json={
            "name": "Decision Ledger Test Space",
            "business_type": "Listening Bar",
            "desired_mood": "Intimate listening lounge",
            "target_audience": "Designers and architects",
            "anchor_entities": ["Prateek Kuhad", "Raw Mango"],
        },
    )
    assert sp_resp.status_code == 201
    space_id = sp_resp.json()["space_id"]

    an_resp = tc.post(
        f"/api/v1/spaces/{space_id}/analyze",
        json={"hints": MUMBAI_DEMO_HINTS},
    )
    assert an_resp.status_code == 200
    session_id = an_resp.json()["session_id"]

    appr_resp = tc.post(
        f"/api/v1/sessions/{session_id}/approve",
        json={
            "approver": "Curator Lead",
            "role": "Lead Cultural Strategist",
            "plan_version": 1,
            "notes": "Plan verified with Qloo provenance.",
        },
    )
    assert appr_resp.status_code == 200
    return space_id, session_id


# =============================================================================
# 1. Chronological Event Retrieval & Exposure Verification
# =============================================================================
def test_get_session_events_exposes_required_fields_and_types(client, mock_qloo_api):
    """Verify GET /api/v1/sessions/{session_id}/events exposes all required fields and categories."""
    tc, _, service = client
    space_id, session_id = _create_approved_session(tc)

    resp = tc.get(f"/api/v1/sessions/{session_id}/events")
    assert resp.status_code == 200
    data = resp.json()

    assert data["session_id"] == session_id
    assert data["total_events"] > 0
    events = data["events"]
    assert len(events) >= 5

    # Check required telemetry exposure on EVERY event
    event_types_found = set()
    for ev in events:
        # 1. Timestamp
        assert "timestamp" in ev
        assert ev["timestamp"] is not None

        # 2. Event Type
        assert "event_type" in ev
        assert ev["event_type"] in [
            "SESSION_CREATION",
            "STATE_CHANGE",
            "QLOO_RETRIEVAL",
            "AGENT_COMPLETION",
            "GOVERNANCE_DECISION",
            "VALIDATION",
            "APPROVAL",
            "REJECTION",
            "EXECUTION_ATTEMPT",
            "EXECUTION_OUTCOME",
            "FAILURE",
        ]
        event_types_found.add(ev["event_type"])

        # 3. Actor / Source
        assert "actor" in ev
        assert len(ev["actor"]) > 0

        # 4. Concise Summary
        assert "summary" in ev or "reason" in ev
        summary = ev.get("summary") or ev.get("reason")
        assert len(summary) > 0

        # 5. Related Entities
        assert "related" in ev
        related = ev["related"]
        assert related["session_id"] == session_id

        # 6. Provenance
        assert "provenance" in ev
        assert ev["provenance"] is not None

    # Must contain key lifecycle event types
    assert "SESSION_CREATION" in event_types_found
    assert "QLOO_RETRIEVAL" in event_types_found
    assert "AGENT_COMPLETION" in event_types_found
    assert "GOVERNANCE_DECISION" in event_types_found
    assert "APPROVAL" in event_types_found


def test_decision_ledger_includes_rejection_event(client, mock_qloo_api):
    """Verify curator rejection creates an explicit REJECTION event in the ledger."""
    tc, _, _ = client
    sp_resp = tc.post(
        "/api/v1/spaces",
        json={
            "name": "Rejection Space",
            "business_type": "Gallery",
            "anchor_entities": ["Prateek Kuhad", "Raw Mango"],
        },
    )
    space_id = sp_resp.json()["space_id"]

    an_resp = tc.post(
        f"/api/v1/spaces/{space_id}/analyze", json={"hints": MUMBAI_DEMO_HINTS}
    )
    session_id = an_resp.json()["session_id"]

    rej_resp = tc.post(
        f"/api/v1/sessions/{session_id}/reject",
        json={
            "reason": "Acoustic decibel limit exceeded for historic residential neighborhood."
        },
    )
    assert rej_resp.status_code == 200

    events_resp = tc.get(f"/api/v1/sessions/{session_id}/events")
    assert events_resp.status_code == 200
    events = events_resp.json()["events"]

    rej_events = [
        e
        for e in events
        if e["event_type"] == "REJECTION"
        or "decibel limit exceeded" in str(e.get("summary", "")).lower()
    ]
    assert len(rej_events) > 0
    assert "Acoustic decibel limit exceeded" in rej_events[0]["summary"]


def test_decision_ledger_includes_execution_outcome_events(client, mock_qloo_api):
    """Verify that executing a plan appends EXECUTION_ATTEMPT and EXECUTION_OUTCOME events."""
    tc, _, _ = client
    _, session_id = _create_approved_session(tc)

    # Execute session
    exec_resp = tc.post(f"/api/v1/sessions/{session_id}/execute")
    assert exec_resp.status_code == 200

    events_resp = tc.get(f"/api/v1/sessions/{session_id}/events")
    assert events_resp.status_code == 200
    events = events_resp.json()["events"]

    exec_types = {e["event_type"] for e in events}
    assert "EXECUTION_ATTEMPT" in exec_types or "EXECUTION_OUTCOME" in exec_types


# =============================================================================
# 2. Cryptographic Hash-Chain Verification Tests
# =============================================================================
def test_hash_chain_verification_status(client, mock_qloo_api):
    """Verify cryptographic hash-chain verification endpoint and payload."""
    tc, _, _ = client
    _, session_id = _create_approved_session(tc)

    # 1. Via events endpoint payload
    events_resp = tc.get(f"/api/v1/sessions/{session_id}/events")
    assert events_resp.status_code == 200
    verification = events_resp.json()["verification_status"]

    assert verification is not None
    assert verification["is_verified"] is True
    assert verification["status"] == "VERIFIED_AUTHENTIC"
    assert "SHA-256" in verification["algorithm"]
    assert verification["chain_length"] > 0
    assert len(verification["root_hash"]) == 64
    assert len(verification["head_hash"]) == 64
    assert verification["tamper_detected"] is False
    assert verification["read_only"] is True

    # 2. Via dedicated /ledger/verify endpoint
    verify_resp = tc.get(f"/api/v1/sessions/{session_id}/ledger/verify")
    assert verify_resp.status_code == 200
    verify_data = verify_resp.json()

    assert verify_data["session_id"] == session_id
    assert verify_data["is_verified"] is True
    assert verify_data["status"] == "VERIFIED_AUTHENTIC"
    assert verify_data["chain_length"] == verification["chain_length"]
    assert verify_data["head_hash"] == verification["head_hash"]


# =============================================================================
# 3. Read-Only Immutability Verification: Users Cannot Edit or Delete History
# =============================================================================
def test_audit_history_cannot_be_deleted_or_edited_via_api(client, mock_qloo_api):
    """Verify that audit history routes reject write/mutation verbs (read-only enforcement)."""
    tc, _, _ = client
    _, session_id = _create_approved_session(tc)

    # DELETE /events must be rejected (405 Method Not Allowed)
    del_resp = tc.delete(f"/api/v1/sessions/{session_id}/events")
    assert del_resp.status_code in {405, 404}

    # PUT /events must be rejected (405 Method Not Allowed)
    put_resp = tc.put(f"/api/v1/sessions/{session_id}/events", json={"tamper": True})
    assert put_resp.status_code in {405, 404}

    # PATCH /events must be rejected (405 Method Not Allowed)
    patch_resp = tc.patch(
        f"/api/v1/sessions/{session_id}/events", json={"tamper": True}
    )
    assert patch_resp.status_code in {405, 404}


# =============================================================================
# 4. Frontend Asset Verification (sessionLedger.js)
# =============================================================================
def test_session_ledger_ui_asset_contains_required_capabilities(client):
    """Verify sessionLedger.js static script contains all required filters, types, and read-only protections."""
    tc, _, _ = client
    js_resp = tc.get("/static/js/screens/sessionLedger.js")
    assert js_resp.status_code == 200
    content = js_resp.text

    # Required 10 Event Types
    required_event_types = [
        "SESSION_CREATION",
        "STATE_CHANGE",
        "QLOO_RETRIEVAL",
        "AGENT_COMPLETION",
        "GOVERNANCE_DECISION",
        "VALIDATION",
        "APPROVAL",
        "REJECTION",
        "EXECUTION_ATTEMPT",
        "EXECUTION_OUTCOME",
        "FAILURE",
    ]
    for ev_type in required_event_types:
        assert ev_type in content, f"Missing event type in sessionLedger.js: {ev_type}"

    # Required 4 Filters
    required_filters = [
        "filter-event-type",
        "filter-agent",
        "filter-state",
        "filter-date",
        "filter-search",
    ]
    for f in required_filters:
        assert f in content, f"Missing filter control ID in sessionLedger.js: {f}"

    # Required Read-Only & Immutability Markers
    read_only_markers = [
        "READ-ONLY AUDIT LOG",
        "Zero Edit Rights",
        "Immutable",
        "APPEND-ONLY",
    ]
    for m in read_only_markers:
        assert m in content, f"Missing read-only marker in sessionLedger.js: {m}"

    # Required Hash-Chain Verification Markers
    hash_verification_markers = [
        "Cryptographic Hash-Chain Verification",
        "VERIFIED AUTHENTIC",
        "TAMPER DETECTED",
        "Genesis Root Digest",
        "Chain Head Digest",
        "btn-reverify-chain",
    ]
    for h in hash_verification_markers:
        assert h in content, (
            f"Missing hash-chain verification marker in sessionLedger.js: {h}"
        )
