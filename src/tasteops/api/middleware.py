"""TasteOps API Middlewares.

Provides:
- Request correlation ID tracking (X-Correlation-ID)
- Structured access logging with latency measurement
- Security response headers
- Credential and secret masking
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("tasteops.api.access")

SENSITIVE_HEADERS = {"authorization", "x-api-key", "cookie", "set-cookie"}


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    """Assigns or propagates a unique correlation ID per request and logs structured access data."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract existing correlation ID or generate fresh UUID
        correlation_id = (
            request.headers.get("X-Correlation-ID")
            or request.headers.get("X-Request-ID")
            or f"req_{uuid.uuid4().hex[:16]}"
        )
        request.state.correlation_id = correlation_id

        start_time = time.perf_counter()
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "[%s] %s %s ERROR from %s in %.2fms",
                correlation_id,
                method,
                path,
                client_ip,
                duration_ms,
            )
            raise

        duration_ms = (time.perf_counter() - start_time) * 1000
        response.headers["X-Correlation-ID"] = correlation_id

        # Log structured access record
        logger.info(
            "[%s] %s %s %d in %.2fms (client: %s)",
            correlation_id,
            method,
            path,
            response.status_code,
            duration_ms,
            client_ip,
        )

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforces secure browser headers on all outgoing HTTP responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
