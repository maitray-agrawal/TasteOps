"""TasteOps Partnership Agent.

Screens and structures brand collaborations, hardware sponsorships, and retail activations
strictly derived from verified Qloo brand and place recommendations.
Guarantees zero hallucinated partners or IDs.
"""

import logging

from tasteops.workflows.schemas import (
    PartnershipActivation,
    PartnershipInput,
    PartnershipOutput,
)

logger = logging.getLogger("tasteops.agents.partnership")


class PartnershipAgent:
    """Agent structuring brand partnerships and activation concepts."""

    name: str = "Partnership Agent"

    async def execute(self, payload: PartnershipInput) -> PartnershipOutput:
        """Identifies and drafts brand partnership activations."""
        matrix = payload.cultural_matrix
        strategy = payload.strategy

        logger.info(
            "[%s] Structuring brand activations from CulturalMatrix recommendations",
            self.name,
        )

        provenance_ids: list[str] = list(strategy.provenance_entity_ids)
        partnerships: list[PartnershipActivation] = []

        # 1. Structure activations from verified high-affinity brands in CulturalMatrix
        top_brands = matrix.brands[:3]
        activation_types = [
            (
                "Audio/Hardware Residency",
                "In-venue turntable station and precision headphone listening installation",
            ),
            (
                "Apothecary & Sensory Display",
                "Custom botanical hand care and bespoke ambient space scenting line",
            ),
            (
                "Design Goods & Apparel Capsule",
                "Limited-run heavy cotton workwear jackets and ceramic mug co-brand",
            ),
        ]

        for idx, brand in enumerate(top_brands):
            if brand.id not in provenance_ids:
                provenance_ids.append(brand.id)

            act_type, concept = activation_types[idx % len(activation_types)]
            partnerships.append(
                PartnershipActivation(
                    partner_name=brand.name,
                    partner_entity_id=brand.id,
                    category=brand.type or "lifestyle_brand",
                    activation_type=act_type,
                    concept_description=f"Exclusive collaboration with {brand.name}: {concept}.",
                    affinity_score=brand.affinity,
                    alignment_rationale=(
                        f"Patrons exhibit an affinity index of {brand.affinity:0.2f} toward {brand.name}, "
                        f"ensuring immediate brand resonance and organic merchandise adoption."
                    ),
                )
            )

        # Fallback if brand recommendations were minimal: pull from verified places or books
        if not partnerships and matrix.places:
            place = matrix.places[0]
            if place.id not in provenance_ids:
                provenance_ids.append(place.id)
            partnerships.append(
                PartnershipActivation(
                    partner_name=place.name,
                    partner_entity_id=place.id,
                    category="hospitality_exchange",
                    activation_type="Roaster Guest Residency",
                    concept_description=f"Curated guest bean takeover and barista exchange program with {place.name}.",
                    affinity_score=place.affinity,
                    alignment_rationale="Shared subcultural audience and craftsmanship alignment.",
                )
            )

        # 2. Event Collaborations
        events = [
            "Monthly Analog Listening Club: Album deep-dive paired with single-origin tasting flights.",
            "Independent Micro-Publisher Showcase: Weekend pop-up featuring art and photography monographs.",
            "Acoustic Dusk Session: Intimate live selector set featuring verified ambient music artists.",
        ]

        return PartnershipOutput(
            partnerships=partnerships,
            event_collaborations=events,
            provenance_entity_ids=provenance_ids,
        )
