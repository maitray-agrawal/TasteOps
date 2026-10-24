"""Contract tests for all 10 public MCP tools in TasteOps Cultural Intelligence."""

import uuid

import pytest
import respx

from tasteops.client import QlooClient
from tasteops.mcp.schemas import (
    CategoryRecommendationsOutput,
    GetCulturalMatrixOutput,
    GetCulturalProfileOutput,
    HealthCheckOutput,
    ResolveEntityOutput,
    ResolveTagOutput,
)
from tasteops.mcp.server import create_cultural_intelligence_mcp


async def invoke(server, tool_name: str, arguments: dict) -> dict:
    """Helper invoking an MCP tool and extracting its structured dictionary."""
    result = await server.call_tool(tool_name, arguments)
    assert result.is_error is False
    assert result.structured_content is not None
    return result.structured_content


# -----------------------------------------------------------------------------
# 1. health_check Contract
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contract_health_check(mock_settings):
    """Verifies health_check returns typed output, request_id, and status."""
    client = QlooClient(settings=mock_settings)
    server = create_cultural_intelligence_mcp(client)

    raw = await invoke(server, "health_check", {})
    output = HealthCheckOutput.model_validate(raw)

    assert output.status == "healthy"
    assert output.server == "tasteops-cultural-intelligence"
    assert output.version == "1.0.0"
    assert output.base_url == "https://hackathon.api.qloo.com"
    uuid.UUID(output.request_id)
    assert output.latency_ms >= 0.0
    assert output.error is None


# -----------------------------------------------------------------------------
# 2. resolve_entity Contract
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contract_resolve_entity_success(mock_settings):
    """Verifies resolve_entity output conforms to typed schema with confidence & provenance."""
    mock_payload = {
        "results": [
            {
                "id": "ent_a24_film",
                "name": "A24",
                "type": "brand",
                "subtype": "film-studio",
            }
        ]
    }

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/search").respond(status_code=200, json=mock_payload)

        client = QlooClient(settings=mock_settings)
        server = create_cultural_intelligence_mcp(client)

        raw = await invoke(
            server,
            "resolve_entity",
            {"query": "A24", "expected_type": "brand", "min_confidence": 0.5},
        )
        output = ResolveEntityOutput.model_validate(raw)

        uuid.UUID(output.request_id)
        assert output.is_resolved is True
        assert output.input == "A24"
        assert output.resolved_entity_id == "ent_a24_film"
        assert output.entity_name == "A24"
        assert output.entity_type == "brand"
        assert output.confidence >= 0.5
        assert output.source == "qloo_search"
        assert "score" in output.evidence
        assert "match_method" in output.evidence
        assert output.latency_ms >= 0.0
        assert output.error is None


@pytest.mark.asyncio
async def test_contract_resolve_entity_validation_failure(mock_settings):
    """Verifies resolve_entity deterministic error behavior on invalid input."""
    client = QlooClient(settings=mock_settings)
    server = create_cultural_intelligence_mcp(client)

    raw = await invoke(
        server,
        "resolve_entity",
        {"query": "", "min_confidence": -0.5},  # empty string + invalid bounds
    )
    output = ResolveEntityOutput.model_validate(raw)

    uuid.UUID(output.request_id)
    assert output.is_resolved is False
    assert output.resolved_entity_id is None
    assert output.confidence == 0.0
    assert output.error is not None


# -----------------------------------------------------------------------------
# 3. resolve_tag Contract
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contract_resolve_tag_success(mock_settings):
    """Verifies resolve_tag output conforms to typed schema with confidence & provenance."""
    mock_payload = {
        "results": [
            {
                "id": "tag_jp_minimalism",
                "name": "Japanese Minimalism",
                "category": "style",
            }
        ]
    }

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/v2/tags").respond(status_code=200, json=mock_payload)

        client = QlooClient(settings=mock_settings)
        server = create_cultural_intelligence_mcp(client)

        raw = await invoke(
            server,
            "resolve_tag",
            {"query": "Japanese Minimalism", "expected_category": "style"},
        )
        output = ResolveTagOutput.model_validate(raw)

        uuid.UUID(output.request_id)
        assert output.is_resolved is True
        assert output.input == "Japanese Minimalism"
        assert output.resolved_tag_id == "tag_jp_minimalism"
        assert output.tag_name == "Japanese Minimalism"
        assert output.category == "style"
        assert output.confidence >= 0.5
        assert output.source == "qloo_tags"
        assert "score" in output.evidence
        assert output.latency_ms >= 0.0
        assert output.error is None


@pytest.mark.asyncio
async def test_contract_resolve_tag_validation_failure(mock_settings):
    """Verifies resolve_tag deterministic error behavior on invalid input."""
    client = QlooClient(settings=mock_settings)
    server = create_cultural_intelligence_mcp(client)

    raw = await invoke(
        server,
        "resolve_tag",
        {"query": "", "min_confidence": 2.5},
    )
    output = ResolveTagOutput.model_validate(raw)

    uuid.UUID(output.request_id)
    assert output.is_resolved is False
    assert output.resolved_tag_id is None
    assert output.confidence == 0.0
    assert output.error is not None


