"""TasteOps Experience Architect Agent.

Purpose:
Design a coherent cultural experience for the physical space based on CulturalTwin and CulturalMatrix.

Generates:
1. Sonic Identity (acoustic architecture, music directives, daypart schedules, curated artists)
2. Reading/Library Identity (editorial philosophy, curated publications, display strategy)
3. Brand Ecosystem (material craft, vetted brand partners, tactile palette)
4. Local Experience Ecosystem (neighborhood context, spatial hospitality benchmarks)
5. Cultural Programming Ideas (recurring salons, format descriptions, community outcomes)
6. Atmosphere Guidelines (acoustic decibel targets, lighting Kelvin, hospitality choreography, spatial zones)

Key Guarantees:
- Every recommendation contains: recommendation, Qloo evidence, cultural rationale, confidence, expected role.
- Never invents Qloo evidence.
- Does not blindly accept every Qloo result; applies coherence filtering.
- Fully machine-readable structured JSON / Pydantic schema.
"""

from __future__ import annotations

import logging

from tasteops.models.cultural_matrix import (
    CulturalMatrix,
    CulturalRecommendation,
    CulturalTwin,
)
from tasteops.workflows.schemas import (
    AtmosphereGuidelines,
    BrandEcosystem,
    CulturalProgrammingIdeas,
    DaypartProgram,
    ExperienceDesignInput,
    ExperienceDesignOutput,
    ExperienceRecommendation,
    LocalExperienceEcosystem,
    ProgrammingActivation,
    ReadingLibraryIdentity,
    SonicIdentity,
    SpatialZone,
)

logger = logging.getLogger("tasteops.agents.architect")


