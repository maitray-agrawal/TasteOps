"""TasteOps New Space Workflow Integration Tests.

Validates the full New Space workflow:
Collects:
- business/brand
- location
- audience
- positioning
- goals
- budget
- constraints
- cultural preferences
- optional references

Flow:
POST /spaces
        ↓
POST /spaces/{space_id}/analyze
        ↓
session page (GET /sessions/{session_id})

The Cultural Twin view must clearly display:
- audience profile
- cultural themes
- mood
- anchor entities
- resolved entities
- resolved tags
- constraints
- exclusions
- confidence
- evidence
- provenance

Clearly distinguishes:
SOURCE EVIDENCE
INFERENCE
RECOMMENDATION

If evidence is missing, shows that it is missing.
Never invents Qloo entities, scores, IDs, or evidence.
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
from tests.fixtures.demo_mumbai_boutique_hotel import (
    MUMBAI_DEMO_HINTS,
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
def client(tmp_path, mock_mcp_adapter):
    """Provides a fully integrated TestClient with real SQLite persistence and mock MCP."""
    adapter, _, _, _ = mock_mcp_adapter
    db_path = tmp_path / "test_new_space_workflow.db"
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
        title="TasteOps New Space Integration Test",
        environment="test",
        database_path=str(db_path),
    )
    app = create_app(settings=settings)

    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_space_repository] = lambda: space_repo
    app.dependency_overrides[get_service] = lambda: service

    with TestClient(app) as tc:
        yield tc, db, service


# ---------------------------------------------------------------------------
# 1. New Space Workflow: POST /spaces -> POST analyze -> GET session
# ---------------------------------------------------------------------------
def test_new_space_complete_workflow(client, mock_qloo_api):
    tc, db, service = client

    # Step 1: POST /spaces collecting all required fields
    create_payload = {
        "name": "Kitsuné Musique Lab Kyoto",
        "business_type": "Analog Vinyl Listening Bar & Cafe",
        "brand": "Maison Kitsuné",
        "location": {
            "city": "Kyoto",
            "country": "Japan",
            "address": "Gion Historic District, Higashiyama",
            "latitude": 35.0037,
            "longitude": 135.7772,
            "radius_meters": 2000,
        },
        "target_audience": "Design purists, vinyl collectors, ambient music lovers aged 25-45",
        "positioning": "Underground Franco-Japanese sound and coffee sanctuary",
        "goals": [
            "Bridge Parisian indie music with Kyoto craftsmanship",
            "Foster intimate analog community",
        ],
        "budget": "$150,000 USD / High-end boutique allocation",
        "desired_mood": "Warm intimate acoustic warmth, wabi-sabi minimalism, golden-hour circadian lighting",
        "cultural_preferences": [
            "Japanese jazz kissa culture",
            "Japanese ambient electronic music",
            "artisanal fermented teas",
        ],
        "constraints": [
            "Acoustic cap at 78 dB",
            "Timber-only resonance",
            "No digital screens in main listening lounge",
        ],
        "anchor_entities": [
            "Ryuichi Sakamoto",
            "Midori Takada",
            "Blue Bottle Coffee",
            "Aesop",
        ],
    }

    space_resp = tc.post("/api/v1/spaces", json=create_payload)
    assert space_resp.status_code == 201
    space_data = space_resp.json()
    space_id = space_data["space_id"]
    assert space_id.startswith("space_")
    assert space_data["name"] == "Kitsuné Musique Lab Kyoto"
    assert space_data["brief"]["brand"] == "Maison Kitsuné"
    assert space_data["brief"]["business_type"] == "Analog Vinyl Listening Bar & Cafe"
    assert space_data["brief"]["target_audience"] == create_payload["target_audience"]
    assert space_data["brief"]["positioning"] == create_payload["positioning"]
    assert space_data["brief"]["desired_mood"] == create_payload["desired_mood"]
    assert space_data["brief"]["anchor_entities"] == create_payload["anchor_entities"]

    # Step 2: POST /spaces/{space_id}/analyze
    analyze_resp = tc.post(
        f"/api/v1/spaces/{space_id}/analyze",
        json={"hints": MUMBAI_DEMO_HINTS, "auto_run": True, "take_per_category": 5},
    )
    assert analyze_resp.status_code == 200
    analyze_data = analyze_resp.json()
    session_id = analyze_data["session_id"]
    assert session_id is not None
    assert analyze_data["current_state"] == "AWAITING_APPROVAL"

    # Step 3: session page (GET /sessions/{session_id})
    session_resp = tc.get(f"/api/v1/sessions/{session_id}")
    assert session_resp.status_code == 200
    session_data = session_resp.json()

    # Verify Cultural Twin fields:
    ct = session_data["cultural_twin"]
    assert ct is not None

    # Audience profile
    assert ct["audience_profile"] != ""
    assert isinstance(ct["audience_profile"], str)

    # Cultural themes
    assert isinstance(ct["cultural_themes"], list)
    assert len(ct["cultural_themes"]) > 0

    # Mood profile
    assert ct["mood_profile"] != ""
    assert isinstance(ct["mood_profile"], str)

    # Anchor entities (Source Evidence)
    assert isinstance(ct["anchor_entities"], list)
    assert len(ct["anchor_entities"]) > 0

    # Resolved entities (Source Evidence)
    assert isinstance(ct["resolved_entities"], list)
    for ent in ct["resolved_entities"]:
        assert ent["id"] != ""
        assert ent["name"] != ""
        assert ent["type"] != ""
        assert 0.0 <= ent["confidence"] <= 1.0
        assert ent["source"] != ""
        assert "evidence" in ent
        assert isinstance(ent["evidence"], dict)

    # Resolved tags
    assert isinstance(ct["resolved_tags"], list)
    assert "resolved_tag_details" in ct
    assert isinstance(ct["resolved_tag_details"], list)

    # Constraints & Exclusions (Inference)
    assert "cultural_constraints" in ct
    assert isinstance(ct["cultural_constraints"], list)
    assert "exclusions" in ct
    assert isinstance(ct["exclusions"], list)

    # Confidence (Inference)
    assert 0.0 <= ct["confidence"] <= 1.0

    # Evidence & Provenance (Source Evidence)
    assert "evidence" in ct
    assert isinstance(ct["evidence"], list)
    assert "provenance" in ct
    assert isinstance(ct["provenance"], list)
    assert len(ct["provenance"]) > 0

    # Verify Distinction:
    # 1. SOURCE EVIDENCE: anchor_entities, resolved_entities (with Qloo URN/ID and source), provenance
    assert all(
        "qloo" in p["source"].lower() or "search" in p["source"].lower()
        for p in ct["provenance"]
    )

    # 2. INFERENCE: audience_profile, mood_profile, cultural_themes, cultural_constraints, exclusions
    assert len(ct["cultural_themes"]) > 0

    # 3. RECOMMENDATION: cultural_matrix_summary top affinities
    mat_summary = session_data["cultural_matrix_summary"]
    assert mat_summary is not None
    assert mat_summary["total_entities"] > 0
    assert len(mat_summary["top_affinities"]) > 0

    for items in mat_summary["top_affinities"].values():
        for item in items:
            assert item["id"] != ""
            assert item["name"] != ""
            assert 0.0 <= item["affinity"] <= 1.0
            assert not item["id"].startswith("invented_")


# ---------------------------------------------------------------------------
# 2. Missing Evidence Handling: Brief without anchors
# ---------------------------------------------------------------------------
def test_missing_evidence_handling_in_cultural_twin(client, mock_qloo_api):
    tc, db, service = client

    # Space registered with NO anchor entities
    space_resp = tc.post(
        "/api/v1/spaces",
        json={
            "name": "Minimal Art House",
            "business_type": "Contemporary Art Gallery & Cafe",
            "desired_mood": "Minimalist monochrome quietude",
            "target_audience": "Contemporary art curators",
            "positioning": "Experimental silent gallery",
            "anchor_entities": [],  # explicitly empty
        },
    )
    assert space_resp.status_code == 201
    space_id = space_resp.json()["space_id"]

    analyze_resp = tc.post(
        f"/api/v1/spaces/{space_id}/analyze",
        json={
            "hints": {
                "business_type": "Contemporary Art Gallery & Cafe",
                "desired_mood": "Minimalist monochrome quietude",
                "location": {
                    "city": "New York",
                    "country": "USA",
                    "latitude": 40.7128,
                    "longitude": -74.0060,
                },
            },
            "auto_run": True,
        },
    )
    assert analyze_resp.status_code == 200
    session_id = analyze_resp.json()["session_id"]

    session_resp = tc.get(f"/api/v1/sessions/{session_id}")
    ct = session_resp.json()["cultural_twin"]

    # When no anchors provided in brief, anchor_entities is empty
    assert ct["anchor_entities"] == []
    # Confidence remains bounded and calculated honestly
    assert 0.0 <= ct["confidence"] <= 1.0
