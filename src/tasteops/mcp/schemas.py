"""MCP Tool Input and Output Schemas for Cultural Intelligence."""

from typing import Any

from pydantic import BaseModel, Field


class ResolveEntityInput(BaseModel):
    """Input for resolve_entity tool."""

    query: str = Field(..., min_length=1, description="Natural language cultural anchor (venue, brand, artist)")
    expected_type: str | None = Field(default=None, description="Optional entity domain filter (place, artist, brand)")
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Minimum confidence score threshold")


class ResolveTagInput(BaseModel):
    """Input for resolve_tag tool."""

    query: str = Field(..., min_length=1, description="Natural language vibe, aesthetic motif, or genre")
    expected_category: str | None = Field(default=None, description="Tag domain category filter (style, music, dining)")
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Minimum confidence score threshold")


class GetRelatedCategoryInput(BaseModel):
    """Input for category-specific affinity tools (artists, books, brands, movies)."""

    anchor_entities: list[str] = Field(default_factory=list, description="Seed Qloo entity IDs")
    resolved_tags: list[str] = Field(default_factory=list, description="Seed Qloo tag IDs")
    take: int = Field(default=10, ge=1, le=50, description="Maximum recommendations to return")


class GetRelatedPlacesInput(BaseModel):
    """Input for spatial venue affinity tool."""

    anchor_entities: list[str] = Field(default_factory=list, description="Seed Qloo entity IDs")
    resolved_tags: list[str] = Field(default_factory=list, description="Seed Qloo tag IDs")
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0, description="Latitude for local venue search")
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0, description="Longitude for local venue search")
    radius_meters: int = Field(default=5000, ge=100, le=50000, description="Search radius in meters")
    take: int = Field(default=10, ge=1, le=50, description="Maximum places to return")


class GetCulturalProfileInput(BaseModel):
    """Input for get_cultural_profile tool."""

    entity_id: str | None = Field(default=None, description="Qloo entity ID to profile")
    entity_name: str | None = Field(default=None, description="Natural language entity name to resolve and profile")
    take: int = Field(default=5, ge=1, le=20, description="Top affinities per domain")


class GetCulturalMatrixInput(BaseModel):
    """Input for full CulturalMatrix generation."""

    cultural_twin: dict[str, Any] = Field(
        ...,
        description="CulturalTwin specification (target_audience, location, mood, anchor_entities, resolved_tags)",
    )
    take_per_category: int = Field(default=10, ge=1, le=30, description="Recommendations per category")
