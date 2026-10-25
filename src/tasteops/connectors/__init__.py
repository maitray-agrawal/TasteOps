"""TasteOps External Execution Connectors.

Provides pluggable connector abstractions around the ExecutionTask model
with strict server-side credential isolation, configuration validation,
idempotency enforcement, and zero simulated external execution.
"""

from __future__ import annotations

from tasteops.connectors.base import (
    BaseConnector,
    ConfigurationStatus,
    ConnectorError,
    ConnectorExecutionErrorDetail,
    ConnectorExecutionFailedError,
    ConnectorExecutionRequest,
    ConnectorExecutionResult,
    ConnectorNotConfiguredError,
    DuplicateExecutionError,
    InvalidConfigurationError,
    MissingConnectorError,
)
from tasteops.connectors.email import EmailConnector
from tasteops.connectors.procurement import ProcurementConnector
from tasteops.connectors.registry import (
    ConnectorRegistry,
    create_configured_mock_registry,
    create_default_registry,
)
from tasteops.connectors.spotify import SpotifyConnector

__all__ = [
    "BaseConnector",
    "ConfigurationStatus",
    "ConnectorError",
    "ConnectorExecutionErrorDetail",
    "ConnectorExecutionFailedError",
    "ConnectorExecutionRequest",
    "ConnectorExecutionResult",
    "ConnectorNotConfiguredError",
    "ConnectorRegistry",
    "DuplicateExecutionError",
    "EmailConnector",
    "InvalidConfigurationError",
    "MissingConnectorError",
    "ProcurementConnector",
    "SpotifyConnector",
    "create_configured_mock_registry",
    "create_default_registry",
]
