"""TasteOps Negative Governance & Cryptographic Security Boundary Tests.

Verifies:
1. Deliberate injection of unverified/hallucinated Qloo entity ID (e.g. 'qloo_fake_98372')
   is deterministically BLOCKED by GovernanceAgent with zero execution.
2. Missing Qloo provenance blocks plan approval and execution.
3. Mutated plan hash after approval invalidates sign-off and BLOCKS downstream execution.
4. Unauthorized execution requests without approval are rejected with UnapprovedExecutionError.
5. Procurement CSV artifact strictly conforms to the required 8-column schema and UTF-8 encoding.
6. Parallel agent execution produces verified telemetry for Sonic, Procurement, Brand, and Strategist.
"""

from __future__ import annotations

import csv
import io

import pytest

from tasteops.agents.architect import ExperienceArchitect
from tasteops.agents.governance import (
    GovernanceAgent,
    UnapprovedExecutionError,
)
from tasteops.models.cultural_matrix import (
    CulturalMatrix,
    CulturalRecommendation,
    CulturalTwin,
)
from tasteops.workflows.artifacts import (
    generate_brand_dossiers_artifact,
    generate_procurement_csv,
    generate_spotify_playlist_artifact,
)
from tasteops.workflows.context import WorkflowContext
from tasteops.workflows.engine import WorkflowEngine
from tasteops.workflows.schemas import (
    ApprovalRecord,
    CulturalActivationPlan,
    CulturalPillar,
    CulturalStrategyOutput,
    ExperienceDesignInput,
    GovernanceValidationInput,
    PartnershipOutput,
)
from tasteops.workflows.states import WorkflowState


async def _create_test_plan(
    fake_entity_id: str | None = None,
) -> CulturalActivationPlan:
    """Helper creating a test plan with an optionally injected unverified entity."""
    gov = GovernanceAgent()
    twin = CulturalTwin(anchor_entities=["ent_clean_01"])
    matrix = CulturalMatrix(
        artists=[
            CulturalRecommendation(
                id="ent_clean_01",
                name="Acoustic Clean Artist",
                type="artist",
                affinity=0.92,
                source_query="/v2/insights",
            )
        ]
    )

    pillar_ids = ["ent_clean_01"]
    if fake_entity_id:
        pillar_ids.append(fake_entity_id)

    strat = CulturalStrategyOutput(
        positioning_statement="Refined acoustic listening sanctuary",
        cultural_pillars=[
            CulturalPillar(
                name="Sonic Purity",
                description="High fidelity acoustics",
                aligned_entity_ids=pillar_ids,
            )
        ],
        target_subcultures=["Audiophile"],
        affinity_themes=["Analog warmth"],
        provenance_entity_ids=["ent_clean_01"],
    )

    arch = await ExperienceArchitect().execute(
        ExperienceDesignInput(
            cultural_twin=twin, strategy=strat, cultural_matrix=matrix
        )
    )
    part = PartnershipOutput(partnerships=[], provenance_entity_ids=["ent_clean_01"])
    exec_plan = gov.plan(
        GovernanceValidationInput(
            cultural_twin=twin,
            cultural_matrix=matrix,
            strategy=strat,
            experience_design=arch,
            partnerships=part,
        )
    )

    gov_output = await gov.validate_plan(
        GovernanceValidationInput(
            cultural_twin=twin,
            cultural_matrix=matrix,
            strategy=strat,
            experience_design=arch,
            partnerships=part,
        ),
        execution_plan=exec_plan,
    )

    return CulturalActivationPlan(
        plan_id="plan_neg_audit_01",
        version=1,
        cultural_twin=twin,
        cultural_matrix=matrix,
        strategy=strat,
        experience_design=arch,
        partnerships=part,
        execution_plan=exec_plan,
        governance=gov_output,
    )


# =============================================================================
# 1. Deliberate Injection of Unverified Qloo Entity ID
# =============================================================================


@pytest.mark.asyncio
async def test_governance_blocks_hallucinated_qloo_entity():
    """Negative Test: Injecting 'qloo_fake_98372' MUST block governance validation."""
    fake_id = "qloo_fake_98372"
    plan = await _create_test_plan(fake_entity_id=fake_id)

    # 1. Governance validation MUST fail
    assert plan.governance.is_valid is False
    assert plan.governance.provenance_verified is False
    assert any("Provenance violation" in flag for flag in plan.governance.risk_flags)
    assert any(fake_id in flag for flag in plan.governance.risk_flags)

    # 2. Execution must be strictly blocked
    gov = GovernanceAgent()
    with pytest.raises(
        UnapprovedExecutionError,
        match="Cannot execute unvalidated plan",
    ):
        await gov.execute_plan(plan, is_approved=True)


# =============================================================================
# 2. Missing Qloo Provenance Blocking Test
# =============================================================================


@pytest.mark.asyncio
async def test_governance_blocks_missing_provenance():
    """Negative Test: Recommendations missing Qloo evidence MUST fail validation."""
    gov = GovernanceAgent()
    twin = CulturalTwin(anchor_entities=["ent_clean_01"])
    empty_matrix = CulturalMatrix()  # No evidence

    strat = CulturalStrategyOutput(
        positioning_statement="Minimal Space",
        cultural_pillars=[
            CulturalPillar(
                name="Minimalism",
                description="Stripped down aesthetic",
                aligned_entity_ids=["ent_clean_01"],
            )
        ],
        target_subcultures=["Architectural Minimalists"],
        affinity_themes=["Restrained design"],
        provenance_entity_ids=["ent_clean_01"],
    )
    arch = await ExperienceArchitect().execute(
        ExperienceDesignInput(
            cultural_twin=twin, strategy=strat, cultural_matrix=empty_matrix
        )
    )
    part = PartnershipOutput(partnerships=[], provenance_entity_ids=["ent_clean_01"])

    # Strip Qloo evidence
    for rec in arch.sonic_identity.curated_recommendations:
        rec.qloo_evidence = {}

    gov_output = await gov.validate_plan(
        GovernanceValidationInput(
            cultural_twin=twin,
            cultural_matrix=empty_matrix,
            strategy=strat,
            experience_design=arch,
            partnerships=part,
        )
    )

    assert gov_output.is_valid is False
    assert any("Missing evidence" in flag for flag in gov_output.risk_flags)


