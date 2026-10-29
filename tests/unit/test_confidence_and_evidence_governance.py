"""Regression and contract tests for confidence threshold audit and evidence semantics.

Verifies:
1. Missing affinity with valid, independently computed composite fit score passes governance.
2. Explicit measured affinity of 0.0 fails governance with measured low affinity.
3. Valid positive Qloo affinity passes governance.
4. Missing or malformed composite fit score fails governance with missing evidence.
5. Genuinely low-confidence candidate fails governance.
6. Spatial place entity without affinity preserves None without zero-fabrication.
7. Candidate with missing provenance fails governance (zero-hallucination gate).
8. Mixture of valid and invalid candidates fails governance specifically on invalid entity.
9. Validation retries with unchanged failure inputs exhaust bounded cycles and transition to FAILED.
10. Successful workflow requires human approval gate before execution.
"""

import pytest
import respx

from tasteops.agents.architect import ExperienceArchitect
from tasteops.agents.governance import GovernanceAgent
from tasteops.agents.partnership import PartnershipAgent
from tasteops.models.cultural_matrix import (
    CulturalMatrix,
    CulturalRecommendation,
    CulturalTwin,
)
from tasteops.models.insight import QlooInsight
from tasteops.workflows.engine import WorkflowEngine
from tasteops.workflows.schemas import (
    CulturalActivationPlan,
    CulturalPillar,
    CulturalStrategyOutput,
    ExperienceDesignInput,
    GovernanceValidationInput,
    PartnershipActivation,
    PartnershipOutput,
)
from tasteops.workflows.states import InvalidStateTransitionError, WorkflowState


@pytest.fixture
def clean_twin() -> CulturalTwin:
    return CulturalTwin(
        business_type="artisan listening bar",
        target_audience="Audiophiles and design purists",
        cultural_themes=["analog warmth", "minimalism"],
        mood="contemplative",
        mood_profile="acoustic warmth",
        budget="Medium Tier ($50k buildout)",
        anchor_entities=["ent_clean_anchor"],
    )


@pytest.fixture
def clean_strategy(clean_twin: CulturalTwin) -> CulturalStrategyOutput:
    return CulturalStrategyOutput(
        positioning_statement="Intimate vinyl listening sanctuary with curated spatial acoustics",
        cultural_pillars=[
            CulturalPillar(
                name="Sonic Purity",
                description="High fidelity analog sound",
                aligned_entity_ids=["ent_clean_anchor"],
            )
        ],
        target_subcultures=["Audiophile", "Design Enthusiast"],
        affinity_themes=["Analog warmth"],
        provenance_entity_ids=["ent_clean_anchor"],
    )


# -----------------------------------------------------------------------------
# 1. Missing affinity with valid independently computed composite fit score
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_missing_affinity_with_valid_composite_fit_score(
    clean_twin: CulturalTwin, clean_strategy: CulturalStrategyOutput
):
    """Spatial entity without affinity but with valid composite fit score passes governance."""
    gov = GovernanceAgent()
    matrix = CulturalMatrix(
        places=[
            CulturalRecommendation(
                id="ent_spatial_01",
                name="Leopold Cafe",
                type="place",
                affinity=None,
                source_query="/v2/insights?filter.type=urn:entity:place",
            )
        ]
    )

    part_agent = PartnershipAgent()
    part_output = await part_agent.identify_partnerships(
        cultural_twin=clean_twin,
        cultural_matrix=matrix,
        strategy=clean_strategy,
    )

    assert len(part_output.partnerships) >= 1
    activation = part_output.partnerships[0]

    # Verify score semantics
    assert (
        activation.affinity_score is None
    )  # Truthful: Qloo endpoint did not measure affinity
    assert activation.composite_fit_score is not None
    assert (
        activation.composite_fit_score >= 50.0
    )  # Independently computed composite score

    arch_agent = ExperienceArchitect()
    arch_output = await arch_agent.execute(
        ExperienceDesignInput(
            cultural_twin=clean_twin, strategy=clean_strategy, cultural_matrix=matrix
        )
    )

    gov_input = GovernanceValidationInput(
        cultural_twin=clean_twin,
        cultural_matrix=matrix,
        strategy=clean_strategy,
        experience_design=arch_output,
        partnerships=part_output,
    )

    validation = await gov.validate_plan(gov_input)
    assert validation.is_valid is True
    assert validation.provenance_verified is True
    assert validation.readiness_score == 1.0

    conf_check = next(
        c
        for c in validation.compliance_checks
        if c.rule_name == "confidence_threshold_audit"
    )
    assert conf_check.passed is True


