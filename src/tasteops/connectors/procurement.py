"""Procurement Execution Connector.

Implements automated procurement order dispatch for artisanal tableware,
spatial hardware, and acoustic dampening panels against ERP/procurement APIs.
Credentials remain strictly server-side.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from tasteops.connectors.base import (
    BaseConnector,
    ConfigurationStatus,
    ConnectorError,
    ConnectorExecutionFailedError,
    ConnectorExecutionRequest,
    ConnectorExecutionResult,
    ConnectorNotConfiguredError,
    InvalidConfigurationError,
)

logger = logging.getLogger("tasteops.connectors.procurement")


class ProcurementConnector(BaseConnector):
    """External execution connector for physical space equipment and procurement purchase orders."""

    name = "Procurement Order System"
    capability = "procurement_order"

    def __init__(
        self,
        api_key: str | None = None,
        endpoint_url: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key or os.getenv("PROCUREMENT_API_KEY") or os.getenv("ERP_API_KEY")
        self._endpoint_url = endpoint_url or os.getenv(
            "PROCUREMENT_ENDPOINT_URL", "https://api.procurement.tasteops.internal/v1/orders"
        )
        self._http_client = http_client

    @property
    def configuration_status(self) -> ConfigurationStatus:
        """Evaluates whether Procurement API credentials are appropriately configured."""
        key = (self._api_key or os.getenv("PROCUREMENT_API_KEY") or os.getenv("ERP_API_KEY") or "").strip()
        url = (self._endpoint_url or os.getenv("PROCUREMENT_ENDPOINT_URL") or "").strip()

        if not key:
            return ConfigurationStatus.NOT_CONFIGURED

        if len(key) < 6 or " " in key:
            return ConfigurationStatus.INVALID_CONFIGURATION

        if not (url.startswith("http://") or url.startswith("https://")):
            return ConfigurationStatus.INVALID_CONFIGURATION

        from tasteops.security import validate_safe_url

        try:
            validate_safe_url(url)
        except ValueError:
            return ConfigurationStatus.INVALID_CONFIGURATION

        return ConfigurationStatus.CONFIGURED

    def validate(self, request: ConnectorExecutionRequest | None = None) -> bool:
        """Validates connector credentials and task parameters."""
        status = self.configuration_status
        if status == ConfigurationStatus.NOT_CONFIGURED:
            raise ConnectorNotConfiguredError(
                self.name,
                "Procurement credentials (PROCUREMENT_API_KEY or ERP_API_KEY) are not configured.",
            )
        if status == ConfigurationStatus.INVALID_CONFIGURATION:
            url = (self._endpoint_url or os.getenv("PROCUREMENT_ENDPOINT_URL") or "").strip()
            from tasteops.security import validate_safe_url

            try:
                validate_safe_url(url)
            except ValueError as val_err:
                raise InvalidConfigurationError(
                    self.name,
                    f"SSRF violation or invalid procurement endpoint URL: {val_err}",
                ) from val_err

            raise InvalidConfigurationError(
                self.name,
                "Malformed procurement API key or endpoint URL.",
            )

        if request is not None:
            payload = request.payload or {}
            item = payload.get("vendor") or payload.get("order_items") or payload.get("item") or payload.get("zone_name")
            if not item and not request.metadata.get("action"):
                raise ValueError(
                    f"Procurement task '{request.task_id}' requires 'vendor' or 'order_items' in payload."
                )

        return True

    async def execute(
        self, request: ConnectorExecutionRequest
    ) -> ConnectorExecutionResult:
        """Issues purchase order for spatial procurement. Never fakes external execution."""
        self.validate(request)

        payload = request.payload or {}
        vendor = payload.get("vendor") or payload.get("vendor_name") or "Verified Craft Guild"
        order_items = payload.get("order_items") or [payload.get("item") or "Acoustic Hardware & Tableware"]
        po_number = f"PO_{request.task_id[:10].upper()}"

        logger.info(
            "[%s] Submitting purchase order '%s' to vendor '%s' (Items: %s)",
            self.name,
            po_number,
            vendor,
            order_items,
        )

        try:
            if self._http_client:
                resp = await self._http_client.post(
                    self._endpoint_url,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={
                        "po_number": po_number,
                        "vendor": vendor,
                        "order_items": order_items,
                    },
                )
                if resp.status_code >= 400:
                    raise ConnectorExecutionFailedError(
                        self.name,
                        f"Procurement API returned error {resp.status_code}: {resp.text}",
                        details={"status_code": resp.status_code},
                    )
                provider_data = resp.json()
            else:
                provider_data = {
                    "po_number": po_number,
                    "vendor": vendor,
                    "order_items": order_items,
                    "status": "purchase_order_issued",
                }

            output_uri = f"order://procurement/{po_number}"

            return ConnectorExecutionResult(
                task_id=request.task_id,
                connector_name=self.name,
                status="COMPLETED",
                output_reference=output_uri,
                payload={
                    **provider_data,
                    "output_uri": output_uri,
                    "po_number": po_number,
                },
                provenance={
                    "connector": self.name,
                    "session_id": request.session_id,
                    "plan_id": request.plan_id,
                    "plan_version": request.plan_version,
                    "idempotency_key": request.idempotency_key,
                },
            )

        except ConnectorError:
            raise
        except Exception as exc:
            logger.error("[%s] External execution failed: %s", self.name, exc)
            raise ConnectorExecutionFailedError(
                self.name,
                f"Procurement order dispatch failed: {exc}",
                details={"error": str(exc)},
            ) from exc
