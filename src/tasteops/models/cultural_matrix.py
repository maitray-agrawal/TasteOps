"""Cultural Matrix Models for Physical Spaces.

Defines CulturalTwin inputs, CulturalRecommendation items, CategoryQueryMetadata,
and CulturalMatrix output schemas.
"""

import re
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class LocationInput(BaseModel):
    """Location specification for physical spaces (lat/lon or WKT point)."""

    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    wkt: str | None = Field(
        default=None, description="WKT point e.g. POINT(-73.985 40.748)"
    )
    radius_meters: int = Field(
        default=2000, ge=10, le=200000, description="Spatial search radius"
    )

    @field_validator("wkt")
    @classmethod
    def validate_wkt(cls, v: str | None) -> str | None:
        if v is not None:
            cleaned = v.strip()
            if not re.match(
                r"^POINT\s*\(\s*[-+]?[0-9]*\.?[0-9]+\s+[-+]?[0-9]*\.?[0-9]+\s*\)$",
                cleaned,
                re.IGNORECASE,
            ):
                raise ValueError(
                    f"Invalid WKT format '{v}'. Expected 'POINT(longitude latitude)'"
                )
            return cleaned
        return None

    def to_wkt(self) -> str | None:
        """Converts coordinates to standard WKT string."""
        if self.wkt:
            return self.wkt
        if self.longitude is not None and self.latitude is not None:
            return f"POINT({self.longitude} {self.latitude})"
        return None


class ResolvedEntity(BaseModel):
    """Verified Qloo entity with provenance and narrative relevance."""

    id: str = Field(..., description="Verified Qloo entity ID (never invented)")
    name: str = Field(..., description="Entity name")
    type: str = Field(..., description="Entity domain type (e.g. brand, place, artist)")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Resolution match confidence score"
    )
    why_it_matters: str = Field(
        ..., description="Explanation of why this cultural signal matters to the space"
    )
    source: str = Field(default="qloo_search", description="Data provenance source")
    evidence: dict[str, Any] = Field(
        default_factory=dict, description="Resolution provenance and match details"
    )


class ResolvedTag(BaseModel):
    """Verified Qloo tag with provenance and aesthetic relevance."""

    id: str = Field(..., description="Verified Qloo tag ID (never invented)")
    name: str = Field(..., description="Tag name")
    category: str | None = Field(default=None, description="Tag category")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Resolution match confidence score"
    )
    why_it_matters: str = Field(
        ..., description="Explanation of why this tag signal matters to the space"
    )


class PhysicalSpaceBrief(BaseModel):
    """User input brief defining a physical space activation."""

    business_type: str = Field(
        ...,
        description="Venue type (e.g. 'specialty coffee lab', 'analog listening bar', 'boutique hotel')",
    )
    location: LocationInput | dict[str, Any] | str | None = Field(
        default=None,
        description="Physical location coordinates, WKT, or description",
    )
    target_audience: str | None = Field(
        default=None,
        description="Target demographic or psychographic audience summary",
    )
    positioning: str | None = Field(
        default=None,
        description="Market positioning (e.g. 'craft premium', 'underground', 'accessible luxury')",
    )
    desired_mood: str | None = Field(
        default=None,
        description="Atmospheric vibe and energy (e.g. 'minimalist, warm acoustic focus')",
    )
    budget: str | None = Field(
        default=None,
        description="Budget tier or parameters (e.g. 'boutique premium', 'lean craft')",
    )
    constraints: list[str] | dict[str, Any] | None = Field(
        default=None,
        description="Physical, operational, or aesthetic boundaries and constraints",
    )
    anchor_entities: list[str] = Field(
        default_factory=list,
        description="Natural language anchor references (brands, venues, artists, aesthetics)",
    )


