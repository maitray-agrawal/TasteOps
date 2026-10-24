"""TasteOps Qloo Client Layer.

Async HTTP client for Qloo Cultural Intelligence APIs:
- GET /search
- GET /v2/tags
- GET /v2/insights

Features:
- Configurable base URL (default: https://hackathon.api.qloo.com)
- Authentication via X-Api-Key
- Safe request logging without leaking API keys
- Transient error retry with exponential backoff (429, 5xx, timeouts)
- Immediate failure on auth errors (401, 403) - never retried
- Normalized application exceptions
- Typed Pydantic models for queries and responses
"""

import asyncio
import json
import logging
import time
from typing import Any, Self

import httpx

from tasteops.cache import AsyncTTLCache, CacheBackend
from tasteops.config import QlooSettings
from tasteops.exceptions import (
    QlooAuthenticationError,
    QlooException,
    QlooNotFoundError,
    QlooRateLimitError,
    QlooServerError,
    QlooTimeoutError,
    QlooValidationError,
)
from tasteops.models.entity import QlooEntity
from tasteops.models.error import QlooError
from tasteops.models.insight import QlooInsight
from tasteops.models.params import InsightParams, SearchParams, TagParams
from tasteops.models.tag import QlooTag

logger = logging.getLogger("tasteops.qloo_client")


