"""Compliance tests verifying adherence to the official Qloo Hackathon Developer Guide.

Verifies:
1. Banned Endpoints:
   - The codebase never constructs or calls `/recs` or `/recommendations`.
   - `QlooClient` strictly guards against calling `/recs` or `/recommendations`.
   - All recommendation and affinity queries strictly route through `/v2/insights`.
2. Parameter Validity:
   - `InsightsService` strictly applies spatial parameters (`filter.location`, `radius`)
     only to `place` and `destination` entities.
   - Spatial parameters are never passed to `artist`, `book`, or `brand` queries.
3. Base URL Compliance:
   - System configuration strictly defaults to `https://hackathon.api.qloo.com`.
   - FastMCP Server reports `https://hackathon.api.qloo.com`.
"""

from pathlib import Path

import pytest
import respx

from tasteops.client import QlooClient
from tasteops.config import QlooSettings
from tasteops.exceptions import QlooValidationError
from tasteops.mcp.server import create_cultural_intelligence_mcp
from tasteops.models.params import InsightParams
from tasteops.services.insights_service import CATEGORY_CAPABILITIES, InsightsService


class TestBannedEndpointsCompliance:
    """Verifies that /recs and /recommendations are never called or constructed."""

    @pytest.mark.asyncio
    async def test_client_actively_blocks_recs_endpoint(self, mock_settings):
        """QlooClient._execute_get actively rejects /recs with QlooValidationError."""
        client = QlooClient(settings=mock_settings)
        with pytest.raises(QlooValidationError) as exc:
            await client._execute_get("/recs")
        assert "is banned by the Qloo Hackathon Developer Guide" in str(exc.value)
        assert "/v2/insights" in str(exc.value)

    @pytest.mark.asyncio
    async def test_client_actively_blocks_recommendations_endpoint(self, mock_settings):
        """QlooClient._execute_get actively rejects /recommendations with QlooValidationError."""
        client = QlooClient(settings=mock_settings)
        with pytest.raises(QlooValidationError) as exc:
            await client._execute_get("/recommendations")
        assert "is banned by the Qloo Hackathon Developer Guide" in str(exc.value)
        assert "/v2/insights" in str(exc.value)

    @pytest.mark.asyncio
    async def test_client_actively_blocks_subpaths_of_banned_endpoints(
        self, mock_settings
    ):
        """QlooClient._execute_get actively rejects /recs/artist or /recommendations/places."""
        client = QlooClient(settings=mock_settings)
        with pytest.raises(QlooValidationError):
            await client._execute_get("/recs/artist")
        with pytest.raises(QlooValidationError):
            await client._execute_get("/recommendations/places")

    @pytest.mark.asyncio
    async def test_insights_queries_route_exclusively_to_v2_insights(
        self, mock_settings
    ):
        """Calling get_insights dispatches to /v2/insights, never to /recs."""
        async with respx.mock(
            base_url="https://hackathon.api.qloo.com", assert_all_called=True
        ) as mock_router:
            mock_route = mock_router.get("/v2/insights").respond(
                status_code=200, json={"results": []}
            )

            client = QlooClient(settings=mock_settings)
            params = InsightParams(
                filter_type="urn:entity:artist",
                signal_entities=["ent_floating_points"],
            )
            await client.get_insights(params)

            assert mock_route.called
            assert mock_route.call_count == 1
            request_url = str(mock_route.calls[0].request.url)
            assert "/v2/insights" in request_url
            assert "/recs" not in request_url
            assert "/recommendations" not in request_url

    def test_static_code_audit_for_banned_endpoints(self):
        """Scans all Python source files in tasteops to ensure no call to /recs or /recommendations exists."""
        src_dir = Path(__file__).resolve().parent.parent.parent / "src" / "tasteops"
        assert src_dir.exists(), f"Source directory {src_dir} not found"

        violations = []
        for py_file in src_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            for line_no, line in enumerate(content.splitlines(), start=1):
                clean = line.strip()
                # Skip comments, docstrings, and client guard code checking for banned endpoints
                if (
                    clean.startswith("#")
                    or "banned" in clean.lower()
                    or "never" in clean.lower()
                    or "clean_path" in clean
                    or '{"/recs"' in clean
                    or '("/recs/"' in clean
                ):
                    continue
                if (
                    '"/recs' in clean
                    or "'/recs" in clean
                    or '"/recommendations' in clean
                    or "'/recommendations" in clean
                ):
                    violations.append(f"{py_file.name}:{line_no}: {clean}")

        assert not violations, (
            f"Banned endpoint references found in source code: {violations}"
        )


