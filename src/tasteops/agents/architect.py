"""TasteOps Experience Architect Agent.

Translates cultural strategy and Qloo taste recommendations into physical space programming:
spatial zoning, acoustic/music directives, and daypart transitions.
Guarantees strict provenance tracking.
"""

import logging

from tasteops.workflows.schemas import (
    DaypartProgram,
    ExperienceDesignInput,
    ExperienceDesignOutput,
    SpatialZone,
)

logger = logging.getLogger("tasteops.agents.architect")


class ExperienceArchitect:
    """Agent translating cultural strategy into sensory, sonic, and spatial architecture."""

    name: str = "Experience Architect"

    async def execute(self, payload: ExperienceDesignInput) -> ExperienceDesignOutput:
        """Designs physical and temporal experience directives."""
        strategy = payload.strategy
        matrix = payload.cultural_matrix

        logger.info(
            "[%s] Formulating spatial and sonic programming directives", self.name
        )

        provenance_ids: list[str] = list(strategy.provenance_entity_ids)

        # 1. Music Curation Directives
        top_artists = matrix.artists[:4]
        artist_names = [a.name for a in top_artists]
        artist_ids = [a.id for a in top_artists]
        for aid in artist_ids:
            if aid not in provenance_ids:
                provenance_ids.append(aid)

        artist_str = (
            ", ".join(artist_names)
            if artist_names
            else "curated ambient acoustic anchors"
        )
        music_directives = [
            f"Anchor sound identity around {artist_str} with zero aggressive dynamic peaks.",
            "Maintain warm analog mastering timbre; prioritize 33/45 RPM vinyl playback during evening dayparts.",
            "Transition tempo deliberately across the daily cycle: 65-80 BPM in morning, rising to 85-105 BPM at evening dusk.",
            "Keep vocal intrusion minimal during daytime dwell hours to maintain co-working focus.",
        ]

        # 2. Daypart Programs
        dayparts: list[DaypartProgram] = [
            DaypartProgram(
                time_window="07:00 - 12:00",
                title="Morning Ritual & Focus",
                atmosphere="Diffused natural daylight, soft 2700K ambient illumination, low acoustic density.",
                audio_theme="Warm acoustic guitar, minimalist piano, organic ambient soundscapes.",
                featured_artist_ids=artist_ids[:2],
            ),
            DaypartProgram(
                time_window="12:00 - 17:00",
                title="Afternoon Dwell & Creative Momentum",
                atmosphere="Warm interior lighting, focused task illumination, gentle buzz.",
                audio_theme="Lo-fi instrumental beats, modern jazz fusion, downtempo electronica.",
                featured_artist_ids=artist_ids[1:3]
                if len(artist_ids) > 2
                else artist_ids[:1],
            ),
            DaypartProgram(
                time_window="17:00 - 00:00",
                title="Evening Analog & Listening Session",
                atmosphere="Subdued 2200K amber lighting, directional spotlighting on record players and glassware.",
                audio_theme="Deep ambient electronic, Japanese city pop, selector vinyl deep-cuts.",
                featured_artist_ids=artist_ids[2:4]
                if len(artist_ids) >= 4
                else artist_ids[:2],
            ),
        ]

        # 3. Spatial Zones
        top_brands = matrix.brands[:3]
        brand_ids = [b.id for b in top_brands]
        for bid in brand_ids:
            if bid not in provenance_ids:
                provenance_ids.append(bid)

        zones: list[SpatialZone] = [
            SpatialZone(
                zone_name="Espresso & Order Bar",
                intended_mood="Crisp, efficient, tactile craft celebration.",
                design_reference_ids=brand_ids[:1],
                tactile_elements=[
                    "Fluted cast concrete counter",
                    "Brushed copper taps",
                    "Neutral stoneware ceramics",
                ],
            ),
            SpatialZone(
                zone_name="Acoustic Listening Lounge",
                intended_mood="Intimate, enveloping, contemplative.",
                design_reference_ids=brand_ids[1:2]
                if len(brand_ids) > 1
                else brand_ids[:1],
                tactile_elements=[
                    "Walnut wood acoustic paneling",
                    "Mohair upholstered banquettes",
                    "Integrated headphone jacks",
                ],
            ),
            SpatialZone(
                zone_name="Mezzanine Reading & Work Nook",
                intended_mood="Quiet, spacious, focused immersion.",
                design_reference_ids=[b.id for b in matrix.places[:1]]
                if matrix.places
                else [],
                tactile_elements=[
                    "Cast iron reading lamps",
                    "Smoked oak communal tables",
                    "Curated independent art monographs",
                ],
            ),
        ]

        # 4. Sensory Pairings
        sensory_pairings = [
            "Single-origin natural Ethiopian pour-over paired with low-frequency ambient drone.",
            "Chilled sparkling hojicha tea paired with mid-century teak and textured linen seating.",
            "Cedarwood, vetiver, and ozone scent diffusion timed to midday light transitions.",
        ]

        return ExperienceDesignOutput(
            music_curation_directives=music_directives,
            daypart_programs=dayparts,
            spatial_zones=zones,
            sensory_pairings=sensory_pairings,
            provenance_entity_ids=provenance_ids,
        )
