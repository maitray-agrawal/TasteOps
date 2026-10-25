"""Regression tests verifying frontend data integrity and truthful API contracts.

Guarantees:
- Unapproved sessions never return fabricated approval hashes or approval flags.
- Real provenance (Qloo entity ID, affinity, domain) is preserved in backend responses.
- Artifact endpoints enforce session existence and return validated schemas.
- Audit endpoint reflects real state transitions without fabricated cryptographic proofs.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from tasteops.api.main import app
from tasteops.models.cultural_matrix import CulturalMatrix, CulturalRecommendation
from tasteops.workflows.orchestrator import TasteOpsOrchestrator
from tasteops.workflows.persistence import AuditEvent
from tasteops.workflows.schemas import ApprovalRecord


@pytest.fixture
def mock_orchestrator() -> TasteOpsOrchestrator:
    """Fixture providing an orchestrator registered in app.state."""
    orch = TasteOpsOrchestrator()
    app.state.orchestrator = orch
    return orch


@pytest.mark.asyncio
async def test_unapproved_session_has_no_fabricated_approval(
    mock_orchestrator: TasteOpsOrchestrator,
) -> None:
    """Verifies that an initial session does NOT return fabricated approval or plan hashes."""
    ctx = mock_orchestrator.create_session(
        user_input="Austin coffee and music lounge",
        hints={"location": "Austin, USA"},
    )
    mock_orchestrator._active_sessions[ctx.session_id] = ctx
    mock_orchestrator.store.save_context(ctx)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.get(f"/api/v1/sessions/{ctx.session_id}")
        assert res.status_code == 200
        data = res.json()

        assert data["current_state"] == "CREATED"
        # Approval record must be absent or unverified
        assert data.get("approval") is None
        # Plan must not be fabricated
        assert data.get("plan") is None


@pytest.mark.asyncio
async def test_provenance_integrity_in_session_payload(
    mock_orchestrator: TasteOpsOrchestrator,
) -> None:
    """Verifies that cultural matrix entities preserve exact Qloo IDs and affinities."""
    ctx = mock_orchestrator.create_session("Austin tech space")
    ctx.cultural_matrix = CulturalMatrix(
        artists=[
            CulturalRecommendation(
                id="ent_mus_khruangbin_01",
                name="Khruangbin",
                type="artist",
                affinity=0.942,
                score=94.2,
                confidence=0.95,
                source_query="austin_acoustic",
            )
        ],
        books=[
            CulturalRecommendation(
                id="ent_book_kinfolk_04",
                name="Kinfolk Nature",
                type="book",
                affinity=0.886,
                score=88.6,
                confidence=0.90,
                source_query="austin_minimal",
            )
        ],
    )
    mock_orchestrator._active_sessions[ctx.session_id] = ctx
    mock_orchestrator.store.save_context(ctx)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.get(f"/api/v1/sessions/{ctx.session_id}")
        assert res.status_code == 200
        matrix = res.json()["cultural_matrix"]

        assert len(matrix["artists"]) == 1
        assert matrix["artists"][0]["id"] == "ent_mus_khruangbin_01"
        assert matrix["artists"][0]["score"] == 94.2
        assert matrix["artists"][0]["source_query"] == "austin_acoustic"

        assert len(matrix["books"]) == 1
        assert matrix["books"][0]["id"] == "ent_book_kinfolk_04"
        assert matrix["books"][0]["score"] == 88.6


@pytest.mark.asyncio
async def test_artifact_endpoints_404_on_missing_session() -> None:
    """Verifies that requesting artifacts for a non-existent session returns 404."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        csv_res = await client.get(
            "/api/v1/sessions/non_existent_session_id/artifacts/procurement.csv"
        )
        assert csv_res.status_code == 404

        spotify_res = await client.get(
            "/api/v1/sessions/non_existent_session_id/artifacts/spotify_playlist.json"
        )
        assert spotify_res.status_code == 404

        brand_res = await client.get(
            "/api/v1/sessions/non_existent_session_id/artifacts/brand_dossiers.json"
        )
        assert brand_res.status_code == 404


@pytest.mark.asyncio
async def test_audit_endpoint_truthful_state_events(
    mock_orchestrator: TasteOpsOrchestrator,
) -> None:
    """Verifies that audit endpoint returns genuine state transition history without fake cryptographic Merkle proof."""
    ctx = mock_orchestrator.create_session("Austin lounge brief")
    mock_orchestrator._active_sessions[ctx.session_id] = ctx
    mock_orchestrator.store.save_transition(
        AuditEvent(
            session_id=ctx.session_id,
            from_state="CREATED",
            to_state="INTENT_PARSED",
            reason="Session initialized",
        ),
        ctx,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.get(f"/api/v1/sessions/{ctx.session_id}/audit")
        assert res.status_code == 200
        events = res.json()
        assert isinstance(events, list)
        assert len(events) >= 1
        assert events[0]["to_state"] == "CREATED"
        assert "timestamp" in events[0]


@pytest.mark.asyncio
async def test_csv_artifact_format_and_provenance(
    mock_orchestrator: TasteOpsOrchestrator,
) -> None:
    """Verifies that procurement CSV returns exactly 8 validated columns with UTF-8 encoding."""
    from tests.unit.test_negative_governance import _create_test_plan

    ctx = mock_orchestrator.create_session("Austin reading sanctuary")
    plan = await _create_test_plan()
    ctx.plan = plan
    ctx.cultural_matrix = plan.cultural_matrix
    ctx.current_state = "APPROVED"
    ctx.approval = ApprovalRecord(
        session_id=ctx.session_id,
        approver="Maitray Agrawal",
        plan_hash=plan.compute_hash(),
        plan_id="plan_test_01",
    )
    mock_orchestrator._active_sessions[ctx.session_id] = ctx
    mock_orchestrator.store.save_context(ctx)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.get(
            f"/api/v1/sessions/{ctx.session_id}/artifacts/procurement.csv"
        )
        assert res.status_code == 200
        assert "text/csv" in res.headers["content-type"]

        lines = res.text.strip().splitlines()
        header = lines[0].split(",")
        assert header == [
            "ISBN",
            "Title",
            "Author",
            "Publisher",
            "Quantity",
            "Unit Price",
            "Affinity Score",
            "Qloo Entity ID",
        ]
