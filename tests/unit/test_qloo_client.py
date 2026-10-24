"""Unit tests for QlooClient and its error handling, retries, and normalization."""

import logging

import httpx
import pytest
import respx

from tasteops.client import QlooClient
from tasteops.exceptions import (
    QlooAuthenticationError,
    QlooNotFoundError,
    QlooRateLimitError,
    QlooTimeoutError,
    QlooValidationError,
)
from tasteops.models import InsightParams, SearchParams, TagParams


@pytest.mark.asyncio
async def test_search_200_success(mock_settings, sample_search_payload):
    """Test successful 200 OK entity search and model normalization."""
    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_route = mock_router.get("/search").respond(
            status_code=200,
            json=sample_search_payload,
        )

        async with QlooClient(settings=mock_settings) as client:
            entities = await client.search(SearchParams(query="Blue Bottle", type="place", take=10))

            assert len(entities) == 2
            assert entities[0].id == "ent_blue_bottle_123"
            assert entities[0].name == "Blue Bottle Coffee"
            assert entities[0].type == "place"
            assert entities[0].subtype == "cafe"
            assert "specialty-coffee" in entities[0].tags
            assert entities[0].metadata["city"] == "New York"

            # Check normalized object tags for second entity
            assert entities[1].id == "ent_stumptown_456"
            assert "cold-brew" in entities[1].tags

            # Verify request headers and params
            assert mock_route.called
            last_request = mock_route.calls.last.request
            assert last_request.headers["X-Api-Key"] == "test_mock_qloo_api_key_12345"
            assert last_request.url.params["query"] == "Blue Bottle"
            assert last_request.url.params["type"] == "place"


@pytest.mark.asyncio
async def test_get_tags_200_success(mock_settings, sample_tags_payload):
    """Test successful 200 OK tag resolution."""
    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/v2/tags").respond(
            status_code=200,
            json=sample_tags_payload,
        )

        async with QlooClient(settings=mock_settings) as client:
            tags = await client.get_tags(TagParams(query="beats", type="music"))

            assert len(tags) == 2
            assert tags[0].id == "tag_lofi_beats"
            assert tags[0].name == "Lo-Fi Beats"
            assert tags[0].category == "music"
            assert tags[0].urn == "urn:tag:music:genre:lofi"


@pytest.mark.asyncio
async def test_get_insights_200_success(mock_settings, sample_insights_payload):
    """Test successful 200 OK insights query via GET."""
    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_route = mock_router.get("/v2/insights").respond(
            status_code=200,
            json=sample_insights_payload,
        )

        async with QlooClient(settings=mock_settings) as client:
            params = InsightParams(
                signal_entities=["ent_blue_bottle_123"],
                filter_type="urn:entity:artist",
                location_wkt="POINT(-73.985 40.748)",
                location_radius=2000,
                explainability=True,
                take=10,
            )
            insights = await client.get_insights(params)

            assert len(insights) == 2
            assert insights[0].id == "ent_four_tet"
            assert insights[0].affinity == 0.94
            assert insights[0].score == 94.0
            assert len(insights[0].explainability) == 1

            assert mock_route.called
            last_request = mock_route.calls.last.request
            assert last_request.method == "GET"
            assert last_request.url.params["signal.interests.entities"] == "ent_blue_bottle_123"
            assert last_request.url.params["filter.type"] == "urn:entity:artist"
            assert last_request.url.params["filter.location"] == "POINT(-73.985 40.748)"
            assert last_request.url.params["filter.location.radius"] == "2000"
            assert last_request.url.params["feature.explainability"] == "true"


@pytest.mark.asyncio
async def test_401_unauthorized_never_retried(mock_settings):
    """Test 401 Unauthorized raises QlooAuthenticationError immediately without retrying."""
    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_route = mock_router.get("/search").respond(
            status_code=401,
            json={"error": "Invalid API Key", "message": "API key provided is invalid or expired."},
        )

        async with QlooClient(settings=mock_settings) as client:
            with pytest.raises(QlooAuthenticationError) as exc_info:
                await client.search("test query")

            assert exc_info.value.status_code == 401
            assert "authentication failed" in str(exc_info.value).lower()
            # Must ONLY be called once - never retried
            assert mock_route.call_count == 1


@pytest.mark.asyncio
async def test_403_forbidden_never_retried(mock_settings):
    """Test 403 Forbidden raises QlooAuthenticationError immediately without retrying."""
    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_route = mock_router.get("/v2/insights").respond(
            status_code=403,
            json={"error": "Forbidden", "message": "Endpoint not permitted for your plan."},
        )

        async with QlooClient(settings=mock_settings) as client:
            with pytest.raises(QlooAuthenticationError) as exc_info:
                await client.get_insights(InsightParams(signal_entities=["ent_123"]))

            assert exc_info.value.status_code == 403
            assert mock_route.call_count == 1


@pytest.mark.asyncio
async def test_404_not_found_never_retried(mock_settings):
    """Test 404 Not Found raises QlooNotFoundError without retrying."""
    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_route = mock_router.get("/search").respond(
            status_code=404,
            json={"error": "NotFound", "message": "Requested resource was not found."},
        )

        async with QlooClient(settings=mock_settings) as client:
            with pytest.raises(QlooNotFoundError) as exc_info:
                await client.search("non_existent_entity")

            assert exc_info.value.status_code == 404
            assert mock_route.call_count == 1


