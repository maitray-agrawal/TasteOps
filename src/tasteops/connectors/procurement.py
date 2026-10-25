"""Procurement Execution Connector.

Implements automated procurement order dispatch for artisanal tableware,
spatial hardware, and acoustic dampening panels against ERP/procurement APIs.
Credentials remain strictly server-side.
"""

from __future__ import annotations

import logging
import os

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
        allowed_hosts: list[str] | set[str] | None = None,
        allow_private: bool | None = None,
    ) -> None:
        self._api_key = (
            api_key or os.getenv("PROCUREMENT_API_KEY") or os.getenv("ERP_API_KEY")
        )
        self._endpoint_url = endpoint_url or os.getenv(
            "PROCUREMENT_ENDPOINT_URL",
            "https://api.procurement.tasteops.internal/v1/orders",
        )
        self._http_client = http_client

        # Host allowlist: explicit list, or parsed from PROCUREMENT_ALLOWED_HOSTS env var
        env_allowed = os.getenv("PROCUREMENT_ALLOWED_HOSTS")
        if allowed_hosts is not None:
            self._allowed_hosts: set[str] | None = {
                h.strip().lower() for h in allowed_hosts if h.strip()
            }
        elif env_allowed:
            self._allowed_hosts = {
                h.strip().lower() for h in env_allowed.split(",") if h.strip()
            }
        else:
            self._allowed_hosts = None

        if allow_private is not None:
            self._allow_private = allow_private
        elif os.getenv("PROCUREMENT_ALLOW_PRIVATE") is not None:
            self._allow_private = os.getenv(
                "PROCUREMENT_ALLOW_PRIVATE", ""
            ).lower() in ("true", "1")
        else:
            # Default to True for enterprise internal ERP endpoints (.internal / .local / private enterprise network)
            self._allow_private = True

    @property
    def configuration_status(self) -> ConfigurationStatus:
        """Evaluates whether Procurement API credentials are appropriately configured."""
        key = (
            self._api_key
            or os.getenv("PROCUREMENT_API_KEY")
            or os.getenv("ERP_API_KEY")
            or ""
        ).strip()
        url = (
            self._endpoint_url or os.getenv("PROCUREMENT_ENDPOINT_URL") or ""
        ).strip()

        if not key:
            return ConfigurationStatus.NOT_CONFIGURED

        if len(key) < 6 or " " in key:
            return ConfigurationStatus.INVALID_CONFIGURATION

        if not url.startswith(("http://", "https://")):
            return ConfigurationStatus.INVALID_CONFIGURATION

        from tasteops.security import validate_safe_url

        try:
            # Validate URL with host allowlist and network policy
            validate_safe_url(
                url,
                allow_private=self._allow_private,
                allowed_hosts=self._allowed_hosts,
            )
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
            url = (
                self._endpoint_url or os.getenv("PROCUREMENT_ENDPOINT_URL") or ""
            ).strip()
            from tasteops.security import validate_safe_url

            try:
                validate_safe_url(
                    url,
                    allow_private=self._allow_private,
                    allowed_hosts=self._allowed_hosts,
                )
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
            item = (
                payload.get("vendor")
                or payload.get("order_items")
                or payload.get("item")
                or payload.get("zone_name")
            )
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
        vendor = (
            payload.get("vendor")
            or payload.get("vendor_name")
            or "Verified Craft Guild"
        )
        order_items = payload.get("order_items") or [
            payload.get("item") or "Acoustic Hardware & Tableware"
        ]
        po_number = f"PO_{request.task_id[:10].upper()}"

        logger.info(
            "[%s] Submitting purchase order '%s' to vendor '%s' (Items: %s)",
            self.name,
            po_number,
            vendor,
            order_items,
        )

        try:
            client = self._http_client
            if client is None:
                raise ConnectorExecutionFailedError(
                    self.name,
                    "Missing HTTP client: Procurement connector cannot execute external integration without a configured HTTP transport. Real provider calls must be mocked in tests.",
                    details={"error_code": "MISSING_HTTP_CLIENT"},
                )

            if not self._endpoint_url:
                raise InvalidConfigurationError(self.name, "Missing endpoint_url")

            from tasteops.security import validate_safe_redirect, validate_safe_url

            # Validate endpoint before dispatch
            validate_safe_url(
                self._endpoint_url,
                allow_private=self._allow_private,
                allowed_hosts=self._allowed_hosts,
            )

            timeout = httpx.Timeout(15.0, connect=5.0)
            headers = {
                "Authorization": f"Bearer {self._api_key}",
                "Idempotency-Key": request.idempotency_key,
                "Content-Type": "application/json",
            }
            resp = await client.post(
                self._endpoint_url,
                headers=headers,
                json={
                    "po_number": po_number,
                    "vendor": vendor,
                    "order_items": order_items,
                    "idempotency_key": request.idempotency_key,
                    "session_id": request.session_id,
                },
                timeout=timeout,
            )

            # Connection-level redirect validation: prevent open redirect SSRF attacks
            if resp.is_redirect or resp.status_code in (301, 302, 303, 307, 308):
                redirect_loc = resp.headers.get("Location")
                if redirect_loc:
                    try:
                        validate_safe_redirect(
                            redirect_loc,
                            self._endpoint_url,
                            allow_private=self._allow_private,
                            allowed_hosts=self._allowed_hosts,
                        )
                    except ValueError as redir_err:
                        raise ConnectorExecutionFailedError(
                            self.name,
                            f"SSRF violation: Redirect to prohibited destination blocked: {redir_err}",
                            details={
                                "redirect_url": redirect_loc,
                                "ssrf_violation": True,
                            },
                        ) from redir_err

            if resp.status_code >= 400:
                raise ConnectorExecutionFailedError(
                    self.name,
                    f"Procurement API returned error {resp.status_code}: {resp.text}",
                    details={"status_code": resp.status_code},
                )

            if resp.status_code not in (200, 201, 202):
                raise ConnectorExecutionFailedError(
                    self.name,
                    f"Procurement remote service returned unconfirmed status {resp.status_code}. Order not confirmed.",
                    details={"status_code": resp.status_code},
                )

            provider_data = (
                resp.json()
                if resp.content
                else {"order_id": po_number, "status": "CONFIRMED"}
            )

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
                    "vendor": vendor,
                    "order_items": order_items,
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
