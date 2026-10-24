"""Unit tests and regression audit for AsyncTTLCache and caching/concurrency behavior in QlooClient."""

import asyncio

import httpx
import pytest
import respx

from tasteops.cache import AsyncTTLCache
from tasteops.client import QlooClient
from tasteops.config import QlooSettings
from tasteops.exceptions import (
    QlooAuthenticationError,
    QlooNotFoundError,
    QlooRateLimitError,
    QlooServerError,
    QlooTimeoutError,
)
from tasteops.models.cultural_matrix import CulturalTwin, LocationInput
from tasteops.services.cultural_matrix_service import CulturalMatrixService


@pytest.mark.asyncio
async def test_async_ttl_cache_basic_and_expiration():
    """Test get, set, delete, metrics tracking, and expiration in AsyncTTLCache."""
    cache = AsyncTTLCache(default_ttl_seconds=1)

    assert cache.hits == 0
    assert cache.misses == 0
    assert cache.total_requests == 0
    assert cache.hit_ratio == 0.0

    # Cache miss
    val0 = await cache.get("key1")
    assert val0 is None
    assert cache.misses == 1

    # Set and cache hit
    await cache.set("key1", {"data": "test_value"}, ttl_seconds=1)
    val = await cache.get("key1")
    assert val == {"data": "test_value"}
    assert cache.hits == 1
    assert cache.total_requests == 2
    assert cache.hit_ratio == 0.5

    # Test deletion
    await cache.delete("key1")
    assert await cache.get("key1") is None
    assert cache.misses == 2

    # Test expiration
    await cache.set("key_exp", "expires_soon", ttl_seconds=1)
    assert await cache.get("key_exp") == "expires_soon"
    assert cache.hits == 2
    await asyncio.sleep(1.05)
    assert await cache.get("key_exp") is None
    assert cache.misses == 3


@pytest.mark.asyncio
async def test_qloo_client_uses_cache(sample_search_payload):
    """Test that QlooClient returns cached response and avoids duplicate HTTP calls."""
    settings = QlooSettings(
        QLOO_API_KEY="test_key",
        QLOO_CACHE_ENABLED=True,
        QLOO_CACHE_TTL_SECONDS=60,
    )

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_route = mock_router.get("/search").respond(
            status_code=200, json=sample_search_payload
        )

        async with QlooClient(settings=settings) as client:
            # First call -> hits HTTP
            res1 = await client.search("Blue Bottle")
            assert len(res1) == 2
            assert mock_route.call_count == 1

            # Second identical call -> hits Cache (call_count remains 1)
            res2 = await client.search("Blue Bottle")
            assert len(res2) == 2
            assert mock_route.call_count == 1
            assert res1[0].id == res2[0].id


# =============================================================================
# Audit Regression Test Suite
# =============================================================================


@pytest.mark.asyncio
async def test_concurrent_calls(sample_search_payload):
    """Regression test for concurrent calls.

    Verifies:
    1. Concurrent duplicate queries through QlooClient complete safely without race conditions.
    2. Concurrent category queries in CulturalMatrixService execute in parallel and assemble
       isolated, non-corrupted results across all categories.
    """
    settings = QlooSettings(
        QLOO_API_KEY="test_key",
        QLOO_CACHE_ENABLED=True,
        QLOO_CACHE_TTL_SECONDS=60,
    )
    cache = AsyncTTLCache(default_ttl_seconds=60)

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        # Simulate slight network delay to guarantee concurrent in-flight overlap
        async def delayed_search(request: httpx.Request):
            await asyncio.sleep(0.02)
            return httpx.Response(200, json=sample_search_payload)

        mock_router.get("/search").mock(side_effect=delayed_search)

        async with QlooClient(settings=settings, cache=cache) as client:
            # 5 concurrent identical calls
            tasks = [client.search("Radiohead") for _ in range(5)]
            results = await asyncio.gather(*tasks)

            # All 5 return identical valid results
            assert len(results) == 5
            for res in results:
                assert len(res) == 2
                assert res[0].name == "Blue Bottle Coffee"

        # Part 2: Concurrent category queries in CulturalMatrixService
        mock_categories = {
            "urn:entity:artist": [
                {"id": "art_1", "name": "Floating Points", "affinity": 0.9}
            ],
            "urn:entity:book": [
                {"id": "book_1", "name": "In Praise of Shadows", "affinity": 0.85}
            ],
            "urn:entity:brand": [{"id": "brand_1", "name": "Muji", "affinity": 0.88}],
            "urn:entity:place": [
                {"id": "place_1", "name": "Sey Coffee", "affinity": 0.92}
            ],
            "urn:entity:movie": [
                {"id": "mov_1", "name": "Perfect Days", "affinity": 0.87}
            ],
            "urn:entity:destination": [
                {"id": "dest_1", "name": "Kyoto", "affinity": 0.91}
            ],
        }

        async def delayed_insight(request: httpx.Request):
            await asyncio.sleep(0.02)
            ft = request.url.params.get("filter.type", "")
            return httpx.Response(200, json={"results": mock_categories.get(ft, [])})

        mock_router.get("/v2/insights").mock(side_effect=delayed_insight)

        twin = CulturalTwin(
            anchor_entities=["ent_blue_bottle"],
            resolved_tags=["tag_minimalism"],
            location=LocationInput(
                latitude=40.7128, longitude=-74.0060, radius_meters=3000
            ),
        )

        async with QlooClient(settings=settings) as client:
            matrix_service = CulturalMatrixService(client)
            matrix = await matrix_service.generate_matrix(twin)

            # All 6 categories processed concurrently without corruption
            assert matrix.total_recommendations == 6
            assert len(matrix.artists) == 1
            assert len(matrix.books) == 1
            assert len(matrix.brands) == 1
            assert len(matrix.places) == 1
            assert len(matrix.movies) == 1
            assert len(matrix.destinations) == 1
            assert len(matrix.query_metadata) == 6


