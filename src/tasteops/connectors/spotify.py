"""Spotify Execution Connector.

Implements Spotify Web API integration for audio seeding, daypart sonic
calibration, and playlist generation based on Qloo cultural affinity matrices.
Credentials remain strictly server-side.
"""

from __future__ import annotations

import logging
import os
from typing import ClassVar

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

logger = logging.getLogger("tasteops.connectors.spotify")


class SpotifyConnector(BaseConnector):
    """External execution connector for Spotify audio curation and playlist seeding.

    Uses current Spotify Web API endpoints:
    - POST /v1/me/playlists: Creates playlist container for current user.
    - POST /v1/playlists/{playlist_id}/items: Adds audio items/tracks to playlist.
    - Obsolete /tracks endpoint is strictly prohibited.
    Required OAuth Scopes: playlist-modify-public, playlist-modify-private.
    """

    name = "Spotify Web API"
    capability = "spotify_audio_seed"
    required_scopes: ClassVar[list[str]] = [
        "playlist-modify-public",
        "playlist-modify-private",
    ]

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        access_token: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        # Provider credentials remain server-side
        self._client_id = client_id or os.getenv("SPOTIFY_CLIENT_ID")
        self._client_secret = client_secret or os.getenv("SPOTIFY_CLIENT_SECRET")
        self._access_token = access_token or os.getenv("SPOTIFY_ACCESS_TOKEN")
        self._http_client = http_client

    @property
    def configuration_status(self) -> ConfigurationStatus:
        """Evaluates whether Spotify API credentials are appropriately configured."""
        cid = (self._client_id or os.getenv("SPOTIFY_CLIENT_ID") or "").strip()
        sec = (self._client_secret or os.getenv("SPOTIFY_CLIENT_SECRET") or "").strip()
        tok = (self._access_token or os.getenv("SPOTIFY_ACCESS_TOKEN") or "").strip()

        if not cid and not sec and not tok:
            return ConfigurationStatus.NOT_CONFIGURED

        # Either valid access token OR valid client_id + client_secret pair
        if tok:
            if len(tok) < 6 or " " in tok:
                return ConfigurationStatus.INVALID_CONFIGURATION
            return ConfigurationStatus.CONFIGURED

        if not cid or not sec:
            return ConfigurationStatus.INVALID_CONFIGURATION

        if len(cid) < 6 or len(sec) < 6 or " " in cid or " " in sec:
            return ConfigurationStatus.INVALID_CONFIGURATION

        return ConfigurationStatus.CONFIGURED

    def validate(self, request: ConnectorExecutionRequest | None = None) -> bool:
        """Validates connector credentials and task parameters."""
        status = self.configuration_status
        if status == ConfigurationStatus.NOT_CONFIGURED:
            raise ConnectorNotConfiguredError(
                self.name,
                "Spotify credentials (SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET or SPOTIFY_ACCESS_TOKEN) are not configured.",
            )
        if status == ConfigurationStatus.INVALID_CONFIGURATION:
            raise InvalidConfigurationError(
                self.name,
                "Incomplete or malformed Spotify credentials.",
            )

        if request is not None:
            payload = request.payload or {}
            artist = (
                payload.get("artist_name")
                or payload.get("artist_id")
                or payload.get("lead_artist")
                or payload.get("playlist_id")
            )
            if not artist and not request.metadata.get("action"):
                raise ValueError(
                    f"Spotify execution task '{request.task_id}' requires 'artist_name', 'artist_id' or 'playlist_id' in payload."
                )

        return True

    async def execute(
        self, request: ConnectorExecutionRequest
    ) -> ConnectorExecutionResult:
        """Executes Spotify playlist creation and item seeding. Never fakes external execution."""
        # Enforce validation and zero-fake execution
        self.validate(request)

        payload = request.payload or {}
        artist_name = (
            payload.get("artist_name")
            or payload.get("lead_artist")
            or payload.get("artist_id")
            or "Verified Ground Truth Artist"
        )
        daypart = payload.get("daypart", "evening")
        playlist_name = payload.get(
            "playlist_name", f"TasteOps Curated — {artist_name} ({daypart.title()})"
        )
        description = payload.get(
            "description",
            f"Curated by TasteOps Cultural Intelligence OS for seed artist {artist_name}.",
        )

        # Track URIs if provided
        track_uris: list[str] = (
            payload.get("track_uris")
            or payload.get("item_uris")
            or payload.get("uris")
            or []
        )

        logger.info(
            "[%s] Dispatching playlist task '%s' for '%s' (Daypart: %s, Tracks: %d)",
            self.name,
            request.task_id,
            artist_name,
            daypart,
            len(track_uris),
        )

        try:
            client = self._http_client
            if client is None:
                raise ConnectorExecutionFailedError(
                    self.name,
                    "Missing HTTP client: Spotify connector cannot execute external integration without a configured HTTP transport. Real provider calls must be mocked in tests.",
                    details={"error_code": "MISSING_HTTP_CLIENT"},
                )

            token = self._access_token or self._client_secret
            timeout = httpx.Timeout(15.0, connect=5.0)
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            playlist_id = payload.get("playlist_id")
            playlist_uri = payload.get("playlist_uri")
            snapshot_id = None

            # 1. Create Playlist via POST /me/playlists if not already existing
            if not playlist_id:
                create_resp = await client.post(
                    "https://api.spotify.com/v1/me/playlists",
                    headers=headers,
                    json={
                        "name": playlist_name,
                        "description": description,
                        "public": False,
                    },
                    timeout=timeout,
                )
                if create_resp.status_code >= 400:
                    raise ConnectorExecutionFailedError(
                        self.name,
                        f"Spotify POST /me/playlists returned error {create_resp.status_code}: {create_resp.text}",
                        details={
                            "status_code": create_resp.status_code,
                            "required_scopes": self.required_scopes,
                        },
                    )
                create_data = create_resp.json()
                playlist_id = create_data.get("id")
                playlist_uri = (
                    create_data.get("uri") or f"spotify:playlist:{playlist_id}"
                )

            # 2. Add Playlist Items via POST /playlists/{playlist_id}/items if tracks are specified
            if track_uris and playlist_id:
                # Strictly enforce modern /items endpoint, never /tracks
                items_url = f"https://api.spotify.com/v1/playlists/{playlist_id}/items"
                items_resp = await client.post(
                    items_url,
                    headers=headers,
                    json={"uris": track_uris},
                    timeout=timeout,
                )
                if items_resp.status_code >= 400:
                    raise ConnectorExecutionFailedError(
                        self.name,
                        f"Spotify POST /playlists/{{id}}/items returned error {items_resp.status_code}: {items_resp.text}",
                        details={
                            "status_code": items_resp.status_code,
                            "playlist_id": playlist_id,
                        },
                    )
                items_data = items_resp.json()
                snapshot_id = items_data.get("snapshot_id")

            output_uri = playlist_uri or f"spotify:playlist:{playlist_id}"

            return ConnectorExecutionResult(
                task_id=request.task_id,
                connector_name=self.name,
                status="COMPLETED",
                output_reference=output_uri,
                payload={
                    "playlist_id": playlist_id,
                    "playlist_uri": output_uri,
                    "snapshot_id": snapshot_id,
                    "artist_name": artist_name,
                    "daypart": daypart,
                    "item_count": len(track_uris),
                    "output_uri": output_uri,
                    "affinity_source": "qloo_cultural_matrix",
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
                f"Spotify external execution failed: {exc}",
                details={"error": str(exc)},
            ) from exc
