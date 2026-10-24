"""TasteOps MCP Server Package."""

from tasteops.mcp.schemas import (
    CategoryRecommendationsOutput,
    CulturalProfileAffinities,
    GetCulturalMatrixInput,
    GetCulturalMatrixOutput,
    GetCulturalProfileInput,
    GetCulturalProfileOutput,
    GetRelatedCategoryInput,
    GetRelatedPlacesInput,
    HealthCheckInput,
    HealthCheckOutput,
    MCPErrorOutput,
    ResolveEntityInput,
    ResolveEntityOutput,
    ResolveTagInput,
    ResolveTagOutput,
)
from tasteops.mcp.server import create_cultural_intelligence_mcp

__all__ = [
    "CategoryRecommendationsOutput",
    "CulturalProfileAffinities",
    "GetCulturalMatrixInput",
    "GetCulturalMatrixOutput",
    "GetCulturalProfileInput",
    "GetCulturalProfileOutput",
    "GetRelatedCategoryInput",
    "GetRelatedPlacesInput",
    "HealthCheckInput",
    "HealthCheckOutput",
    "MCPErrorOutput",
    "ResolveEntityInput",
    "ResolveEntityOutput",
    "ResolveTagInput",
    "ResolveTagOutput",
    "create_cultural_intelligence_mcp",
]