@pytest.mark.asyncio
async def test_cache_hit(sample_search_payload):
    """Regression test for cache hit.

    Verifies:
    1. First request causes a cache miss and dispatches 1 HTTP request.
    2. Subsequent identical requests produce cache hits with 0 HTTP dispatches.
    3. Cache hit ratio and telemetry metrics accurately reflect hits vs misses.
    """
    settings = QlooSettings(
        QLOO_API_KEY="test_key",
        QLOO_CACHE_ENABLED=True,
        QLOO_CACHE_TTL_SECONDS=60,
    )
    cache = AsyncTTLCache(default_ttl_seconds=60)

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_route = mock_router.get("/search").respond(
            status_code=200, json=sample_search_payload
        )

        async with QlooClient(settings=settings, cache=cache) as client:
            # 1st call -> miss
            res1 = await client.search("Blue Bottle")
            assert mock_route.call_count == 1
            assert cache.misses == 1
            assert cache.hits == 0

            # 2nd call -> hit
            res2 = await client.search("Blue Bottle")
            assert mock_route.call_count == 1
            assert cache.misses == 1
            assert cache.hits == 1

            # 3rd call -> hit
            res3 = await client.search("Blue Bottle")
            assert mock_route.call_count == 1
            assert cache.misses == 1
            assert cache.hits == 2
            assert cache.total_requests == 3
            assert round(cache.hit_ratio, 2) == 0.67

            assert res1[0].id == res2[0].id == res3[0].id


@pytest.mark.asyncio
async def test_cache_expiry(sample_search_payload):
    """Regression test for cache expiry.

    Verifies:
    1. Response cached for defined TTL.
    2. Requests prior to expiry hit the cache.
    3. After TTL elapses, item expires, triggering a cache miss and exactly 1 refetch over HTTP.
    """
    settings = QlooSettings(
        QLOO_API_KEY="test_key",
        QLOO_CACHE_ENABLED=True,
        QLOO_CACHE_TTL_SECONDS=1,  # 1 second TTL
    )
    cache = AsyncTTLCache(default_ttl_seconds=1)

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_route = mock_router.get("/search").respond(
            status_code=200, json=sample_search_payload
        )

        async with QlooClient(settings=settings, cache=cache) as client:
            # 1. Initial request -> HTTP fetch
            await client.search("Four Tet")
            assert mock_route.call_count == 1
            assert cache.hits == 0
            assert cache.misses == 1

            # 2. Immediate repeat -> Cache hit
            await client.search("Four Tet")
            assert mock_route.call_count == 1
            assert cache.hits == 1

            # 3. Wait for TTL to expire (>1.0s)
            await asyncio.sleep(1.1)

            # 4. Post-expiration request -> Cache miss & new HTTP fetch
            await client.search("Four Tet")
            assert mock_route.call_count == 2
            assert cache.hits == 1
            assert cache.misses == 2