class TestParameterValidityCompliance:
    """Verifies that spatial parameters are strictly applied only to place and destination."""

    def test_category_capabilities_registry(self):
        """Audit the registry to verify spatial capability flags."""
        # Spatial categories
        assert CATEGORY_CAPABILITIES["place"].supports_spatial_location is True
        assert CATEGORY_CAPABILITIES["destination"].supports_spatial_location is True

        # Non-spatial categories MUST be False
        assert CATEGORY_CAPABILITIES["artist"].supports_spatial_location is False
        assert CATEGORY_CAPABILITIES["book"].supports_spatial_location is False
        assert CATEGORY_CAPABILITIES["brand"].supports_spatial_location is False
        assert CATEGORY_CAPABILITIES["movie"].supports_spatial_location is False

    def test_spatial_parameters_applied_to_places_and_destinations(self, mock_settings):
        """Spatial parameters (filter.location, filter.location.radius) are included for place and destination."""
        client = QlooClient(settings=mock_settings)
        service = InsightsService(client)

        wkt = "POINT(-73.9857 40.7484)"
        radius = 2500

        # Place
        place_params = service.build_insight_params(
            category="place",
            anchor_entities=["ent_coffee_01"],
            resolved_tags=["tag_cafe"],
            location_wkt=wkt,
            location_radius=radius,
        )
        place_query = place_params.to_query_params()
        assert place_query["filter.location"] == wkt
        assert place_query["filter.location.radius"] == "2500"
        assert place_query["filter.type"] == "urn:entity:place"

        # Destination
        dest_params = service.build_insight_params(
            category="destination",
            anchor_entities=["ent_hotel_01"],
            resolved_tags=["tag_resort"],
            location_wkt=wkt,
            location_radius=radius,
        )
        dest_query = dest_params.to_query_params()
        assert dest_query["filter.location"] == wkt
        assert dest_query["filter.location.radius"] == "2500"
        assert dest_query["filter.type"] == "urn:entity:destination"

    def test_spatial_parameters_strictly_omitted_for_non_spatial_categories(
        self, mock_settings
    ):
        """Spatial parameters are NEVER passed to artist, book, brand, or movie queries."""
        client = QlooClient(settings=mock_settings)
        service = InsightsService(client)

        wkt = "POINT(-73.9857 40.7484)"
        radius = 2500

        non_spatial_categories = ["artist", "book", "brand", "movie"]

        for category in non_spatial_categories:
            params = service.build_insight_params(
                category=category,
                anchor_entities=["ent_anchor_01"],
                resolved_tags=["tag_aesthetic_01"],
                location_wkt=wkt,
                location_radius=radius,
            )
            query_params = params.to_query_params()

            # Confirm filter.location and filter.location.radius are strictly absent
            assert "filter.location" not in query_params, (
                f"filter.location illegally present in {category} query"
            )
            assert "filter.location.radius" not in query_params, (
                f"filter.location.radius illegally present in {category} query"
            )

            # Confirm non-spatial parameters are intact
            assert query_params["filter.type"] == f"urn:entity:{category}"
            assert "signal.interests.entities" in query_params
            assert "signal.interests.tags" in query_params


class TestBaseUrlCompliance:
    """Verifies that the system strictly points to https://hackathon.api.qloo.com."""

    def test_config_settings_default_base_url(self):
        """QlooSettings default base_url must strictly be https://hackathon.api.qloo.com."""
        settings = QlooSettings(QLOO_API_KEY="mock_key")
        assert settings.base_url == "https://hackathon.api.qloo.com"

    def test_qloo_client_default_base_url(self, mock_settings):
        """QlooClient without explicit base_url defaults strictly to https://hackathon.api.qloo.com."""
        client = QlooClient(settings=mock_settings)
        assert client.base_url == "https://hackathon.api.qloo.com"

    @pytest.mark.asyncio
    async def test_mcp_server_reports_hackathon_base_url(self, mock_settings):
        """FastMCP health_check tool reports https://hackathon.api.qloo.com."""
        client = QlooClient(settings=mock_settings)
        server = create_cultural_intelligence_mcp(client)

        call_res = await server.call_tool("health_check", {})
        assert call_res.is_error is False
        assert call_res.structured_content is not None
        assert (
            call_res.structured_content["base_url"] == "https://hackathon.api.qloo.com"
        )
        assert call_res.structured_content["status"] == "healthy"

    def test_env_example_specifies_hackathon_url(self):
        """.env.example specifies QLOO_BASE_URL=https://hackathon.api.qloo.com."""
        env_example_path = (
            Path(__file__).resolve().parent.parent.parent / ".env.example"
        )
        assert env_example_path.exists(), ".env.example file not found"
        content = env_example_path.read_text(encoding="utf-8")
        assert "QLOO_BASE_URL=https://hackathon.api.qloo.com" in content
