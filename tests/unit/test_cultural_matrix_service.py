"""Unit tests for CulturalMatrixService and InsightsService."""

import httpx
import pytest
import respx

from tasteops.client import QlooClient
from tasteops.models.cultural_matrix import CulturalTwin, LocationInput
from tasteops.services.cultural_matrix_service import CulturalMatrixService
from tasteops.services.insights_service import InsightsService


@pytest.fixture
def sample_twin():
    return CulturalTwin(
        target_audience="Design-conscious creative professionals, coffee aficionados",
        location=LocationInput(
            latitude=40.7484, longitude=-73.9857, radius_meters=2000
        ),
        business_type="Minimalist specialty coffee lounge and listening bar",
        mood="Warm, intimate, analog, acoustic focus",
        positioning="High-end third-wave cafe by day, vinyl bar by night",
        anchor_entities=["ent_blue_bottle_123", "ent_four_tet"],
        resolved_tags=["tag_lofi_beats", "tag_jp_minimalism"],
    )


def test_capability_validation_does_not_pass_location_to_non_spatial_entities(
    mock_settings,
):
    """Ensure non-spatial entities (artist, book, brand, movie) never receive spatial location filters."""
    client = QlooClient(settings=mock_settings)
    service = InsightsService(client)

    # Place (spatial): location MUST be included
    place_params = service.build_insight_params(
        category="place",
        anchor_entities=["ent_1"],
        resolved_tags=["tag_1"],
        location_wkt="POINT(-73.985 40.748)",
        location_radius=2000,
    )
    query_dict = place_params.to_query_params()
    assert "filter.location" in query_dict
    assert "filter.location.radius" in query_dict

    # Artist (non-spatial): location MUST NOT be included
    artist_params = service.build_insight_params(
        category="artist",
        anchor_entities=["ent_1"],
        resolved_tags=["tag_1"],
        location_wkt="POINT(-73.985 40.748)",
        location_radius=2000,
    )
    artist_query = artist_params.to_query_params()
    assert "filter.location" not in artist_query
    assert "filter.location.radius" not in artist_query

    # Book (non-spatial)
    book_params = service.build_insight_params(
        category="book",
        anchor_entities=["ent_1"],
        resolved_tags=["tag_1"],
        location_wkt="POINT(-73.985 40.748)",
        location_radius=2000,
    )
    book_query = book_params.to_query_params()
    assert "filter.location" not in book_query


@pytest.mark.asyncio
async def test_generate_cultural_matrix_concurrent_success(mock_settings, sample_twin):
    """Test concurrent execution across all 6 categories and verify normalized output."""
    mock_responses = {
        "urn:entity:artist": [
            {
                "id": "art_1",
                "name": "Floating Points",
                "affinity": 0.92,
                "explainability": ["Shared aesthetic with Four Tet"],
            }
        ],
        "urn:entity:book": [
            {"id": "book_1", "name": "In Praise of Shadows", "affinity": 0.88}
        ],
        "urn:entity:brand": [{"id": "brand_1", "name": "Muji", "affinity": 0.91}],
        "urn:entity:place": [
            {
                "id": "place_1",
                "name": "Sey Coffee",
                "affinity": 0.95,
                "metadata": {"neighborhood": "Bushwick"},
            }
        ],
        "urn:entity:movie": [{"id": "mov_1", "name": "Perfect Days", "affinity": 0.89}],
        "urn:entity:destination": [
            {"id": "dest_1", "name": "Kyoto, Japan", "affinity": 0.93}
        ],
    }

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:

        def insight_side_effect(request: httpx.Request):
            filter_type = request.url.params.get("filter.type", "")
            results = mock_responses.get(filter_type, [])
            return httpx.Response(200, json={"results": results})

        mock_router.get("/v2/insights").mock(side_effect=insight_side_effect)

        async with QlooClient(settings=mock_settings) as client:
            matrix_service = CulturalMatrixService(client)
            matrix = await matrix_service.generate_matrix(sample_twin)

            assert matrix.total_recommendations == 6

            # Verify each category recommendations
            assert len(matrix.artists) == 1
            assert matrix.artists[0].name == "Floating Points"
            assert matrix.artists[0].type == "artist"
            assert matrix.artists[0].affinity == 0.92
            assert (
                matrix.artists[0].source_signal["anchor_entities"]
                == sample_twin.anchor_entities
            )
            assert matrix.artists[0].explainability == [
                "Shared aesthetic with Four Tet"
            ]

            assert len(matrix.books) == 1
            assert matrix.books[0].name == "In Praise of Shadows"

            assert len(matrix.brands) == 1
            assert matrix.brands[0].name == "Muji"

            assert len(matrix.places) == 1
            assert matrix.places[0].name == "Sey Coffee"
            assert matrix.places[0].metadata["neighborhood"] == "Bushwick"

            assert len(matrix.movies) == 1
            assert matrix.movies[0].name == "Perfect Days"

            assert len(matrix.destinations) == 1
            assert matrix.destinations[0].name == "Kyoto, Japan"

            # Check query metadata diagnostics
            assert len(matrix.query_metadata) == 6
            for qm in matrix.query_metadata:
                assert qm.status == "success"
                assert qm.items_count == 1
                assert qm.retries == 0


