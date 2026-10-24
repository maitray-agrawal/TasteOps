"""Resolution Schemas for Cultural Anchors and Tags.

Provides typed provenance and evidence tracking for entity and tag resolution.
Guarantees verified IDs and prevents fabrication.
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from tasteops.models.entity import QlooEntity
from tasteops.models.tag import QlooTag


class ResolutionEvidence(BaseModel):
    """Provenance and algorithmic evidence for a resolution decision."""

    source: str = Field(..., description="Qloo endpoint source (e.g. 'qloo_search', 'qloo_tags')")
    raw_query: str = Field(..., description="Original raw natural language input")
    normalized_query: str = Field(..., description="Preprocessed query string used for matching")
    match_method: str = Field(
        ...,
        description="Matching heuristic applied (e.g. 'exact_case_insensitive', 'token_subset', 'fuzzy_ratio', 'unresolved')",
    )
    score: float = Field(..., ge=0.0, le=1.0, description="Raw algorithmic match score [0.0 - 1.0]")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp of resolution",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Supplemental candidate count or scoring metrics",
    )


class EntityCandidate(BaseModel):
    """Ranked alternative candidate entity from Qloo."""

    entity: QlooEntity = Field(..., description="The verified Qloo entity candidate")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Match confidence score [0.0 - 1.0]")
    match_reason: str = Field(..., description="Explanation of candidate ranking")


class EntityResolutionResult(BaseModel):
    """Resolved entity output with provenance, confidence, and preserved alternatives."""

    input: str = Field(..., description="Input natural-language term")
    resolved_entity_id: str | None = Field(
        default=None,
        description="Official verified Qloo entity ID, or None if unresolved/rejected",
    )
    entity_type: str | None = Field(
        default=None,
        description="Entity domain type (e.g. brand, artist, place)",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence score of resolution [0.0 - 1.0]",
    )
    source: str = Field(
        default="qloo_search",
        description="Resolution data source",
    )
    entity: QlooEntity | None = Field(
        default=None,
        description="Complete normalized entity model if resolved",
    )
    alternatives: list[EntityCandidate] = Field(
        default_factory=list,
        description="Preserved alternative candidates ranked descending by confidence",
    )
    evidence: ResolutionEvidence = Field(
        ...,
        description="Cryptic or algorithmic provenance proving this ID is verified from Qloo",
    )

    @property
    def is_resolved(self) -> bool:
        """True if a verified Qloo entity was successfully resolved above confidence threshold."""
        return self.resolved_entity_id is not None and self.confidence > 0.0


class TagCandidate(BaseModel):
    """Ranked alternative candidate tag from Qloo."""

    tag: QlooTag = Field(..., description="The verified Qloo tag candidate")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Match confidence score [0.0 - 1.0]")
    match_reason: str = Field(..., description="Explanation of candidate ranking")


class TagResolutionResult(BaseModel):
    """Resolved tag output with provenance, metadata, and preserved alternatives."""

    input: str = Field(..., description="Input natural-language tag/concept term")
    resolved_tag_id: str | None = Field(
        default=None,
        description="Official verified Qloo tag ID, or None if unresolved/rejected",
    )
    tag_name: str | None = Field(
        default=None,
        description="Official display name of the tag",
    )
    category: str | None = Field(
        default=None,
        description="Tag taxonomy category (e.g. music, dining, fashion)",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence score of resolution [0.0 - 1.0]",
    )
    source: str = Field(
        default="qloo_tags",
        description="Resolution data source",
    )
    tag: QlooTag | None = Field(
        default=None,
        description="Complete normalized tag model if resolved",
    )
    alternatives: list[TagCandidate] = Field(
        default_factory=list,
        description="Preserved alternative candidates ranked descending by confidence",
    )
    evidence: ResolutionEvidence = Field(
        ...,
        description="Provenance record proving this tag exists in Qloo taxonomy",
    )

    @property
    def is_resolved(self) -> bool:
        """True if a verified Qloo tag was successfully resolved above confidence threshold."""
        return self.resolved_tag_id is not None and self.confidence > 0.0