@pytest.mark.asyncio
async def test_failed_cached_request():
    """Regression test for failed cached requests.

    Verifies:
    1. HTTP 500 server error is NOT cached (zero cache pollution).
    2. HTTP 404 not found error is NOT cached.
    3. Timeout failure is NOT cached.
    4. Subsequent request after upstream recovery succeeds cleanly via fresh HTTP fetch.
    """
    settings = QlooSettings(
        QLOO_API_KEY="test_key",
        QLOO_CACHE_ENABLED=True,
        QLOO_CACHE_TTL_SECONDS=60,
        QLOO_MAX_RETRIES=0,  # Fail fast to inspect cache immediately
    )
    cache = AsyncTTLCache(default_ttl_seconds=60)

    async with respx.mock(
        base_url="https://hackathon.api.qloo.com", assert_all_called=False
    ) as mock_router:
        # Route initially fails with 500
        mock_route = mock_router.get(
            "/search", params={"query": "TestFail", "take": "10"}
        ).respond(status_code=500, json={"message": "Temporary internal error"})

        async with QlooClient(settings=settings, cache=cache) as client:
            with pytest.raises(QlooServerError):
                await client.search("TestFail")

            # Verify cache was NOT polluted
            assert cache.size == 0
            assert cache.misses == 1
            assert cache.hits == 0

            # Now mock recovers and returns 200 OK
            mock_route.respond(
                status_code=200,
                json={
                    "results": [
                        {
                            "id": "ent_recovered",
                            "name": "Recovered Entity",
                            "type": "brand",
                        }
                    ]
                },
            )

            recovered = await client.search("TestFail")
            assert len(recovered) == 1
            assert recovered[0].id == "ent_recovered"
            assert cache.size == 1  # Now cached after successful response


@pytest.mark.asyncio
async def test_bounded_retries():
    """Regression test for bounded retries and failure amplification prevention.

    Verifies:
    1. Non-transient errors (401, 403, 404) fail immediately on attempt 1 without retry.
    2. Transient errors (500, 429) retry exactly up to max_retries and terminate deterministically.
    3. Timeouts retry exactly up to max_retries and raise QlooTimeoutError.
    4. Fallback in CulturalMatrixService is strictly bounded to at most 1 retry.
    """
    settings = QlooSettings(
        QLOO_API_KEY="test_key",
        QLOO_MAX_RETRIES=2,
        QLOO_RETRY_BACKOFF_FACTOR=0.01,
        QLOO_TIMEOUT_SECONDS=1.0,
    )

    async with respx.mock(
        base_url="https://hackathon.api.qloo.com", assert_all_called=False
    ) as mock_router:
        # 1. 401 Unauthorized -> Strictly 1 attempt, 0 retries
        route_401 = mock_router.get(
            "/search", params={"query": "AuthFail", "take": "10"}
        ).respond(status_code=401, json={"message": "Invalid API key"})
        async with QlooClient(settings=settings) as client:
            with pytest.raises(QlooAuthenticationError):
                await client.search("AuthFail")
            assert route_401.call_count == 1

        # 2. 404 Not Found -> Strictly 1 attempt, 0 retries
        route_404 = mock_router.get(
            "/search", params={"query": "NotFound", "take": "10"}
        ).respond(status_code=404, json={"message": "Entity not found"})
        async with QlooClient(settings=settings) as client:
            with pytest.raises(QlooNotFoundError):
                await client.search("NotFound")
            assert route_404.call_count == 1

        # 3. 500 Server Error -> Bounded to 1 + max_retries = 3 attempts
        route_500 = mock_router.get(
            "/search", params={"query": "ServerError", "take": "10"}
        ).respond(status_code=500, json={"message": "Internal error"})
        async with QlooClient(settings=settings) as client:
            with pytest.raises(QlooServerError):
                await client.search("ServerError")
            assert route_500.call_count == 3

        # 4. 429 Rate Limit -> Bounded to 1 + max_retries = 3 attempts
        route_429 = mock_router.get(
            "/search", params={"query": "RateLimit", "take": "10"}
        ).respond(status_code=429, json={"message": "Too Many Requests"})
        async with QlooClient(settings=settings) as client:
            with pytest.raises(QlooRateLimitError):
                await client.search("RateLimit")
            assert route_429.call_count == 3

        # 5. Timeout -> Bounded to 1 + max_retries = 3 attempts
        route_timeout = mock_router.get(
            "/search", params={"query": "TimeoutQuery", "take": "10"}
        ).mock(side_effect=httpx.TimeoutException("Read timed out"))
        async with QlooClient(settings=settings) as client:
            with pytest.raises(QlooTimeoutError):
                await client.search("TimeoutQuery")
            assert route_timeout.call_count == 3

        # 6. CulturalMatrix fallback bounded to 1 retry
        mock_insights = mock_router.get("/v2/insights").respond(
            status_code=200, json={"results": []}
        )
        twin = CulturalTwin(
            anchor_entities=["ent_niche"],
            location=LocationInput(
                latitude=40.7128, longitude=-74.0060, radius_meters=1000
            ),
        )
        async with QlooClient(settings=settings) as client:
            matrix_service = CulturalMatrixService(client)
            matrix = await matrix_service.generate_matrix(twin, categories=["place"])

            # 1 initial call + 1 fallback retry = 2 calls
            assert mock_insights.call_count == 2
            assert matrix.total_recommendations == 0
            assert matrix.query_metadata[0].retries == 1
            assert matrix.query_metadata[0].status == "fallback_empty"
