"""Regression and Audit Tests for Cultural Intelligence Layer Anti-Hallucination Guarantees.

Verifies:
1. Unknown entity handling (no invented IDs)
2. Ambiguous entity handling (alternatives preserved, no synthetic hybrid names)
3. Unknown tag handling (no invented tag IDs)
4. Low-confidence entity rejection
5. Empty response handling (zero hallucinated recommendations, fallback recorded)
6. Malformed provider response handling (graceful error trapping, zero invented data)
7. Partial category failure resilience (unaffected domains succeed, failed domains remain empty)
8. Provenance guarantee (recommendations must trace to verified provider evidence)
"""

import pytest
import respx

from tasteops.agents.governance import GovernanceAgent
from tasteops.client import QlooClient
from tasteops.models.cultural_matrix import CulturalTwin, LocationInput
from tasteops.services.cultural_matrix_service import CulturalMatrixService
from tasteops.services.entity_resolver import EntityResolver
from tasteops.services.tag_resolver import TagResolver

# -----------------------------------------------------------------------------
# 1. Unknown Entity Audit
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_entity_returns_unresolved_zero_invented_id(mock_settings):
    """Verifies that an unknown entity returns is_resolved=False with None ID and zero hallucination."""
    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/search").respond(status_code=200, json={"results": []})

        client = QlooClient(settings=mock_settings)
        resolver = EntityResolver(client)

        result = await resolver.resolve("ZzzNonExistentAnchor9999XYZ")

        assert result.is_resolved is False
        assert result.resolved_entity_id is None
        assert result.entity is None
        assert result.confidence == 0.0
        assert result.source == "qloo_search"
        assert result.evidence.match_method == "unresolved_no_results"
        assert result.evidence.score == 0.0
        assert result.alternatives == []


# -----------------------------------------------------------------------------
# 2. Ambiguous Entity Audit
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ambiguous_entity_preserves_candidates_no_invented_composite(
    mock_settings,
):
    """Verifies that ambiguous results preserve distinct candidates without inventing synthetic entities."""
    mock_candidates = {
        "results": [
            {
                "id": "ent_chelsea_market",
                "name": "Chelsea Market",
                "type": "place",
                "subtype": "food-hall",
            },
            {
                "id": "ent_chelsea_hotel",
                "name": "Chelsea Hotel",
                "type": "place",
                "subtype": "hotel",
            },
            {
                "id": "ent_chelsea_piers",
                "name": "Chelsea Piers",
                "type": "place",
                "subtype": "sports-complex",
            },
        ]
    }

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/search").respond(status_code=200, json=mock_candidates)

        client = QlooClient(settings=mock_settings)
        resolver = EntityResolver(client)

        result = await resolver.resolve("Chelsea", expected_type="place")

        # Top candidate is resolved based on prefix/subset match
        assert result.is_resolved is True
        assert result.resolved_entity_id == "ent_chelsea_market"
        assert result.entity.name == "Chelsea Market"

        # Guarantees: All alternative candidates retain their exact provider IDs and names
        assert len(result.alternatives) == 2
        alt_ids = [alt.entity.id for alt in result.alternatives]
        alt_names = [alt.entity.name for alt in result.alternatives]
        assert "ent_chelsea_hotel" in alt_ids
        assert "ent_chelsea_piers" in alt_ids
        assert "Chelsea Hotel" in alt_names
        assert "Chelsea Piers" in alt_names

        # Guarantee: No composite or synthetic name invented
        for name in [result.entity.name] + alt_names:
            assert name in [
                "Chelsea Market",
                "Chelsea Hotel",
                "Chelsea Piers",
            ]


# -----------------------------------------------------------------------------
# 3. Unknown Tag Audit
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_tag_returns_unresolved_zero_invented_id(mock_settings):
    """Verifies that unknown tags are strictly rejected without fabricating taxonomy IDs."""
    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/v2/tags").respond(status_code=200, json={"tags": []})

        client = QlooClient(settings=mock_settings)
        resolver = TagResolver(client)

        result = await resolver.resolve("hyperpop-polka-fusion-vibes-999")

        assert result.is_resolved is False
        assert result.resolved_tag_id is None
        assert result.tag_name is None
        assert result.confidence == 0.0
        assert result.evidence.match_method == "rejected_unknown_tag"


