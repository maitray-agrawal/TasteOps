"""TasteOps Cultural Strategist Agent.

Purpose:
Transform a user's physical-space brief into a structured, validated CulturalTwin.
Synthesizes audience profile, cultural themes, mood breakdown, and cultural guardrails
based strictly on verified Qloo entities and tags resolved via the Cultural Intelligence MCP.

Key Guarantees:
- Always resolves entities/tags using the Cultural Intelligence MCP.
- Never invents Qloo IDs or tags; unknown terms are rejected from verified collections.
- Explains why each cultural signal matters to the space's positioning.
- Does NOT produce recommendations yet (the output is the foundational CulturalTwin).
"""

from __future__ import annotations

import logging
from typing import Any

from tasteops.agents.mcp_adapter import CulturalIntelligenceMCPAdapter
from tasteops.models.cultural_matrix import (
    CulturalTwin,
    LocationInput,
    PhysicalSpaceBrief,
    ResolvedEntity,
    ResolvedTag,
)
from tasteops.workflows.schemas import (
    CulturalPillar,
    CulturalStrategyInput,
    CulturalStrategyOutput,
)

logger = logging.getLogger("tasteops.agents.strategist")


class CulturalStrategist:
    """Agent responsible for transforming briefs into CulturalTwins and formulating cultural strategy."""

    name: str = "Cultural Strategist"

    def __init__(
        self, mcp_adapter: CulturalIntelligenceMCPAdapter | None = None
    ) -> None:
        self.mcp = mcp_adapter or CulturalIntelligenceMCPAdapter()

    # -------------------------------------------------------------------------
    # Core Function: Transform Physical Space Brief into CulturalTwin
    # -------------------------------------------------------------------------
    async def transform_brief(
        self, brief: PhysicalSpaceBrief | dict[str, Any]
    ) -> CulturalTwin:
        """Transforms a physical-space brief into a structured, validated CulturalTwin.

        Steps:
        1. Ingest brief (business_type, location, target_audience, positioning, desired_mood, budget, constraints, anchor_entities).
        2. Resolve entities and tags strictly via Cultural Intelligence MCP server.
        3. Never invent Qloo IDs.
        4. Explain why each verified cultural signal matters to the space.
        5. Synthesize audience profile, cultural themes, mood breakdown, guardrails, and exclusions.
        6. Return foundational CulturalTwin without recommendations.
        """
        if isinstance(brief, dict):
            brief_obj = PhysicalSpaceBrief.model_validate(brief)
        elif isinstance(brief, PhysicalSpaceBrief):
            brief_obj = brief
        else:
            raise TypeError(
                f"Expected PhysicalSpaceBrief or dict, got {type(brief).__name__}"
            )

        logger.info(
            "[%s] Transforming physical-space brief for '%s' (Anchors: %d)",
            self.name,
            brief_obj.business_type,
            len(brief_obj.anchor_entities),
        )

        # 1. Normalize Location
        location_model: LocationInput | None = None
        if isinstance(brief_obj.location, dict):
            location_model = LocationInput(**brief_obj.location)
        elif isinstance(brief_obj.location, LocationInput):
            location_model = brief_obj.location

        # 2. Resolve Cultural Anchors via Cultural Intelligence MCP
        resolved_entities: list[ResolvedEntity] = []
        resolved_tags: list[str] = []
        resolved_tag_details: list[ResolvedTag] = []
        signal_explanations: dict[str, str] = {}
        resolution_confidences: list[float] = []

        for term in brief_obj.anchor_entities:
            clean_term = term.strip()
            if not clean_term:
                continue

            # Attempt entity resolution first via MCP
            entity_res = await self.mcp.resolve_entity(query=clean_term)
            if entity_res.get("is_resolved") and entity_res.get("resolved_entity_id"):
                ent_id = str(entity_res["resolved_entity_id"])
                ent_name = str(entity_res.get("entity_name", clean_term))
                ent_type = str(entity_res.get("entity_type", "brand"))
                conf = float(entity_res.get("confidence", 1.0))
                resolution_confidences.append(conf)

                why_it_matters = self._explain_entity_signal(
                    ent_name, ent_type, brief_obj
                )

                resolved_entities.append(
                    ResolvedEntity(
                        id=ent_id,
                        name=ent_name,
                        type=ent_type,
                        confidence=conf,
                        why_it_matters=why_it_matters,
                        source="qloo_search",
                        evidence=entity_res.get("evidence", {}),
                    )
                )
                signal_explanations[ent_id] = why_it_matters
                continue

            # If not an entity, attempt tag resolution via MCP
            tag_res = await self.mcp.resolve_tag(query=clean_term)
            resolved_tid = tag_res.get("resolved_tag_id") or tag_res.get("tag_id")
            if tag_res.get("is_resolved") and resolved_tid:
                tag_id = str(resolved_tid)
                tag_name = str(tag_res.get("tag_name", clean_term))
                tag_conf = float(tag_res.get("confidence", 1.0))
                resolution_confidences.append(tag_conf)

                why_it_matters = self._explain_tag_signal(tag_name, brief_obj)

                if tag_id not in resolved_tags:
                    resolved_tags.append(tag_id)
                    resolved_tag_details.append(
                        ResolvedTag(
                            id=tag_id,
                            name=tag_name,
                            category=tag_res.get("category"),
                            confidence=tag_conf,
                            why_it_matters=why_it_matters,
                        )
                    )
                signal_explanations[tag_id] = why_it_matters
                continue

            # Term failed validation against Qloo knowledge graph: NEVER invent an ID
            logger.warning(
                "[%s] Anchor term '%s' could not be resolved via Qloo MCP. Omitted to preserve zero-hallucination guarantee.",
                self.name,
                clean_term,
            )

        # 3. Check desired_mood and positioning for aesthetic motif tags
        if brief_obj.desired_mood:
            for candidate in [m.strip() for m in brief_obj.desired_mood.split(",")]:
                if len(candidate) > 3 and candidate not in brief_obj.anchor_entities:
                    tag_res = await self.mcp.resolve_tag(query=candidate)
                    mood_tid = tag_res.get("resolved_tag_id") or tag_res.get("tag_id")
                    if tag_res.get("is_resolved") and mood_tid:
                        tid = str(mood_tid)
                        if tid not in resolved_tags:
                            tname = str(tag_res.get("tag_name", candidate))
                            tconf = float(tag_res.get("confidence", 1.0))
                            resolution_confidences.append(tconf)
                            why = self._explain_tag_signal(tname, brief_obj)
                            resolved_tags.append(tid)
                            resolved_tag_details.append(
                                ResolvedTag(
                                    id=tid,
                                    name=tname,
                                    category=tag_res.get("category"),
                                    confidence=tconf,
                                    why_it_matters=why,
                                )
                            )
                            signal_explanations[tid] = why

        # 4. Synthesize Audience Profile
        audience_profile = self._synthesize_audience_profile(
            brief_obj, resolved_entities
        )

        # 5. Synthesize Cultural Themes
        cultural_themes = self._synthesize_cultural_themes(
            brief_obj, resolved_entities, resolved_tag_details
        )

        # 6. Synthesize Mood Profile
        mood_profile = self._synthesize_mood_profile(brief_obj, resolved_tag_details)

        # 7. Synthesize Cultural Constraints and Exclusions
        cultural_constraints, exclusions = self._synthesize_constraints_and_exclusions(
            brief_obj
        )

        # 8. Compute Overall Confidence Score
        if resolution_confidences:
            confidence = round(
                sum(resolution_confidences) / len(resolution_confidences), 3
            )
        elif brief_obj.anchor_entities:
            # Anchors were provided but none could be validated
            confidence = 0.5
        else:
            confidence = 0.9

        # 9. Formulate Structured CulturalTwin (No recommendations produced yet)
        return CulturalTwin(
            audience_profile=audience_profile,
            cultural_themes=cultural_themes,
            mood_profile=mood_profile,
            anchor_entities=list(brief_obj.anchor_entities),
            resolved_entities=resolved_entities,
            resolved_tags=resolved_tags,
            cultural_constraints=cultural_constraints,
            exclusions=exclusions,
            confidence=confidence,
            resolved_tag_details=resolved_tag_details,
            signal_explanations=signal_explanations,
            business_type=brief_obj.business_type,
            target_audience=brief_obj.target_audience,
            mood=brief_obj.desired_mood,
            positioning=brief_obj.positioning,
            budget=brief_obj.budget,
            location=location_model,
            constraints={"raw_constraints": brief_obj.constraints}
            if brief_obj.constraints
            else {},
        )

    # Alias for orchestration convenience
    create_cultural_twin = transform_brief

    # -------------------------------------------------------------------------
    # Signal Reasoning & Synthesis Helpers
    # -------------------------------------------------------------------------
    def _explain_entity_signal(
        self, name: str, entity_type: str, brief: PhysicalSpaceBrief
    ) -> str:
        """Generates contextual rationale explaining why a verified entity signal matters."""
        venue = brief.business_type or "physical space"
        mood = brief.desired_mood or "atmosphere"
        positioning = brief.positioning or "curated craft"

        if entity_type == "brand":
            return (
                f"Anchors the material craft, industrial design language, and patron quality expectations for {venue}. "
                f"Reflects the {positioning} market alignment exemplified by {name}."
            )
        if entity_type == "artist":
            return (
                f"Defines the acoustic sensibility, sonic energy, and nuanced background listening palette for {venue}, "
                f"reinforcing a {mood} sonic texture."
            )
        if entity_type == "place":
            return (
                f"Serves as an architectural and hospitality benchmark for {venue}, "
                f"demonstrating spatial pacing, patron density, and social ritual resonant with {name}."
            )
        return f"Grounds the cultural identity of {venue} in proven taste affinities aligned with {name} ({entity_type})."

    def _explain_tag_signal(self, name: str, brief: PhysicalSpaceBrief) -> str:
        """Generates contextual rationale explaining why a verified tag signal matters."""
        venue = brief.business_type or "space"
        return (
            f"Informs sensory curation, intentional spatial geometry, and material restraint for {venue}, "
            f"directly embodying the '{name}' aesthetic philosophy."
        )

    def _synthesize_audience_profile(
        self, brief: PhysicalSpaceBrief, resolved_entities: list[ResolvedEntity]
    ) -> str:
        """Synthesizes demographic and psychographic patron profile."""
        base_audience = (
            brief.target_audience
            or "Culturally engaged urban patrons and design-conscious enthusiasts"
        )
        positioning = brief.positioning or "specialty craft"
        business = brief.business_type or "venue"

        anchors_summary = ""
        if resolved_entities:
            top_names = ", ".join([e.name for e in resolved_entities[:3]])
            anchors_summary = f" with strong affinity overlap with {top_names}"

        return (
            f"{base_audience} seeking a {positioning} {business} experience{anchors_summary}. "
            "Patrons prioritize tangible materiality, unhurried hospitality, acoustic fidelity, "
            "and authentic cultural provenance over mass-market commercial convenience."
        )

    def _synthesize_cultural_themes(
        self,
        brief: PhysicalSpaceBrief,
        resolved_entities: list[ResolvedEntity],
        resolved_tags: list[ResolvedTag],
    ) -> list[str]:
        """Synthesizes 3 to 5 core cultural themes guiding the space."""
        themes: list[str] = []

        # Theme 1: Sonic / Atmospheric
        mood = brief.desired_mood or "Warm Acoustic"
        themes.append(f"Acoustic Presence & {mood.title()} Atmospheres")

        # Theme 2: Design / Materiality
        if resolved_tags:
            tag_name = resolved_tags[0].name.title()
            themes.append(f"Material Restraint & {tag_name} Design Philosophy")
        else:
            themes.append("Tactile Materiality & Architectural Negative Space")

        # Theme 3: Hospitality / Ritual
        business = brief.business_type.title()
        themes.append(f"Deliberate Pacing & Modern {business} Rituals")

        # Theme 4: Cultural Provenance
        if resolved_entities:
            entity_name = resolved_entities[0].name
            themes.append(f"Subcultural Credibility Anchored by {entity_name}")
        else:
            themes.append("Analog Authenticity in a Hyper-Digitalized Landscape")

        return themes

    def _synthesize_mood_profile(
        self, brief: PhysicalSpaceBrief, resolved_tags: list[ResolvedTag]
    ) -> str:
        """Synthesizes a multi-sensory mood profile."""
        base_mood = brief.desired_mood or "Warm, intimate, minimalist"
        tag_vibes = ", ".join([t.name for t in resolved_tags[:2]])
        tag_clause = f", refined by {tag_vibes}" if tag_vibes else ""

        return (
            f"Atmospheric Baseline: {base_mood}{tag_clause}. "
            "Sonic: Analog warmth with non-fatiguing acoustic dynamics and low conversational interference. "
            "Visual: Natural matte timber, architectural shadows, and warm 2700K lighting. "
            "Temporal: Gentle morning focus transitioning into a low-lit, intimate evening sanctuary."
        )

    def _synthesize_constraints_and_exclusions(
        self, brief: PhysicalSpaceBrief
    ) -> tuple[list[str], list[str]]:
        """Extracts cultural constraints and explicit exclusions."""
        constraints: list[str] = []
        exclusions: list[str] = []

        # Default standard cultural constraints for curated spaces
        constraints.append(
            "Acoustic decibel levels strictly calibrated to maintain conversational clarity without shouting (SPL < 75dB)"
        )
        constraints.append(
            "Material palette restricted to authentic tactile surfaces (solid timber, raw brass, textured linen, matte ceramics)"
        )
        constraints.append(
            "Digital screens and promotional monitors strictly prohibited in patron seating and listening zones"
        )

        # Ingest user-provided constraints
        if brief.constraints:
            if isinstance(brief.constraints, list):
                constraints.extend([str(c) for c in brief.constraints])
            elif isinstance(brief.constraints, dict):
                for k, v in brief.constraints.items():
                    constraints.append(f"{k}: {v}")

        # Explicit cultural exclusions / anti-patterns
        exclusions.append(
            "Commercial Top 40, EDM, and abrasive algorithmic streaming playlists"
        )
        exclusions.append(
            "High-glare fluorescent overhead lighting and garish neon displays"
        )
        exclusions.append(
            "Disruptive corporate branding, branded collateral, and intrusive promotional signage"
        )
        exclusions.append(
            "High-turnover fast-casual furniture or sterile synthetic materials"
        )

        return constraints, exclusions

    # -------------------------------------------------------------------------
    # Downstream Synthesis: Execute once CulturalMatrix is generated
    # -------------------------------------------------------------------------
    async def execute(self, payload: CulturalStrategyInput) -> CulturalStrategyOutput:
        """Executes strategic synthesis over the CulturalTwin and CulturalMatrix."""
        if isinstance(payload, dict):
            payload = CulturalStrategyInput.model_validate(payload)
        elif not isinstance(payload, CulturalStrategyInput):
            raise TypeError(
                f"Expected CulturalStrategyInput or dict, got {type(payload).__name__}"
            )

        twin = payload.cultural_twin
        matrix = payload.cultural_matrix

        logger.info(
            "[%s] Formulating cultural strategy for '%s' (Anchors: %d)",
            self.name,
            twin.business_type or "Physical Space",
            len(twin.resolved_entity_ids),
        )

        # 1. Gather all verified entity IDs for provenance verification
        provenance_ids: list[str] = list(twin.resolved_entity_ids)
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
        mood_str = twin.mood or twin.mood_profile or "refined, contemporary atmosphere"
        audience_str = (
            twin.target_audience or twin.audience_profile or "discerning modern patrons"
        )

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
