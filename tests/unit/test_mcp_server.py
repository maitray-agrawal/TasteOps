"""Automated tests for every Cultural Intelligence MCP Tool."""

import uuid

import httpx
import pytest
import respx

from tasteops.client import QlooClient
from tasteops.mcp.server import create_cultural_intelligence_mcp


async def invoke_tool(server, name: str, args: dict) -> dict:
    """Helper invoking an MCP tool and extracting the structured dict result."""
    call_result = await server.call_tool(name, args)
    assert call_result.is_error is False
    assert call_result.structured_content is not None
    return call_result.structured_content


@pytest.mark.asyncio
async def test_mcp_tool_listing_and_security(mock_settings):
    """Test that all required tools exist, and raw Qloo access is NOT exposed."""
    client = QlooClient(settings=mock_settings)
    server = create_cultural_intelligence_mcp(client)

    tools = await server.list_tools()
    tool_names = [t.name for t in tools]

    expected_tools = [
        "health_check",
        "resolve_entity",
        "resolve_tag",
        "get_cultural_profile",
        "get_related_artists",
        "get_related_books",
        "get_related_brands",
        "get_related_places",
        "get_related_movies",
        "get_cultural_matrix",
    ]
    for expected in expected_tools:
        assert expected in tool_names, f"Expected MCP tool '{expected}' not found in server tools."

    # Verify no raw Qloo HTTP execution tool is exposed
    assert "call_qloo" not in tool_names
    assert "raw_http" not in tool_names
    assert "execute_request" not in tool_names


@pytest.mark.asyncio
async def test_mcp_health_check(mock_settings):
    """Test health_check tool returns server status, request ID, and base URL."""
    client = QlooClient(settings=mock_settings)
    server = create_cultural_intelligence_mcp(client)

    data = await invoke_tool(server, "health_check", {})

    assert data["status"] == "healthy"
    assert data["server"] == "tasteops-cultural-intelligence"
    assert "request_id" in data
    # Verify request_id is valid UUID
    uuid.UUID(data["request_id"])
    assert data["base_url"] == "https://hackathon.api.qloo.com"


@pytest.mark.asyncio
async def test_mcp_resolve_entity(mock_settings):
    """Test resolve_entity tool."""
    mock_payload = {
        "results": [
            {
                "id": "ent_blue_bottle",
                "name": "Blue Bottle Coffee",
                "type": "place",
                "subtype": "cafe",
            }
        ]
    }

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/search").respond(status_code=200, json=mock_payload)

        client = QlooClient(settings=mock_settings)
        server = create_cultural_intelligence_mcp(client)

        data = await invoke_tool(server, "resolve_entity", {"query": "Blue Bottle", "expected_type": "place"})

        assert data["is_resolved"] is True
        assert data["resolved_entity_id"] == "ent_blue_bottle"
        assert data["entity_name"] == "Blue Bottle Coffee"
        assert data["confidence"] >= 0.8
        uuid.UUID(data["request_id"])


@pytest.mark.asyncio
async def test_mcp_resolve_tag(mock_settings):
    """Test resolve_tag tool."""
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

        data = await invoke_tool(server, "resolve_tag", {"query": "Japanese Minimalism", "expected_category": "style"})

        assert data["is_resolved"] is True
        assert data["resolved_tag_id"] == "tag_jp_minimalism"
        assert data["category"] == "style"
        uuid.UUID(data["request_id"])


@pytest.mark.asyncio
async def test_mcp_get_cultural_profile(mock_settings):
    """Test get_cultural_profile tool synthesizing cross-domain affinities."""
    mock_insights = {
        "results": [
            {"id": "art_1", "name": "Tycho", "affinity": 0.89},
        ]
    }

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/v2/insights").respond(status_code=200, json=mock_insights)

        client = QlooClient(settings=mock_settings)
        server = create_cultural_intelligence_mcp(client)

        data = await invoke_tool(server, "get_cultural_profile", {"entity_id": "ent_123", "take": 3})

        assert data["entity_id"] == "ent_123"
        assert "affinities" in data
        assert "artists" in data["affinities"]
        uuid.UUID(data["request_id"])


