"""Validated parameter models for Qloo endpoints.

Prevents arbitrary or unvalidated input from LLMs / external callers
from being passed directly into the HTTP client.
"""

import re

from pydantic import BaseModel, Field, field_validator, model_validator


class SearchParams(BaseModel):
    """Validated query parameters for GET /search."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Search term (e.g. venue name, brand, artist)",
    )
    type: str | None = Field(
        default=None,
        description="Filter by entity type (e.g. place, artist, brand, movie, book)",
    )
    take: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of results to return",
    )
    sample: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="Sample size constraint if supported",
    )

    @field_validator("query")
    @classmethod
    def clean_query(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Query cannot be blank or whitespace-only.")
        return cleaned

    def to_query_params(self) -> dict[str, str]:
        params: dict[str, str] = {
            "query": self.query,
            "take": str(self.take),
        }
        if self.type:
            params["type"] = self.type.strip()
        if self.sample is not None:
            params["sample"] = str(self.sample)
        return params


class TagParams(BaseModel):
    """Validated query parameters for GET /v2/tags."""

    query: str | None = Field(
        default=None,
        max_length=100,
        description="Keyword to search within tag taxonomy",
    )
    type: str | None = Field(
        default=None,
        description="Tag domain category filter (e.g. music, dining, fashion, brand)",
    )
    take: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of tags to return",
    )

    @field_validator("query")
    @classmethod
    def clean_query(cls, v: str | None) -> str | None:
        if v is not None:
            cleaned = v.strip()
            return cleaned if cleaned else None
        return None

    def to_query_params(self) -> dict[str, str]:
        params: dict[str, str] = {
            "take": str(self.take),
        }
        if self.query:
            params["query"] = self.query
        if self.type:
            params["type"] = self.type.strip()
        return params


_POINT_REGEX = re.compile(r"^POINT\s*\(\s*[-+]?[0-9]*\.?[0-9]+\s+[-+]?[0-9]*\.?[0-9]+\s*\)$", re.IGNORECASE)


class InsightParams(BaseModel):
    """Validated query parameters for GET /v2/insights.

    Qloo /v2/insights expects dot-notation parameters for filtering and signals.
    """

    filter_type: str | None = Field(
        default=None,
        description="Target category URN (e.g. urn:entity:place, urn:entity:artist, urn:entity:brand, urn:tag)",
    )
    signal_entities: list[str] = Field(
        default_factory=list,
        description="Seed entity IDs representing taste drivers",
    )
    signal_tags: list[str] = Field(
        default_factory=list,
        description="Seed tag IDs or taxonomy descriptors",
    )
    location_wkt: str | None = Field(
        default=None,
        description="WKT coordinate string, e.g. POINT(longitude latitude)",
    )
    location_radius: int | None = Field(
        default=None,
        ge=10,
        le=200000,
        description="Search radius in meters",
    )
    filter_tags: list[str] = Field(
        default_factory=list,
        description="Tag IDs to filter target entities",
    )
    exclude_entities: list[str] = Field(
        default_factory=list,
        description="Entity IDs to exclude from insights",
    )
    explainability: bool = Field(
        default=True,
        description="Whether to request explainability attribution in results",
    )
    take: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of insight items to return",
    )

    @field_validator("location_wkt")
    @classmethod
    def validate_wkt(cls, v: str | None) -> str | None:
        if v is not None:
            cleaned = v.strip()
            if not _POINT_REGEX.match(cleaned):
                raise ValueError(
                    f"Invalid location_wkt '{v}'. Expected format 'POINT(longitude latitude)' e.g. 'POINT(-73.985 40.748)'"
                )
            return cleaned
        return None

    @model_validator(mode="after")
    def validate_signals_or_filters(self) -> InsightParams:
        has_signal = bool(self.signal_entities or self.signal_tags or self.location_wkt)
        if not has_signal:
            raise ValueError(
                "InsightParams requires at least one signal (signal_entities, signal_tags) or location_wkt."
            )
        return self

    def to_query_params(self) -> dict[str, str]:
        params: dict[str, str] = {
            "take": str(self.take),
        }
        if self.filter_type:
            params["filter.type"] = self.filter_type
        if self.signal_entities:
            params["signal.interests.entities"] = ",".join(s.strip() for s in self.signal_entities if s.strip())
        if self.signal_tags:
            params["signal.interests.tags"] = ",".join(s.strip() for s in self.signal_tags if s.strip())
        if self.location_wkt:
            params["filter.location"] = self.location_wkt
        if self.location_radius is not None:
            params["filter.location.radius"] = str(self.location_radius)
        if self.filter_tags:
            params["filter.tags"] = ",".join(t.strip() for t in self.filter_tags if t.strip())
        if self.exclude_entities:
            params["filter.exclude.entities"] = ",".join(e.strip() for e in self.exclude_entities if e.strip())
        if self.explainability:
            params["feature.explainability"] = "true"
        return params