# -----------------------------------------------------------------------------
# 2. Explicit measured affinity of 0.0
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_explicit_measured_affinity_zero_fails_governance(
    clean_twin: CulturalTwin, clean_strategy: CulturalStrategyOutput
):
    """A candidate with an explicit measured affinity of 0.0 must be rejected by governance."""
    gov = GovernanceAgent()
    matrix = CulturalMatrix(
        brands=[
            CulturalRecommendation(
                id="ent_brand_zero",
                name="Zero Affinity Brand",
                type="brand",
                affinity=0.0,  # Explicitly measured zero
                source_query="/v2/insights",
            )
        ]
    )

    part_agent = PartnershipAgent()
    part_output = await part_agent.identify_partnerships(
        cultural_twin=clean_twin,
        cultural_matrix=matrix,
        strategy=clean_strategy,
    )

    activation = part_output.partnerships[0]
    assert activation.affinity_score == 0.0  # Preserves measured zero

    arch_agent = ExperienceArchitect()
    arch_output = await arch_agent.execute(
        ExperienceDesignInput(
            cultural_twin=clean_twin, strategy=clean_strategy, cultural_matrix=matrix
        )
    )

    gov_input = GovernanceValidationInput(
        cultural_twin=clean_twin,
        cultural_matrix=matrix,
        strategy=clean_strategy,
        experience_design=arch_output,
        partnerships=part_output,
    )

    validation = await gov.validate_plan(gov_input)
    assert validation.is_valid is False
    assert validation.readiness_score == 0.3

    conf_check = next(
        c
        for c in validation.compliance_checks
        if c.rule_name == "confidence_threshold_audit"
    )
    assert conf_check.passed is False
    assert "measured low affinity: 0.00 < 0.50" in conf_check.detail


# -----------------------------------------------------------------------------
# 3. Valid positive Qloo affinity
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_valid_positive_qloo_affinity(
    clean_twin: CulturalTwin, clean_strategy: CulturalStrategyOutput
):
    """Candidates with measured positive Qloo affinity pass governance confidence audit."""
    gov = GovernanceAgent()
    matrix = CulturalMatrix(
        brands=[
            CulturalRecommendation(
                id="ent_brand_high",
                name="Audio-Technica",
                type="brand",
                affinity=0.91,
                source_query="/v2/insights",
            )
        ]
    )

    part_agent = PartnershipAgent()
    part_output = await part_agent.identify_partnerships(
        cultural_twin=clean_twin,
        cultural_matrix=matrix,
        strategy=clean_strategy,
    )

    activation = part_output.partnerships[0]
    assert activation.affinity_score == 0.91
    assert activation.composite_fit_score is not None

    arch_agent = ExperienceArchitect()
    arch_output = await arch_agent.execute(
        ExperienceDesignInput(
            cultural_twin=clean_twin, strategy=clean_strategy, cultural_matrix=matrix
        )
    )

    gov_input = GovernanceValidationInput(
        cultural_twin=clean_twin,
        cultural_matrix=matrix,
        strategy=clean_strategy,
        experience_design=arch_output,
        partnerships=part_output,
    )

    validation = await gov.validate_plan(gov_input)
    assert validation.is_valid is True
    conf_check = next(
        c
        for c in validation.compliance_checks
        if c.rule_name == "confidence_threshold_audit"
    )
    assert conf_check.passed is True


# -----------------------------------------------------------------------------
# 4. Missing or malformed composite fit score
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_missing_or_malformed_composite_fit_score(
    clean_twin: CulturalTwin, clean_strategy: CulturalStrategyOutput
):
    """If neither affinity nor composite fit score is provided, governance rejects it."""
    gov = GovernanceAgent()
    matrix = CulturalMatrix(
        brands=[
            CulturalRecommendation(
                id="ent_brand_none",
                name="Evidence-Free Brand",
                type="brand",
                affinity=None,
                source_query="/v2/insights",
            )
        ]
    )

    # Malformed activation: affinity_score=None and composite_fit_score=None
    malformed_part = PartnershipOutput(
        partnerships=[
            PartnershipActivation(
                partner_name="Evidence-Free Brand",
                partner_entity_id="ent_brand_none",
                category="apparel",
                activation_type="Residency",
                concept_description="Pop up activation",
                affinity_score=None,
                composite_fit_score=None,
                alignment_rationale="Speculative alignment",
            )
        ],
        candidates=[],
        provenance_entity_ids=["ent_brand_none"],
    )

    arch_agent = ExperienceArchitect()
    arch_output = await arch_agent.execute(
        ExperienceDesignInput(
            cultural_twin=clean_twin, strategy=clean_strategy, cultural_matrix=matrix
        )
    )

    gov_input = GovernanceValidationInput(
        cultural_twin=clean_twin,
        cultural_matrix=matrix,
        strategy=clean_strategy,
        experience_design=arch_output,
        partnerships=malformed_part,
    )

    validation = await gov.validate_plan(gov_input)
    assert validation.is_valid is False
    conf_check = next(
        c
        for c in validation.compliance_checks
        if c.rule_name == "confidence_threshold_audit"
    )
    assert conf_check.passed is False
    assert "missing affinity and composite fit evidence" in conf_check.detail