class QlooClient:
    """Async client for Qloo Cultural Intelligence Hackathon API."""

    def __init__(
        self,
        settings: QlooSettings | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        cache: CacheBackend | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """Initializes QlooClient.

        Can be initialized from environment variables or explicit parameters.
        """
        if settings is None:
            settings_kwargs: dict[str, Any] = {}
            if api_key is not None:
                settings_kwargs["QLOO_API_KEY"] = api_key
            if base_url is not None:
                settings_kwargs["QLOO_BASE_URL"] = base_url
            if timeout is not None:
                settings_kwargs["QLOO_TIMEOUT_SECONDS"] = timeout
            if max_retries is not None:
                settings_kwargs["QLOO_MAX_RETRIES"] = max_retries
            self.settings = QlooSettings(**settings_kwargs)
        else:
            self.settings = settings

        self.base_url = self.settings.base_url.rstrip("/")
        self._headers = {
            "X-Api-Key": self.settings.raw_api_key,
            "Accept": "application/json",
            "User-Agent": "TasteOps-Cultural-Intelligence/1.0",
        }
        self._timeout = httpx.Timeout(self.settings.timeout_seconds)
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

        if cache is not None:
            self.cache: CacheBackend | None = cache
        elif self.settings.cache_enabled and self.settings.cache_ttl_seconds > 0:
            self.cache = AsyncTTLCache(
                default_ttl_seconds=self.settings.cache_ttl_seconds
            )
        else:
            self.cache = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._headers,
                timeout=self._timeout,
                transport=self._transport,
            )
        return self._client

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        """Closes the underlying HTTP client session."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _sanitize_log_headers(self, headers: httpx.Headers) -> dict[str, str]:
        """Redacts sensitive headers such as X-Api-Key from log messages."""
        sanitized = {}
        for k, v in headers.items():
            if k.lower() in ("x-api-key", "authorization", "cookie"):
                sanitized[k] = "***REDACTED***"
            else:
                sanitized[k] = v
        return sanitized

    async def _execute_get(
        self, endpoint: str, query_params: dict[str, str] | None = None
    ) -> Any:
        """Executes GET request with retries, timeout handling, and error normalization.

        Auth failures (401, 403) and 404s fail immediately without retrying.
        Transient errors (429, 5xx, timeouts) are retried with exponential backoff.
        """
        client = self._get_client()
        url = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        max_attempts = 1 + self.settings.max_retries
        backoff = self.settings.retry_backoff_factor

        cache_key: str | None = None
        if self.cache is not None and self.settings.cache_enabled:
            sorted_params = tuple(sorted((query_params or {}).items()))
            cache_key = f"{url}:{sorted_params}"
            cached_payload = await self.cache.get(cache_key)
            if cached_payload is not None:
                logger.debug("Cache hit for Qloo GET %s | Key: %s", url, cache_key)
                return cached_payload

        for attempt in range(1, max_attempts + 1):
            start_time = time.perf_counter()
            logger.debug(
                "Dispatching Qloo API request [Attempt %d/%d]: GET %s | Params: %s",
                attempt,
                max_attempts,
                url,
                query_params,
            )

            try:
                response = await client.get(url, params=query_params)
                elapsed_ms = (time.perf_counter() - start_time) * 1000

                logger.info(
                    "Qloo API response: GET %s -> Status: %d (%0.2f ms)",
                    url,
                    response.status_code,
                    elapsed_ms,
                )

                # 1. Success (2xx)
                if response.is_success:
                    try:
                        data = response.json()
                        if self.cache is not None and cache_key is not None:
                            await self.cache.set(
                                cache_key,
                                data,
                                ttl_seconds=self.settings.cache_ttl_seconds,
                            )
                        return data
                    except json.JSONDecodeError as err:
                        logger.error(
                            "Failed to decode JSON from Qloo response: %s",
                            response.text[:200],
                        )
                        raise QlooValidationError(
                            message=f"Qloo returned invalid JSON: {err!s}",
                            status_code=response.status_code,
                            details={"raw_response": response.text[:500]},
                        ) from err

                # 2. Authentication Failures (401, 403) - NEVER RETRY
                if response.status_code in (401, 403):
                    error_detail = self._extract_error_details(response)
                    logger.critical(
                        "Qloo authentication failure (HTTP %d). Check QLOO_API_KEY. Details: %s",
                        response.status_code,
                        error_detail.message,
                    )
                    raise QlooAuthenticationError(
                        message=f"Qloo authentication failed (HTTP {response.status_code}): {error_detail.message}",
                        status_code=response.status_code,
                        details=error_detail.details,
                    )

                # 3. Not Found (404) - Do NOT retry
                if response.status_code == 404:
                    error_detail = self._extract_error_details(response)
                    logger.warning(
                        "Qloo resource not found (HTTP 404): %s", error_detail.message
                    )
                    raise QlooNotFoundError(
                        message=f"Qloo resource not found: {error_detail.message}",
                        status_code=404,
                        details=error_detail.details,
                    )

                # 4. Bad Request / Validation Error (400, 422) - Do NOT retry
                if response.status_code in (400, 422):
                    error_detail = self._extract_error_details(response)
                    logger.warning(
                        "Qloo validation error (HTTP %d): %s",
                        response.status_code,
                        error_detail.message,
                    )
                    raise QlooValidationError(
                        message=f"Qloo rejected request: {error_detail.message}",
                        status_code=response.status_code,
                        details=error_detail.details,
                    )

                # 5. Rate Limited (429) - Transient, can retry
                if response.status_code == 429:
                    retry_after_header = response.headers.get("Retry-After")
                    retry_after_val = (
                        float(retry_after_header)
                        if retry_after_header and retry_after_header.isdigit()
                        else backoff * (2 ** (attempt - 1))
                    )
                    if attempt < max_attempts:
                        logger.warning(
                            "Qloo rate limited (429). Retrying in %0.2fs (Attempt %d/%d)",
                            retry_after_val,
                            attempt,
                            max_attempts,
                        )
                        await asyncio.sleep(retry_after_val)
                        continue
                    else:
                        raise QlooRateLimitError(
                            message="Qloo rate limit exceeded. Max retries exhausted.",
                            status_code=429,
                            retry_after=retry_after_val,
                        )

                # 6. Server Errors (5xx) - Transient, can retry
                if response.status_code >= 500:
                    if attempt < max_attempts:
                        sleep_time = backoff * (2 ** (attempt - 1))
                        logger.warning(
                            "Qloo server error (%d). Retrying in %0.2fs (Attempt %d/%d)",
                            response.status_code,
                            sleep_time,
                            attempt,
                            max_attempts,
                        )
                        await asyncio.sleep(sleep_time)
                        continue
                    else:
                        error_detail = self._extract_error_details(response)
                        raise QlooServerError(
                            message=f"Qloo server error (HTTP {response.status_code}): {error_detail.message}",
                            status_code=response.status_code,
                            details=error_detail.details,
                        )

                # Unhandled other HTTP status codes
                error_detail = self._extract_error_details(response)
                raise QlooException(
                    message=f"Qloo unexpected HTTP status {response.status_code}: {error_detail.message}",
                    status_code=response.status_code,
                    details=error_detail.details,
                )

            except httpx.TimeoutException as err:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                logger.warning(
                    "Qloo request timeout after %0.2fms [Attempt %d/%d]: %s",
                    elapsed_ms,
                    attempt,
                    max_attempts,
                    str(err),
                )
                if attempt < max_attempts:
                    sleep_time = backoff * (2 ** (attempt - 1))
                    await asyncio.sleep(sleep_time)
                    continue
                raise QlooTimeoutError(
                    message=f"Qloo API request timed out after {self.settings.timeout_seconds}s.",
                    details={"endpoint": url, "attempts": attempt},
                ) from err

            except httpx.RequestError as err:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                logger.warning(
                    "Qloo network transport error after %0.2fms [Attempt %d/%d]: %s",
                    elapsed_ms,
                    attempt,
                    max_attempts,
                    str(err),
                )
                if attempt < max_attempts:
                    sleep_time = backoff * (2 ** (attempt - 1))
                    await asyncio.sleep(sleep_time)
                    continue
                raise QlooException(
                    message=f"Qloo network communication failed: {err!s}",
                    details={"endpoint": url, "attempts": attempt},
                ) from err

        raise QlooException("Unexpected termination of request retry loop.")

    def _extract_error_details(self, response: httpx.Response) -> QlooError:
        """Parses error payload from Qloo response."""
        try:
            body = response.json()
            message = (
                body.get("message")
                or body.get("error")
                or body.get("detail")
                or response.text
                or "Unknown error"
            )
            error_type = body.get("type") or f"HTTP_{response.status_code}"
            return QlooError(
                status_code=response.status_code,
                error_type=str(error_type),
                message=str(message),
                details=body if isinstance(body, dict) else {"raw": body},
            )
        except Exception:
            return QlooError(
                status_code=response.status_code,
                error_type=f"HTTP_{response.status_code}",
                message=response.text[:200] or "Unknown HTTP error",
                details={"raw_text": response.text[:500]},
            )

    def _extract_result_list(self, payload: Any) -> list[Any]:
        """Extracts items array from Qloo's response payload."""
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            if "results" in payload and isinstance(payload["results"], list):
                return payload["results"]
            if "data" in payload and isinstance(payload["data"], list):
                return payload["data"]
            if "entities" in payload and isinstance(payload["entities"], list):
                return payload["entities"]
            if "tags" in payload and isinstance(payload["tags"], list):
                return payload["tags"]
            if "insights" in payload and isinstance(payload["insights"], list):
                return payload["insights"]
            # If payload is empty dict
            if not payload:
                return []
        raise QlooValidationError(
            message="Qloo payload format is unrecognized. Expected a list or dict with 'results'/'data' array.",
            details={"payload_type": type(payload).__name__},
        )

    # -------------------------------------------------------------------------
    # Core API Endpoints
    # -------------------------------------------------------------------------

    async def search(
        self,
        params: SearchParams | dict[str, Any] | str,
        *,
        entity_type: str | None = None,
        take: int = 10,
    ) -> list[QlooEntity]:
        """Executes GET /search to resolve cultural entities.

        Accepts a validated SearchParams instance, a dictionary, or a query string.
        """
        if isinstance(params, str):
            validated_params = SearchParams(query=params, type=entity_type, take=take)
        elif isinstance(params, dict):
            validated_params = SearchParams(**params)
        elif isinstance(params, SearchParams):
            validated_params = params
        else:
            raise QlooValidationError(
                f"Invalid parameter type for search: {type(params).__name__}. Expected SearchParams, dict, or str."
            )

        raw_data = await self._execute_get(
            "/search", query_params=validated_params.to_query_params()
        )
        items = self._extract_result_list(raw_data)

        entities: list[QlooEntity] = []
        for index, item in enumerate(items):
            try:
                entities.append(QlooEntity.model_validate(item))
            except Exception as err:
                raise QlooValidationError(
                    message=f"Failed to normalize entity item at index {index}: {err!s}",
                    details={"item": item},
                ) from err

        return entities

    async def get_tags(
        self,
        params: TagParams | dict[str, Any] | str | None = None,
        *,
        tag_type: str | None = None,
        take: int = 20,
    ) -> list[QlooTag]:
        """Executes GET /v2/tags to query the cultural tag taxonomy."""
        if params is None:
            validated_params = TagParams(take=take, type=tag_type)
        elif isinstance(params, str):
            validated_params = TagParams(query=params, type=tag_type, take=take)
        elif isinstance(params, dict):
            validated_params = TagParams(**params)
        elif isinstance(params, TagParams):
            validated_params = params
        else:
            raise QlooValidationError(
                f"Invalid parameter type for get_tags: {type(params).__name__}. Expected TagParams, dict, or str."
            )

        raw_data = await self._execute_get(
            "/v2/tags", query_params=validated_params.to_query_params()
        )
        items = self._extract_result_list(raw_data)

        tags: list[QlooTag] = []
        for index, item in enumerate(items):
            try:
                tags.append(QlooTag.model_validate(item))
            except Exception as err:
                raise QlooValidationError(
                    message=f"Failed to normalize tag item at index {index}: {err!s}",
                    details={"item": item},
                ) from err

        return tags

    async def get_insights(
        self,
        params: InsightParams | dict[str, Any],
    ) -> list[QlooInsight]:
        """Executes GET /v2/insights to fetch cross-domain cultural affinity rankings.

        NOTE: Uses GET /v2/insights exclusively. Never calls /recs or /recommendations.
        """
        if isinstance(params, dict):
            validated_params = InsightParams(**params)
        elif isinstance(params, InsightParams):
            validated_params = params
        else:
            raise QlooValidationError(
                f"Invalid parameter type for get_insights: {type(params).__name__}. Expected InsightParams or dict."
            )

        raw_data = await self._execute_get(
            "/v2/insights", query_params=validated_params.to_query_params()
        )
        items = self._extract_result_list(raw_data)

        insights: list[QlooInsight] = []
        for index, item in enumerate(items):
            try:
                insights.append(QlooInsight.model_validate(item))
            except Exception as err:
                raise QlooValidationError(
                    message=f"Failed to normalize insight item at index {index}: {err!s}",
                    details={"item": item},
                ) from err

        return insights
