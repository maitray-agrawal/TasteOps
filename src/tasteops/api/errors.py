"""TasteOps Centralized API Exception Handlers.

Maps TasteOps domain exceptions, validation errors, and Qloo errors to RFC 7807
problem details envelopes. Guarantees that internal secret keys are never leaked.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from tasteops.agents.governance import (
    ProvenanceValidationError,
    UnapprovedExecutionError,
)
from tasteops.api.schemas.common import ErrorDetail
from tasteops.api.service import (
    BlueprintNotReadyError,
    SessionNotFoundError,
    SpaceNotFoundError,
)
from tasteops.connectors import (
    ConnectorError,
    ConnectorNotConfiguredError,
    DuplicateExecutionError,
    InvalidConfigurationError,
    MissingConnectorError,
)
from tasteops.exceptions import (
    QlooAuthenticationError,
    QlooNotFoundError,
    QlooRateLimitError,
    QlooServerError,
    QlooTimeoutError,
)
from tasteops.workflows.states import InvalidStateTransitionError

logger = logging.getLogger("tasteops.api.errors")

HTTP_422_UNPROCESSABLE: int = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)


def _get_correlation_id(request: Request) -> str:
    """Extracts correlation ID from request state or headers."""
    return getattr(request.state, "correlation_id", "unknown-correlation-id")


def _build_error_response(
    request: Request,
    status_code: int,
    title: str,
    detail: str,
    code: str,
    errors: list[dict[str, Any]] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Constructs a standard RFC 7807 JSON response."""
    correlation_id = _get_correlation_id(request)
    error_detail = ErrorDetail(
        type=f"https://tasteops.io/errors/{code.lower()}",
        title=title,
        status=status_code,
        detail=detail,
        instance=str(request.url.path),
        code=code,
        correlation_id=correlation_id,
        errors=errors,
    )
    resp_headers = {"X-Correlation-ID": correlation_id}
    if headers:
        resp_headers.update(dict(headers))

    return JSONResponse(
        status_code=status_code,
        content={"error": error_detail.model_dump(exclude_none=True)},
        headers=resp_headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Registers all custom exception handlers on the FastAPI application instance."""

    # 404 Space Not Found
    @app.exception_handler(SpaceNotFoundError)
    async def space_not_found_handler(
        request: Request, exc: SpaceNotFoundError
    ) -> JSONResponse:
        logger.warning("[%s] Space not found: %s", _get_correlation_id(request), exc)
        return _build_error_response(
            request=request,
            status_code=status.HTTP_404_NOT_FOUND,
            title="Space Not Found",
            detail=str(exc),
            code="SPACE_NOT_FOUND",
        )

    # 404 Session Not Found
    @app.exception_handler(SessionNotFoundError)
    async def session_not_found_handler(
        request: Request, exc: SessionNotFoundError
    ) -> JSONResponse:
        logger.warning("[%s] Session not found: %s", _get_correlation_id(request), exc)
        return _build_error_response(
            request=request,
            status_code=status.HTTP_404_NOT_FOUND,
            title="Workflow Session Not Found",
            detail=str(exc),
            code="SESSION_NOT_FOUND",
        )

    # 404 Qloo Entity Not Found
    @app.exception_handler(QlooNotFoundError)
    async def qloo_not_found_handler(
        request: Request, exc: QlooNotFoundError
    ) -> JSONResponse:
        logger.warning(
            "[%s] Qloo entity not found: %s", _get_correlation_id(request), exc
        )
        return _build_error_response(
            request=request,
            status_code=status.HTTP_404_NOT_FOUND,
            title="Cultural Entity Not Found",
            detail=exc.message,
            code="ENTITY_NOT_FOUND",
        )

    # 409 Blueprint Not Ready
    @app.exception_handler(BlueprintNotReadyError)
    async def blueprint_not_ready_handler(
        request: Request, exc: BlueprintNotReadyError
    ) -> JSONResponse:
        logger.info(
            "[%s] Blueprint not ready conflict: %s", _get_correlation_id(request), exc
        )
        return _build_error_response(
            request=request,
            status_code=status.HTTP_409_CONFLICT,
            title="Blueprint Not Ready",
            detail=str(exc),
            code="BLUEPRINT_NOT_READY",
        )

    # 409 Invalid State Transition
    @app.exception_handler(InvalidStateTransitionError)
    async def invalid_transition_handler(
        request: Request, exc: InvalidStateTransitionError
    ) -> JSONResponse:
        logger.warning(
            "[%s] Invalid workflow state transition: %s",
            _get_correlation_id(request),
            exc,
        )
        return _build_error_response(
            request=request,
            status_code=status.HTTP_409_CONFLICT,
            title="Invalid Workflow State Transition",
            detail=str(exc),
            code="INVALID_STATE_TRANSITION",
        )

    # 403 Unapproved Execution Gate Violation
    @app.exception_handler(UnapprovedExecutionError)
    async def unapproved_execution_handler(
        request: Request, exc: UnapprovedExecutionError
    ) -> JSONResponse:
        logger.warning(
            "[%s] Unapproved execution attempt blocked: %s",
            _get_correlation_id(request),
            exc,
        )
        return _build_error_response(
            request=request,
            status_code=status.HTTP_403_FORBIDDEN,
            title="Execution Gate Violation",
            detail=str(exc),
            code="EXECUTION_UNAPPROVED",
        )

    # 422 Provenance Validation Error
    @app.exception_handler(ProvenanceValidationError)
    async def provenance_error_handler(
        request: Request, exc: ProvenanceValidationError
    ) -> JSONResponse:
        logger.error(
            "[%s] Provenance integrity validation failed: %s",
            _get_correlation_id(request),
            exc,
        )
        return _build_error_response(
            request=request,
            status_code=HTTP_422_UNPROCESSABLE,
            title="Provenance Validation Failed",
            detail=str(exc),
            code="PROVENANCE_INTEGRITY_VIOLATION",
        )

    # 401 Qloo Authentication Error (No secret key leakage!)
    @app.exception_handler(QlooAuthenticationError)
    async def qloo_auth_error_handler(
        request: Request, exc: QlooAuthenticationError
    ) -> JSONResponse:
        logger.critical(
            "[%s] Qloo authentication failed. Check QLOO_API_KEY.",
            _get_correlation_id(request),
        )
        return _build_error_response(
            request=request,
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Cultural Intelligence Authentication Failed",
            detail="The Qloo API key is missing, invalid, or unauthorized.",
            code="AUTH_KEY_INVALID",
        )

    # 429 Qloo Rate Limit Error
    @app.exception_handler(QlooRateLimitError)
    async def qloo_rate_limit_handler(
        request: Request, exc: QlooRateLimitError
    ) -> JSONResponse:
        retry_after = str(int(exc.retry_after or 5))
        logger.warning(
            "[%s] Qloo rate limit reached. Retry-After: %s",
            _get_correlation_id(request),
            retry_after,
        )
        return _build_error_response(
            request=request,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            title="Rate Limit Exceeded",
            detail="Rate limit reached for cultural intelligence queries. Please retry later.",
            code="RATE_LIMIT_EXCEEDED",
            headers={"Retry-After": retry_after},
        )

    # 504 Qloo Timeout
    @app.exception_handler(QlooTimeoutError)
    async def qloo_timeout_handler(
        request: Request, exc: QlooTimeoutError
    ) -> JSONResponse:
        logger.error(
            "[%s] Qloo upstream request timed out: %s",
            _get_correlation_id(request),
            exc,
        )
        return _build_error_response(
            request=request,
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            title="Cultural Intelligence Service Timeout",
            detail="Upstream cultural data provider timed out. Please try again.",
            code="QLOO_TIMEOUT",
        )

    # 502 Qloo Server Error
    @app.exception_handler(QlooServerError)
    async def qloo_server_error_handler(
        request: Request, exc: QlooServerError
    ) -> JSONResponse:
        logger.error(
            "[%s] Qloo upstream 5xx server error: %s",
            _get_correlation_id(request),
            exc,
        )
        return _build_error_response(
            request=request,
            status_code=status.HTTP_502_BAD_GATEWAY,
            title="Upstream Cultural Intelligence Error",
            detail="Upstream cultural intelligence service is temporarily unavailable.",
            code="QLOO_SERVER_ERROR",
        )

    # 422 Request Validation Error (FastAPI / Pydantic)
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        raw_errors = exc.errors()
        logger.info(
            "[%s] Request payload validation failed (%d errors)",
            _get_correlation_id(request),
            len(raw_errors),
        )
        formatted_errors: list[dict[str, Any]] = []
        for err in raw_errors:
            formatted_errors.append(
                {
                    "loc": list(err.get("loc", [])),
                    "msg": err.get("msg", "Validation error"),
                    "type": err.get("type", "value_error"),
                }
            )
        return _build_error_response(
            request=request,
            status_code=HTTP_422_UNPROCESSABLE,
            title="Unprocessable Entity",
            detail="The request body or query parameters failed validation checks.",
            code="UNPROCESSABLE_ENTITY",
            errors=formatted_errors,
        )

    # Standard FastAPI HTTPException
    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        logger.info(
            "[%s] HTTP Exception %d: %s",
            _get_correlation_id(request),
            exc.status_code,
            exc.detail,
        )
        code = f"HTTP_{exc.status_code}"
        return _build_error_response(
            request=request,
            status_code=exc.status_code,
            title="HTTP Error",
            detail=str(exc.detail),
            code=code,
            headers=exc.headers,
        )

    # 409 Duplicate Execution Idempotency Violation
    @app.exception_handler(DuplicateExecutionError)
    async def duplicate_execution_handler(
        request: Request, exc: DuplicateExecutionError
    ) -> JSONResponse:
        logger.warning(
            "[%s] Duplicate execution attempt rejected: %s",
            _get_correlation_id(request),
            exc,
        )
        return _build_error_response(
            request=request,
            status_code=status.HTTP_409_CONFLICT,
            title="Duplicate Execution Rejected",
            detail=exc.message,
            code="DUPLICATE_IDEMPOTENCY_KEY",
        )

    # 422 Missing Connector Error
    @app.exception_handler(MissingConnectorError)
    async def missing_connector_handler(
        request: Request, exc: MissingConnectorError
    ) -> JSONResponse:
        logger.error(
            "[%s] Missing execution connector: %s",
            _get_correlation_id(request),
            exc,
        )
        return _build_error_response(
            request=request,
            status_code=HTTP_422_UNPROCESSABLE,
            title="Missing Execution Connector",
            detail=exc.message,
            code="MISSING_CONNECTOR",
        )

    # 422 Connector Not Configured Error
    @app.exception_handler(ConnectorNotConfiguredError)
    async def connector_not_configured_handler(
        request: Request, exc: ConnectorNotConfiguredError
    ) -> JSONResponse:
        logger.warning(
            "[%s] Execution connector not configured: %s",
            _get_correlation_id(request),
            exc,
        )
        return _build_error_response(
            request=request,
            status_code=HTTP_422_UNPROCESSABLE,
            title="Connector Not Configured",
            detail=exc.message,
            code="NOT_CONFIGURED",
        )

    # 422 Invalid Connector Configuration
    @app.exception_handler(InvalidConfigurationError)
    async def invalid_connector_config_handler(
        request: Request, exc: InvalidConfigurationError
    ) -> JSONResponse:
        logger.error(
            "[%s] Connector configuration invalid: %s",
            _get_correlation_id(request),
            exc,
        )
        return _build_error_response(
            request=request,
            status_code=HTTP_422_UNPROCESSABLE,
            title="Invalid Connector Configuration",
            detail=exc.message,
            code="INVALID_CONFIGURATION",
        )

    # 502 Generic Connector Error
    @app.exception_handler(ConnectorError)
    async def connector_generic_error_handler(
        request: Request, exc: ConnectorError
    ) -> JSONResponse:
        logger.error(
            "[%s] Connector error: %s",
            _get_correlation_id(request),
            exc,
        )
        return _build_error_response(
            request=request,
            status_code=status.HTTP_502_BAD_GATEWAY,
            title="Connector Execution Error",
            detail=exc.message,
            code=exc.code,
        )

    # Unhandled 500 Catch-all (Guarantees no secret keys or internal traces leak)
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        correlation_id = _get_correlation_id(request)
        logger.exception(
            "[%s] Unhandled internal server error during request processing",
            correlation_id,
        )
        return _build_error_response(
            request=request,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail="An unexpected internal server error occurred. Please contact support with the correlation ID.",
            code="INTERNAL_SERVER_ERROR",
        )
