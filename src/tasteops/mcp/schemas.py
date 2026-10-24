"""MCP Tool Input and Output Schemas for Cultural Intelligence."""

from typing import Any

from pydantic import BaseModel, Field

# =============================================================================
# Input Schemas
# =============================================================================


class HealthCheckInput(BaseModel):
    """Input for health_check tool (no arguments required)."""


class ResolveEntityInput(BaseModel):
    """Input for resolve_entity tool."""

    query: str = Field(
        ...,
        min_length=1,
        description="Natural language cultural anchor (venue, brand, artist)",
    )
    expected_type: str | None = Field(
        default=None, description="Optional entity domain filter (place, artist, brand)"
    )
    min_confidence: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Minimum confidence score threshold"
    )


class ResolveTagInput(BaseModel):
    """Input for resolve_tag tool."""

    query: str = Field(
        ...,
        min_length=1,
        description="Natural language vibe, aesthetic motif, or genre",
    )
    expected_category: str | None = Field(
        default=None, description="Tag domain category filter (style, music, dining)"
    )
    min_confidence: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Minimum confidence score threshold"
    )


class GetRelatedCategoryInput(BaseModel):
    """Input for category-specific affinity tools (artists, books, brands, movies)."""

    anchor_entities: list[str] = Field(
        default_factory=list, description="Seed Qloo entity IDs"
    )
    resolved_tags: list[str] = Field(
        default_factory=list, description="Seed Qloo tag IDs"
    )
    take: int = Field(
        default=10, ge=1, le=50, description="Maximum recommendations to return"
    )


class GetRelatedPlacesInput(BaseModel):
    """Input for spatial venue affinity tool."""

    anchor_entities: list[str] = Field(
        default_factory=list, description="Seed Qloo entity IDs"
    )
    resolved_tags: list[str] = Field(
        default_factory=list, description="Seed Qloo tag IDs"
    )
    latitude: float | None = Field(
        default=None, ge=-90.0, le=90.0, description="Latitude for local venue search"
    )
    longitude: float | None = Field(
        default=None,
        ge=-180.0,
        le=180.0,
        description="Longitude for local venue search",
    )
    radius_meters: int = Field(
        default=5000, ge=100, le=50000, description="Search radius in meters"
    )
    take: int = Field(default=10, ge=1, le=50, description="Maximum places to return")


class GetCulturalProfileInput(BaseModel):
    """Input for get_cultural_profile tool."""

    entity_id: str | None = Field(default=None, description="Qloo entity ID to profile")
    entity_name: str | None = Field(
        default=None, description="Natural language entity name to resolve and profile"
    )
    take: int = Field(default=5, ge=1, le=20, description="Top affinities per domain")


class GetCulturalMatrixInput(BaseModel):
    """Input for full CulturalMatrix generation."""

    cultural_twin: dict[str, Any] = Field(
        ...,
        description="CulturalTwin specification (target_audience, location, mood, anchor_entities, resolved_tags)",
    )
    take_per_category: int = Field(
        default=10, ge=1, le=30, description="Recommendations per category"
    )


# =============================================================================
# Output Schemas
# =============================================================================


class HealthCheckOutput(BaseModel):
    """Output schema for health_check tool."""

    request_id: str = Field(description="Unique UUID request identifier")
    status: str = Field(default="healthy", description="Server health status")
    server: str = Field(
        default="tasteops-cultural-intelligence", description="Server name"
    )
    version: str = Field(default="1.0.0", description="Server semantic version")
    base_url: str = Field(description="Configured Qloo API base URL")
    timestamp: str = Field(description="ISO-8601 UTC timestamp")
    latency_ms: float = Field(description="Execution latency in milliseconds")
    error: str | None = Field(
        default=None, description="Error message if health check degraded"
    )


class ResolveEntityOutput(BaseModel):
    """Output schema for resolve_entity tool with provenance and confidence."""

    request_id: str = Field(description="Unique UUID request identifier")
    is_resolved: bool = Field(description="Whether the anchor successfully resolved")
    input: str = Field(description="Raw input anchor query")
    resolved_entity_id: str | None = Field(
        default=None, description="Verified Qloo entity ID"
    )
    entity_name: str | None = Field(default=None, description="Normalized entity name")
    entity_type: str | None = Field(default=None, description="Entity domain type")
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Match confidence score [0.0 - 1.0]"
    )
    source: str = Field(
        default="qloo_search", description="Resolution provenance source"
    )
    evidence: dict[str, Any] = Field(
        default_factory=dict, description="Resolution algorithmic provenance"
    )
    alternatives_count: int = Field(
        default=0, description="Number of candidate alternatives evaluated"
    )
    alternatives: list[dict[str, Any]] = Field(
        default_factory=list, description="Top alternative candidate entities"
    )
    latency_ms: float = Field(
        default=0.0, description="Execution latency in milliseconds"
    )
    error: str | None = Field(
        default=None, description="Error description on resolution failure"
    )