# -----------------------------------------------------------------------------
# 5. Genuinely low-confidence candidate
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_genuinely_low_confidence_candidate(
    clean_twin: CulturalTwin, clean_strategy: CulturalStrategyOutput
):
    """A candidate with a composite fit score below 50.0 must fail governance."""
    gov = GovernanceAgent()
    matrix = CulturalMatrix(
        brands=[
            CulturalRecommendation(
                id="ent_brand_low_fit",
                name="Mass Market Fast Food",
                type="brand",
                affinity=None,
                source_query="/v2/insights",
            )
        ]
    )

    low_fit_part = PartnershipOutput(
        partnerships=[
            PartnershipActivation(
                partner_name="Mass Market Fast Food",
                partner_entity_id="ent_brand_low_fit",
                category="food",
                activation_type="Residency",
                concept_description="Drive-thru kiosk in listening room",
                affinity_score=None,
                composite_fit_score=32.0,  # Well below 50.0 threshold
                alignment_rationale="Clashing commercial partnership",
            )
        ],
        candidates=[],
        provenance_entity_ids=["ent_brand_low_fit"],
    )

    arch_agent = ExperienceArchitect()
    arch_output = await arch_agent.execute(
        ExperienceDesignInput(
            cultural_twin=clean_twin, strategy=clean_strategy, cultural_matrix=matrix
        )
    )

    gov_input = GovernanceValidationInput(
        cultural_twin=clean_twin,
        cultural_matrix=matrix,
        strategy=clean_strategy,
        experience_design=arch_output,
        partnerships=low_fit_part,
    )

    validation = await gov.validate_plan(gov_input)
    assert validation.is_valid is False
    conf_check = next(
        c
        for c in validation.compliance_checks
        if c.rule_name == "confidence_threshold_audit"
    )
    assert conf_check.passed is False
    assert "low composite fit: 32.0 < 50.0" in conf_check.detail


# -----------------------------------------------------------------------------
# 6. Spatial place entity without affinity measurement preserves None
# -----------------------------------------------------------------------------
def test_spatial_place_normalization_preserves_none():
    """Normalizing raw spatial place search items without affinity must yield affinity=None, not 0.0."""
    raw_qloo_place = {
        "id": "20BFD7E8-2558-4D3B-835C-45A63996D3B0",
        "name": "The Taj Mahal Palace, Mumbai",
        "type": "place",
        # Neither affinity nor score provided by spatial search endpoint
    }

    insight = QlooInsight.model_validate(raw_qloo_place)
    assert insight.affinity is None
    assert insight.score is None

    rec = CulturalRecommendation(
        id=insight.id,
        name=insight.name,
        type="place",
        affinity=insight.affinity,
        score=insight.score,
        confidence=insight.affinity,
        source_query="/v2/insights?filter.type=urn:entity:place",
    )
    assert rec.affinity is None
    assert rec.confidence is None


