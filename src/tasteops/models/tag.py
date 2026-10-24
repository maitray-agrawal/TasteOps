"""Normalized Qloo Tag Model."""

from typing import Any

from pydantic import BaseModel, Field, model_validator


class QlooTag(BaseModel):
    """Normalized cultural or categorical tag (e.g. genre, vibe, aesthetic, dining style)."""

    id: str = Field(..., description="Unique tag ID or slug")
    name: str = Field(..., description="Readable label or name of the tag")
    category: str | None = Field(
        default=None, description="Tag domain category (e.g. music, dining, fashion)"
    )
    urn: str | None = Field(
        default=None, description="URN descriptor (e.g. urn:tag:dining:cuisine)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional tag metadata or statistics"
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_raw_qloo_tag(cls, data: Any) -> Any:
        """Normalizes variations in raw Qloo tag payloads."""
        if not isinstance(data, dict):
            return data

        tag_id = data.get("id") or data.get("tag_id") or data.get("slug")
        if tag_id is not None:
            data["id"] = str(tag_id)

        name = data.get("name") or data.get("label") or data.get("title")
        if name is not None:
            data["name"] = str(name)

        return data
