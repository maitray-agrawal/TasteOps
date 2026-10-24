"""Unit tests for AsyncTTLCache and caching behavior in QlooClient."""

import asyncio

import pytest
import respx

from tasteops.cache import AsyncTTLCache
from tasteops.client import QlooClient
from tasteops.config import QlooSettings


@pytest.mark.asyncio
async def test_async_ttl_cache_basic_and_expiration():
    """Test get, set, delete, and expiration in AsyncTTLCache."""
    cache = AsyncTTLCache(default_ttl_seconds=1)

    await cache.set("key1", {"data": "test_value"}, ttl_seconds=1)
    val = await cache.get("key1")
    assert val == {"data": "test_value"}

    # Test deletion
    await cache.delete("key1")
    assert await cache.get("key1") is None

    # Test expiration
    await cache.set("key_exp", "expires_soon", ttl_seconds=1)
    assert await cache.get("key_exp") == "expires_soon"
    await asyncio.sleep(1.05)
    assert await cache.get("key_exp") is None


@pytest.mark.asyncio
async def test_qloo_client_uses_cache(sample_search_payload):
    """Test that QlooClient returns cached response and avoids duplicate HTTP calls."""
    settings = QlooSettings(
        QLOO_API_KEY="test_key",
        QLOO_CACHE_ENABLED=True,
        QLOO_CACHE_TTL_SECONDS=60,
    )

    async with respx.mock(base_url="https://hackathon.api.qloo.com") as mock_router:
        mock_route = mock_router.get("/search").respond(status_code=200, json=sample_search_payload)

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
