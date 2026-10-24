"""TasteOps Cultural Matrix Service.

Computes a holistic CulturalMatrix across music, books, fashion/brands, dining/places,
movies, and destinations for a given physical space's CulturalTwin.

Features:
- Validates parameters against entity-type capabilities
- Executes independent category queries concurrently via asyncio.gather
- Implements deterministic single-retry fallbacks on empty results
- Retains full provenance, source signals, and query diagnostics
- Strictly avoids hallucinating any entity IDs
"""

import asyncio
import logging
import time
from typing import Any

from tasteops.client import QlooClient
from tasteops.models.cultural_matrix import (
    CategoryQueryMetadata,
    CulturalMatrix,
    CulturalMatrixEvidence,
    CulturalRecommendation,
    CulturalTwin,
)
from tasteops.models.params import InsightParams
from tasteops.services.insights_service import InsightsService

logger = logging.getLogger("tasteops.cultural_matrix_service")

# Supported categories for CulturalMatrix
DEFAULT_CATEGORIES: list[str] = [
    "artist",
    "book",
    "brand",
    "place",
    "movie",
    "destination",
]


class CulturalMatrixService:
    """Service generating multidimensional cultural intelligence matrixes for physical spaces."""

    def __init__(
        self,
        client: QlooClient,
        insights_service: InsightsService | None = None,
    ) -> None:
        self.client = client
        self.insights_service = insights_service or InsightsService(client)

    async def generate_matrix(
        self,
        twin: CulturalTwin,
        *,
        categories: list[str] | None = None,
        take_per_category: int = 15,
    ) -> CulturalMatrix:
        """Generates a complete CulturalMatrix for a CulturalTwin.

        Executes category queries concurrently, applies deterministic fallback on empty
        results, and returns normalized recommendations with provenance.
        """
        target_categories = categories or DEFAULT_CATEGORIES
        logger.info(
            "Generating CulturalMatrix for '%s' (Audience: %s, Anchors: %d, Tags: %d)",
            twin.business_type or "Physical Space",
            twin.target_audience or "General",
            len(twin.anchor_entities),
            len(twin.resolved_tags),
        )

        # Check if any signals or location exist
        has_signals = bool(
            twin.resolved_entity_ids
            or twin.anchor_entities
            or twin.resolved_tags
            or twin.location
        )
        if not has_signals:
            logger.warning(
                "CulturalTwin contains no anchor entities, tags, or location. Returning empty matrix."
            )
            return CulturalMatrix(
                evidence=[
                    CulturalMatrixEvidence(
                        category="all",
                        message="CulturalTwin provided no anchors, tags, or location signals.",
                        signals_used=[],
                    )
                ]
            )

        # Execute all category queries concurrently
        tasks = [
            self._query_category_with_fallback(twin, category, take=take_per_category)
            for category in target_categories
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Assemble CulturalMatrix
        matrix = CulturalMatrix()

        for category, res in zip(target_categories, results):
            if isinstance(res, BaseException):
                logger.error(
                    "Category '%s' query failed with exception: %s", category, res
                )
                matrix.query_metadata.append(
                    CategoryQueryMetadata(
                        category=category,
                        filter_type=f"urn:entity:{category}",
                        status="error",
                        retries=0,
                        items_count=0,
                        params_used={"error": str(res)},
                    )
                )
                matrix.evidence.append(
                    CulturalMatrixEvidence(
                        category=category,
                        message=f"Query failed with error: {res!s}",
                        signals_used=twin.anchor_entities + twin.resolved_tags,
                    )
                )
                continue

            recommendations, metadata, evidence = res
            matrix.query_metadata.append(metadata)
            if evidence:
                matrix.evidence.append(evidence)

            # Assign recommendations to appropriate category field
            if category == "artist":
                matrix.artists.extend(recommendations)
            elif category == "book":
                matrix.books.extend(recommendations)
            elif category == "brand":
                matrix.brands.extend(recommendations)
            elif category == "place":
                matrix.places.extend(recommendations)
            elif category == "movie":
                matrix.movies.extend(recommendations)
            elif category == "destination":
                matrix.destinations.extend(recommendations)

        logger.info(
            "CulturalMatrix generation complete. Total recommendations: %d",
            matrix.total_recommendations,
        )
        return matrix

    async def _query_category_with_fallback(
        self,
        twin: CulturalTwin,
        category: str,
        take: int,
    ) -> tuple[
        list[CulturalRecommendation], CategoryQueryMetadata, CulturalMatrixEvidence
    ]:
        """Queries Qloo Insights for a single category with a deterministic single-retry fallback on empty."""
        start_time = time.perf_counter()
        capability = self.insights_service.get_capability(category)

        location_wkt = twin.location.to_wkt() if twin.location else None
        location_radius = twin.location.radius_meters if twin.location else None

        # Build initial query params conforming to category capabilities
        try:
            params = self.insights_service.build_insight_params(
                category=category,
                anchor_entities=twin.resolved_entity_ids or twin.anchor_entities,
                resolved_tags=twin.resolved_tags,
                location_wkt=location_wkt,
                location_radius=location_radius,
                take=take,
            )
        except ValueError as err:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            meta = CategoryQueryMetadata(
                category=category,
                filter_type=capability.urn,
                status="skipped_no_valid_signals",
                retries=0,
                items_count=0,
                latency_ms=elapsed_ms,
                params_used={"skipped_reason": str(err)},
            )
            ev = CulturalMatrixEvidence(
                category=category,
                message=f"Category skipped: {err!s}",
                signals_used=[],
            )
            return [], meta, ev

        source_signal: dict[str, Any] = {
            "anchor_entities": twin.anchor_entities,
            "resolved_tags": twin.resolved_tags,
            "location": location_wkt,
            "radius": location_radius if capability.supports_spatial_location else None,
        }

        # 1. First Attempt
        try:
            recs = await self.insights_service.fetch_category_insights(
                params, category, source_signal
            )
        except Exception as e:
            logger.warning("Category '%s' initial query failed: %s", category, e)
            recs = []

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # If initial query yielded results, return success immediately
        if recs:
            meta = CategoryQueryMetadata(
                category=category,
                filter_type=capability.urn,
                status="success",
                retries=0,
                items_count=len(recs),
                latency_ms=elapsed_ms,
                params_used=params.to_query_params(),
            )
            ev = CulturalMatrixEvidence(
                category=category,
                message=f"Successfully retrieved {len(recs)} recommendations using direct signals.",
                signals_used=twin.anchor_entities + twin.resolved_tags,
            )
            return recs, meta, ev

        # 2. Deterministic Fallback Rule & Single Retry
        logger.info(
            "Category '%s' returned 0 results. Evaluating deterministic fallback rules...",
            category,
        )
        fallback_params, fallback_desc = self._compute_fallback_params(
            twin=twin,
            category=category,
            original_params=params,
            take=take,
        )

        if not fallback_params:
            # No fallback possible
            meta = CategoryQueryMetadata(
                category=category,
                filter_type=capability.urn,
                status="empty",
                retries=0,
                items_count=0,
                latency_ms=elapsed_ms,
                params_used=params.to_query_params(),
            )
            ev = CulturalMatrixEvidence(
                category=category,
                message="No results returned from Qloo; no applicable fallback available.",
                signals_used=twin.anchor_entities + twin.resolved_tags,
            )
            return [], meta, ev

        # Execute single retry with broadened fallback query
        logger.info(
            "Category '%s' retrying once with fallback: %s", category, fallback_desc
        )
        fallback_source_signal = {
            **source_signal,
            "fallback_applied": fallback_desc,
        }

        try:
            fallback_recs = await self.insights_service.fetch_category_insights(
                fallback_params, category, fallback_source_signal
            )
        except Exception as err:
            logger.warning("Category '%s' fallback query failed: %s", category, err)
            fallback_recs = []

        total_elapsed_ms = (time.perf_counter() - start_time) * 1000

        if fallback_recs:
            meta = CategoryQueryMetadata(
                category=category,
                filter_type=capability.urn,
                status="fallback_success",
                retries=1,
                fallback_applied=fallback_desc,
                items_count=len(fallback_recs),
                latency_ms=total_elapsed_ms,
                params_used=fallback_params.to_query_params(),
            )
            ev = CulturalMatrixEvidence(
                category=category,
                message=f"Initial query returned 0 results; fallback ({fallback_desc}) successfully returned {len(fallback_recs)} recommendations.",
                signals_used=fallback_params.signal_entities
                + fallback_params.signal_tags,
            )
            return fallback_recs, meta, ev
        else:
            meta = CategoryQueryMetadata(
                category=category,
                filter_type=capability.urn,
                status="fallback_empty",
                retries=1,
                fallback_applied=fallback_desc,
                items_count=0,
                latency_ms=total_elapsed_ms,
                params_used=fallback_params.to_query_params(),
            )
            ev = CulturalMatrixEvidence(
                category=category,
                message=f"Category returned 0 results after initial attempt and broadened fallback ({fallback_desc}). Zero items hallucinated.",
                signals_used=fallback_params.signal_entities
                + fallback_params.signal_tags,
            )
            return [], meta, ev

    def _compute_fallback_params(
        self,
        twin: CulturalTwin,
        category: str,
        original_params: InsightParams,
        take: int,
    ) -> tuple[InsightParams | None, str | None]:
        """Determines the single deterministic fallback query according to domain rules."""
        capability = self.insights_service.get_capability(category)

        # Rule A: Spatial entity (place, destination) with strict location radius
        # Broaden radius by 5x (e.g. 2,000m -> 10,000m) or relax tag filters
        if capability.supports_spatial_location and original_params.location_radius:
            expanded_radius = min(100000, original_params.location_radius * 5)
            if expanded_radius > original_params.location_radius:
                return (
                    InsightParams(
                        filter_type=capability.urn,
                        signal_entities=twin.resolved_entity_ids
                        or twin.anchor_entities,
                        signal_tags=twin.resolved_tags,
                        location_wkt=original_params.location_wkt,
                        location_radius=expanded_radius,
                        take=take,
                    ),
                    f"expand_spatial_radius_to_{expanded_radius}m",
                )

        # Rule B: Non-spatial entity with both anchor entities and tags
        # Over-filtering often happens when both entities and niche tags are combined.
        # Fallback: Relax to anchor entities only
        if twin.anchor_entities and twin.resolved_tags:
            return (
                InsightParams(
                    filter_type=capability.urn,
                    signal_entities=twin.anchor_entities,
                    signal_tags=[],
                    take=take,
                ),
                "relax_to_anchor_entities_only",
            )

        # Rule C: Only tags were provided
        # Fallback: Relax to top tag only
        if not twin.anchor_entities and len(twin.resolved_tags) > 1:
            return (
                InsightParams(
                    filter_type=capability.urn,
                    signal_entities=[],
                    signal_tags=[twin.resolved_tags[0]],
                    take=take,
                ),
                "relax_to_primary_tag_only",
            )

        # Rule D: Spatial entity with location and anchor entities
        # Fallback: Drop location constraint if hyper-local space returned nothing
        if (
            capability.supports_spatial_location
            and original_params.location_wkt
            and twin.anchor_entities
        ):
            return (
                InsightParams(
                    filter_type=capability.urn,
                    signal_entities=twin.anchor_entities,
                    take=take,
                ),
                "drop_spatial_constraint_to_global_affinity",
            )

        return None, None
