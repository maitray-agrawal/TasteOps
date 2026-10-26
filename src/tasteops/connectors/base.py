"""Execution Connector Abstractions and Telemetry Models.

Defines the core interface, configuration lifecycle, execution requests,
typed results, and typed error hierarchy for downstream activation connectors.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from tasteops.workflows.schemas import ExecutionTask


class ConfigurationStatus(str, Enum):
    """Configuration lifecycle states for external execution connectors."""

    CONFIGURED = "CONFIGURED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"


class ConnectorExecutionRequest(BaseModel):
    """Enforces mandatory telemetry required for every external execution request.

    Every execution request must include:
    - session_id
    - plan_id
    - plan_version
    - task_id
    - idempotency_key
    """

    session_id: str = Field(
        ..., min_length=1, description="Active workflow session identifier"
    )
    plan_id: str = Field(
        ..., min_length=1, description="Parent activation plan identifier"
    )
    plan_version: int = Field(
        ..., ge=1, description="Plan revision number authorizing execution"
    )
    task_id: str = Field(
        ..., min_length=1, description="Unique execution task identifier"
    )
    idempotency_key: str = Field(
        ...,
        min_length=1,
        description="Unique key preventing duplicate external dispatch",
    )

    # Optional task payload & context
    task_type: str = Field(default="", description="Category/capability classification")
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Execution input parameters"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Telemetry provenance trace"
    )

    @classmethod
    def from_task(
        cls,
        task: ExecutionTask,
        session_id: str,
        plan_id: str,
        plan_version: int = 1,
        idempotency_key: str | None = None,
    ) -> ConnectorExecutionRequest:
        """Constructs a validated request directly from an existing ExecutionTask model."""
        resolved_key = (
            idempotency_key
            or getattr(task, "idempotency_key", None)
            or f"idem_{task.task_id}"
        )
        return cls(
            session_id=session_id,
            plan_id=plan_id,
            plan_version=plan_version,
            task_id=task.task_id,
            idempotency_key=resolved_key,
            task_type=getattr(task, "category", "") or getattr(task, "task_type", ""),
            payload=getattr(task, "input", {}) or {},
            metadata={
                "action": getattr(task, "action", ""),
                "owner": getattr(task, "owner", "GovernanceAgent"),
                "provenance": getattr(task, "provenance", {}),
            },
        )


class ConnectorExecutionResult(BaseModel):
    """Typed execution outcome emitted upon verified connector dispatch."""

    task_id: str = Field(..., description="Executed task identifier")
    connector_name: str = Field(..., description="Authoritative connector name")
    status: str = Field(default="COMPLETED", description="Execution status")
    output_reference: str = Field(
        ...,
        description="External resource reference URI (e.g. spotify://..., email://...)",
    )
    executed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp of verified external execution",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Detailed provider response payload"
    )
    provenance: dict[str, Any] = Field(
        default_factory=dict, description="Cryptographic provenance audit trace"
    )


class ConnectorExecutionErrorDetail(BaseModel):
    """Typed error envelope for connector configuration and runtime failures."""

    connector_name: str = Field(..., description="Target connector identifier")
    error_code: str = Field(..., description="Standardized error code")
    message: str = Field(..., description="Sanitized human-readable error description")
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Contextual diagnostic details without secrets",
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


# -----------------------------------------------------------------------------
# Typed Connector Exceptions Hierarchy
# -----------------------------------------------------------------------------


class ConnectorError(Exception):
    """Base exception for all connector operations."""

    def __init__(
        self,
        message: str,
        connector_name: str = "",
        code: str = "CONNECTOR_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.connector_name = connector_name
        self.code = code
        self.details = details or {}

    def to_detail(self) -> ConnectorExecutionErrorDetail:
        return ConnectorExecutionErrorDetail(
            connector_name=self.connector_name,
            error_code=self.code,
            message=self.message,
            details=self.details,
        )


class ConnectorNotConfiguredError(ConnectorError):
    """Raised when execution is attempted on an unconfigured connector."""

    def __init__(self, connector_name: str, message: str | None = None) -> None:
        msg = (
            message
            or f"Connector '{connector_name}' is NOT_CONFIGURED. "
            f"Server-side provider credentials must be configured prior to execution."
        )
        super().__init__(
            message=msg,
            connector_name=connector_name,
            code="NOT_CONFIGURED",
        )


class InvalidConfigurationError(ConnectorError):
    """Raised when connector credentials or settings fail validation."""

    def __init__(self, connector_name: str, message: str) -> None:
        super().__init__(
            message=f"Connector '{connector_name}' has INVALID_CONFIGURATION: {message}",
            connector_name=connector_name,
            code="INVALID_CONFIGURATION",
        )


class MissingConnectorError(ConnectorError):
    """Raised when a task requires a capability with no registered connector."""

    def __init__(self, capability: str) -> None:
        super().__init__(
            message=f"Missing execution connector: No connector registered for capability '{capability}'. "
            f"Execution fails explicitly.",
            connector_name=capability,
            code="MISSING_CONNECTOR",
        )


class DuplicateExecutionError(ConnectorError):
    """Raised when an execution request attempts duplicate dispatch with the same idempotency key."""

    def __init__(self, idempotency_key: str, task_id: str = "") -> None:
        super().__init__(
            message=f"Duplicate execution rejected: task '{task_id}' with idempotency key "
            f"'{idempotency_key}' was already executed.",
            connector_name="IdempotencyGuard",
            code="DUPLICATE_IDEMPOTENCY_KEY",
            details={"idempotency_key": idempotency_key, "task_id": task_id},
        )
        self.idempotency_key = idempotency_key
        self.task_id = task_id


class ConnectorExecutionFailedError(ConnectorError):
    """Raised when external provider call fails during execution."""

    def __init__(
        self,
        connector_name: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            connector_name=connector_name,
            code="EXECUTION_FAILED",
            details=details,
        )


# -----------------------------------------------------------------------------
# Base Connector Interface
# -----------------------------------------------------------------------------


class BaseConnector(ABC):
    """Abstract interface defining required contract for all TasteOps execution connectors.

    Each connector must provide:
    - name: human-readable connector title
    - capability: target execution capability/category
    - configuration_status: CONFIGURED, NOT_CONFIGURED, INVALID_CONFIGURATION
    - validate(): verifies credentials and payload syntax
    - execute(): dispatches external integration; NEVER fakes external execution
    - typed result: ConnectorExecutionResult
    - typed error: ConnectorError hierarchy
    """

    name: str
    capability: str

    @property
    @abstractmethod
    def configuration_status(self) -> ConfigurationStatus:
        """Returns the active configuration status of this connector."""

    @abstractmethod
    def validate(self, request: ConnectorExecutionRequest | None = None) -> bool:
        """Validates connector readiness and request parameters.

        Raises:
            ConnectorNotConfiguredError: If connector is not configured.
            InvalidConfigurationError: If connector settings are malformed.
            ValueError: If request payload is missing required fields.
        """

    @abstractmethod
    async def execute(
        self, request: ConnectorExecutionRequest
    ) -> ConnectorExecutionResult:
        """Executes the external integration task against the third-party provider.

        Must NEVER fake external execution. If connector is unconfigured,
        execution must fail explicitly.
        """