# -----------------------------------------------------------------------------
# 4. get_cultural_profile Contract
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contract_get_cultural_profile_success(mock_settings):
    """Verifies get_cultural_profile output conforms to typed schema with affinities & provenance."""
    mock_insights = {
        "results": [
            {
                "id": "art_four_tet",
                "name": "Four Tet",
                "affinity": 0.94,
                "explainability": ["High audience affinity"],
            }
        ]
    }

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/v2/insights").respond(status_code=200, json=mock_insights)

        client = QlooClient(settings=mock_settings)
        server = create_cultural_intelligence_mcp(client)

        raw = await invoke(
            server,
            "get_cultural_profile",
            {"entity_id": "ent_a24_film", "take": 5},
        )
        output = GetCulturalProfileOutput.model_validate(raw)

        uuid.UUID(output.request_id)
        assert output.entity_id == "ent_a24_film"
        assert output.total_affinities >= 1
        assert len(output.affinities.artists) >= 1
        assert output.affinities.artists[0]["name"] == "Four Tet"
        assert output.affinities.artists[0]["confidence"] == 0.94
        assert output.latency_ms >= 0.0
        assert output.error is None


@pytest.mark.asyncio
async def test_contract_get_cultural_profile_missing_inputs(mock_settings):
    """Verifies get_cultural_profile returns deterministic error if neither ID nor name given."""
    client = QlooClient(settings=mock_settings)
    server = create_cultural_intelligence_mcp(client)

    raw = await invoke(server, "get_cultural_profile", {})
    output = GetCulturalProfileOutput.model_validate(raw)

    uuid.UUID(output.request_id)
    assert output.error is not None
    assert "Must provide either" in output.error


# -----------------------------------------------------------------------------
# 5. get_related_artists Contract
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contract_get_related_artists(mock_settings):
    """Verifies get_related_artists output conforms to typed schema with provenance & confidence."""
    mock_payload = {
        "results": [
            {
                "id": "art_bonobo",
                "name": "Bonobo",
                "affinity": 0.91,
                "explainability": ["Audience alignment"],
            }
        ]
    }

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/v2/insights").respond(status_code=200, json=mock_payload)

        client = QlooClient(settings=mock_settings)
        server = create_cultural_intelligence_mcp(client)

        raw = await invoke(
            server,
            "get_related_artists",
            {"anchor_entities": ["ent_blue_bottle"], "take": 5},
        )
        output = CategoryRecommendationsOutput.model_validate(raw)

        uuid.UUID(output.request_id)
        assert output.category == "artist"
        assert output.total_count == 1
        rec = output.recommendations[0]
        assert rec["name"] == "Bonobo"
        assert rec["confidence"] == 0.91
        assert rec["source_query"] == "/v2/insights?filter.type=urn:entity:artist"
        assert "anchor_entities" in rec["source_signal"]
        assert output.latency_ms >= 0.0
        assert output.error is None


# -----------------------------------------------------------------------------
# 6. get_related_books Contract
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contract_get_related_books(mock_settings):
    """Verifies get_related_books output conforms to typed schema with provenance & confidence."""
    mock_payload = {
        "results": [
            {
                "id": "book_wabisabi",
                "name": "Wabi-Sabi for Artists",
                "affinity": 0.88,
            }
        ]
    }

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/v2/insights").respond(status_code=200, json=mock_payload)

        client = QlooClient(settings=mock_settings)
        server = create_cultural_intelligence_mcp(client)

        raw = await invoke(
            server,
            "get_related_books",
            {"anchor_entities": ["ent_blue_bottle"], "take": 5},
        )
        output = CategoryRecommendationsOutput.model_validate(raw)

        uuid.UUID(output.request_id)
        assert output.category == "book"
        assert output.total_count == 1
        assert output.recommendations[0]["name"] == "Wabi-Sabi for Artists"
        assert output.recommendations[0]["confidence"] == 0.88
        assert output.latency_ms >= 0.0


# -----------------------------------------------------------------------------
# 7. get_related_brands Contract
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contract_get_related_brands(mock_settings):
    """Verifies get_related_brands output conforms to typed schema with provenance & confidence."""
    mock_payload = {
        "results": [
            {
                "id": "brand_audio_technica",
                "name": "Audio-Technica",
                "affinity": 0.92,
            }
        ]
    }

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/v2/insights").respond(status_code=200, json=mock_payload)

        client = QlooClient(settings=mock_settings)
        server = create_cultural_intelligence_mcp(client)

        raw = await invoke(
            server,
            "get_related_brands",
            {"anchor_entities": ["ent_blue_bottle"], "take": 5},
        )
        output = CategoryRecommendationsOutput.model_validate(raw)

        uuid.UUID(output.request_id)
        assert output.category == "brand"
        assert output.total_count == 1
        assert output.recommendations[0]["name"] == "Audio-Technica"
        assert output.recommendations[0]["confidence"] == 0.92
        assert output.latency_ms >= 0.0


