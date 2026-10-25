"""Normalized Qloo Insight Model."""

from typing import Any

from pydantic import BaseModel, Field, model_validator


class QlooInsight(BaseModel):
    """Normalized cross-domain affinity insight returned from /v2/insights."""

    id: str = Field(..., description="Unique entity or tag ID for the insight")
    name: str = Field(..., description="Entity or tag name")
    type: str | None = Field(
        default=None,
        description="Insight entity or tag category (e.g. urn:entity:place, urn:entity:artist)",
    )
    affinity: float = Field(
        ...,
        description="Normalized affinity index or probability score (typically 0.0 to 1.0)",
    )
    score: float | None = Field(
        default=None, description="Raw ranking score or index from Qloo"
    )
    explainability: list[str] = Field(
        default_factory=list,
        description="Affinity explanations, shared traits, or seed attributions",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata, location, tags, etc."
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_raw_qloo_insight(cls, data: Any) -> Any:
        """Normalizes variations in Qloo /v2/insights response items."""
        if not isinstance(data, dict):
            return data

        # Resolve ID
        item_id = data.get("id") or data.get("entity_id") or data.get("tag_id")
        if item_id is not None:
            data["id"] = str(item_id)

        # Resolve Name
        name = data.get("name") or data.get("title") or data.get("label") or "Unknown"
        data["name"] = str(name)

        # Resolve affinity/score
        # Qloo can return 'affinity', 'score', 'rank', or 'confidence'
        raw_affinity = data.get("affinity")
        raw_score = data.get("score")

        if raw_affinity is None and raw_score is not None:
            # If score is given on 0-100 scale, normalize to 0-1
            try:
                numeric_score = float(raw_score)
                data["score"] = numeric_score
                if numeric_score > 1.0 and numeric_score <= 100.0:
                    data["affinity"] = round(numeric_score / 100.0, 4)
                elif numeric_score <= 1.0:
                    data["affinity"] = round(numeric_score, 4)
                else:
                    data["affinity"] = 1.0
            except ValueError, TypeError:
                data["affinity"] = 0.0
        elif raw_affinity is not None:
            try:
                numeric_affinity = float(raw_affinity)
                if numeric_affinity > 1.0 and numeric_affinity <= 100.0:
                    data["affinity"] = round(numeric_affinity / 100.0, 4)
                    data["score"] = numeric_affinity
                else:
                    data["affinity"] = round(numeric_affinity, 4)
                    data["score"] = (
                        raw_score if raw_score is not None else numeric_affinity
                    )
            except ValueError, TypeError:
                data["affinity"] = 0.0
        else:
            data["affinity"] = 0.0

        # Resolve explainability
        explain = (
            data.get("explainability") or data.get("reasons") or data.get("explanation")
        )
        if isinstance(explain, list):
            data["explainability"] = [
                str(x.get("text") if isinstance(x, dict) and "text" in x else x)
                for x in explain
            ]
        elif isinstance(explain, str):
            data["explainability"] = [explain]

        return data