@pytest.mark.asyncio
async def test_timeout_handling(mock_settings):
    """Test request timeout is caught, retried up to max_retries, and raises QlooTimeoutError."""
    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_route = mock_router.get("/search").mock(
            side_effect=httpx.ReadTimeout("Read operation timed out")
        )

        async with QlooClient(settings=mock_settings) as client:
            with pytest.raises(QlooTimeoutError) as exc_info:
                await client.search("timeout query")

            assert "timed out" in str(exc_info.value).lower()
            # Total attempts = 1 initial + 2 retries = 3 attempts
            assert mock_route.call_count == 3


@pytest.mark.asyncio
async def test_empty_entities(mock_settings):
    """Test empty results array returns an empty list without error."""
    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/search").respond(
            status_code=200,
            json={"results": []},
        )

        async with QlooClient(settings=mock_settings) as client:
            entities = await client.search("obscure venue")
            assert entities == []


@pytest.mark.asyncio
async def test_malformed_json_response(mock_settings):
    """Test non-JSON malformed response raises QlooValidationError."""
    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/search").respond(
            status_code=200,
            text="<html><head><title>Bad Gateway</title></head><body>Bad Gateway</body></html>",
            headers={"Content-Type": "text/html"},
        )

        async with QlooClient(settings=mock_settings) as client:
            with pytest.raises(QlooValidationError) as exc_info:
                await client.search("malformed json")

            assert "invalid json" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_malformed_item_schema(mock_settings):
    """Test payload with missing required fields raises QlooValidationError."""
    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/search").respond(
            status_code=200,
            # Missing both id and name
            json={"results": [{"invalid_key": "some_value"}]},
        )

        async with QlooClient(settings=mock_settings) as client:
            with pytest.raises(QlooValidationError) as exc_info:
                await client.search("bad schema")

            assert "failed to normalize" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_transient_500_retried_and_succeeds(mock_settings, sample_search_payload):
    """Test transient 500 error retries and succeeds on next attempt."""
    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_route = mock_router.get("/search")
        mock_route.side_effect = [
            httpx.Response(500, json={"error": "Internal Server Error"}),
            httpx.Response(200, json=sample_search_payload),
        ]

        async with QlooClient(settings=mock_settings) as client:
            entities = await client.search("transient query")
            assert len(entities) == 2
            assert mock_route.call_count == 2


@pytest.mark.asyncio
async def test_transient_429_exhausted(mock_settings):
    """Test repeated 429 rate limit raises QlooRateLimitError after max retries."""
    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_route = mock_router.get("/search").respond(
            status_code=429,
            json={"error": "Rate limit exceeded"},
            headers={"Retry-After": "0.01"},
        )

        async with QlooClient(settings=mock_settings) as client:
            with pytest.raises(QlooRateLimitError) as exc_info:
                await client.search("rate limit query")

            assert exc_info.value.status_code == 429
            assert mock_route.call_count == 3


def test_api_key_never_logged_or_exposed_in_repr(mock_settings):
    """Security check: QlooSettings repr and client log redacting must never expose raw key."""
    settings_str = repr(mock_settings)
    assert "test_mock_qloo_api_key_12345" not in settings_str
    assert "***REDACTED***" in settings_str


def test_validated_search_params_rejects_blank():
    """Ensure SearchParams rejects empty or whitespace-only queries."""
    with pytest.raises(ValueError):
        SearchParams(query="   ")


def test_validated_insight_params_rejects_invalid_wkt():
    """Ensure InsightParams rejects malformed WKT strings."""
    with pytest.raises(ValueError, match="Invalid location_wkt"):
        InsightParams(signal_entities=["ent_1"], location_wkt="INVALID(-73, 40)")


def test_validated_insight_params_requires_signals():
    """Ensure InsightParams requires at least one signal or location."""
    with pytest.raises(ValueError, match="requires at least one signal"):
        InsightParams()


@pytest.mark.asyncio
async def test_logs_never_contain_api_key(mock_settings, caplog, sample_search_payload):
    """Test requirement 9: Request metadata is logged, but API key is strictly never logged."""
    caplog.set_level(logging.DEBUG, logger="tasteops.qloo_client")

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_router.get("/search").respond(
            status_code=200,
            json=sample_search_payload,
        )

        async with QlooClient(settings=mock_settings) as client:
            await client.search(SearchParams(query="Blue Bottle", take=5))

    raw_key = mock_settings.raw_api_key
    assert raw_key not in caplog.text
    assert "GET /search" in caplog.text
    assert "Status: 200" in caplog.text


def test_base_url_default_and_custom(monkeypatch):
    """Test requirement 2: Base URL defaults to hackathon endpoint and is configurable."""
    monkeypatch.setenv("QLOO_API_KEY", "env_test_key")
    default_client = QlooClient()
    assert default_client.base_url == "https://hackathon.api.qloo.com"

    custom_client = QlooClient(base_url="https://custom.api.qloo.com/v2")
    assert custom_client.base_url == "https://custom.api.qloo.com/v2"
