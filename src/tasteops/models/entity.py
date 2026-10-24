"""Normalized Qloo Entity Model."""

from typing import Any

from pydantic import BaseModel, Field, model_validator


class QlooEntity(BaseModel):
    """Normalized cultural entity representing a place, venue, artist, brand, etc."""

    id: str = Field(..., description="Unique Qloo entity ID")
    name: str = Field(..., description="Display name of the entity")
    type: str | None = Field(
        default=None, description="Entity category/type (e.g. place, artist, brand)"
    )
    subtype: str | None = Field(
        default=None, description="Secondary categorization (e.g. restaurant, cafe)"
    )
    urn: str | None = Field(
        default=None, description="URN identifier (e.g. urn:entity:place)"
    )
    description: str | None = Field(
        default=None, description="Optional brief description or summary"
    )
    tags: list[str] = Field(
        default_factory=list, description="Associated tag keywords or tag IDs"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional properties (location, address, etc.)"
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_raw_qloo_entity(cls, data: Any) -> Any:
        """Normalizes common variations in Qloo's raw entity payload."""
        if not isinstance(data, dict):
            return data

        # Resolve ID from id or entity_id or _id
        entity_id = data.get("id") or data.get("entity_id") or data.get("_id")
        if entity_id is not None:
            data["id"] = str(entity_id)

        # Resolve Name from name or title or label
        name = data.get("name") or data.get("title") or data.get("label")
        if name is not None:
            data["name"] = str(name)

        # Normalize tags if provided as objects or strings
        raw_tags = data.get("tags")
        if isinstance(raw_tags, list):
            norm_tags = []
            for tag in raw_tags:
                if isinstance(tag, str):
                    norm_tags.append(tag)
                elif isinstance(tag, dict) and "name" in tag:
                    norm_tags.append(tag["name"])
                elif isinstance(tag, dict) and "id" in tag:
                    norm_tags.append(tag["id"])
            data["tags"] = norm_tags

        return data