# -----------------------------------------------------------------------------
# 4. Low-Confidence Entity Rejection Audit
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_low_confidence_entity_strictly_rejected(mock_settings):
    """Verifies that entities matching below min_confidence threshold are rejected."""
    mock_low_match = {
        "results": [
            {
                "id": "ent_xylophone_store",
                "name": "Xylophone Specialty Store",
                "type": "place",
            }
        ]
    }

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/search").respond(status_code=200, json=mock_low_match)

        client = QlooClient(settings=mock_settings)
        resolver = EntityResolver(client)

        # "Blue Bottle" compared against "Xylophone Specialty Store" has fuzzy similarity < 0.50
        result = await resolver.resolve("Blue Bottle", min_confidence=0.50)

        assert result.is_resolved is False
        assert result.resolved_entity_id is None
        assert result.entity is None
        assert result.confidence < 0.50
        assert result.evidence.match_method == "rejected_below_confidence"


# -----------------------------------------------------------------------------
# 5. Empty Response & Exhausted Fallback Audit
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_response_exhausted_fallback_zero_hallucination(mock_settings):
    """Verifies that empty results across initial and fallback queries return empty lists with zero hallucinated items."""
    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/v2/insights").respond(status_code=200, json={"results": []})

        client = QlooClient(settings=mock_settings)
        service = CulturalMatrixService(client)

        twin = CulturalTwin(
            business_type="Boutique Hotel",
            anchor_entities=["ent_anchor_1"],
            resolved_tags=["tag_rare_genre"],
        )

        matrix = await service.generate_matrix(twin, categories=["artist"])

        assert matrix.artists == []
        assert len(matrix.query_metadata) == 1
        meta = matrix.query_metadata[0]
        assert meta.status == "fallback_empty"
        assert meta.items_count == 0
        assert meta.retries == 1

        # Check evidence documentation
        assert len(matrix.evidence) == 1
        ev = matrix.evidence[0]
        assert "Zero items hallucinated" in ev.message


# -----------------------------------------------------------------------------
# 6. Malformed Provider Response Audit
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_malformed_provider_response_handled_gracefully(mock_settings):
    """Verifies that malformed provider responses do not crash the service and produce zero invented data."""
    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        # Corrupted payload missing expected structure
        mock_router.get("/v2/insights").respond(
            status_code=200, json={"unexpected_root_key": "corrupted_payload"}
        )

        client = QlooClient(settings=mock_settings)
        service = CulturalMatrixService(client)

        twin = CulturalTwin(
            business_type="Jazz Bar",
            anchor_entities=["ent_miles_davis"],
        )

        matrix = await service.generate_matrix(twin, categories=["artist"])

        # Service gracefully traps the validation error, keeps domain list empty
        assert matrix.artists == []
        assert len(matrix.query_metadata) == 1
        assert matrix.query_metadata[0].status in ("empty", "fallback_empty")
        assert matrix.query_metadata[0].items_count == 0


