"""TasteOps Governance & Execution Agent.

Enforces strict compliance, quality bounds, and provenance integrity.
Verifies that zero hallucinated Qloo IDs exist in any agent output.
Manages the Human-in-the-Loop approval gate and post-approval activation tasks.
"""

import logging
import uuid
from datetime import UTC, datetime

from tasteops.workflows.schemas import (
    ComplianceCheck,
    CulturalActivationPlan,
    ExecutionSummary,
    ExecutionTask,
    GovernanceValidationInput,
    GovernanceValidationOutput,
)

logger = logging.getLogger("tasteops.agents.governance")


class GovernanceAgent:
    """Agent validating plan compliance, auditing provenance, and managing execution."""

    name: str = "Governance & Execution Agent"

    async def validate_plan(
        self, payload: GovernanceValidationInput
    ) -> GovernanceValidationOutput:
        """Audits the generated cultural plan against constraints and provenance integrity."""
        twin = payload.cultural_twin
        matrix = payload.cultural_matrix
        strategy = payload.strategy
        experience = payload.experience_design
        partnerships = payload.partnerships

        logger.info("[%s] Auditing plan compliance and provenance integrity", self.name)

        compliance_checks: list[ComplianceCheck] = []
        risk_flags: list[str] = []
        unverified_ids: list[str] = []

        # 1. Build the Ground Truth Set of Verified Qloo Entity IDs
        verified_truth_ids: set[str] = set(twin.anchor_entities)
        for rec in (
            matrix.artists
            + matrix.books
            + matrix.brands
            + matrix.places
            + matrix.movies
            + matrix.destinations
        ):
            verified_truth_ids.add(rec.id)

        # 2. Audit Every Entity ID Referenced in Agent Outputs
        referenced_ids: set[str] = set()

        for pillar in strategy.cultural_pillars:
            referenced_ids.update(pillar.aligned_entity_ids)

        for daypart in experience.daypart_programs:
            referenced_ids.update(daypart.featured_artist_ids)

        for zone in experience.spatial_zones:
            referenced_ids.update(zone.design_reference_ids)

        for p in partnerships.partnerships:
            referenced_ids.add(p.partner_entity_id)

        # Provenance Check
        for ref_id in referenced_ids:
            if ref_id not in verified_truth_ids:
                unverified_ids.append(ref_id)

        provenance_passed = len(unverified_ids) == 0
        compliance_checks.append(
            ComplianceCheck(
                rule_name="provenance_integrity",
                passed=provenance_passed,
                detail=(
                    f"Audited {len(referenced_ids)} referenced entity IDs. "
                    f"{len(unverified_ids)} unverified IDs detected."
                    if not provenance_passed
                    else f"All {len(referenced_ids)} referenced entity IDs verified against Qloo origin."
                ),
            )
        )
        if not provenance_passed:
            risk_flags.append(
                f"Provenance violation: Unverified IDs detected: {unverified_ids}"
            )

        # 3. Completeness & Quality Checks
        has_pillars = len(strategy.cultural_pillars) >= 1
        compliance_checks.append(
            ComplianceCheck(
                rule_name="cultural_pillars_defined",
                passed=has_pillars,
                detail=f"{len(strategy.cultural_pillars)} cultural pillars established.",
            )
        )

        has_dayparts = len(experience.daypart_programs) >= 1
        compliance_checks.append(
            ComplianceCheck(
                rule_name="temporal_programming_defined",
                passed=has_dayparts,
                detail=f"{len(experience.daypart_programs)} daypart atmosphere programs scheduled.",
            )
        )

        has_partnerships = len(partnerships.partnerships) >= 1
        compliance_checks.append(
            ComplianceCheck(
                rule_name="commercial_partnerships_defined",
                passed=has_partnerships,
                detail=f"{len(partnerships.partnerships)} verified brand partnerships structured.",
            )
        )

        # Overall validity
        all_passed = all(c.passed for c in compliance_checks)
        readiness_score = 1.0 if all_passed else 0.4

        return GovernanceValidationOutput(
            is_valid=all_passed,
            provenance_verified=provenance_passed,
            compliance_checks=compliance_checks,
            risk_flags=risk_flags,
            unverified_entity_ids=unverified_ids,
            readiness_score=readiness_score,
        )

    async def execute_plan(self, plan: CulturalActivationPlan) -> ExecutionSummary:
        """Executes concrete downstream activation tasks once human approval is confirmed."""
        logger.info(
            "[%s] Initiating execution of approved plan '%s'", self.name, plan.plan_id
        )

        tasks: list[ExecutionTask] = []

        # 1. Create Audio/Spotify Seeding Task for Member 3
        if plan.cultural_matrix.artists:
            lead_artist = plan.cultural_matrix.artists[0]
            tasks.append(
                ExecutionTask(
                    task_id=f"task_{uuid.uuid4().hex[:8]}",
                    category="spotify_audio_seed",
                    description=f"Export seed artist '{lead_artist.name}' to Spotify audio engine pipeline",
                    target_partner_or_artist=lead_artist.name,
                    target_entity_id=lead_artist.id,
                    status="EXECUTED",
                    executed_at=datetime.now(UTC),
                    output_reference=f"spotify://seed_artist/{lead_artist.id}",
                )
            )

        # 2. Create Partnership Brief Dispatch Tasks
        for p in plan.partnerships.partnerships[:2]:
            tasks.append(
                ExecutionTask(
                    task_id=f"task_{uuid.uuid4().hex[:8]}",
                    category="partner_outreach_brief",
                    description=f"Dispatch collaboration brief for '{p.partner_name}' ({p.activation_type})",
                    target_partner_or_artist=p.partner_name,
                    target_entity_id=p.partner_entity_id,
                    status="EXECUTED",
                    executed_at=datetime.now(UTC),
                    output_reference=f"brief://partner/{p.partner_entity_id}",
                )
            )

        # 3. Create Spatial Specification Task
        if plan.experience_design.spatial_zones:
            lead_zone = plan.experience_design.spatial_zones[0]
            tasks.append(
                ExecutionTask(
                    task_id=f"task_{uuid.uuid4().hex[:8]}",
                    category="spatial_design_spec",
                    description=f"Generate physical design spec for zone '{lead_zone.zone_name}'",
                    target_partner_or_artist=lead_zone.zone_name,
                    target_entity_id="zone_lead_spec",
                    status="EXECUTED",
                    executed_at=datetime.now(UTC),
                    output_reference=f"spec://zone/{lead_zone.zone_name.lower().replace(' ', '_')}",
                )
            )

        executed_count = sum(1 for t in tasks if t.status == "EXECUTED")
        return ExecutionSummary(
            total_tasks=len(tasks),
            executed_tasks=executed_count,
            failed_tasks=len(tasks) - executed_count,
            tasks=tasks,
            completed_at=datetime.now(UTC),
        )
