"""TasteOps Insights Service.

Encapsulates Qloo Insights endpoint interactions with entity-type capability validation,
deterministic query construction, and result normalization.
"""

import logging
from dataclasses import dataclass
from typing import Any

from tasteops.client import QlooClient
from tasteops.models.cultural_matrix import CulturalRecommendation
from tasteops.models.insight import QlooInsight
from tasteops.models.params import InsightParams

logger = logging.getLogger("tasteops.insights_service")


@dataclass(frozen=True)
class EntityTypeCapability:
    """Configured capabilities and supported filter signals for a Qloo entity type."""

    category: str
    urn: str
    supports_spatial_location: bool
    supports_filter_tags: bool
    supports_entity_signals: bool = True
    supports_tag_signals: bool = True


# Configured capability registry for initial supported categories
CATEGORY_CAPABILITIES: dict[str, EntityTypeCapability] = {
    "artist": EntityTypeCapability(
        category="artist",
        urn="urn:entity:artist",
        supports_spatial_location=False,
        supports_filter_tags=True,
    ),
    "book": EntityTypeCapability(
        category="book",
        urn="urn:entity:book",
        supports_spatial_location=False,
        supports_filter_tags=True,
    ),
    "brand": EntityTypeCapability(
        category="brand",
        urn="urn:entity:brand",
        supports_spatial_location=False,
        supports_filter_tags=True,
    ),
    "place": EntityTypeCapability(
        category="place",
        urn="urn:entity:place",
        supports_spatial_location=True,
        supports_filter_tags=True,
    ),
    "movie": EntityTypeCapability(
        category="movie",
        urn="urn:entity:movie",
        supports_spatial_location=False,
        supports_filter_tags=True,
    ),
    "destination": EntityTypeCapability(
        category="destination",
        urn="urn:entity:destination",
        supports_spatial_location=True,
        supports_filter_tags=True,
    ),
}


class InsightsService:
    """Orchestrates capability-aware Qloo Insights queries."""

    def __init__(self, client: QlooClient) -> None:
        self.client = client

    def get_capability(self, category: str) -> EntityTypeCapability:
        """Returns the configured capability profile for a category name or URN."""
        cat_key = category.lower().replace("urn:entity:", "")
        if cat_key not in CATEGORY_CAPABILITIES:
            # Default fallback capability
            return EntityTypeCapability(
                category=cat_key,
                urn=f"urn:entity:{cat_key}",
                supports_spatial_location=False,
                supports_filter_tags=True,
            )
        return CATEGORY_CAPABILITIES[cat_key]

    def build_insight_params(
        self,
        category: str,
        anchor_entities: list[str],
        resolved_tags: list[str],
        location_wkt: str | None = None,
        location_radius: int | None = None,
        take: int = 15,
        explainability: bool = True,
    ) -> InsightParams:
        """Constructs validated InsightParams conforming strictly to category capabilities."""
        capability = self.get_capability(category)

        # Enforce capability constraints: do not pass location to non-spatial entities
        valid_location_wkt = location_wkt if capability.supports_spatial_location else None
        valid_radius = location_radius if capability.supports_spatial_location else None

        valid_entities = anchor_entities if capability.supports_entity_signals else []
        valid_tags = resolved_tags if capability.supports_tag_signals else []

        # At least one signal or location is required by InsightParams
        if not valid_entities and not valid_tags and not valid_location_wkt:
            raise ValueError(
                f"Cannot build InsightParams for category '{category}': "
                f"No supported signals (entities, tags, or spatial location) provided."
            )

        return InsightParams(
            filter_type=capability.urn,
            signal_entities=valid_entities,
            signal_tags=valid_tags,
            location_wkt=valid_location_wkt,
            location_radius=valid_radius,
            explainability=explainability,
            take=take,
        )

    async def fetch_category_insights(
        self,
        params: InsightParams,
        category: str,
        source_signal: dict[str, Any],
    ) -> list[CulturalRecommendation]:
        """Queries Qloo Insights and maps results to typed CulturalRecommendation items."""
        raw_insights: list[QlooInsight] = await self.client.get_insights(params)

        recommendations: list[CulturalRecommendation] = []
        for item in raw_insights:
            recommendations.append(
                CulturalRecommendation(
                    id=item.id,
                    name=item.name,
                    type=category,
                    affinity=item.affinity,
                    score=item.score,
                    confidence=item.affinity,
                    source_query=f"/v2/insights?filter.type={params.filter_type}",
                    source_signal=source_signal,
                    explainability=item.explainability,
                    metadata=item.metadata,
                )
            )

        return recommendations