# -----------------------------------------------------------------------------
# 8. get_related_places Contract
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contract_get_related_places_spatial_success(mock_settings):
    """Verifies get_related_places spatial filtering and typed output."""
    mock_payload = {
        "results": [
            {
                "id": "place_public_records",
                "name": "Public Records",
                "affinity": 0.95,
            }
        ]
    }

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/v2/insights").respond(status_code=200, json=mock_payload)

        client = QlooClient(settings=mock_settings)
        server = create_cultural_intelligence_mcp(client)

        raw = await invoke(
            server,
            "get_related_places",
            {
                "anchor_entities": ["ent_blue_bottle"],
                "latitude": 40.7128,
                "longitude": -74.0060,
                "radius_meters": 3000,
                "take": 5,
            },
        )
        output = CategoryRecommendationsOutput.model_validate(raw)

        uuid.UUID(output.request_id)
        assert output.category == "place"
        assert output.total_count == 1
        assert output.recommendations[0]["name"] == "Public Records"
        assert output.recommendations[0]["confidence"] == 0.95
        assert output.latency_ms >= 0.0


@pytest.mark.asyncio
async def test_contract_get_related_places_validation_failure(mock_settings):
    """Verifies get_related_places deterministic error on out-of-range coordinates."""
    client = QlooClient(settings=mock_settings)
    server = create_cultural_intelligence_mcp(client)

    raw = await invoke(
        server,
        "get_related_places",
        {
            "anchor_entities": ["ent_blue_bottle"],
            "latitude": 120.0,  # invalid latitude > 90.0
            "longitude": -74.0060,
        },
    )
    output = CategoryRecommendationsOutput.model_validate(raw)

    uuid.UUID(output.request_id)
    assert output.category == "place"
    assert output.error is not None
    assert output.total_count == 0


# -----------------------------------------------------------------------------
# 9. get_related_movies Contract
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contract_get_related_movies(mock_settings):
    """Verifies get_related_movies output conforms to typed schema with provenance & confidence."""
    mock_payload = {
        "results": [
            {
                "id": "mov_drive_my_car",
                "name": "Drive My Car",
                "affinity": 0.89,
            }
        ]
    }

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/v2/insights").respond(status_code=200, json=mock_payload)

        client = QlooClient(settings=mock_settings)
        server = create_cultural_intelligence_mcp(client)

        raw = await invoke(
            server,
            "get_related_movies",
            {"anchor_entities": ["ent_blue_bottle"], "take": 5},
        )
        output = CategoryRecommendationsOutput.model_validate(raw)

        uuid.UUID(output.request_id)
        assert output.category == "movie"
        assert output.total_count == 1
        assert output.recommendations[0]["name"] == "Drive My Car"
        assert output.recommendations[0]["confidence"] == 0.89
        assert output.latency_ms >= 0.0


# -----------------------------------------------------------------------------
# 10. get_cultural_matrix Contract
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contract_get_cultural_matrix_success(mock_settings):
    """Verifies get_cultural_matrix output conforms to typed schema with 6 domains and provenance."""
    mock_payload = {
        "results": [{"id": "item_rec_1", "name": "Recommended Item", "affinity": 0.90}]
    }

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/v2/insights").respond(status_code=200, json=mock_payload)

        client = QlooClient(settings=mock_settings)
        server = create_cultural_intelligence_mcp(client)

        twin = {
            "business_type": "Audiophile Bar",
            "mood": "Intimate, warm, analog",
            "anchor_entities": ["ent_blue_bottle"],
            "resolved_tags": ["tag_jp_minimalism"],
            "location": {
                "latitude": 40.7484,
                "longitude": -73.9857,
                "radius_meters": 2000,
            },
        }

        raw = await invoke(
            server,
            "get_cultural_matrix",
            {"cultural_twin": twin, "take_per_category": 5},
        )
        output = GetCulturalMatrixOutput.model_validate(raw)

        uuid.UUID(output.request_id)
        assert output.status == "success"
        assert output.total_recommendations > 0
        assert output.cultural_matrix is not None
        matrix = output.cultural_matrix
        assert "artists" in matrix
        assert "books" in matrix
        assert "brands" in matrix
        assert "places" in matrix
        assert "movies" in matrix
        assert "destinations" in matrix
        assert "evidence" in matrix
        assert "query_metadata" in matrix
        assert output.latency_ms >= 0.0
        assert output.error is None


@pytest.mark.asyncio
async def test_contract_get_cultural_matrix_validation_failure(mock_settings):
    """Verifies get_cultural_matrix deterministic error output on invalid twin format."""
    client = QlooClient(settings=mock_settings)
    server = create_cultural_intelligence_mcp(client)

    raw = await invoke(
        server,
        "get_cultural_matrix",
        {
            "cultural_twin": {
                "location": {
                    "latitude": 999.0,  # Invalid latitude > 90.0
                    "longitude": 0.0,
                }
            }
        },
    )
    output = GetCulturalMatrixOutput.model_validate(raw)

    uuid.UUID(output.request_id)
    assert output.status == "error"
    assert output.cultural_matrix is None
    assert output.total_recommendations == 0
    assert output.error is not None
