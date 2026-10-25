"""Connector Registry and Execution Dispatcher.

Coordinates connector lifecycle, task routing, idempotency enforcement,
and explicit failure for missing or unconfigured connectors.
Provider credentials remain strictly isolated on the server.
"""

from __future__ import annotations

import logging
from typing import Any

from tasteops.connectors.base import (
    BaseConnector,
    ConnectorExecutionRequest,
    ConnectorExecutionResult,
    DuplicateExecutionError,
    MissingConnectorError,
)
from tasteops.connectors.email import EmailConnector
from tasteops.connectors.procurement import ProcurementConnector
from tasteops.connectors.spotify import SpotifyConnector
from tasteops.workflows.schemas import ExecutionTask

logger = logging.getLogger("tasteops.connectors.registry")


class ConnectorRegistry:
    """Central registry and dispatcher for TasteOps activation connectors.

    Enforces:
    1. Explicit missing connector failure (no silent defaults).
    2. Rejection of duplicate execution attempts for identical idempotency keys.
    3. Mandatory presence of all 5 request telemetry fields (session_id, plan_id,
       plan_version, task_id, idempotency_key).
    4. Server-side credential isolation.
    """

    def __init__(self) -> None:
        # Maps capability/category string -> BaseConnector instance
        self._connectors: dict[str, BaseConnector] = {}
        # Tracks executed idempotency keys: idempotency_key -> ConnectorExecutionResult
        self._executed_store: dict[str, ConnectorExecutionResult] = {}

    def register(
        self, connector: BaseConnector, alias_capabilities: list[str] | None = None
    ) -> None:
        """Registers a connector under its primary capability and optional aliases."""
        self._connectors[connector.capability] = connector
        self._connectors[connector.name] = connector
        if alias_capabilities:
            for alias in alias_capabilities:
                self._connectors[alias] = connector
        logger.info(
            "Registered connector '%s' for capability '%s'",
            connector.name,
            connector.capability,
        )

    def get_connector(self, capability_or_name: str) -> BaseConnector | None:
        """Looks up a connector by capability or name."""
        return self._connectors.get(capability_or_name)

    def list_connectors(self) -> list[dict[str, Any]]:
        """Returns safe telemetry summaries of all registered connectors without credentials."""
        seen = set()
        summaries = []
        for conn in self._connectors.values():
            if conn.name in seen:
                continue
            seen.add(conn.name)
            summaries.append(
                {
                    "name": conn.name,
                    "capability": conn.capability,
                    "configuration_status": conn.configuration_status.value,
                }
            )
        return summaries

    def is_executed(self, idempotency_key: str) -> bool:
        """Returns True if the idempotency key was already executed."""
        return idempotency_key in self._executed_store

    def get_execution_result(
        self, idempotency_key: str
    ) -> ConnectorExecutionResult | None:
        """Retrieves prior execution result for an idempotency key."""
        return self._executed_store.get(idempotency_key)

    async def dispatch(
        self, request: ConnectorExecutionRequest
    ) -> ConnectorExecutionResult:
        """Dispatches an execution request to the appropriate registered connector.

        Guarantees:
        - Validates all 5 mandatory request telemetry fields.
        - Rejects duplicate execution attempts for the same idempotency key.
        - Fails explicitly if no connector is registered for the task capability.
        - Dispatches without simulating external execution.
        """
        # 1. Validate mandatory telemetry
        if not request.session_id or not request.session_id.strip():
            raise ValueError("Execution request must include non-empty 'session_id'.")
        if not request.plan_id or not request.plan_id.strip():
            raise ValueError("Execution request must include non-empty 'plan_id'.")
        if not request.plan_version or request.plan_version < 1:
            raise ValueError(
                "Execution request must include valid 'plan_version' >= 1."
            )
        if not request.task_id or not request.task_id.strip():
            raise ValueError("Execution request must include non-empty 'task_id'.")
        if not request.idempotency_key or not request.idempotency_key.strip():
            raise ValueError(
                "Execution request must include non-empty 'idempotency_key'."
            )

        # 2. Reject duplicate execution attempts for the same idempotency key
        if request.idempotency_key in self._executed_store:
            logger.warning(
                "Duplicate execution attempt rejected for idempotency key '%s' (Task ID: %s)",
                request.idempotency_key,
                request.task_id,
            )
            raise DuplicateExecutionError(
                idempotency_key=request.idempotency_key,
                task_id=request.task_id,
            )

        # 3. Missing connector check: Fail explicitly if no connector registered
        target_capability = request.task_type or request.metadata.get("category", "")
        connector = self.get_connector(target_capability)

        if connector is None:
            logger.error(
                "No connector registered for capability '%s'. Failing explicitly.",
                target_capability,
            )
            raise MissingConnectorError(target_capability or request.task_id)

        # 4. Connector validation & execution
        connector.validate(request)
        result = await connector.execute(request)

        # 5. Record executed idempotency key
        self._executed_store[request.idempotency_key] = result
        return result

    def record_execution(
        self, idempotency_key: str, result: ConnectorExecutionResult
    ) -> None:
        """Records an external execution result in registry idempotency store (used for hydration)."""
        self._executed_store[idempotency_key] = result

    async def dispatch_task(
        self,
        task: ExecutionTask,
        session_id: str,
        plan_id: str,
        plan_version: int = 1,
    ) -> ConnectorExecutionResult:
        """Convenience method to construct request and dispatch from an ExecutionTask."""
        request = ConnectorExecutionRequest.from_task(
            task=task,
            session_id=session_id,
            plan_id=plan_id,
            plan_version=plan_version,
        )
        return await self.dispatch(request)


def create_default_registry() -> ConnectorRegistry:
    """Constructs a ConnectorRegistry pre-populated with standard TasteOps connectors."""
    registry = ConnectorRegistry()

    # 1. Spotify Audio Seeding Connector
    spotify = SpotifyConnector()
    registry.register(
        spotify, alias_capabilities=["spotify", "sonic_identity", "audio_seeding"]
    )

    # 2. Email & Partnership Outreach Connector
    email = EmailConnector()
    registry.register(
        email, alias_capabilities=["email", "partner_outreach", "outreach_brief"]
    )

    # 3. Procurement & Equipment Connector
    procurement = ProcurementConnector()
    registry.register(
        procurement,
        alias_capabilities=["procurement", "spatial_design_spec", "materials_order"],
    )

    return registry


def create_configured_mock_registry(
    http_client: Any | None = None,
) -> ConnectorRegistry:
    """Constructs a ConnectorRegistry pre-configured with mock provider credentials for test/dev."""
    registry = ConnectorRegistry()

    spotify = SpotifyConnector(
        client_id="mock_spotify_client_id_test",
        client_secret="mock_spotify_client_secret_test",
        http_client=http_client,
    )
    registry.register(
        spotify, alias_capabilities=["spotify", "sonic_identity", "audio_seeding"]
    )

    email = EmailConnector(
        api_key="mock_sendgrid_key_test_12345",
        from_email="curator@tasteops.ai",
        http_client=http_client,
    )
    registry.register(
        email, alias_capabilities=["email", "partner_outreach", "outreach_brief"]
    )

    procurement = ProcurementConnector(
        api_key="mock_procurement_key_test_12345",
        endpoint_url="https://api.procurement.tasteops.internal/v1/orders",
        http_client=http_client,
    )
    registry.register(
        procurement,
        alias_capabilities=["procurement", "spatial_design_spec", "materials_order"],
    )

    return registry
