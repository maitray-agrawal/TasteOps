"""Integration tests for Experience Blueprint Interface and Provenance Architecture.

Validates the Experience Blueprint requirements:
Display:
- strategic objective
- audience
- cultural positioning
- experience concept
- activation ideas
- partnership opportunities
- budget considerations
- risks
- evidence
- confidence

Every recommendation must have an evidence/provenance path.

Visually distinguish:
1. Evidence
2. Agent inference
3. Recommendation
4. Execution action

The interface must make it possible to answer:
"Why was this recommendation made?"
without exposing chain-of-thought.
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
from tasteops.workflows.states import WorkflowState
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
        router.get("/search").respond(
            status_code=200, json=MUMBAI_SEARCH_MOCK_RESPONSE
        )
        router.get("/v2/tags").respond(
            status_code=200, json=MUMBAI_TAGS_MOCK_RESPONSE
        )
        router.get("/v2/insights").respond(
            status_code=200, json=MUMBAI_INSIGHTS_MOCK_RESPONSE
        )
        yield router


@pytest.fixture
def client(tmp_path, mock_mcp_adapter):
    """Provides a TestClient with SQLite persistence and mock MCP."""
    adapter, _, _, _ = mock_mcp_adapter
    db_path = tmp_path / "test_experience_blueprint.db"
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
        title="TasteOps Experience Blueprint Integration Test",
        environment="test",
        database_path=str(db_path),
    )
    app = create_app(settings=settings)

    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_space_repository] = lambda: space_repo
    app.dependency_overrides[get_service] = lambda: service

    with TestClient(app) as tc:
        yield tc, db, service


def test_experience_blueprint_complete_telemetry(client, mock_qloo_api):
    """Verify that GET /api/v1/sessions/{session_id}/blueprint displays all required fields."""
    tc, db, service = client

    # Step 1: Create space
    space_resp = tc.post(
        "/api/v1/spaces",
        json={
            "name": "Ginza Listening Sanctuary",
            "business_type": "Audiophile Cafe & Listening Bar",
            "desired_mood": "Warm analog acoustic resonance, wabi-sabi minimalism",
            "target_audience": "Design purists, vinyl collectors, ambient music lovers",
            "positioning": "Tokyo-Parisian intimate sound and coffee sanctuary",
            "anchor_entities": ["Ryuichi Sakamoto", "Midori Takada", "Aesop", "Snow Peak"],
        },
    )
    assert space_resp.status_code == 201
    space_id = space_resp.json()["space_id"]

    # Step 2: Trigger analysis to reach AWAITING_APPROVAL
    analyze_resp = tc.post(
        f"/api/v1/spaces/{space_id}/analyze",
        json={"hints": MUMBAI_DEMO_HINTS, "auto_run": True},
    )
    assert analyze_resp.status_code == 200
    session_id = analyze_resp.json()["session_id"]

    # Step 3: Fetch Blueprint
    bp_resp = tc.get(f"/api/v1/sessions/{session_id}/blueprint")
    assert bp_resp.status_code == 200
    bp = bp_resp.json()

    # 1. Strategic Objective
    assert bp["strategic_objective"] is not None
    assert isinstance(bp["strategic_objective"], str)
    assert len(bp["strategic_objective"]) > 0

    # 2. Audience
    assert bp["audience"] is not None
    assert isinstance(bp["audience"], dict)
    assert "target_audience" in bp["audience"]
    assert "target_subcultures" in bp["audience"]
    assert isinstance(bp["audience"]["target_subcultures"], list)

    # 3. Cultural Positioning
    assert bp["cultural_positioning"] is not None
    assert isinstance(bp["cultural_positioning"], dict)
    assert "positioning_statement" in bp["cultural_positioning"]
    assert "cultural_pillars" in bp["cultural_positioning"]
    assert len(bp["cultural_positioning"]["cultural_pillars"]) > 0

    # 4. Experience Concept
    assert bp["experience_concept"] is not None
    assert isinstance(bp["experience_concept"], dict)
    assert "spatial_zones" in bp["experience_concept"]
    assert "soundscape_design" in bp["experience_concept"]
    assert "material_palette" in bp["experience_concept"]
    assert "hospitality_tempo" in bp["experience_concept"]

    # 5. Activation Ideas
    assert bp["activation_ideas"] is not None
    assert isinstance(bp["activation_ideas"], list)
    assert len(bp["activation_ideas"]) > 0
    for act in bp["activation_ideas"]:
        assert "title" in act
        assert "cadence" in act
        assert "format_description" in act

    # 6. Partnership Opportunities
    assert bp["partnership_opportunities"] is not None
    assert isinstance(bp["partnership_opportunities"], list)
    assert len(bp["partnership_opportunities"]) > 0
    for part in bp["partnership_opportunities"]:
        assert "brand" in part
        assert "partnership_concept" in part
        assert "score" in part

    # 7. Budget Considerations
    assert bp["budget_considerations"] is not None
    assert isinstance(bp["budget_considerations"], dict)
    assert "estimated_cost" in bp["budget_considerations"]
    assert "action_costs" in bp["budget_considerations"]

    # 8. Risks
    assert bp["risks"] is not None
    assert isinstance(bp["risks"], list)
    assert len(bp["risks"]) > 0
    for r in bp["risks"]:
        assert "risk" in r
        assert "category" in r

    # 9. Evidence
    assert bp["evidence"] is not None
    assert isinstance(bp["evidence"], list)
    assert len(bp["evidence"]) > 0
    for ev in bp["evidence"]:
        assert "entity_id" in ev
        assert "name" in ev
        assert "source" in ev

    # 10. Confidence
    assert 0.0 <= bp["confidence"] <= 1.0


def test_recommendation_provenance_path_answers_why_recommended(client, mock_qloo_api):
    """Verify that every recommendation has a 4-tier provenance path answering why it was made."""
    tc, db, service = client

    space_resp = tc.post(
        "/api/v1/spaces",
        json={
            "name": "Acoustic Tea Salon",
            "business_type": "Artisanal Tea & Sound Lounge",
            "anchor_entities": ["Blue Bottle Coffee", "Aesop"],
        },
    )
    space_id = space_resp.json()["space_id"]

    analyze_resp = tc.post(
        f"/api/v1/spaces/{space_id}/analyze",
        json={"hints": MUMBAI_DEMO_HINTS, "auto_run": True},
    )
    session_id = analyze_resp.json()["session_id"]

    bp_resp = tc.get(f"/api/v1/sessions/{session_id}/blueprint")
    assert bp_resp.status_code == 200
    bp = bp_resp.json()

    prov_map = bp["recommendation_provenance_map"]
    assert isinstance(prov_map, dict)
    assert len(prov_map) > 0

    # Test each recommendation in the map has the 4 distinct epistemic layers
    for rec_name, trail in prov_map.items():
        assert "entity_name" in trail
        assert "category" in trail

        # Layer 1: Ground-Truth Evidence
        assert "evidence" in trail
        ev = trail["evidence"]
        assert "entity_id" in ev
        assert "source" in ev
        assert "affinity" in ev

        # Layer 2: Agent Inference
        assert "agent_inference" in trail
        inf = trail["agent_inference"]
        assert "curatorial_rationale" in inf
        assert "confidence_score" in inf

        # Layer 3: Curatorial Recommendation
        assert "recommendation" in trail
        rec = trail["recommendation"]
        assert "title" in rec
        assert "role" in rec

        # Layer 4: Execution Action
        assert "execution_action" in trail
        act = trail["execution_action"]
        assert "task" in act
        assert "owner" in act


def test_no_raw_chain_of_thought_in_blueprint(client, mock_qloo_api):
    """Ensure zero chain-of-thought or raw internal prompts are leaked in the blueprint."""
    tc, db, service = client

    space_resp = tc.post(
        "/api/v1/spaces",
        json={
            "name": "Audit Sound Lab",
            "business_type": "Music Lounge",
            "anchor_entities": ["Blue Note"],
        },
    )
    space_id = space_resp.json()["space_id"]

    analyze_resp = tc.post(
        f"/api/v1/spaces/{space_id}/analyze",
        json={"hints": MUMBAI_DEMO_HINTS, "auto_run": True},
    )
    session_id = analyze_resp.json()["session_id"]

    bp_resp = tc.get(f"/api/v1/sessions/{session_id}/blueprint")
    raw_text = bp_resp.text.lower()

    forbidden_tokens = [
        "thought:",
        "chain-of-thought",
        "chain_of_thought",
        "internal reasoning:",
        "<think>",
        "</think>",
        "raw_prompt",
        "system_prompt",
    ]
    for token in forbidden_tokens:
        assert token not in raw_text, f"Forbidden chain-of-thought token detected: {token}"


def test_blueprint_route_and_static_asset_served(client):
    """Verify SPA shell route and static JS asset are served cleanly."""
    tc, _, _ = client

    # SPA shell route
    res = tc.get("/sessions/sess_demo_123/blueprint")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "TasteOps" in res.text

    # Static JS screen
    res_js = tc.get("/static/js/screens/sessionBlueprint.js")
    assert res_js.status_code == 200
    assert "javascript" in res_js.headers["content-type"]
    assert "renderSessionBlueprint" in res_js.text
    assert "tasteopsInspectProvenance" in res_js.text
