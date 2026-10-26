"""Email & Partnership Outreach Execution Connector.

Implements transactional email and brand collaboration brief dispatch
with server-side credential isolation and delivery validation.
"""

from __future__ import annotations

import logging
import os
import re

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

logger = logging.getLogger("tasteops.connectors.email")
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EmailConnector(BaseConnector):
    """External execution connector for brand collaboration briefs and curator mail dispatch."""

    name = "Transactional Email Engine"
    capability = "partner_outreach_brief"

    def __init__(
        self,
        api_key: str | None = None,
        from_email: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = (
            api_key or os.getenv("SENDGRID_API_KEY") or os.getenv("EMAIL_API_KEY")
        )
        self._from_email = from_email or os.getenv(
            "EMAIL_FROM_ADDRESS", "curator@tasteops.ai"
        )
        self._http_client = http_client

    @property
    def configuration_status(self) -> ConfigurationStatus:
        """Evaluates whether Email / Outreach API credentials are appropriately configured."""
        key = (
            self._api_key
            or os.getenv("SENDGRID_API_KEY")
            or os.getenv("EMAIL_API_KEY")
            or ""
        ).strip()
        from_addr = (
            self._from_email or os.getenv("EMAIL_FROM_ADDRESS") or "curator@tasteops.ai"
        ).strip()

        if not key:
            return ConfigurationStatus.NOT_CONFIGURED

        if len(key) < 8 or " " in key:
            return ConfigurationStatus.INVALID_CONFIGURATION

        if not EMAIL_REGEX.match(from_addr):
            return ConfigurationStatus.INVALID_CONFIGURATION

        return ConfigurationStatus.CONFIGURED

    def validate(self, request: ConnectorExecutionRequest | None = None) -> bool:
        """Validates connector credentials and task parameters."""
        status = self.configuration_status
        if status == ConfigurationStatus.NOT_CONFIGURED:
            raise ConnectorNotConfiguredError(
                self.name,
                "Email credentials (SENDGRID_API_KEY or EMAIL_API_KEY) are not configured.",
            )
        if status == ConfigurationStatus.INVALID_CONFIGURATION:
            raise InvalidConfigurationError(
                self.name,
                "Malformed email API key or sender address.",
            )

        if request is not None:
            payload = request.payload or {}
            partner = (
                payload.get("partner_name")
                or payload.get("recipient_email")
                or payload.get("partner_entity_id")
            )
            if not partner and not request.metadata.get("action"):
                raise ValueError(
                    f"Email execution task '{request.task_id}' requires 'partner_name' or 'recipient_email' in payload."
                )

        return True

    async def execute(
        self, request: ConnectorExecutionRequest
    ) -> ConnectorExecutionResult:
        """Dispatches collaboration outreach brief. Never fakes external execution."""
        self.validate(request)

        payload = request.payload or {}
        partner_name = (
            payload.get("partner_name")
            or payload.get("partner_entity_id")
            or "Target Brand Partner"
        )
        partner_id = (
            payload.get("partner_entity_id") or f"partner_{request.task_id[:8]}"
        )
        activation_type = payload.get("activation_type", "tactile_residency")

        logger.info(
            "[%s] Dispatching collaboration brief for partner '%s' (%s)",
            self.name,
            partner_name,
            activation_type,
        )

        try:
            client = self._http_client
            if client is None:
                raise ConnectorExecutionFailedError(
                    self.name,
                    "Missing HTTP client: Email connector cannot execute external integration without a configured HTTP transport. Real provider calls must be mocked in tests.",
                    details={"error_code": "MISSING_HTTP_CLIENT"},
                )

            timeout = httpx.Timeout(15.0, connect=5.0)
            headers = {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }

            recipient_email = (
                payload.get("recipient_email")
                or payload.get("email")
                or f"partnerships@{partner_name.lower().replace(' ', '')}.com"
            )
            subject = payload.get(
                "subject", f"TasteOps Cultural Residency Proposal: {partner_name}"
            )
            body_text = payload.get(
                "body",
                f"Formal partnership outreach brief for {partner_name} ({activation_type}). "
                "Curated by TasteOps Cultural Intelligence OS.",
            )

            # Official SendGrid v3 Mail Send payload schema
            sendgrid_payload = {
                "personalizations": [
                    {
                        "to": [{"email": recipient_email, "name": partner_name}],
                        "subject": subject,
                    }
                ],
                "from": {"email": self._from_email, "name": "TasteOps Curator"},
                "content": [{"type": "text/plain", "value": body_text}],
            }

            resp = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers=headers,
                json=sendgrid_payload,
                timeout=timeout,
            )
            if resp.status_code >= 400:
                raise ConnectorExecutionFailedError(
                    self.name,
                    f"Email provider returned error {resp.status_code}: {resp.text}",
                    details={"status_code": resp.status_code},
                )

            # SendGrid returns HTTP 202 Accepted for asynchronous queueing and MTA delivery.
            # Truthfulness Requirement: A 202 acceptance must NEVER be represented as confirmed delivery.
            message_id = (
                resp.headers.get("X-Message-Id")
                or (resp.json().get("message_id") if resp.content else None)
                or f"msg_{partner_id}"
            )

            provider_data = {
                "provider_status": "PROVIDER_ACCEPTED",
                "delivery_status": "ACCEPTED_FOR_DELIVERY",
                "is_confirmed_delivered": False,
                "status_code": resp.status_code,
                "message_id": message_id,
                "partner_id": partner_id,
                "partner_name": partner_name,
                "recipient_email": recipient_email,
            }

            output_uri = f"brief://partner/{partner_id}"

            return ConnectorExecutionResult(
                task_id=request.task_id,
                connector_name=self.name,
                status="COMPLETED",
                output_reference=output_uri,
                payload={
                    **provider_data,
                    "message_id": message_id,
                    "output_uri": output_uri,
                    "activation_type": activation_type,
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
                f"Email external dispatch failed: {exc}",
                details={"error": str(exc)},
            ) from exc