class ExperienceArchitect:
    """Agent translating CulturalTwin and CulturalMatrix into a coherent physical-space cultural experience."""

    name: str = "Experience Architect"

    async def design_experience(
        self,
        cultural_twin: CulturalTwin,
        cultural_matrix: CulturalMatrix,
    ) -> ExperienceDesignOutput:
        """Designs physical, acoustic, and spatial experience directives."""
        if isinstance(cultural_twin, dict):
            cultural_twin = CulturalTwin.model_validate(cultural_twin)
        elif not isinstance(cultural_twin, CulturalTwin):
            raise TypeError(
                f"Expected CulturalTwin or dict, got {type(cultural_twin).__name__}"
            )

        if isinstance(cultural_matrix, dict):
            cultural_matrix = CulturalMatrix.model_validate(cultural_matrix)
        elif not isinstance(cultural_matrix, CulturalMatrix):
            raise TypeError(
                f"Expected CulturalMatrix or dict, got {type(cultural_matrix).__name__}"
            )

        logger.info(
            "[%s] Designing coherent cultural experience for '%s'",
            self.name,
            cultural_twin.business_type or "Physical Space",
        )

        provenance_ids: set[str] = set(cultural_twin.resolved_entity_ids)

        # ---------------------------------------------------------------------
        # Curatorial Coherence Filtering
        # ---------------------------------------------------------------------
        # Do not blindly accept every result; filter out low-affinity items and items violating exclusions.
        curated_artists = self._curate_candidates(
            candidates=cultural_matrix.artists,
            twin=cultural_twin,
            category="artist",
            role_template="Primary sonic anchor during listening sessions; establishes the acoustic density and vinyl rotation focus",
            max_items=4,
        )
        curated_books = self._curate_candidates(
            candidates=cultural_matrix.books,
            twin=cultural_twin,
            category="book",
            role_template="Tactile reading monograph on communal oak tables; stimulates contemplative patron dwell time",
            max_items=3,
        )
        curated_brands = self._curate_candidates(
            candidates=cultural_matrix.brands,
            twin=cultural_twin,
            category="brand",
            role_template="Physical tableware, lighting, or amenity partner; embodies tactile material craft",
            max_items=3,
        )
        curated_places = self._curate_candidates(
            candidates=cultural_matrix.places + cultural_matrix.destinations,
            twin=cultural_twin,
            category="place",
            role_template="Spatial hospitality and patron pacing benchmark for room acoustics and social density",
            max_items=3,
        )

        # Record all vetted Qloo entity IDs for provenance tracking
        for rec in curated_artists + curated_books + curated_brands + curated_places:
            ent_id = rec.qloo_evidence.get("entity_id") or rec.qloo_evidence.get("id")
            if ent_id:
                provenance_ids.add(str(ent_id))

        # ---------------------------------------------------------------------
        # 1. Sonic Identity
        # ---------------------------------------------------------------------
        artist_names = [r.recommendation for r in curated_artists]
        artist_ids = [
            str(r.qloo_evidence.get("entity_id", ""))
            for r in curated_artists
            if r.qloo_evidence.get("entity_id")
        ]
        artist_ref_str = (
            ", ".join(artist_names[:3]) if artist_names else "curated analog acoustics"
        )

        music_directives = [
            f"Anchor sonic identity around the textured acoustic palette of {artist_ref_str} with zero aggressive dynamic peaks.",
            "Maintain warm analog mastering timbre; prioritize 33/45 RPM vinyl playback during evening dwell hours.",
            "Calibrate tempo deliberately across dayparts: 65-80 BPM in morning, rising to 85-105 BPM at evening transition.",
            "Keep vocal intrusion minimal during daytime co-working hours to protect patron focus and conversational clarity.",
        ]

        dayparts: list[DaypartProgram] = [
            DaypartProgram(
                time_window="07:00 - 12:00",
                title="Morning Ritual & Focus",
                atmosphere="Diffused natural daylight, soft 2700K warm illumination, low acoustic density.",
                audio_theme="Warm acoustic guitar, minimalist piano, organic ambient soundscapes.",
                featured_artist_ids=artist_ids[:2],
            ),
            DaypartProgram(
                time_window="12:00 - 17:00 (Afternoon Momentum)",
                title="Afternoon Dwell & Creative Focus",
                atmosphere="Warm task lighting, focused communal table illumination, gentle hum.",
                audio_theme="Lo-fi instrumental rhythms, contemporary jazz fusion, downtempo electronica.",
                featured_artist_ids=artist_ids[1:3]
                if len(artist_ids) > 2
                else artist_ids[:1],
            ),
            DaypartProgram(
                time_window="17:00 - 00:00 (Evening Listening Session)",
                title="Evening Analog Sanctuary",
                atmosphere="Subdued 2200K amber lighting, directional spotlighting on turntables and glassware.",
                audio_theme="Deep ambient electronic, Japanese city pop, selector vinyl deep-cuts.",
                featured_artist_ids=artist_ids[2:4]
                if len(artist_ids) >= 4
                else artist_ids[:2],
            ),
        ]

        sonic_identity = SonicIdentity(
            overview=(
                f"A deeply considered acoustic architecture engineered for {cultural_twin.business_type or 'the physical space'}, "
                f"harmonizing with {cultural_twin.mood_profile or 'warm, intimate atmospheres'}. Music is treated as a physical material "
                "with deliberate spatial resonance rather than passive background noise."
            ),
            acoustic_profile="Warm analog midrange focus, smooth non-fatiguing high frequencies, and controlled sub-bass resonance (SPL < 75dB)",
            playback_mediums=[
                "Dual audiophile direct-drive turntables with moving-coil cartridges (33/45 RPM)",
                "Custom vacuum-tube pre-amplification stage",
                "Lossless 24-bit/96kHz digital streaming strictly for off-peak transitions",
            ],
            directives=music_directives,
            curated_recommendations=curated_artists,
            dayparts=dayparts,
        )

        # ---------------------------------------------------------------------
        # 2. Reading / Library Identity
        # ---------------------------------------------------------------------
        reading_identity = ReadingLibraryIdentity(
            overview=(
                "A tactile publication library embedded into the venue's social fabric. Print media is curated as an intentional "
                "antidote to screen fatigue, encouraging slow patron dwell time and tactile engagement."
            ),
            curation_themes=[
                "Architectural Minimalism & Japanese Spatial Aesthetics (Ma)",
                "Independent Editorial Periodicals & Slow Design Monographs",
                "Sound Studies, Analog Acoustics & Contemporary Music Criticism",
                "Artisanal Culinary Traditions & Traceable Fermentation",
            ],
            curated_recommendations=curated_books,
            display_strategy=(
                "Integrated into perimeter smoked-oak shelving and communal work tables. "
                "Curated facing-forward with dedicated brass reading task lamps to invite tactile browsing."
            ),
        )

        # ---------------------------------------------------------------------
        # 3. Brand Ecosystem
        # ---------------------------------------------------------------------
        brand_ecosystem = BrandEcosystem(
            overview=(
                "A cohesive network of craft partners whose physical products furnish and elevate the space. "
                "Partnerships are selected exclusively for material authenticity, understated design, and zero visual commercial clutter."
            ),
            material_palette=[
                "Solid white oak and smoked walnut millwork",
                "Handcrafted matte stoneware ceramics in neutral mineral glazes",
                "Brushed unlacquered brass hardware that patinas with patron touch",
                "Washed heavy linen textiles and raw acoustic wool wall hangings",
            ],
            curated_recommendations=curated_brands,
            partnership_criteria=[
                "Subtle physical co-existence: No overt commercial logos or promotional signage in patron zones.",
                "Proven craft provenance: Ethical sourcing, repairable construction, and tactile materiality.",
                "Shared subcultural values: Genuine credibility among design, acoustic, and culinary purists.",
            ],
        )

        # ---------------------------------------------------------------------
        # 4. Local Experience Ecosystem
        # ---------------------------------------------------------------------
        venue_location_str = "Chelsea / West Side Cultural District"
        if cultural_twin.location:
            venue_location_str = f"Coordinates ({cultural_twin.location.latitude}, {cultural_twin.location.longitude}) within {cultural_twin.location.radius_meters}m radius"

        local_ecosystem = LocalExperienceEcosystem(
            overview=(
                "A contextual neighborhood ecosystem grounding the venue within its immediate physical and cultural landscape. "
                "Learns from peer benchmark spaces to optimize patron flow, acoustic dampening, and community loyalty."
            ),
            neighborhood_context=f"Embedded in {venue_location_str}, serving a dense concentration of design studios, galleries, and cultural purists.",
            curated_recommendations=curated_places,
            community_synergies=[
                "Cross-patronage with neighboring independent galleries and contemporary design showrooms.",
                "Collaborative neighborhood cultural walks linking acoustic listening, specialty coffee, and architecture.",
                "Reciprocal guest residencies with peer third-wave hospitality spaces.",
            ],
        )

        # ---------------------------------------------------------------------
        # 5. Cultural Programming Ideas
        # ---------------------------------------------------------------------
        programming_ideas = CulturalProgrammingIdeas(
            overview=(
                "A dynamic yet unhurried event calendar designed to build genuine cultural capital and community dwell time. "
                "Events celebrate the core pillars of deep listening, tactile craft, and deliberate conversation."
            ),
            programming_pillars=[
                "Analog Listening Salons (Full album plays with lights dimmed and phones silenced)",
                "Design & Editorial Conversations (Intimate author and architect Q&As)",
                "Craft Sourcing Tastings (Single-origin coffee cuppings and tea ceremonies)",
            ],
            activations=[
                ProgrammingActivation(
                    title="Deep Listening Sunday: The Album in Full",
                    cadence="Weekly Sunday, 18:00 - 21:00",
                    format_description=(
                        "Lighting dimmed to 2200K warm amber; patron smartphones placed in silent pouches upon entry. "
                        "A seminal full-length vinyl album is played from start to finish without interruption, followed by a curated conversation."
                    ),
                    featured_recommendations=curated_artists[:2],
                    target_audience="Audiophiles, music collectors, and reflective creative professionals",
                    expected_outcome="Establishes premier cultural authority in sound curation; drives extended Sunday evening dwell time.",
                ),
                ProgrammingActivation(
                    title="Tactile Monograph Salon: Design & Architecture",
                    cadence="Bi-weekly Thursday, 17:30 - 19:30",
                    format_description=(
                        "An informal twilight gathering featuring a newly acquired design or architectural monograph. "
                        "Guest designers discuss materiality, negative space, and physical craft over pour-over and tea service."
                    ),
                    featured_recommendations=curated_books[:2],
                    target_audience="Architects, interior designers, and print media collectors",
                    expected_outcome="Strengthens daytime community loyalty and establishes the space as a creative neighborhood clubhouse.",
                ),
                ProgrammingActivation(
                    title="Craft Maker Residency: Form & Function",
                    cadence="Monthly First Saturday, 14:00 - 17:00",
                    format_description=(
                        "In-venue showcase with an independent ceramicist or industrial design partner. "
                        "Patrons interact directly with the makers of the venue's physical tableware and furniture."
                    ),
                    featured_recommendations=curated_brands[:2],
                    target_audience="Craft connoisseurs and design-conscious patrons",
                    expected_outcome="Deepens material credibility and reinforces ethical, artisan-first brand positioning.",
                ),
            ],
        )

        # ---------------------------------------------------------------------
        # 6. Atmosphere Guidelines & Spatial Zones
        # ---------------------------------------------------------------------
        brand_ref_ids = [
            str(r.qloo_evidence.get("entity_id", ""))
            for r in curated_brands
            if r.qloo_evidence.get("entity_id")
        ]
        place_ref_ids = [
            str(r.qloo_evidence.get("entity_id", ""))
            for r in curated_places
            if r.qloo_evidence.get("entity_id")
        ]

        spatial_zones: list[SpatialZone] = [
            SpatialZone(
                zone_name="Espresso & Order Bar",
                intended_mood="Crisp, efficient, tactile craft celebration.",
                design_reference_ids=brand_ref_ids[:1],
                tactile_elements=[
                    "Fluted cast concrete counter",
                    "Brushed copper taps",
                    "Neutral stoneware ceramics",
                ],
            ),
            SpatialZone(
                zone_name="Acoustic Listening Lounge",
                intended_mood="Intimate, enveloping, contemplative.",
                design_reference_ids=brand_ref_ids[1:2]
                if len(brand_ref_ids) > 1
                else brand_ref_ids[:1],
                tactile_elements=[
                    "Walnut wood acoustic paneling",
                    "Mohair upholstered banquettes",
                    "Integrated headphone jacks and turntable display",
                ],
            ),
            SpatialZone(
                zone_name="Mezzanine Reading & Work Nook",
                intended_mood="Quiet, spacious, focused immersion.",
                design_reference_ids=place_ref_ids[:1],
                tactile_elements=[
                    "Cast iron reading lamps with 2700K warm LED",
                    "Smoked oak communal work tables",
                    "Curated independent monographs on forward-facing shelving",
                ],
            ),
        ]

        sensory_pairings = [
            "Single-origin natural Ethiopian pour-over paired with low-frequency ambient drone soundscapes.",
            "Chilled sparkling hojicha tea paired with mid-century teak and textured linen seating.",
            "Cedarwood, hinoki, and ozone scent diffusion timed to midday light transitions.",
        ]

        atmosphere_guidelines = AtmosphereGuidelines(
            sonic_parameters={
                "max_spl_daytime": "72 dBA (allows effortless conversation without raising voice)",
                "max_spl_evening": "78 dBA (immersive listening while maintaining conversational comfort)",
                "acoustic_absorption": "NRC >= 0.85 on rear acoustic walls via slatted timber and recycled felt",
                "speaker_configuration": "Point-source audiophile horn speakers positioned at ear level for seated patrons",
            },
            lighting_parameters={
                "daytime_color_temperature": "2700K (complements natural daylight without cold blue tint)",
                "evening_color_temperature": "2200K (warm candlelit amber ambience)",
                "dimming_protocol": "Continuous gradual dimming aligned with solar sunset over 45 minutes",
                "glare_control": "Zero exposed bulbs; deep-recessed and indirect perimeter cove illumination",
            },
            olfactory_and_thermal={
                "scent_notes": "Japanese Hinoki cypress, cedarwood, subtle dried tea leaf, clean linen",
                "diffusion_cadence": "Intermittent micro-diffusion (5 minutes on, 20 minutes off)",
                "thermal_setpoint": "69°F (20.5°C) with low air-velocity displacement ventilation",
            },
            hospitality_tempo=(
                "Choreographed for unhurried presence: Warm, understated eye contact upon arrival; "
                "deliberate 3-minute pour-over preparation explained with quiet humility; "
                "zero turnover pressure or check-dropping until explicitly requested by patron."
            ),
            spatial_zones=spatial_zones,
            sensory_pairings=sensory_pairings,
        )

        return ExperienceDesignOutput(
            sonic_identity=sonic_identity,
            reading_library_identity=reading_identity,
            brand_ecosystem=brand_ecosystem,
            local_experience_ecosystem=local_ecosystem,
            cultural_programming_ideas=programming_ideas,
            atmosphere_guidelines=atmosphere_guidelines,
            provenance_entity_ids=sorted(provenance_ids),
            music_curation_directives=music_directives,
            daypart_programs=dayparts,
            spatial_zones=spatial_zones,
            sensory_pairings=sensory_pairings,
        )

    async def execute(self, payload: ExperienceDesignInput) -> ExperienceDesignOutput:
        """Executes experience design from structured input payload."""
        if isinstance(payload, dict):
            payload = ExperienceDesignInput.model_validate(payload)
        elif not isinstance(payload, ExperienceDesignInput):
            raise TypeError(
                f"Expected ExperienceDesignInput or dict, got {type(payload).__name__}"
            )

        twin = payload.cultural_twin
        if twin is None:
            # Fallback twin reconstruction from strategy if twin not directly passed
            twin = CulturalTwin(
                business_type="Curated Physical Space",
                mood=payload.strategy.positioning_statement
                if payload.strategy
                else "Refined atmosphere",
                anchor_entities=payload.strategy.provenance_entity_ids
                if payload.strategy
                else [],
            )

        return await self.design_experience(
            cultural_twin=twin,
            cultural_matrix=payload.cultural_matrix,
        )

    # -------------------------------------------------------------------------
    # Curatorial Filtering & Recommendation Structuring
    # -------------------------------------------------------------------------
    def _curate_candidates(
        self,
        candidates: list[CulturalRecommendation],
        twin: CulturalTwin,
        category: str,
        role_template: str,
        max_items: int = 3,
    ) -> list[ExperienceRecommendation]:
        """Filters, ranks, and structures recommendations for coherent cultural experience.

        Applies:
        - Affinity threshold filter (rejects items below threshold).
        - Cultural constraints & exclusions filter (rejects excluded genres or commercial tags).
        - Coherence rationale generation connecting Qloo evidence to the space.
        """
        curated: list[ExperienceRecommendation] = []
        exclusions_lower = [e.lower() for e in twin.exclusions]

        for item in candidates:
            # 1. Affinity threshold: Ensure candidate possesses demonstrable audience overlap
            if item.affinity < 0.50:
                continue

            # 2. Exclusions filter: Reject items clashing with cultural anti-patterns
            item_name_lower = item.name.lower()
            if any(
                ex in item_name_lower or item_name_lower in ex
                for ex in exclusions_lower
                if ex.strip()
            ):
                logger.info(
                    "[%s] Candidate '%s' rejected by cultural exclusion rule.",
                    self.name,
                    item.name,
                )
                continue

            # 3. Formulate specific cultural rationale based on Qloo evidence
            rationale = self._build_cultural_rationale(item, twin, category)

            # 4. Formulate contextual expected role in physical space
            role = self._build_expected_role(item, twin, category, role_template)

            # 5. Build immutable Qloo evidence dictionary
            evidence = {
                "entity_id": item.id,
                "entity_name": item.name,
                "type": item.type,
                "affinity": item.affinity,
                "score": item.score,
                "confidence": item.confidence,
                "source_query": item.source_query,
                "source_signal": item.source_signal,
                "explainability": item.explainability,
            }

            curated.append(
                ExperienceRecommendation(
                    recommendation=item.name,
                    qloo_evidence=evidence,
                    cultural_rationale=rationale,
                    confidence=round(item.affinity, 3),
                    expected_role=role,
                    category=category,
                )
            )

            if len(curated) >= max_items:
                break

        return curated

    def _build_cultural_rationale(
        self,
        item: CulturalRecommendation,
        twin: CulturalTwin,
        category: str,
    ) -> str:
        """Formulates precise curatorial rationale explaining alignment with CulturalTwin."""
        venue = twin.business_type or "physical space"
        mood = twin.mood or twin.mood_profile or "acoustic warmth"

        if category == "artist":
            return (
                f"Demonstrates a {round(item.affinity * 100)}% audience taste overlap with {venue} patrons. "
                f"Contributes an organic, textured sonic palette that reinforces {mood} without jarring conversational distraction."
            )
        if category == "book":
            return (
                f"Reflects the editorial curiosity and contemplative aesthetic of {venue} patrons (affinity: {round(item.affinity * 100)}%). "
                "Enriches the physical environment with tangible print publication authority."
            )
        if category == "brand":
            return (
                f"Shares high brand affinity ({round(item.affinity * 100)}%) with core space anchors. "
                "Embodies material restraint, ethical craftsmanship, and understated physical beauty."
            )
        if category == "place":
            return (
                f"Exemplifies premier spatial hospitality standards with {round(item.affinity * 100)}% patron resonance. "
                "Serves as an architectural and acoustic layout benchmark for dwell time and patron intimacy."
            )
        return f"Vetted cultural anchor ({round(item.affinity * 100)}% affinity) contributing to the coherent identity of {venue}."

    def _build_expected_role(
        self,
        item: CulturalRecommendation,
        twin: CulturalTwin,
        category: str,
        role_template: str,
    ) -> str:
        """Assigns an explicit physical space, acoustic, or operational role."""
        if category == "artist":
            return f"Featured artist on vinyl and high-resolution digital playback during evening listening dayparts ({item.name})"
        if category == "book":
            return f"Display monograph on communal oak tables and mezzanine reading shelves for patron browsing ({item.name})"
        if category == "brand":
            return f"Material tableware, amenity, or hardware partner specifying physical ceramics and tactile fixtures ({item.name})"
        if category == "place":
            return f"Spatial zoning and operational benchmark guiding acoustic dampening, seating ergonomics, and patron pacing ({item.name})"
        return role_template
