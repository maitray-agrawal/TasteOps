"""TasteOps Async TTL Cache for Cultural Intelligence API responses.

Provides an asyncio-safe in-memory TTL cache protocol and implementation
to prevent redundant Qloo API calls and respect rate limits.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class CacheEntry:
    """Internal cache entry storing a payload and its expiration epoch."""

    value: Any
    expires_at: float

    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class CacheBackend(Protocol):
    """Protocol defining interface for async cache backends."""

    async def get(self, key: str) -> Any | None:
        ...

    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        ...

    async def delete(self, key: str) -> None:
        ...

    async def clear(self) -> None:
        ...


class AsyncTTLCache:
    """In-memory asyncio-safe TTL cache."""

    def __init__(self, default_ttl_seconds: int = 3600) -> None:
        self.default_ttl = default_ttl_seconds
        self._store: dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        """Retrieves cached value if present and unexpired."""
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.is_expired():
                del self._store[key]
                return None
            return entry.value

    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Stores a value with expiration TTL."""
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        if ttl <= 0:
            return
        expires_at = time.time() + ttl
        async with self._lock:
            self._store[key] = CacheEntry(value=value, expires_at=expires_at)

    async def delete(self, key: str) -> None:
        """Removes an item from cache."""
        async with self._lock:
            self._store.pop(key, None)

    async def clear(self) -> None:
        """Clears all cached entries."""
        async with self._lock:
            self._store.clear()

    @property
    def size(self) -> int:
        """Current number of active keys in cache."""
        return len(self._store)
