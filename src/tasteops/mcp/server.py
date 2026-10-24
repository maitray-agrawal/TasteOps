"""TasteOps Cultural Intelligence MCP Server.

Exposes high-level cultural intelligence tools for AI agent orchestration:
- resolve_entity
- resolve_tag
- get_cultural_profile
- get_related_artists
- get_related_books
- get_related_brands
- get_related_places
- get_related_movies
- get_cultural_matrix
- health_check

Features:
- Structured logging with unique request IDs (UUID4)
- High-level intelligence abstractions (never exposes raw Qloo HTTP requests)
- Strict validation and graceful error formatting
"""

import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from mcp.server.mcpserver import MCPServer

from tasteops.client import QlooClient
from tasteops.models.cultural_matrix import CulturalTwin, LocationInput
from tasteops.services.cultural_matrix_service import CulturalMatrixService
from tasteops.services.entity_resolver import EntityResolver
from tasteops.services.insights_service import InsightsService
from tasteops.services.tag_resolver import TagResolver

logger = logging.getLogger("tasteops.mcp")


def create_cultural_intelligence_mcp(client: QlooClient | None = None) -> MCPServer:
    """Factory creating and configuring the TasteOps Cultural Intelligence MCPServer."""
    qloo_client = client or QlooClient()
    entity_resolver = EntityResolver(qloo_client)
    tag_resolver = TagResolver(qloo_client)
    insights_service = InsightsService(qloo_client)
    matrix_service = CulturalMatrixService(qloo_client, insights_service)

    server = MCPServer(name="tasteops-cultural-intelligence")

    # -------------------------------------------------------------------------
    # Health Check Tool
    # -------------------------------------------------------------------------
    @server.tool(
        name="health_check",
        description="Performs health diagnostics on the Cultural Intelligence MCP server and configuration.",
    )
    async def health_check() -> dict[str, Any]:
        """Returns health diagnostics, base URL, and server status."""
        request_id = str(uuid.uuid4())
        start_time = time.perf_counter()
        logger.info("[Req: %s] Executing health_check", request_id)

        latency_ms = (time.perf_counter() - start_time) * 1000
        return {
            "request_id": request_id,
            "status": "healthy",
            "server": "tasteops-cultural-intelligence",
            "version": "1.0.0",
            "base_url": qloo_client.base_url,
            "timestamp": datetime.now(UTC).isoformat(),
            "latency_ms": round(latency_ms, 2),
        }

    # -------------------------------------------------------------------------
    # Entity Resolution Tool
    # -------------------------------------------------------------------------
    @server.tool(
        name="resolve_entity",
        description="Resolves a natural language cultural anchor (venue, brand, artist) to a verified Qloo entity with confidence and provenance.",
    )
    async def resolve_entity(
        query: str,
        expected_type: str | None = None,
        min_confidence: float = 0.5,
    ) -> dict[str, Any]:
        """Resolves natural language anchor term into verified Qloo entity ID."""
        request_id = str(uuid.uuid4())
        start_time = time.perf_counter()
        logger.info(
            "[Req: %s] resolve_entity: query='%s', type=%s",
            request_id,
            query,
            expected_type,
        )

        try:
            result = await entity_resolver.resolve(
                query=query,
                expected_type=expected_type,
                min_confidence=min_confidence,
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return {
                "request_id": request_id,
                "is_resolved": result.is_resolved,
                "input": result.input,
                "resolved_entity_id": result.resolved_entity_id,
                "entity_name": result.entity.name if result.entity else None,
                "entity_type": result.entity_type,
                "confidence": result.confidence,
                "source": result.source,
                "evidence": result.evidence.model_dump(),
                "alternatives_count": len(result.alternatives),
                "alternatives": [a.model_dump() for a in result.alternatives[:5]],
                "latency_ms": round(elapsed_ms, 2),
            }
        except Exception as e:
            logger.error("[Req: %s] resolve_entity error: %s", request_id, e)
            return {
                "request_id": request_id,
                "error": str(e),
                "is_resolved": False,
                "resolved_entity_id": None,
                "confidence": 0.0,
            }

    # -------------------------------------------------------------------------
    # Tag Resolution Tool
    # -------------------------------------------------------------------------
    @server.tool(
        name="resolve_tag",
        description="Resolves a cultural aesthetic, vibe, genre, or mood descriptor into a verified Qloo taxonomy tag.",
    )
    async def resolve_tag(
        query: str,
        expected_category: str | None = None,
        min_confidence: float = 0.5,
    ) -> dict[str, Any]:
        """Resolves natural language vibe into verified Qloo taxonomy tag."""
        request_id = str(uuid.uuid4())
        start_time = time.perf_counter()
        logger.info(
            "[Req: %s] resolve_tag: query='%s', category=%s",
            request_id,
            query,
            expected_category,
        )

        try:
            result = await tag_resolver.resolve(
                query=query,
                expected_category=expected_category,
                min_confidence=min_confidence,
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return {
                "request_id": request_id,
                "is_resolved": result.is_resolved,
                "input": result.input,
                "resolved_tag_id": result.resolved_tag_id,
                "tag_name": result.tag_name,
                "category": result.category,
                "confidence": result.confidence,
                "source": result.source,
                "evidence": result.evidence.model_dump(),
                "alternatives_count": len(result.alternatives),
                "latency_ms": round(elapsed_ms, 2),
            }
        except Exception as e:
            logger.error("[Req: %s] resolve_tag error: %s", request_id, e)
            return {
                "request_id": request_id,
                "error": str(e),
                "is_resolved": False,
                "resolved_tag_id": None,
                "confidence": 0.0,
            }

    # -------------------------------------------------------------------------
    # Cultural Profile Tool
    # -------------------------------------------------------------------------
    @server.tool(
        name="get_cultural_profile",
        description="Generates an immediate cross-domain taste profile for an entity, showing multi-category cultural resonance.",
    )
    async def get_cultural_profile(
        entity_id: str | None = None,
        entity_name: str | None = None,
        take: int = 5,
    ) -> dict[str, Any]:
        """Profiles a single anchor entity across music, brands, and spaces."""
        request_id = str(uuid.uuid4())
        start_time = time.perf_counter()
        logger.info(
            "[Req: %s] get_cultural_profile: id=%s, name=%s",
            request_id,
            entity_id,
            entity_name,
        )

        try:
            target_id = entity_id
            target_name = entity_name

            # If name passed without ID, resolve entity first
            if not target_id and target_name:
                res = await entity_resolver.resolve(target_name)
                if not res.is_resolved:
                    return {
                        "request_id": request_id,
                        "error": f"Could not resolve entity '{target_name}' to a verified Qloo entity ID.",
                        "is_resolved": False,
                    }
                target_id = res.resolved_entity_id
                target_name = res.entity.name if res.entity else target_name

            if not target_id:
                return {
                    "request_id": request_id,
                    "error": "Must provide either entity_id or entity_name to get_cultural_profile.",
                }

            # Query cross-domain affinities
            twin = CulturalTwin(anchor_entities=[target_id])
            matrix = await matrix_service.generate_matrix(
                twin,
                categories=["artist", "brand", "place"],
                take_per_category=take,
            )

            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return {
                "request_id": request_id,
                "entity_id": target_id,
                "entity_name": target_name or "Verified Entity",
                "affinities": {
                    "artists": [a.model_dump() for a in matrix.artists],
                    "brands": [b.model_dump() for b in matrix.brands],
                    "places": [p.model_dump() for p in matrix.places],
                },
                "total_affinities": matrix.total_recommendations,
                "latency_ms": round(elapsed_ms, 2),
            }
        except Exception as e:
            logger.error("[Req: %s] get_cultural_profile error: %s", request_id, e)
            return {"request_id": request_id, "error": str(e)}

    # -------------------------------------------------------------------------
    # Domain-Specific Tools
    # -------------------------------------------------------------------------
    async def _query_single_domain(
        category: str,
        anchor_entities: list[str],
        resolved_tags: list[str],
        take: int,
        location: LocationInput | None = None,
    ) -> dict[str, Any]:
        request_id = str(uuid.uuid4())
        start_time = time.perf_counter()
        logger.info(
            "[Req: %s] Query domain '%s' (Anchors: %d, Tags: %d)",
            request_id,
            category,
            len(anchor_entities),
            len(resolved_tags),
        )

        try:
            twin = CulturalTwin(
                anchor_entities=anchor_entities,
                resolved_tags=resolved_tags,
                location=location,
            )
            matrix = await matrix_service.generate_matrix(
                twin,
                categories=[category],
                take_per_category=take,
            )
            items = getattr(matrix, f"{category}s", [])
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            return {
                "request_id": request_id,
                "category": category,
                "recommendations": [item.model_dump() for item in items],
                "total_count": len(items),
                "query_metadata": [qm.model_dump() for qm in matrix.query_metadata],
                "latency_ms": round(elapsed_ms, 2),
            }
        except Exception as e:
            logger.error(
                "[Req: %s] Query domain '%s' error: %s", request_id, category, e
            )
            return {
                "request_id": request_id,
                "category": category,
                "error": str(e),
                "recommendations": [],
            }

    @server.tool(
        name="get_related_artists",
        description="Finds high-affinity musical artists matching anchor entities or cultural tags.",
    )
    async def get_related_artists(
        anchor_entities: list[str] | None = None,
        resolved_tags: list[str] | None = None,
        take: int = 10,
    ) -> dict[str, Any]:
        return await _query_single_domain(
            "artist", anchor_entities or [], resolved_tags or [], take
        )

    @server.tool(
        name="get_related_books",
        description="Finds high-affinity books, literature, and design publications matching cultural anchors.",
    )
    async def get_related_books(
        anchor_entities: list[str] | None = None,
        resolved_tags: list[str] | None = None,
        take: int = 10,
    ) -> dict[str, Any]:
        return await _query_single_domain(
            "book", anchor_entities or [], resolved_tags or [], take
        )

    @server.tool(
        name="get_related_brands",
        description="Finds high-affinity lifestyle, design, equipment, and fashion brands matching cultural anchors.",
    )
    async def get_related_brands(
        anchor_entities: list[str] | None = None,
        resolved_tags: list[str] | None = None,
        take: int = 10,
    ) -> dict[str, Any]:
        return await _query_single_domain(
            "brand", anchor_entities or [], resolved_tags or [], take
        )

    @server.tool(
        name="get_related_places",
        description="Finds high-affinity venues, coffee shops, listening bars, and galleries, optionally filtered by geographic coordinates.",
    )
    async def get_related_places(
        anchor_entities: list[str] | None = None,
        resolved_tags: list[str] | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        radius_meters: int = 5000,
        take: int = 10,
    ) -> dict[str, Any]:
        loc = None
        if latitude is not None and longitude is not None:
            loc = LocationInput(
                latitude=latitude, longitude=longitude, radius_meters=radius_meters
            )
        return await _query_single_domain(
            "place", anchor_entities or [], resolved_tags or [], take, location=loc
        )

    @server.tool(
        name="get_related_movies",
        description="Finds high-affinity films, cinema movements, and cinematic references matching cultural anchors.",
    )
    async def get_related_movies(
        anchor_entities: list[str] | None = None,
        resolved_tags: list[str] | None = None,
        take: int = 10,
    ) -> dict[str, Any]:
        return await _query_single_domain(
            "movie", anchor_entities or [], resolved_tags or [], take
        )

    # -------------------------------------------------------------------------
    # Full Cultural Matrix Tool
    # -------------------------------------------------------------------------
    @server.tool(
        name="get_cultural_matrix",
        description="Generates a full multidimensional CulturalMatrix across artists, books, brands, places, movies, and destinations for a physical space's CulturalTwin.",
    )
    async def get_cultural_matrix(
        cultural_twin: dict[str, Any],
        take_per_category: int = 10,
    ) -> dict[str, Any]:
        """Generates comprehensive CulturalMatrix for physical spaces."""
        request_id = str(uuid.uuid4())
        start_time = time.perf_counter()
        logger.info("[Req: %s] get_cultural_matrix invoked", request_id)

        try:
            # Validate input against CulturalTwin schema
            twin_model = CulturalTwin.model_validate(cultural_twin)

            matrix = await matrix_service.generate_matrix(
                twin_model,
                take_per_category=take_per_category,
            )

            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return {
                "request_id": request_id,
                "status": "success",
                "cultural_matrix": matrix.model_dump(),
                "total_recommendations": matrix.total_recommendations,
                "latency_ms": round(elapsed_ms, 2),
            }
        except Exception as e:
            logger.error(
                "[Req: %s] get_cultural_matrix validation/execution error: %s",
                request_id,
                e,
            )
            return {
                "request_id": request_id,
                "status": "error",
                "error": str(e),
                "cultural_matrix": None,
            }

    return server


def main() -> None:
    """Entrypoint for running the TasteOps Cultural Intelligence MCP server over stdio."""
    import asyncio

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    server = create_cultural_intelligence_mcp()
    asyncio.run(server.run_stdio_async())


if __name__ == "__main__":
    main()
