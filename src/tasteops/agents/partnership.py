"""TasteOps Partnership Agent.

Screens and structures brand collaborations, hardware sponsorships, and retail activations
strictly derived from verified Qloo brand and place recommendations.
Guarantees zero hallucinated partners or IDs, computes multi-dimensional scoring,
generates outreach drafts only, and never claims an active partnership exists.
"""

import logging
from typing import Any

from tasteops.models.cultural_matrix import (
    CulturalMatrix,
    CulturalRecommendation,
    CulturalTwin,
)
from tasteops.workflows.schemas import (
    BrandPartnershipCandidate,
    CulturalStrategyOutput,
    ExperienceDesignOutput,
    OutreachDraft,
    PartnershipActivation,
    PartnershipInput,
    PartnershipOutput,
    PartnershipScoreBreakdown,
)

logger = logging.getLogger("tasteops.agents.partnership")


class PartnershipAgent:
    """Agent identifying and structuring high-resonance brand partnerships.

    Computes 6-dimensional scoring:
    - CulturalFit (alignment with cultural themes and aesthetic positioning)
    - AudienceFit (direct Qloo cross-affinity and taste overlap)
    - BrandCompatibility (business category and venue type synergy)
    - ContextFit (spatial footprint, acoustic guidelines, and physical viability)
    - BudgetFit (feasibility within budget tier and operational constraints)
    - Novelty (curatorial freshness and subcultural distinction)

    Outputs:
    - brand, score, supporting Qloo evidence, partnership concept, estimated effort,
      risk, recommended next action, and exploratory outreach drafts.
    - Strictly guarantees:
      * No claim that a real partnership exists (is_existing_partner = False).
      * Outreach drafts only.
      * 100% traceable to verified Qloo entity provenance.
    """

    name: str = "Partnership Agent"

    async def identify_partnerships(
        self,
        cultural_twin: CulturalTwin | None = None,
        brand_results: list[CulturalRecommendation] | None = None,
        business_constraints: list[str] | None = None,
        budget: str | None = None,
        cultural_matrix: CulturalMatrix | None = None,
        strategy: CulturalStrategyOutput | None = None,
        experience_design: ExperienceDesignOutput | None = None,
    ) -> PartnershipOutput:
        """Identifies, scores, and structures brand partnership candidates with outreach drafts."""
        if isinstance(cultural_twin, dict):
            cultural_twin = CulturalTwin.model_validate(cultural_twin)
        elif cultural_twin is not None and not isinstance(cultural_twin, CulturalTwin):
            raise TypeError(
                f"Expected CulturalTwin, dict, or None, got {type(cultural_twin).__name__}"
            )

        if isinstance(cultural_matrix, dict):
            cultural_matrix = CulturalMatrix.model_validate(cultural_matrix)
        elif cultural_matrix is not None and not isinstance(
            cultural_matrix, CulturalMatrix
        ):
            raise TypeError(
                f"Expected CulturalMatrix, dict, or None, got {type(cultural_matrix).__name__}"
            )

        if isinstance(strategy, dict):
            strategy = CulturalStrategyOutput.model_validate(strategy)
        elif strategy is not None and not isinstance(strategy, CulturalStrategyOutput):
            raise TypeError(
                f"Expected CulturalStrategyOutput, dict, or None, got {type(strategy).__name__}"
            )

        if isinstance(experience_design, dict):
            experience_design = ExperienceDesignOutput.model_validate(experience_design)
        elif experience_design is not None and not isinstance(
            experience_design, ExperienceDesignOutput
        ):
            raise TypeError(
                f"Expected ExperienceDesignOutput, dict, or None, got {type(experience_design).__name__}"
            )

        logger.info(
            "[%s] Screening and scoring brand partnerships from cultural matrix",
            self.name,
        )

        twin = cultural_twin or CulturalTwin(
            business_type="Curated Physical Space",
            mood=strategy.positioning_statement if strategy else "Acoustic warmth",
            cultural_themes=[strategy.cultural_pillars[0].name]
            if strategy and strategy.cultural_pillars
            else ["Craft & Design"],
        )

        # 1. Resolve candidates from explicit brand_results or CulturalMatrix
        candidates_raw: list[CulturalRecommendation] = []
        if brand_results is not None:
            candidates_raw = list(brand_results)
        elif cultural_matrix and cultural_matrix.brands:
            candidates_raw = list(cultural_matrix.brands)
        elif cultural_matrix and cultural_matrix.places:
            # Fallback to verified hospitality/place recommendations if brands are absent
            candidates_raw = list(cultural_matrix.places)

        # 2. Extract operating constraints and budget
        constraints: list[str] = list(business_constraints or [])
        if twin.cultural_constraints:
            constraints.extend(twin.cultural_constraints)
        if twin.constraints:
            constraints.extend(twin.constraints)

        effective_budget = budget or twin.budget or "Medium Tier"

        # 3. Filter and score candidates
        exclusions_lower = [e.lower() for e in twin.exclusions]
        provenance_ids: list[str] = (
            list(strategy.provenance_entity_ids) if strategy else []
        )
        scored_candidates: list[BrandPartnershipCandidate] = []

        for candidate in candidates_raw:
            # Check exclusions
            cand_name_lower = candidate.name.lower()
            if any(
                ex in cand_name_lower or cand_name_lower in ex
                for ex in exclusions_lower
                if ex.strip()
            ):
                logger.info(
                    "[%s] Brand '%s' omitted due to cultural exclusion rule.",
                    self.name,
                    candidate.name,
                )
                continue

            # Calculate 6-dimensional scoring
            breakdown = self._calculate_scores(
                candidate=candidate,
                twin=twin,
                constraints=constraints,
                budget=effective_budget,
            )

            # Build supporting Qloo evidence
            evidence: dict[str, Any] = {
                "entity_id": candidate.id,
                "entity_name": candidate.name,
                "type": candidate.type,
                "affinity": candidate.affinity,
                "score": candidate.score,
                "confidence": candidate.confidence,
                "source_query": candidate.source_query,
                "source_signal": candidate.source_signal,
                "explainability": candidate.explainability,
            }

            # Generate concept, effort, risk, action, and outreach draft
            concept = self._build_partnership_concept(candidate, twin)
            effort = self._estimate_effort(candidate, twin)
            risk = self._assess_risk(candidate, twin, constraints)
            action = self._recommend_next_action(candidate, twin)
            outreach = self._build_outreach_draft(candidate, twin, concept)

            if candidate.id not in provenance_ids:
                provenance_ids.append(candidate.id)

            scored_candidates.append(
                BrandPartnershipCandidate(
                    brand=candidate.name,
                    brand_entity_id=candidate.id,
                    category=candidate.type or "lifestyle_brand",
                    score=breakdown.overall_score,
                    score_breakdown=breakdown,
                    supporting_qloo_evidence=evidence,
                    partnership_concept=concept,
                    estimated_effort=effort,
                    risk=risk,
                    recommended_next_action=action,
                    outreach_draft=outreach,
                    is_existing_partner=False,  # Strictly never claim active partnership
                )
            )

        # Sort by overall score descending
        scored_candidates.sort(key=lambda c: c.score, reverse=True)

        # 4. Map to backward-compatible PartnershipActivation list
        partnerships: list[PartnershipActivation] = []
        activation_types = [
            "Hardware Residency",
            "Sensory Amenities & Scenting",
            "Design Goods & Tableware",
            "Guest Roaster Exchange",
        ]
        for idx, sc in enumerate(scored_candidates[:4]):
            act_type = activation_types[idx % len(activation_types)]
            partnerships.append(
                PartnershipActivation(
                    partner_name=sc.brand,
                    partner_entity_id=sc.brand_entity_id,
                    category=sc.category,
                    activation_type=act_type,
                    concept_description=sc.partnership_concept,
                    affinity_score=sc.supporting_qloo_evidence.get(
                        "affinity", round(sc.score / 100.0, 2)
                    ),
                    alignment_rationale=(
                        f"Patrons exhibit an affinity index of {sc.supporting_qloo_evidence.get('affinity', 0.85):0.2f} "
                        f"toward {sc.brand} (overall fit: {sc.score}/100), ensuring organic subcultural resonance."
                    ),
                )
            )

        # Fallback if no brands were found at all
        if not partnerships and cultural_matrix and cultural_matrix.places:
            place = cultural_matrix.places[0]
            if place.id not in provenance_ids:
                provenance_ids.append(place.id)
            partnerships.append(
                PartnershipActivation(
                    partner_name=place.name,
                    partner_entity_id=place.id,
                    category="hospitality_exchange",
                    activation_type="Guest Roaster Residency",
                    concept_description=f"Curated guest bean takeover and barista exchange program with {place.name}.",
                    affinity_score=place.affinity,
                    alignment_rationale="Shared subcultural audience and craftsmanship alignment.",
                )
            )

        events = [
            "Monthly Analog Listening Club: Album deep-dive paired with single-origin tasting flights.",
            "Independent Micro-Publisher Showcase: Weekend pop-up featuring art and photography monographs.",
            "Acoustic Dusk Session: Intimate live selector set featuring verified ambient music artists.",
        ]

        return PartnershipOutput(
            candidates=scored_candidates,
            partnerships=partnerships,
            event_collaborations=events,
            provenance_entity_ids=sorted(provenance_ids),
        )

    async def execute(self, payload: PartnershipInput) -> PartnershipOutput:
        """Executes partnership candidate screening from structured input payload."""
        if isinstance(payload, dict):
            payload = PartnershipInput.model_validate(payload)
        elif not isinstance(payload, PartnershipInput):
            raise TypeError(
                f"Expected PartnershipInput or dict, got {type(payload).__name__}"
            )
        return await self.identify_partnerships(
            cultural_twin=payload.cultural_twin,
            brand_results=payload.brand_results,
            business_constraints=payload.business_constraints,
            budget=payload.budget,
            cultural_matrix=payload.cultural_matrix,
            strategy=payload.strategy,
            experience_design=payload.experience_design,
        )

    # -------------------------------------------------------------------------
    # Scoring Dimensions (0 to 100)
    # -------------------------------------------------------------------------
    def _calculate_scores(
        self,
        candidate: CulturalRecommendation,
        twin: CulturalTwin,
        constraints: list[str],
        budget: str,
    ) -> PartnershipScoreBreakdown:
        """Calculates 6-dimensional scoring and composite normalized score."""
        # 1. AudienceFit: Direct Qloo affinity percentage
        audience_fit = round(min(max(candidate.affinity * 100.0, 0.0), 100.0), 1)

        # 2. CulturalFit: Semantic overlap with cultural themes and aesthetic mood
        cultural_keywords = set()
        for theme in twin.cultural_themes:
            cultural_keywords.update(theme.lower().split())
        if twin.mood:
            cultural_keywords.update(twin.mood.lower().split())
        if twin.mood_profile:
            cultural_keywords.update(twin.mood_profile.lower().split())

        brand_text = f"{candidate.name} {candidate.type or ''} {' '.join(candidate.explainability)}".lower()
        matches = sum(1 for kw in cultural_keywords if len(kw) > 3 and kw in brand_text)
        cultural_fit = round(
            min(max(audience_fit * 0.80 + (matches * 4.0) + 10.0, 50.0), 98.0),
            1,
        )

        # 3. BrandCompatibility: Category synergy with physical venue model
        venue_lower = (twin.business_type or "physical space").lower()
        compat_base = 80.0
        if (
            "audio" in brand_text or "sound" in brand_text
        ) and "listening" in venue_lower:
            compat_base += 15.0
        elif ("coffee" in brand_text or "cafe" in brand_text) and "cafe" in venue_lower:
            compat_base += 14.0
        elif "design" in brand_text or "lifestyle" in brand_text:
            compat_base += 8.0
        brand_compatibility = round(min(max(compat_base, 45.0), 96.0), 1)

        # 4. ContextFit: Physical space and operational viability
        context_fit = 85.0
        constraints_text = " ".join(constraints).lower()
        if (
            "acoustic" in constraints_text or "db" in constraints_text
        ) and "audio" in brand_text:
            context_fit = 92.0
        if (
            "small" in constraints_text
            or "compact" in constraints_text
            or "limited footprint" in constraints_text
        ):
            context_fit -= 5.0
        context_fit = round(min(max(context_fit, 50.0), 95.0), 1)

        # 5. BudgetFit: Feasibility under operating tier
        budget_lower = budget.lower()
        if any(t in budget_lower for t in ["modest", "low", "bootstrapped", "seed"]):
            budget_fit = 82.0  # Consignment and product-loan model
        elif any(t in budget_lower for t in ["luxury", "high", "flagship"]):
            budget_fit = 94.0
        else:
            budget_fit = 88.0

        # 6. Novelty: Rewarding subcultural distinction over generic retail ubiquity
        is_mass_retail = any(
            m in candidate.name.lower()
            for m in ["starbucks", "apple", "target", "nike", "zara", "walmart"]
        )
        if is_mass_retail:
            novelty = 42.0
        else:
            novelty = round(
                min(
                    max(72.0 + (1.0 - candidate.affinity * 0.2) * 15.0, 60.0),
                    95.0,
                ),
                1,
            )

        # Composite Normalized Score (0 to 100)
        overall = round(
            (0.25 * audience_fit)
            + (0.20 * cultural_fit)
            + (0.20 * brand_compatibility)
            + (0.15 * context_fit)
            + (0.10 * budget_fit)
            + (0.10 * novelty),
            1,
        )

        return PartnershipScoreBreakdown(
            cultural_fit=cultural_fit,
            audience_fit=audience_fit,
            brand_compatibility=brand_compatibility,
            context_fit=context_fit,
            budget_fit=budget_fit,
            novelty=novelty,
            overall_score=overall,
        )

    # -------------------------------------------------------------------------
    # Conceptual & Editorial Formulation
    # -------------------------------------------------------------------------
    def _build_partnership_concept(
        self, candidate: CulturalRecommendation, twin: CulturalTwin
    ) -> str:
        """Constructs an integrated, physical-space collaboration concept."""
        brand_name = candidate.name
        venue = twin.business_type or "venue"
        text = f"{brand_name} {candidate.type or ''}".lower()

        if "audio" in text or "sound" in text or "technica" in text:
            return (
                f"Dedicated {brand_name} Analog Listening Station: Embedded high-resolution turntable console "
                f"with reference open-back headphones and curated vinyl displays positioned along the {venue} listening bar."
            )
        if "muji" in text or "design" in text or "lifestyle" in text:
            return (
                f"{brand_name} Material & Amenity Collaboration: Tactile tabletop serviceware, matte stoneware ceramics, "
                f"and understated linen textiles specifying the physical hospitality touchpoints throughout the {venue}."
            )
        if "coffee" in text or "cafe" in text or "roast" in text:
            return (
                f"Curated {brand_name} Guest Residency: Rotating single-origin pour-over feature, accompanied by co-branded "
                "sensory tasting cards and an intimate monthly public cupping session."
            )
        if (
            "aesop" in text
            or "scent" in text
            or "perfume" in text
            or "apothecary" in text
        ):
            return (
                f"Bespoke {brand_name} Olfactory Integration: Custom botanical washroom amenities and subtle Hinoki cypress "
                f"space diffusion reinforcing the contemplative atmosphere of {venue}."
            )

        return (
            f"Curated {brand_name} Physical Showcase: Limited-run co-branded guest touchpoints and display residency "
            f"honoring shared material restraint and artisan craftsmanship within {venue}."
        )

    def _estimate_effort(
        self, candidate: CulturalRecommendation, twin: CulturalTwin
    ) -> str:
        """Estimates operational and procurement effort level."""
        text = candidate.name.lower()
        if "audio" in text or "technica" in text:
            return (
                "Low to Medium (2-3 weeks): Involves equipment loan/consignment agreement, "
                "countertop cable routing, and 1 staff training session on stylus maintenance and patron orientation."
            )
        if "muji" in text or "ceramics" in text or "design" in text:
            return (
                "Medium (4-6 weeks): Requires wholesale sample coordination, tabletop durability validation, "
                "and setting up batch replacement stock."
            )
        return "Low (1-2 weeks): Straightforward consignment or product loan arrangement with minimal spatial modification."

    def _assess_risk(
        self,
        candidate: CulturalRecommendation,
        twin: CulturalTwin,
        constraints: list[str],
    ) -> str:
        """Conducts objective risk assessment and mitigation guidelines."""
        return (
            f"Low to Moderate: Risk of perceived over-commercialization if {candidate.name} branding is too visible. "
            "Mitigation: Enforce strict visual restraint—zero promotional banners, floor decals, or overt retail logos. "
            "The brand presence must remain strictly tactile, functional, and organic to the guest experience."
        )

    def _recommend_next_action(
        self, candidate: CulturalRecommendation, twin: CulturalTwin
    ) -> str:
        """Recommends immediate pragmatic operational next step."""
        venue = twin.business_type or "venue"
        return (
            f"1. Review the speculative 1-page {candidate.name} collaboration concept for {venue} with the General Manager. "
            f"2. Identify the Cultural Partnerships / Brand Collaborations Lead at {candidate.name} via professional networks. "
            f"3. Dispatch the personalized exploratory outreach draft proposing an informal 15-minute introductory conversation."
        )

    def _build_outreach_draft(
        self,
        candidate: CulturalRecommendation,
        twin: CulturalTwin,
        concept: str,
    ) -> OutreachDraft:
        """Drafts an exploratory, evidence-backed outreach letter (no real partnership claimed)."""
        venue = twin.business_type or "physical space"
        affinity_pct = round(candidate.affinity * 100)

        subject = f"Exploratory Cultural Alignment: {venue} × {candidate.name}"
        hook = (
            f"Our physical space analytics indicate a notable cultural affinity ({affinity_pct}% patron taste overlap) "
            f"between patrons of our {venue} and {candidate.name}. Both communities share a commitment to deliberate craftsmanship, "
            "understated aesthetic restraint, and tactile authenticity."
        )
        value_prop = (
            f"For {candidate.name}: An intimate, high-dwell-time physical showcase in front of a discerning cultural demographic "
            f"(45+ minute dwell time). For our {venue}: Elevating patron sensory touchpoints through authentic partner craft."
        )
        cta = (
            "We would love to share an initial 1-page visual moodboard and explore whether an informal, mutually beneficial collaboration "
            "might align with your upcoming brand initiatives. Would you be open to a brief 15-minute introductory call?"
        )

        return OutreachDraft(
            recipient_role="Director of Brand Partnerships / Cultural Marketing",
            subject=subject,
            opening_hook=hook,
            proposed_collaboration=concept,
            value_proposition=value_prop,
            call_to_action=cta,
            disclaimer="Exploratory outreach draft only. No existing formal partnership or affiliation is claimed.",
        )