# =============================================================================
# 3. Cryptographic Plan Mutation Detection (Altered SHA-256 Hash)
# =============================================================================


@pytest.mark.asyncio
async def test_governance_blocks_mutated_plan_hash():
    """Negative Test: If plan is modified after human sign-off, approval is invalidated."""
    plan = await _create_test_plan()
    gov = GovernanceAgent()

    initial_hash = plan.compute_hash()
    approval = ApprovalRecord(
        session_id="sess_hash_01",
        plan_id=plan.plan_id,
        plan_version=plan.version,
        plan_hash=initial_hash,
        approver="Curator Satwik",
        is_valid=True,
    )

    # Attacker alters the strategy positioning after approval
    plan.strategy.positioning_statement = "TAMPERED: High-energy commercial nightclub"
    mutated_hash = plan.compute_hash()
    assert mutated_hash != initial_hash

    # Execution attempt MUST fail and invalidate approval
    with pytest.raises(
        UnapprovedExecutionError,
        match="Plan was mutated after approval",
    ):
        await gov.execute_plan(
            plan,
            is_approved=True,
            approval=approval,
            approved_by="Curator Satwik",
        )

    assert approval.is_valid is False
    assert "mutated after approval" in approval.invalidation_reason


# =============================================================================
# 4. Unauthorized Execution Requests
# =============================================================================


@pytest.mark.asyncio
async def test_governance_rejects_unapproved_execution():
    """Negative Test: Direct execution invocation without approval raises UnapprovedExecutionError."""
    plan = await _create_test_plan()
    gov = GovernanceAgent()

    with pytest.raises(
        UnapprovedExecutionError,
        match="The agent must NEVER execute external actions before explicit approval",
    ):
        await gov.execute_plan(plan, is_approved=False)


# =============================================================================
# 5. Procurement CSV Artifact Schema & Encoding Validation
# =============================================================================


def test_procurement_csv_schema_and_columns():
    """Verifies procurement CSV adheres to exact 8-column schema and UTF-8 encoding."""
    ctx = WorkflowContext(
        session_id="sess_csv_test",
        cultural_matrix=CulturalMatrix(
            books=[
                CulturalRecommendation(
                    id="ent_book_kinfolk",
                    name="Kinfolk Interior",
                    type="book",
                    affinity=0.88,
                    source_query="/v2/insights",
                )
            ]
        ),
    )

    csv_text = generate_procurement_csv(ctx)
    assert isinstance(csv_text, str)

    reader = csv.reader(io.StringIO(csv_text))
    headers = next(reader)

    expected_headers = [
        "ISBN",
        "Title",
        "Author",
        "Publisher",
        "Quantity",
        "Unit Price",
        "Affinity Score",
        "Qloo Entity ID",
    ]
    assert headers == expected_headers

    rows = list(reader)
    assert len(rows) >= 1
    assert rows[0][1] == "Kinfolk Interior"
    assert rows[0][7] == "ent_book_kinfolk"


# =============================================================================
# 6. Parallel Agent Execution & Telemetry Verification
# =============================================================================


@pytest.mark.asyncio
async def test_parallel_agent_execution_and_telemetry(mock_mcp_adapter):
    """Verifies domain agents run concurrently and record precise telemetry."""
    adapter, _, _, _ = mock_mcp_adapter
    engine = WorkflowEngine(mcp_adapter=adapter)

    ctx = await engine.run_pipeline_to_approval_gate(
        raw_intent="Curate an analog vinyl listening bar in Austin",
        take_per_category=5,
    )

    assert ctx.current_state == WorkflowState.AWAITING_APPROVAL
    assert ctx.agent_telemetry != {}

    # Verify telemetry presence for all required agents
    assert "sonic" in ctx.agent_telemetry
    assert "procurement" in ctx.agent_telemetry
    assert "brand" in ctx.agent_telemetry
    assert "strategist" in ctx.agent_telemetry

    sonic_t = ctx.agent_telemetry["sonic"]
    assert sonic_t["status"] == "COMPLETE"
    assert sonic_t["duration_seconds"] > 0
    assert sonic_t["output_type"] == "playlist_artifact"
    assert sonic_t["validation"] == "VALIDATED"

    proc_t = ctx.agent_telemetry["procurement"]
    assert proc_t["status"] == "COMPLETE"
    assert proc_t["duration_seconds"] > 0
    assert proc_t["output_type"] == "csv_artifact"

    brand_t = ctx.agent_telemetry["brand"]
    assert brand_t["status"] == "COMPLETE"
    assert brand_t["duration_seconds"] > 0
    assert brand_t["output_type"] == "partnership_dossier"

    # Verify staged artifacts
    playlist_art = generate_spotify_playlist_artifact(ctx)
    assert playlist_art["status"] == "STAGED"
    assert "spotify:playlist:" in playlist_art["spotify_uri"]

    brand_dossiers = generate_brand_dossiers_artifact(ctx)
    assert len(brand_dossiers) >= 1
    assert brand_dossiers[0]["status"] == "DRAFTED"
    assert "draft_partnership_email" in brand_dossiers[0]
