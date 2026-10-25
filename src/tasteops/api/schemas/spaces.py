"""TasteOps API Space Schemas.

Defines request and response schemas for physical venue spaces and analysis triggers.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class SpaceCreateRequest(BaseModel):
    """Payload to register a new physical space venue."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Descriptive name of the physical venue or concept",
        examples=["Chelsea Analog Audio Kissa"],
    )
    business_type: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="Type of venue or establishment",
        examples=["Analog Vinyl Listening Bar & Cafe"],
    )
    location: dict[str, Any] | str | None = Field(
        default=None,
        description="Geographic coordinates, WKT geometry, or address description",
        examples=[{"latitude": 40.7484, "longitude": -73.9857, "radius_meters": 2000}],
    )
    target_audience: str | None = Field(
        default=None,
        description="Demographic or psychographic profile of intended visitors",
        examples=["Audiophiles, music collectors, design purists aged 25-45"],
    )
    positioning: str | None = Field(
        default=None,
        description="Market and aesthetic positioning",
        examples=["Japanese-inspired craft audio sanctuary"],
    )
    desired_mood: str | None = Field(
        default=None,
        description="Sensory, acoustic, and atmospheric energy",
        examples=["Warm acoustic focus, minimalist, intimate"],
    )
    budget: str | None = Field(
        default=None,
        description="Budget tier or capital allocation",
        examples=["High-end boutique"],
    )
    constraints: list[str] | dict[str, Any] | None = Field(
        default=None,
        description="Physical, architectural, acoustic, or operational constraints",
        examples=[["SPL capped at 75dB", "No digital screens in seating zones"]],
    )
    anchor_entities: list[str] = Field(
        default_factory=list,
        description="Known reference brands, venues, or aesthetics grounding the concept",
        examples=[["Blue Bottle Coffee", "Japanese minimalism"]],
    )
    brand: str | None = Field(
        default=None,
        description="Brand identity or parent corporate brand",
        examples=["Maison Kitsuné", "Aman Resorts"],
    )
    goals: list[str] | str | None = Field(
        default=None,
        description="Core operational, cultural, or activation goals",
        examples=[
            [
                "Bridge Franco-Japanese indie music with analog craft",
                "Foster listening community",
            ]
        ],
    )
    cultural_preferences: list[str] | str | None = Field(
        default=None,
        description="Aesthetic preferences, motifs, or cultural interests",
        examples=[["Japanese jazz kissa culture", "Mid-century modernist timber"]],
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional custom properties or client metadata",
    )


class SpaceResponse(BaseModel):
    """Response model representing a registered physical space."""

    space_id: str = Field(..., description="Unique space identifier (space_...)")
    name: str = Field(..., description="Descriptive venue name")
    business_type: str = Field(..., description="Venue category")
    location: Any | None = Field(default=None, description="Location specification")
    brief: dict[str, Any] = Field(
        default_factory=dict,
        description="Normalized physical space brief and anchor signals",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Custom metadata"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Space registration timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Last update timestamp",
    )


class AnalyzeSpaceRequest(BaseModel):
    """Request payload to initiate cultural intelligence analysis for a space."""

    user_input: str | None = Field(
        default=None,
        description="Optional custom natural language activation brief override",
    )
    hints: dict[str, Any] | None = Field(
        default=None,
        description="Optional structured hints overriding space default attributes",
    )
    take_per_category: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of cultural affinity entities to retrieve per category from Qloo",
    )
    auto_run: bool = Field(
        default=True,
        description="Whether to run the pipeline forward until the Human Approval Gate is reached",
    )
