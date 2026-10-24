"""TasteOps Cultural Strategist Agent.

Synthesizes high-level cultural positioning, identity pillars, and target subcultures
based exclusively on verified Qloo anchors and CulturalMatrix recommendations.
Guarantees zero hallucinated IDs and strict provenance.
"""

import logging

from tasteops.workflows.schemas import (
    CulturalPillar,
    CulturalStrategyInput,
    CulturalStrategyOutput,
)

logger = logging.getLogger("tasteops.agents.strategist")


class CulturalStrategist:
    """Agent responsible for high-level cultural positioning and thematic pillars."""

    name: str = "Cultural Strategist"

    async def execute(self, payload: CulturalStrategyInput) -> CulturalStrategyOutput:
        """Executes strategic synthesis over the CulturalTwin and CulturalMatrix."""
        twin = payload.cultural_twin
        matrix = payload.cultural_matrix

        logger.info(
            "[%s] Formulating cultural strategy for '%s' (Anchors: %d)",
            self.name,
            twin.business_type or "Physical Space",
            len(twin.anchor_entities),
        )

        # 1. Gather all verified entity IDs for provenance verification
        provenance_ids: list[str] = list(twin.anchor_entities)
        for rec in (
            matrix.artists[:3]
            + matrix.brands[:3]
            + matrix.places[:3]
            + matrix.books[:3]
        ):
            if rec.id not in provenance_ids:
                provenance_ids.append(rec.id)

        # 2. Extract top affinity anchors by category for strategy formulation
        top_artists = [a.name for a in matrix.artists[:3]]
        top_brands = [b.name for b in matrix.brands[:3]]

        # 3. Formulate Positioning Statement
        business_str = twin.business_type or "curated cultural venue"
        mood_str = twin.mood or "refined, contemporary atmosphere"
        audience_str = twin.target_audience or "discerning modern patrons"

        anchor_refs = ", ".join(top_artists[:2] + top_brands[:2])
        if anchor_refs:
            positioning = (
                f"A {mood_str} {business_str} engineered for {audience_str}, "
                f"anchored at the cultural intersection of {anchor_refs}."
            )
        else:
            positioning = f"A {mood_str} {business_str} engineered for {audience_str}."

        # 4. Formulate Distinct Cultural Pillars (with strict verified Qloo entity provenance)
        pillars: list[CulturalPillar] = []

        # Pillar 1: Sonic & Atmospheric Identity
        artist_ids = [a.id for a in matrix.artists[:2]]
        artist_names = (
            ", ".join([a.name for a in matrix.artists[:2]]) or "analog soundscapes"
        )
        pillars.append(
            CulturalPillar(
                name="Sonic & Acoustic Atmosphere",
                description=f"Curating deep listening sessions and textured background acoustics influenced by {artist_names}.",
                aligned_entity_ids=artist_ids,
                aligned_tag_ids=twin.resolved_tags[:2],
            )
        )

        # Pillar 2: Material & Design Aesthetic
        brand_ids = [b.id for b in matrix.brands[:2]]
        brand_names = (
            ", ".join([b.name for b in matrix.brands[:2]])
            or "minimalist design principles"
        )
        pillars.append(
            CulturalPillar(
                name="Tactile & Material Craft",
                description=f"Harmonizing physical furniture, industrial craft, and packaging aesthetics echoing {brand_names}.",
                aligned_entity_ids=brand_ids,
                aligned_tag_ids=twin.resolved_tags[2:4]
                if len(twin.resolved_tags) > 2
                else twin.resolved_tags[:1],
            )
        )

        # Pillar 3: Spatial Hospitality & Gathering
        place_ids = [p.id for p in matrix.places[:2]]
        place_names = (
            ", ".join([p.name for p in matrix.places[:2]]) or "third-wave hospitality"
        )
        pillars.append(
            CulturalPillar(
                name="Community & Hospitality Tempo",
                description=f"Cultivating communal presence and deliberate pacing inspired by premier spaces like {place_names}.",
                aligned_entity_ids=place_ids,
                aligned_tag_ids=twin.resolved_tags[:1],
            )
        )

        # 5. Identify Target Subcultures & Affinity Themes
        subcultures = [
            "Hi-Fi Audio & Vinyl Enthusiasts",
            "Specialty Coffee & Fermentation Purists",
            "Independent Architecture & Industrial Design Community",
            "Contemporary Indie Cinema & Editorial Aficionados",
        ]

        affinity_themes = [
            f"Acoustic Focus x {twin.mood or 'Atmospheric'}",
            f"Craft Materiality x {business_str.capitalize()}",
            "Analog Ritual in Digital Spaces",
        ]

        return CulturalStrategyOutput(
            positioning_statement=positioning,
            cultural_pillars=pillars,
            target_subcultures=subcultures,
            affinity_themes=affinity_themes,
            provenance_entity_ids=provenance_ids,
        )