class ResolveTagOutput(BaseModel):
    """Output schema for resolve_tag tool with provenance and confidence."""

    request_id: str = Field(description="Unique UUID request identifier")
    is_resolved: bool = Field(description="Whether the tag successfully resolved")
    input: str = Field(description="Raw input tag query")
    resolved_tag_id: str | None = Field(
        default=None, description="Verified Qloo taxonomy tag ID"
    )
    tag_name: str | None = Field(default=None, description="Normalized tag name")
    category: str | None = Field(default=None, description="Tag domain category")
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Match confidence score [0.0 - 1.0]"
    )
    source: str = Field(default="qloo_tags", description="Tag taxonomy source")
    evidence: dict[str, Any] = Field(
        default_factory=dict, description="Resolution algorithmic provenance"
    )
    alternatives_count: int = Field(
        default=0, description="Number of candidate alternatives evaluated"
    )
    latency_ms: float = Field(
        default=0.0, description="Execution latency in milliseconds"
    )
    error: str | None = Field(
        default=None, description="Error description on resolution failure"
    )


class CulturalProfileAffinities(BaseModel):
    """Container for cross-domain affinity recommendations."""

    artists: list[dict[str, Any]] = Field(
        default_factory=list, description="Artist recommendations"
    )
    brands: list[dict[str, Any]] = Field(
        default_factory=list, description="Brand recommendations"
    )
    places: list[dict[str, Any]] = Field(
        default_factory=list, description="Place recommendations"
    )


class GetCulturalProfileOutput(BaseModel):
    """Output schema for get_cultural_profile tool."""

    request_id: str = Field(description="Unique UUID request identifier")
    entity_id: str | None = Field(default=None, description="Profiled entity ID")
    entity_name: str | None = Field(default=None, description="Profiled entity name")
    affinities: CulturalProfileAffinities = Field(
        default_factory=CulturalProfileAffinities,
        description="Cross-domain affinity items",
    )
    total_affinities: int = Field(
        default=0, description="Total recommendation count across all profiled domains"
    )
    latency_ms: float = Field(
        default=0.0, description="Execution latency in milliseconds"
    )
    is_resolved: bool | None = Field(
        default=None, description="Resolution state if entity_name was supplied"
    )
    error: str | None = Field(
        default=None, description="Error description on profile failure"
    )


class CategoryRecommendationsOutput(BaseModel):
    """Output schema for domain-specific affinity recommendations with provenance."""

    request_id: str = Field(description="Unique UUID request identifier")
    category: str = Field(description="Target cultural domain category")
    recommendations: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Recommendations with affinity, confidence, and provenance",
    )
    total_count: int = Field(
        default=0, description="Total recommendation items returned"
    )
    query_metadata: list[dict[str, Any]] = Field(
        default_factory=list, description="Query execution provenance and telemetry"
    )
    latency_ms: float = Field(
        default=0.0, description="Execution latency in milliseconds"
    )
    error: str | None = Field(
        default=None, description="Error description on domain query failure"
    )


class GetCulturalMatrixOutput(BaseModel):
    """Output schema for get_cultural_matrix tool."""

    request_id: str = Field(description="Unique UUID request identifier")
    status: str = Field(description="Status ('success' or 'error')")
    cultural_matrix: dict[str, Any] | None = Field(
        default=None, description="Complete 6-domain CulturalMatrix payload"
    )
    total_recommendations: int = Field(
        default=0, description="Total recommendations across all domains"
    )
    latency_ms: float = Field(
        default=0.0, description="Execution latency in milliseconds"
    )
    error: str | None = Field(
        default=None, description="Error description on matrix generation failure"
    )


class MCPErrorOutput(BaseModel):
    """Standardized deterministic MCP error envelope."""

    request_id: str = Field(description="Unique UUID request identifier")
    status: str = Field(default="error", description="Error status indicator")
    error: str = Field(description="Human-readable root cause error message")
    cultural_matrix: None = Field(
        default=None, description="Null matrix container on error"
    )