@pytest.mark.asyncio
async def test_deterministic_fallback_on_empty_and_retry_once(mock_settings):
    """Test that when a category returns 0 results initially, it applies deterministic fallback and retries once."""
    twin = CulturalTwin(
        anchor_entities=["ent_obscure_cafe"],
        resolved_tags=["tag_niche_1", "tag_niche_2"],
    )

    call_count = {"count": 0}

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:

        def insight_side_effect(request: httpx.Request):
            call_count["count"] += 1
            tags_param = request.url.params.get("signal.interests.tags", "")
            # Initial call with tags returns empty
            if tags_param:
                return httpx.Response(200, json={"results": []})
            # Fallback call with anchor entities only returns success
            return httpx.Response(
                200,
                json={"results": [{"id": "art_2", "name": "Bonobo", "affinity": 0.85}]},
            )

        mock_router.get("/v2/insights").mock(side_effect=insight_side_effect)

        async with QlooClient(settings=mock_settings) as client:
            matrix_service = CulturalMatrixService(client)
            matrix = await matrix_service.generate_matrix(twin, categories=["artist"])

            assert len(matrix.artists) == 1
            assert matrix.artists[0].name == "Bonobo"

            # Verify retry count: initial call + 1 fallback retry = 2 calls
            assert call_count["count"] == 2

            # Verify query metadata recorded fallback
            assert len(matrix.query_metadata) == 1
            qm = matrix.query_metadata[0]
            assert qm.status == "fallback_success"
            assert qm.retries == 1
            assert qm.fallback_applied == "relax_to_anchor_entities_only"


@pytest.mark.asyncio
async def test_zero_hallucination_on_exhausted_fallback(mock_settings):
    """Ensure zero hallucination: when both initial and fallback return empty, 0 items returned."""
    twin = CulturalTwin(
        anchor_entities=["ent_rare_signal"],
        location=LocationInput(
            latitude=40.7484, longitude=-73.9857, radius_meters=1000
        ),
    )

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        # Always return empty results
        mock_router.get("/v2/insights").respond(status_code=200, json={"results": []})

        async with QlooClient(settings=mock_settings) as client:
            matrix_service = CulturalMatrixService(client)
            matrix = await matrix_service.generate_matrix(twin, categories=["place"])

            assert len(matrix.places) == 0
            assert matrix.total_recommendations == 0

            # Verified diagnostics recorded
            qm = matrix.query_metadata[0]
            assert qm.status == "fallback_empty"
            assert qm.retries == 1
            assert qm.items_count == 0


@pytest.mark.asyncio
async def test_empty_twin_returns_empty_matrix(mock_settings):
    """Ensure a CulturalTwin with no signals gracefully returns an empty matrix without querying."""
    twin = CulturalTwin()

    async with QlooClient(settings=mock_settings) as client:
        matrix_service = CulturalMatrixService(client)
        matrix = await matrix_service.generate_matrix(twin)

        assert matrix.total_recommendations == 0
        assert len(matrix.evidence) == 1
        assert "no anchors, tags, or location" in matrix.evidence[0].message