# -----------------------------------------------------------------------------
# 7. Candidate with missing provenance
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_candidate_with_missing_provenance_fails_governance(
    clean_twin: CulturalTwin, clean_strategy: CulturalStrategyOutput
):
    """An unverified entity ID not originating in the CulturalMatrix must fail Zero-Hallucination audit."""
    gov = GovernanceAgent()
    matrix = CulturalMatrix(
        brands=[
            CulturalRecommendation(
                id="ent_verified_01",
                name="Vetted Audio Brand",
                type="brand",
                affinity=0.88,
                source_query="/v2/insights",
            )
        ]
    )

    unverified_part = PartnershipOutput(
        partnerships=[
            PartnershipActivation(
                partner_name="Hallucinated Brand",
                partner_entity_id="ent_unverified_phantom",  # Not in verified matrix!
                category="audio",
                activation_type="Residency",
                concept_description="Hardware installation",
                affinity_score=0.95,
                composite_fit_score=90.0,
                alignment_rationale="Aesthetic synergy",
            )
        ],
        candidates=[],
        provenance_entity_ids=["ent_unverified_phantom"],
    )

    arch_agent = ExperienceArchitect()
    arch_output = await arch_agent.execute(
        ExperienceDesignInput(
            cultural_twin=clean_twin, strategy=clean_strategy, cultural_matrix=matrix
        )
    )

    gov_input = GovernanceValidationInput(
        cultural_twin=clean_twin,
        cultural_matrix=matrix,
        strategy=clean_strategy,
        experience_design=arch_output,
        partnerships=unverified_part,
    )

    validation = await gov.validate_plan(gov_input)
    assert validation.is_valid is False
    assert validation.provenance_verified is False
    assert "ent_unverified_phantom" in validation.unverified_entity_ids

    prov_check = next(
        c
        for c in validation.compliance_checks
        if c.rule_name == "invalid_entities_audit"
    )
    assert prov_check.passed is False


# -----------------------------------------------------------------------------
# 8. Mixture of valid and invalid candidates
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_mixture_of_valid_and_invalid_candidates(
    clean_twin: CulturalTwin, clean_strategy: CulturalStrategyOutput
):
    """When a plan mixes high-affinity, valid spatial, and measured low-affinity candidates, it must fail on the invalid candidate."""
    gov = GovernanceAgent()
    matrix = CulturalMatrix(
        brands=[
            CulturalRecommendation(
                id="ent_valid_brand",
                name="Valid High-Affinity Brand",
                type="brand",
                affinity=0.89,
                source_query="/v2/insights",
            ),
            CulturalRecommendation(
                id="ent_low_brand",
                name="Low-Affinity Brand",
                type="brand",
                affinity=0.22,  # Measured low affinity!
                source_query="/v2/insights",
            ),
        ],
        places=[
            CulturalRecommendation(
                id="ent_valid_place",
                name="Valid Spatial Place",
                type="place",
                affinity=None,  # Spatial place with no affinity
                source_query="/v2/insights",
            )
        ],
    )

    mixed_part = PartnershipOutput(
        partnerships=[
            PartnershipActivation(
                partner_name="Valid High-Affinity Brand",
                partner_entity_id="ent_valid_brand",
                category="hardware",
                activation_type="Residency",
                concept_description="Analog setup",
                affinity_score=0.89,
                composite_fit_score=85.0,
                alignment_rationale="High alignment",
            ),
            PartnershipActivation(
                partner_name="Valid Spatial Place",
                partner_entity_id="ent_valid_place",
                category="hospitality",
                activation_type="Guest Roaster",
                concept_description="Barista residency",
                affinity_score=None,
                composite_fit_score=78.0,
                alignment_rationale="Spatial proximity",
            ),
            PartnershipActivation(
                partner_name="Low-Affinity Brand",
                partner_entity_id="ent_low_brand",
                category="apparel",
                activation_type="Merch",
                concept_description="Merchandise line",
                affinity_score=0.22,
                composite_fit_score=35.0,
                alignment_rationale="Weak alignment",
            ),
        ],
        candidates=[],
        provenance_entity_ids=["ent_valid_brand", "ent_valid_place", "ent_low_brand"],
    )

    arch_agent = ExperienceArchitect()
    arch_output = await arch_agent.execute(
        ExperienceDesignInput(
            cultural_twin=clean_twin, strategy=clean_strategy, cultural_matrix=matrix
        )
    )

    gov_input = GovernanceValidationInput(
        cultural_twin=clean_twin,
        cultural_matrix=matrix,
        strategy=clean_strategy,
        experience_design=arch_output,
        partnerships=mixed_part,
    )

    validation = await gov.validate_plan(gov_input)
    assert validation.is_valid is False
    conf_check = next(
        c
        for c in validation.compliance_checks
        if c.rule_name == "confidence_threshold_audit"
    )
    assert conf_check.passed is False
    assert (
        "Low-Affinity Brand (measured low affinity: 0.22 < 0.50)" in conf_check.detail
    )
    assert "Valid High-Affinity Brand" not in conf_check.detail
    assert "Valid Spatial Place" not in conf_check.detail


