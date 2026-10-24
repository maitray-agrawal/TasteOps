"""TasteOps Cultural Intelligence Exceptions.

Normalized exceptions for Qloo API and resolution errors.
"""

from typing import Any


class QlooException(Exception):
    """Base exception for all Qloo-related errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}

    def __str__(self) -> str:
        if self.status_code:
            return f"[{self.status_code}] {self.message}"
        return self.message


class QlooAuthenticationError(QlooException):
    """Raised when authentication fails (HTTP 401, 403).

    Never retried automatically.
    """


class QlooNotFoundError(QlooException):
    """Raised when an entity, tag, or endpoint is not found (HTTP 404)."""


class QlooRateLimitError(QlooException):
    """Raised when rate limits are exceeded (HTTP 429)."""

    def __init__(
        self,
        message: str,
        status_code: int | None = 429,
        retry_after: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code, details=details)
        self.retry_after = retry_after


class QlooTimeoutError(QlooException):
    """Raised when an HTTP request to Qloo times out."""


class QlooServerError(QlooException):
    """Raised when Qloo returns a 5xx server error."""


class QlooValidationError(QlooException):
    """Raised when input parameters or Qloo response payloads fail validation / are malformed."""