@pytest.mark.asyncio
async def test_mcp_domain_specific_tools(mock_settings):
    """Test get_related_artists, get_related_books, get_related_brands, get_related_places, get_related_movies."""
    domain_items = {
        "artist": [{"id": "a1", "name": "Bonobo", "affinity": 0.91}],
        "book": [{"id": "b1", "name": "Wabi-Sabi for Artists", "affinity": 0.87}],
        "brand": [{"id": "br1", "name": "Audio-Technica", "affinity": 0.93}],
        "place": [{"id": "p1", "name": "Public Records", "affinity": 0.94}],
        "movie": [{"id": "m1", "name": "Drive My Car", "affinity": 0.86}],
    }

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        def insight_side_effect(request: httpx.Request):
            filter_type = request.url.params.get("filter.type", "")
            cat = filter_type.replace("urn:entity:", "")
            results = domain_items.get(cat, [])
            return httpx.Response(200, json={"results": results})

        mock_router.get("/v2/insights").mock(side_effect=insight_side_effect)

        client = QlooClient(settings=mock_settings)
        server = create_cultural_intelligence_mcp(client)

        # 1. Artists
        artists_data = await invoke_tool(server, "get_related_artists", {"anchor_entities": ["ent_1"], "take": 5})
        assert artists_data["category"] == "artist"
        assert artists_data["total_count"] == 1
        assert artists_data["recommendations"][0]["name"] == "Bonobo"

        # 2. Books
        books_data = await invoke_tool(server, "get_related_books", {"anchor_entities": ["ent_1"], "take": 5})
        assert books_data["category"] == "book"
        assert books_data["recommendations"][0]["name"] == "Wabi-Sabi for Artists"

        # 3. Brands
        brands_data = await invoke_tool(server, "get_related_brands", {"anchor_entities": ["ent_1"], "take": 5})
        assert brands_data["category"] == "brand"
        assert brands_data["recommendations"][0]["name"] == "Audio-Technica"

        # 4. Places (with spatial coordinates)
        places_data = await invoke_tool(
            server,
            "get_related_places",
            {"anchor_entities": ["ent_1"], "latitude": 40.7128, "longitude": -74.0060, "radius_meters": 3000},
        )
        assert places_data["category"] == "place"
        assert places_data["recommendations"][0]["name"] == "Public Records"

        # 5. Movies
        movies_data = await invoke_tool(server, "get_related_movies", {"anchor_entities": ["ent_1"], "take": 5})
        assert movies_data["category"] == "movie"
        assert movies_data["recommendations"][0]["name"] == "Drive My Car"


@pytest.mark.asyncio
async def test_mcp_get_cultural_matrix(mock_settings):
    """Test get_cultural_matrix tool with full CulturalTwin input."""
    mock_insights = {
        "results": [
            {"id": "item_1", "name": "Recommended Cultural Anchor", "affinity": 0.90}
        ]
    }

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/v2/insights").respond(status_code=200, json=mock_insights)

        client = QlooClient(settings=mock_settings)
        server = create_cultural_intelligence_mcp(client)

        twin_payload = {
            "business_type": "Japanese Listening Cafe",
            "mood": "Quiet, analog, refined",
            "anchor_entities": ["ent_blue_bottle"],
            "resolved_tags": ["tag_jp_minimalism"],
            "location": {
                "latitude": 40.7484,
                "longitude": -73.9857,
                "radius_meters": 2000,
            },
        }

        data = await invoke_tool(server, "get_cultural_matrix", {"cultural_twin": twin_payload, "take_per_category": 5})

        assert data["status"] == "success"
        assert data["total_recommendations"] > 0
        matrix = data["cultural_matrix"]
        assert "artists" in matrix
        assert "places" in matrix
        assert "books" in matrix
        assert "brands" in matrix
        assert "movies" in matrix
        assert "destinations" in matrix
        uuid.UUID(data["request_id"])
