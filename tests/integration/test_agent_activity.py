"""Integration tests for Agent Activity View and Domain Agent Telemetry.

Validates the Agent Activity view requirements:
Show:
- Cultural Strategist
- Experience Architect
- Partnership Agent
- Governance / Execution Agent

For each agent show:
- status (RUNNING, COMPLETED, FAILED, RETRYING, BLOCKED, AWAITING_APPROVAL)
- start
- completion
- duration
- output summary
- validation status
- evidence count
- failure information

Verifies:
- No raw chain-of-thought is displayed or exposed.
- Concise reasoning summaries, decisions, evidence and provenance.
- Clean SSE event emission and polling fallback compatibility.
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

VALID_STATUSES = {
    "RUNNING",
    "COMPLETED",
    "FAILED",
    "RETRYING",
    "BLOCKED",
    "AWAITING_APPROVAL",
}

EXPECTED_AGENT_KEYS = [
    "cultural_strategist",
    "experience_architect",
    "partnership_agent",
    "governance_agent",
]


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
    """Provides a TestClient with SQLite persistence and mock MCP."""
    adapter, _, _, _ = mock_mcp_adapter
    db_path = tmp_path / "test_agent_activity.db"
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
        title="TasteOps Agent Activity Integration Test",
        environment="test",
        database_path=str(db_path),
    )
    app = create_app(settings=settings)

    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_space_repository] = lambda: space_repo
    app.dependency_overrides[get_service] = lambda: service

    with TestClient(app) as tc:
        yield tc, db, service


def test_agent_activity_telemetry_fields(client, mock_qloo_api):
    """Verify that all 4 agents have full telemetry fields matching requirements."""
    tc, db, service = client

    # Create Space
    space_resp = tc.post(
        "/api/v1/spaces",
        json={
            "name": "Soho Sound Sanctuary",
            "business_type": "Boutique Hotel & Listening Lounge",
            "desired_mood": "Warm intimate acoustic warmth",
            "target_audience": "Audiophiles, creative professionals",
            "anchor_entities": ["Blue Note", "Ace Hotel", "Aesop"],
        },
    )
    assert space_resp.status_code == 201
    space_id = space_resp.json()["space_id"]

    # Run analysis
    analyze_resp = tc.post(
        f"/api/v1/spaces/{space_id}/analyze",
        json={"hints": MUMBAI_DEMO_HINTS, "auto_run": True},
    )
    assert analyze_resp.status_code == 200
    session_id = analyze_resp.json()["session_id"]

    # Query session detail
    session_resp = tc.get(f"/api/v1/sessions/{session_id}")
    assert session_resp.status_code == 200
    data = session_resp.json()

    agent_summaries = data.get("agent_summaries", {})
    assert set(agent_summaries.keys()) >= set(EXPECTED_AGENT_KEYS)

    for key in EXPECTED_AGENT_KEYS:
        agent = agent_summaries[key]
        assert "name" in agent
        assert "status" in agent
        assert agent["status"] in VALID_STATUSES, f"Invalid status: {agent['status']}"
        assert "start" in agent
        assert "completion" in agent
        assert "duration" in agent
        assert "output_summary" in agent
        assert isinstance(agent["output_summary"], dict)
        assert "validation_status" in agent
        assert "evidence_count" in agent
        assert isinstance(agent["evidence_count"], int)
        assert agent["evidence_count"] >= 0
        assert "failure_information" in agent

    # Specific agent checks at AWAITING_APPROVAL:
    # 1. Cultural Strategist
    strat = agent_summaries["cultural_strategist"]
    assert strat["name"] == "Cultural Strategist"
    assert strat["status"] == "COMPLETED"
    assert strat["start"] is not None
    assert strat["completion"] is not None
    assert strat["duration"] is not None
    assert strat["validation_status"] == "PASSED"
    assert strat["evidence_count"] > 0
    assert strat["failure_information"] is None
    assert "decisions" in strat["output_summary"]
    assert "pillars" in strat["output_summary"]

    # 2. Experience Architect
    exp = agent_summaries["experience_architect"]
    assert exp["name"] == "Experience Architect"
    assert exp["status"] == "COMPLETED"
    assert exp["start"] is not None
    assert exp["completion"] is not None
    assert exp["duration"] is not None
    assert exp["validation_status"] == "PASSED"
    assert "decisions" in exp["output_summary"]
    assert "spatial_zones" in exp["output_summary"]

    # 3. Partnership Agent
    part = agent_summaries["partnership_agent"]
    assert part["name"] == "Partnership Agent"
    assert part["status"] == "COMPLETED"
    assert part["start"] is not None
    assert part["completion"] is not None
    assert part["duration"] is not None
    assert part["validation_status"] == "PASSED"
    assert "decisions" in part["output_summary"]
    assert "partners" in part["output_summary"]

    # 4. Governance / Execution Agent
    gov = agent_summaries["governance_agent"]
    assert "Governance" in gov["name"]
    assert gov["status"] == "AWAITING_APPROVAL"
    assert gov["start"] is not None
    assert gov["validation_status"] == "PASSED"
    assert "provenance_verified" in gov["output_summary"]
    assert "compliance_score" in gov["output_summary"]
    assert gov["failure_information"] is None


def test_no_raw_chain_of_thought_leakage(client, mock_qloo_api):
    """Ensure no raw LLM chain-of-thought, internal prompts, or trace dumps exist."""
    tc, db, service = client

    space_resp = tc.post(
        "/api/v1/spaces",
        json={
            "name": "Audit Sanctuary",
            "business_type": "Art Gallery",
            "anchor_entities": ["Tate Modern"],
        },
    )
    space_id = space_resp.json()["space_id"]

    analyze_resp = tc.post(
        f"/api/v1/spaces/{space_id}/analyze",
        json={"hints": MUMBAI_DEMO_HINTS, "auto_run": True},
    )
    session_id = analyze_resp.json()["session_id"]

    resp = tc.get(f"/api/v1/sessions/{session_id}")
    raw_text = resp.text.lower()

    # Disallowed chain-of-thought tokens:
    forbidden_tokens = [
        "thought:",
        "chain-of-thought",
        "chain_of_thought",
        "internal reasoning:",
        "<think>",
        "</think>",
        "prompt_tokens",
        "raw_prompt",
        "system_prompt",
    ]
    for token in forbidden_tokens:
        assert token not in raw_text, (
            f"Forbidden chain-of-thought token detected: {token}"
        )


def test_agent_activity_spa_route_served(client):
    """Ensure SPA route and static JS screen are served cleanly."""
    tc, _, _ = client

    # SPA shell route
    res = tc.get("/sessions/sess_demo_123/activity")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "TasteOps" in res.text

    # Static JS screen
    res_js = tc.get("/static/js/screens/sessionActivity.js")
    assert res_js.status_code == 200
    assert "javascript" in res_js.headers["content-type"]
    assert "renderSessionActivity" in res_js.text
    assert "renderAgentStatusBadge" in res_js.text