# -----------------------------------------------------------------------------
# 9. Validation retries with unchanged failure inputs
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_validation_retries_exhaustion_transitions_to_failed(
    clean_twin: CulturalTwin, clean_strategy: CulturalStrategyOutput
):
    """Validation failure with unchanged inputs loops up to max_validation_cycles and transitions to FAILED."""
    gov = GovernanceAgent()
    matrix = CulturalMatrix(
        brands=[
            CulturalRecommendation(
                id="ent_low_affinity",
                name="Low Affinity Brand",
                type="brand",
                affinity=0.15,
                source_query="/v2/insights",
            )
        ]
    )

    low_part = PartnershipOutput(
        partnerships=[
            PartnershipActivation(
                partner_name="Low Affinity Brand",
                partner_entity_id="ent_low_affinity",
                category="brand",
                activation_type="Hardware",
                concept_description="Audio gear",
                affinity_score=0.15,
                composite_fit_score=40.0,
                alignment_rationale="Low affinity",
            )
        ],
        candidates=[],
        provenance_entity_ids=["ent_low_affinity"],
    )

    arch_agent = ExperienceArchitect()
    arch_output = await arch_agent.execute(
        ExperienceDesignInput(
            cultural_twin=clean_twin, strategy=clean_strategy, cultural_matrix=matrix
        )
    )

    engine = WorkflowEngine(max_validation_cycles=2)
    ctx = engine.initialize_session("Vinyl bar")
    ctx.cultural_twin = clean_twin
    ctx.cultural_matrix = matrix
    ctx.strategy_output = clean_strategy
    ctx.experience_output = arch_output
    ctx.partnership_output = low_part
    ctx.current_state = WorkflowState.PLAN_GENERATED

    gov_input = GovernanceValidationInput(
        cultural_twin=clean_twin,
        cultural_matrix=matrix,
        strategy=clean_strategy,
        experience_design=arch_output,
        partnerships=low_part,
    )
    gov_output = await gov.validate_plan(gov_input)
    ctx.plan = CulturalActivationPlan(
        plan_id="plan_retry_test",
        cultural_twin=clean_twin,
        cultural_matrix=matrix,
        strategy=clean_strategy,
        experience_design=arch_output,
        partnerships=low_part,
        governance=gov_output,
        execution_plan=gov.plan(gov_input),
    )

    # Cycle 1 -> loops back to PLAN_GENERATED
    await engine.validate_and_await_approval(ctx)
    assert ctx.current_state == WorkflowState.PLAN_GENERATED
    assert ctx.validation_cycle_count == 1

    # Cycle 2 -> loops back to PLAN_GENERATED
    await engine.validate_and_await_approval(ctx)
    assert ctx.current_state == WorkflowState.PLAN_GENERATED
    assert ctx.validation_cycle_count == 2

    # Cycle 3 -> exhausted -> legally transitions to FAILED
    await engine.validate_and_await_approval(ctx)
    assert ctx.current_state == WorkflowState.FAILED
    assert "VALIDATION_FAILURE" in ctx.error_message
    assert "cycles exhausted" in ctx.error_message


# -----------------------------------------------------------------------------
# 10. Successful workflow requires human approval before execution
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_successful_workflow_requires_human_approval_gate(
    mock_settings, mock_mcp_adapter
):
    """A valid plan reaches AWAITING_APPROVAL and strictly refuses execution until human signs off."""
    adapter, mock_search, mock_tags, mock_insights = mock_mcp_adapter

    async with respx.mock(
        base_url="https://hackathon.api.qloo.com", assert_all_called=False
    ) as mock_router:
        mock_router.get("/search").respond(status_code=200, json=mock_search)
        mock_router.get("/v2/tags").respond(status_code=200, json=mock_tags)
        mock_router.get("/v2/insights").respond(status_code=200, json=mock_insights)

        engine = WorkflowEngine(mcp_adapter=adapter)
        raw_intent = "Artisan listening bar in Bushwick with single-origin coffee"
        hints = {"raw_anchor_entities": ["Blue Bottle Coffee"]}

        ctx = await engine.run_pipeline_to_approval_gate(raw_intent, hints)

        # Assert state is stopped at AWAITING_APPROVAL
        assert ctx.current_state == WorkflowState.AWAITING_APPROVAL
        assert ctx.plan is not None
        assert ctx.governance_output.is_valid is True
        assert ctx.governance_output.readiness_score == 1.0

        # Execution is strictly refused before human sign-off
        with pytest.raises(InvalidStateTransitionError):
            await engine.execute_plan(ctx)

        # Human approves plan
        approved_ctx = await engine.approve_plan(ctx, approver="curator_agrawal")
        assert approved_ctx.current_state == WorkflowState.APPROVED
        assert approved_ctx.approval is not None
        assert approved_ctx.approval.is_valid is True
        assert approved_ctx.approval.approver == "curator_agrawal"