# -----------------------------------------------------------------------------
# 7. Partial Category Failure Resilience Audit
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_partial_category_failure_resilience(mock_settings):
    """Verifies that when 2 categories fail, the other 4 succeed without data corruption or hallucination."""

    def mock_insights_handler(request):
        filter_type = request.url.params.get("filter.type", "")
        # Simulate 500 server error on books, malformed payload on movies
        if "urn:entity:book" in filter_type:
            return respx.MockResponse(500, json={"error": "Database error"})
        if "urn:entity:movie" in filter_type:
            return respx.MockResponse(200, text="NOT_VALID_JSON{")

        # Healthy responses for artist, brand, place, destination
        cat = filter_type.replace("urn:entity:", "")
        return respx.MockResponse(
            200,
            json={
                "results": [
                    {
                        "id": f"ent_{cat}_valid",
                        "name": f"Valid {cat.capitalize()}",
                        "affinity": 0.90,
                    }
                ]
            },
        )

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/v2/insights").mock(side_effect=mock_insights_handler)

        client = QlooClient(settings=mock_settings, max_retries=1)
        service = CulturalMatrixService(client)

        twin = CulturalTwin(
            business_type="Listening Cafe",
            anchor_entities=["ent_anchor_1"],
            location=LocationInput(
                latitude=40.7128, longitude=-74.0060, radius_meters=3000
            ),
        )

        matrix = await service.generate_matrix(
            twin,
            categories=[
                "artist",
                "book",
                "brand",
                "place",
                "movie",
                "destination",
            ],
        )

        # Successful categories populated
        assert len(matrix.artists) == 1
        assert matrix.artists[0].name == "Valid Artist"
        assert len(matrix.brands) == 1
        assert len(matrix.places) == 1
        assert len(matrix.destinations) == 1

        # Failed categories strictly empty (zero invented books or movies)
        assert matrix.books == []
        assert matrix.movies == []

        # Metadata accurately records telemetry
        meta_by_cat = {m.category: m.status for m in matrix.query_metadata}
        assert meta_by_cat["artist"] == "success"
        assert meta_by_cat["brand"] == "success"
        assert meta_by_cat["place"] == "success"
        assert meta_by_cat["destination"] == "success"
        assert meta_by_cat["book"] in ("empty", "fallback_empty", "error")
        assert meta_by_cat["movie"] in ("empty", "fallback_empty", "error")


# -----------------------------------------------------------------------------
# 8. Provenance Guarantee Audit
# -----------------------------------------------------------------------------


from tasteops.agents.governance import ProvenanceValidationError
from tasteops.workflows.schemas import ExecutionTask


def test_governance_blocks_unsupported_or_hallucinated_provenance():
    """Verifies that GovernanceAgent rejects tasks lacking verified provider provenance."""
    governance = GovernanceAgent()

    # 1. Missing entity ID / incomplete provenance fields
    task_missing = ExecutionTask(
        task_id="task_test_01",
        action="Test Action",
        owner="Curator",
        input={},
        provenance={"source": "qloo_insights"},  # missing required fields
    )
    with pytest.raises(
        ProvenanceValidationError, match="missing mandatory provenance fields"
    ):
        governance.validate_task_provenance(task_missing)

    # 2. Fabricated or unverified entity prefix
    task_unverified = ExecutionTask(
        task_id="task_test_02",
        action="Test Action",
        owner="Curator",
        input={},
        provenance={
            "source": "qloo_insights_brand",
            "source_id": "invalid_fake_qloo_id_123",
            "source_type": "brand",
            "query": "/v2/insights",
            "timestamp": "2026-10-25T00:00:00Z",
            "task_id": "task_test_02",
            "plan_id": "plan_123",
            "session_id": "sess_123",
            "approved_by": "Curator",
            "approved_at": "2026-10-25T00:00:00Z",
            "execution_status": "EXECUTED",
        },
    )
    with pytest.raises(ProvenanceValidationError, match="invalid/unverified Qloo ID"):
        governance.validate_task_provenance(task_unverified)

    # 3. Valid provenance passes cleanly
    task_valid = ExecutionTask(
        task_id="task_test_03",
        action="Test Action",
        owner="Curator",
        input={},
        provenance={
            "source": "qloo_insights_brand",
            "source_id": "ent_valid_qloo_123",
            "source_type": "brand",
            "query": "/v2/insights",
            "timestamp": "2026-10-25T00:00:00Z",
            "task_id": "task_test_03",
            "plan_id": "plan_123",
            "session_id": "sess_123",
            "approved_by": "Curator",
            "approved_at": "2026-10-25T00:00:00Z",
            "execution_status": "EXECUTED",
        },
    )
    governance.validate_task_provenance(task_valid)