class CulturalTwin(BaseModel):
    """Holistic cultural foundation for a physical space or brand."""

    # Explicit fields requested in Cultural Strategist specification:
    audience_profile: str = Field(
        default="",
        description="Synthesized audience demographic / psychographic profile",
    )
    cultural_themes: list[str] = Field(
        default_factory=list,
        description="Synthesized cultural themes guiding the identity",
    )
    mood_profile: str = Field(
        default="",
        description="Atmospheric vibe, sonic texture, and mood breakdown",
    )
    anchor_entities: list[str] = Field(
        default_factory=list,
        description="Original cultural anchor terms from brief, or verified Qloo entity IDs",
    )
    resolved_entities: list[ResolvedEntity] = Field(
        default_factory=list,
        description="Verified Qloo entities with provenance and explanations",
    )
    resolved_tags: list[str] = Field(
        default_factory=list,
        description="Verified Qloo tag IDs representing cultural motifs or aesthetics",
    )
    cultural_constraints: list[str] = Field(
        default_factory=list,
        description="Aesthetic guardrails and cultural constraints",
    )
    exclusions: list[str] = Field(
        default_factory=list,
        description="Aesthetic and cultural elements strictly excluded/avoided",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Aggregate confidence score across resolved cultural signals",
    )

    # Rich metadata & backward-compatibility fields:
    resolved_tag_details: list[ResolvedTag] = Field(
        default_factory=list,
        description="Detailed verified tags with narrative explanations",
    )
    signal_explanations: dict[str, str] = Field(
        default_factory=dict,
        description="Lookup mapping of entity/tag ID to why it matters",
    )
    business_type: str | None = Field(
        default=None,
        description="Venue type e.g. 'specialty cafe', 'boutique hotel', 'listening bar'",
    )
    target_audience: str | None = Field(
        default=None,
        description="Audience demographic / psychographic summary",
    )
    mood: str | None = Field(
        default=None,
        description="Atmospheric vibe e.g. 'minimalist', 'warm intimate'",
    )
    positioning: str | None = Field(
        default=None,
        description="Market positioning e.g. 'craft premium', 'underground'",
    )
    budget: str | None = Field(
        default=None,
        description="Budget level or tier e.g. 'premium', 'high-end boutique'",
    )
    location: LocationInput | None = Field(
        default=None,
        description="Physical coordinates and radius",
    )
    constraints: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional query constraints e.g. {'take': 10, 'price_level_max': 3}",
    )

    @field_validator("constraints", mode="before")
    @classmethod
    def validate_constraints(cls, v: Any) -> dict[str, Any]:
        if isinstance(v, list):
            return {"raw_constraints": v}
        if isinstance(v, dict):
            return v
        if v is None:
            return {}
        return {"raw_constraints": [str(v)]}

    def model_post_init(self, context: Any, /) -> None:
        """Harmonizes audience and mood fields across schemas."""
        if not self.audience_profile and self.target_audience:
            self.audience_profile = self.target_audience
        elif not self.target_audience and self.audience_profile:
            self.target_audience = self.audience_profile

        if not self.mood_profile and self.mood:
            self.mood_profile = self.mood
        elif not self.mood and self.mood_profile:
            self.mood = self.mood_profile

    @property
    def resolved_entity_ids(self) -> list[str]:
        """Returns list of verified Qloo entity IDs."""
        if self.resolved_entities:
            return [e.id for e in self.resolved_entities]
        return self.anchor_entities

    @property
    def resolved_tag_ids(self) -> list[str]:
        """Returns list of verified Qloo tag IDs."""
        return self.resolved_tags


class CulturalRecommendation(BaseModel):
    """Normalized recommendation item retaining provenance, source signals, and metadata."""

    id: str = Field(..., description="Verified Qloo entity ID")
    name: str = Field(..., description="Display name of recommended entity")
    type: str = Field(
        ...,
        description="Entity category (e.g. artist, book, brand, place, movie, destination)",
    )
    affinity: float = Field(
        ..., ge=0.0, le=1.0, description="Normalized affinity score [0.0 - 1.0]"
    )
    score: float | None = Field(default=None, description="Raw affinity score")
    confidence: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Recommendation confidence"
    )
    source_query: str = Field(..., description="API endpoint / category query invoked")
    source_signal: dict[str, Any] = Field(
        default_factory=dict,
        description="Signals used to trigger this recommendation (entities, tags, location)",
    )
    explainability: list[str] = Field(
        default_factory=list,
        description="Reasoning or attribution why this entity fits the cultural twin",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Supplemental metadata (tags, address, city, etc.)",
    )


class CategoryQueryMetadata(BaseModel):
    """Execution diagnostics for a single category query."""

    category: str = Field(
        ...,
        description="Category queried (artist, book, brand, place, movie, destination)",
    )
    filter_type: str = Field(..., description="Target Qloo URN used")
    status: str = Field(
        ...,
        description="Query outcome: 'success', 'empty', 'fallback_success', 'fallback_empty', 'error'",
    )
    retries: int = Field(default=0, description="Number of fallback retries executed")
    fallback_applied: str | None = Field(
        default=None,
        description="Description of deterministic fallback applied, if any",
    )
    items_count: int = Field(
        default=0, description="Number of recommendations returned"
    )
    latency_ms: float = Field(
        default=0.0, description="Query execution duration in milliseconds"
    )
    params_used: dict[str, Any] = Field(
        default_factory=dict, description="Sanitized parameters dispatched to Qloo"
    )


class CulturalMatrixEvidence(BaseModel):
    """Provenance audit log for a category recommendation set."""

    category: str = Field(..., description="Target category")
    message: str = Field(
        ..., description="High-level description of signals and filters utilized"
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    signals_used: list[str] = Field(
        default_factory=list, description="IDs of anchor entities or tags utilized"
    )


class CulturalMatrix(BaseModel):
    """Multidimensional cultural intelligence profile for physical spaces."""

    artists: list[CulturalRecommendation] = Field(default_factory=list)
    books: list[CulturalRecommendation] = Field(default_factory=list)
    brands: list[CulturalRecommendation] = Field(default_factory=list)
    places: list[CulturalRecommendation] = Field(default_factory=list)
    movies: list[CulturalRecommendation] = Field(default_factory=list)
    destinations: list[CulturalRecommendation] = Field(default_factory=list)
    evidence: list[CulturalMatrixEvidence] = Field(default_factory=list)
    query_metadata: list[CategoryQueryMetadata] = Field(default_factory=list)

    @property
    def total_recommendations(self) -> int:
        return (
            len(self.artists)
            + len(self.books)
            + len(self.brands)
            + len(self.places)
            + len(self.movies)
            + len(self.destinations)
        )
