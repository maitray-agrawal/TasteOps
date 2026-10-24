"""Contract verification tests for TasteOps Agent Orchestration Layer.

Verifies strict typed input/output contracts for:
1. Cultural Strategist
2. Experience Architect
3. Partnership Agent
4. Governance / Execution Agent

Checks for each agent:
- Pydantic validation (rejection of malformed data)
- Required fields (no missing essential attributes)
- Provenance (Qloo IDs, source queries, entity types)
- Confidence (bounded strictly [0.0, 1.0] or [0.0, 100.0])
- Failure behavior (deterministic errors, zero silent coercion)
- Deterministic serialization (model_dump and model_dump_json round-trip)
- Compatibility with the workflow engine
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from tasteops.agents.architect import ExperienceArchitect
from tasteops.agents.governance import (
    GovernanceAgent,
    ProvenanceValidationError,
    UnapprovedExecutionError,
)
from tasteops.agents.partnership import PartnershipAgent
from tasteops.agents.strategist import CulturalStrategist
from tasteops.models.cultural_matrix import (
    CulturalMatrix,
    CulturalRecommendation,
    CulturalTwin,
    PhysicalSpaceBrief,
    ResolvedEntity,
    ResolvedTag,
)
from tasteops.workflows.schemas import (
    AtmosphereGuidelines,
    BrandEcosystem,
    BrandPartnershipCandidate,
    CulturalActivationPlan,
    CulturalProgrammingIdeas,
    CulturalStrategyInput,
    CulturalStrategyOutput,
    ExecutionPlan,
    ExecutionSummary,
    ExecutionTask,
    ExperienceDesignInput,
    ExperienceDesignOutput,
    ExperienceRecommendation,
    GovernanceValidationInput,
    GovernanceValidationOutput,
    LocalExperienceEcosystem,
    OutreachDraft,
    PartnershipInput,
    PartnershipOutput,
    PartnershipScoreBreakdown,
    ReadingLibraryIdentity,
    SonicIdentity,
)

# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def sample_matrix() -> CulturalMatrix:
    """Provides a valid, verified CulturalMatrix."""
    return CulturalMatrix(
        artists=[
            CulturalRecommendation(
                id="ent_artist_01",
                name="Floating Points",
                type="artist",
                affinity=0.92,
                source_query="/v2/insights",
            ),
            CulturalRecommendation(
                id="ent_artist_02",
                name="Four Tet",
                type="artist",
                affinity=0.88,
                source_query="/v2/insights",
            ),
        ],
        brands=[
            CulturalRecommendation(
                id="ent_brand_01",
                name="Audio-Technica",
                type="brand",
                affinity=0.91,
                source_query="/v2/insights",
            ),
            CulturalRecommendation(
                id="ent_brand_02",
                name="Hasami Porcelain",
                type="brand",
                affinity=0.86,
                source_query="/v2/insights",
            ),
        ],
        places=[
            CulturalRecommendation(
                id="ent_place_01",
                name="Public Records",
                type="place",
                affinity=0.95,
                source_query="/v2/insights",
            )
        ],
        books=[
            CulturalRecommendation(
                id="ent_book_01",
                name="In Praise of Shadows",
                type="book",
                affinity=0.89,
                source_query="/v2/insights",
            )
        ],
    )


@pytest.fixture
def sample_twin() -> CulturalTwin:
    """Provides a valid, verified CulturalTwin."""
    return CulturalTwin(
        business_type="Analog Vinyl Listening Bar & Cafe",
        target_audience="Audiophiles and design purists aged 25-45",
        mood="Warm, acoustic focus, minimalist, intimate",
        positioning="Japanese-inspired craft audio sanctuary",
        budget="Boutique Premium",
        anchor_entities=["ent_blue_bottle_123"],
        resolved_entities=[
            ResolvedEntity(
                id="ent_blue_bottle_123",
                name="Blue Bottle Coffee",
                type="place",
                confidence=0.95,
                why_it_matters="Anchors third-wave coffee ritual and minimalist spatial tempo.",
                source="qloo_search",
            )
        ],
        resolved_tags=["tag_jp_minimalism"],
        resolved_tag_details=[
            ResolvedTag(
                id="tag_jp_minimalism",
                name="Japanese Minimalism",
                confidence=1.0,
                why_it_matters="Directly informs spatial restraint and organic materiality.",
            )
        ],
        cultural_constraints=["Acoustic decibel levels strictly under 75dB"],
        exclusions=["Commercial Top 40", "Fluorescent lighting"],
        confidence=0.95,
    )


# ===========================================================================
# 1. Cultural Strategist Contract Tests
# ===========================================================================


class TestCulturalStrategistContract:
    """Verifies strict typed input/output contracts for Cultural Strategist."""

    def test_strategist_input_rejects_missing_required_fields(self):
        """Reject PhysicalSpaceBrief missing business_type."""
        with pytest.raises(ValidationError) as exc:
            PhysicalSpaceBrief.model_validate({"target_audience": "Music lovers"})
        assert "business_type" in str(exc.value)

    @pytest.mark.asyncio
    async def test_strategist_transform_brief_rejects_invalid_type(self):
        """Reject brief with invalid container type (e.g. int, str)."""
        strategist = CulturalStrategist()
        with pytest.raises(TypeError) as exc:
            await strategist.transform_brief(12345)  # type: ignore[arg-type]
        assert "Expected PhysicalSpaceBrief or dict" in str(exc.value)

    def test_strategist_strategy_input_requires_twin_and_matrix(self):
        """CulturalStrategyInput must require both cultural_twin and cultural_matrix."""
        with pytest.raises(ValidationError) as exc:
            CulturalStrategyInput.model_validate({})
        errors = str(exc.value)
        assert "cultural_twin" in errors
        assert "cultural_matrix" in errors

    @pytest.mark.asyncio
    async def test_strategist_execute_rejects_invalid_type(self):
        """CulturalStrategist.execute must reject invalid payload types."""
        strategist = CulturalStrategist()
        with pytest.raises(TypeError) as exc:
            await strategist.execute("not_a_valid_payload")  # type: ignore[arg-type]
        assert "Expected CulturalStrategyInput or dict" in str(exc.value)

    @pytest.mark.asyncio
    async def test_strategist_output_conforms_to_schema_and_provenance(
        self, sample_twin, sample_matrix
    ):
        """CulturalStrategist.execute produces valid CulturalStrategyOutput with required fields and provenance."""
        strategist = CulturalStrategist()
        payload = CulturalStrategyInput(
            cultural_twin=sample_twin, cultural_matrix=sample_matrix
        )
        output = await strategist.execute(payload)

        # 1. Pydantic validation & Required fields
        assert isinstance(output, CulturalStrategyOutput)
        assert output.positioning_statement
        assert len(output.cultural_pillars) >= 1
        assert len(output.target_subcultures) >= 1
        assert len(output.affinity_themes) >= 1
        assert len(output.provenance_entity_ids) >= 1

        # 2. Provenance: Every aligned_entity_id in pillars exists in provenance_entity_ids
        for pillar in output.cultural_pillars:
            assert pillar.name
            assert pillar.description
            for eid in pillar.aligned_entity_ids:
                assert eid in output.provenance_entity_ids

    def test_strategist_output_rejects_empty_pillars(self):
        """Reject CulturalStrategyOutput with empty cultural_pillars (min_length=1)."""
        with pytest.raises(ValidationError) as exc:
            CulturalStrategyOutput(
                positioning_statement="Positioning",
                cultural_pillars=[],  # Empty list violates min_length=1
                target_subcultures=["Subculture"],
                affinity_themes=["Theme"],
                provenance_entity_ids=["ent_1"],
            )
        assert "cultural_pillars" in str(exc.value)

    def test_cultural_twin_confidence_bounds(self):
        """CulturalTwin confidence must strictly lie within [0.0, 1.0]."""
        with pytest.raises(ValidationError):
            CulturalTwin(confidence=1.5)
        with pytest.raises(ValidationError):
            CulturalTwin(confidence=-0.1)

    @pytest.mark.asyncio
    async def test_strategist_deterministic_serialization(
        self, sample_twin, sample_matrix
    ):
        """Verify deterministic serialization (model_dump and model_dump_json round-trip)."""
        strategist = CulturalStrategist()
        output = await strategist.execute(
            CulturalStrategyInput(
                cultural_twin=sample_twin, cultural_matrix=sample_matrix
            )
        )

        dumped_dict = output.model_dump()
        assert isinstance(dumped_dict, dict)
        assert dumped_dict["positioning_statement"] == output.positioning_statement

        json_str = output.model_dump_json()
        restored = CulturalStrategyOutput.model_validate_json(json_str)
        assert restored == output


# ===========================================================================
# 2. Experience Architect Contract Tests
# ===========================================================================


class TestExperienceArchitectContract:
    """Verifies strict typed input/output contracts for Experience Architect."""

    def test_architect_input_requires_cultural_matrix(self):
        """ExperienceDesignInput requires cultural_matrix."""
        with pytest.raises(ValidationError) as exc:
            ExperienceDesignInput.model_validate({})
        assert "cultural_matrix" in str(exc.value)

    @pytest.mark.asyncio
    async def test_architect_rejects_invalid_input_types(
        self, sample_twin, sample_matrix
    ):
        """ExperienceArchitect rejects invalid input types with TypeError."""
        architect = ExperienceArchitect()
        with pytest.raises(TypeError) as exc1:
            await architect.execute(42)  # type: ignore[arg-type]
        assert "Expected ExperienceDesignInput or dict" in str(exc1.value)

        with pytest.raises(TypeError) as exc2:
            await architect.design_experience(
                cultural_twin="not_a_twin",
                cultural_matrix=sample_matrix,  # type: ignore[arg-type]
            )
        assert "Expected CulturalTwin or dict" in str(exc2.value)

        with pytest.raises(TypeError) as exc3:
            await architect.design_experience(
                cultural_twin=sample_twin,
                cultural_matrix=None,  # type: ignore[arg-type]
            )
        assert "Expected CulturalMatrix or dict" in str(exc3.value)

    @pytest.mark.asyncio
    async def test_architect_output_contract_all_six_identities(
        self, sample_twin, sample_matrix
    ):
        """ExperienceDesignOutput contains all 6 required identity domains."""
        architect = ExperienceArchitect()
        output = await architect.design_experience(
            cultural_twin=sample_twin, cultural_matrix=sample_matrix
        )

        assert isinstance(output, ExperienceDesignOutput)
        assert isinstance(output.sonic_identity, SonicIdentity)
        assert isinstance(output.reading_library_identity, ReadingLibraryIdentity)
        assert isinstance(output.brand_ecosystem, BrandEcosystem)
        assert isinstance(output.local_experience_ecosystem, LocalExperienceEcosystem)
        assert isinstance(output.cultural_programming_ideas, CulturalProgrammingIdeas)
        assert isinstance(output.atmosphere_guidelines, AtmosphereGuidelines)
        assert len(output.provenance_entity_ids) >= 1

    def test_experience_recommendation_contract_and_confidence_bounds(self):
        """ExperienceRecommendation enforces required fields and bounded confidence [0.0, 1.0]."""
        # Missing qloo_evidence must be rejected
        with pytest.raises(ValidationError) as exc:
            ExperienceRecommendation(
                recommendation="Four Tet",
                cultural_rationale="Acoustic alignment",
                confidence=0.9,
                expected_role="Lead vinyl rotation",
                # qloo_evidence omitted!
            )  # type: ignore[call-arg]
        assert "qloo_evidence" in str(exc.value)

        # Confidence > 1.0 must be rejected
        with pytest.raises(ValidationError):
            ExperienceRecommendation(
                recommendation="Four Tet",
                qloo_evidence={"entity_id": "ent_1"},
                cultural_rationale="Acoustic alignment",
                confidence=1.2,
                expected_role="Lead vinyl rotation",
            )

        # Confidence < 0.0 must be rejected
        with pytest.raises(ValidationError):
            ExperienceRecommendation(
                recommendation="Four Tet",
                qloo_evidence={"entity_id": "ent_1"},
                cultural_rationale="Acoustic alignment",
                confidence=-0.05,
                expected_role="Lead vinyl rotation",
            )

    @pytest.mark.asyncio
    async def test_architect_deterministic_serialization(
        self, sample_twin, sample_matrix
    ):
        """ExperienceDesignOutput serializes deterministically and round-trips via JSON."""
        architect = ExperienceArchitect()
        output = await architect.design_experience(
            cultural_twin=sample_twin, cultural_matrix=sample_matrix
        )

        data = output.model_dump()
        assert isinstance(data, dict)
        assert "sonic_identity" in data
        assert "atmosphere_guidelines" in data

        json_str = output.model_dump_json()
        restored = ExperienceDesignOutput.model_validate_json(json_str)
        assert restored.sonic_identity.overview == output.sonic_identity.overview
        assert restored.provenance_entity_ids == output.provenance_entity_ids


# ===========================================================================
# 3. Partnership Agent Contract Tests
# ===========================================================================


class TestPartnershipAgentContract:
    """Verifies strict typed input/output contracts for Partnership Agent."""

    def test_partnership_input_requires_cultural_matrix(self):
        """PartnershipInput requires cultural_matrix."""
        with pytest.raises(ValidationError) as exc:
            PartnershipInput.model_validate({})
        assert "cultural_matrix" in str(exc.value)

    @pytest.mark.asyncio
    async def test_partnership_agent_rejects_invalid_input_types(
        self, sample_twin, sample_matrix
    ):
        """PartnershipAgent rejects invalid input types with TypeError."""
        agent = PartnershipAgent()
        with pytest.raises(TypeError) as exc1:
            await agent.execute("bad_input")  # type: ignore[arg-type]
        assert "Expected PartnershipInput or dict" in str(exc1.value)

        with pytest.raises(TypeError) as exc2:
            await agent.identify_partnerships(
                cultural_twin=999,
                cultural_matrix=sample_matrix,  # type: ignore[arg-type]
            )
        assert "Expected CulturalTwin, dict, or None" in str(exc2.value)

    @pytest.mark.asyncio
    async def test_partnership_output_conforms_to_schema_and_guardrails(
        self, sample_twin, sample_matrix
    ):
        """PartnershipOutput contains valid candidates, scores, outreach drafts, and guardrails."""
        agent = PartnershipAgent()
        output = await agent.identify_partnerships(
            cultural_twin=sample_twin, cultural_matrix=sample_matrix
        )

        assert isinstance(output, PartnershipOutput)
        assert len(output.candidates) >= 1
        assert len(output.provenance_entity_ids) >= 1

        for candidate in output.candidates:
            assert isinstance(candidate, BrandPartnershipCandidate)
            assert candidate.brand
            assert candidate.brand_entity_id in output.provenance_entity_ids
            # Bounded score [0.0, 100.0]
            assert 0.0 <= candidate.score <= 100.0
            # Guardrail: Never claim active partnership
            assert candidate.is_existing_partner is False
            # Outreach draft
            assert isinstance(candidate.outreach_draft, OutreachDraft)
            assert (
                "Exploratory outreach draft only" in candidate.outreach_draft.disclaimer
            )
            # Supporting Qloo evidence
            assert isinstance(candidate.supporting_qloo_evidence, dict)
            assert candidate.supporting_qloo_evidence["entity_id"]

    def test_partnership_score_breakdown_bounds_rejection(self):
        """PartnershipScoreBreakdown strictly rejects scores outside [0.0, 100.0]."""
        with pytest.raises(ValidationError):
            PartnershipScoreBreakdown(
                cultural_fit=105.0,  # Out of bounds!
                audience_fit=90.0,
                brand_compatibility=80.0,
                context_fit=85.0,
                budget_fit=88.0,
                novelty=75.0,
                overall_score=87.0,
            )

        with pytest.raises(ValidationError):
            PartnershipScoreBreakdown(
                cultural_fit=-5.0,  # Out of bounds!
                audience_fit=90.0,
                brand_compatibility=80.0,
                context_fit=85.0,
                budget_fit=88.0,
                novelty=75.0,
                overall_score=87.0,
            )

    @pytest.mark.asyncio
    async def test_partnership_deterministic_serialization(
        self, sample_twin, sample_matrix
    ):
        """PartnershipOutput serializes deterministically and round-trips via JSON."""
        agent = PartnershipAgent()
        output = await agent.identify_partnerships(
            cultural_twin=sample_twin, cultural_matrix=sample_matrix
        )

        data = output.model_dump()
        assert isinstance(data, dict)
        assert "candidates" in data
        assert "provenance_entity_ids" in data

        json_str = output.model_dump_json()
        restored = PartnershipOutput.model_validate_json(json_str)
        assert len(restored.candidates) == len(output.candidates)
        assert restored.provenance_entity_ids == output.provenance_entity_ids


# ===========================================================================
# 4. Governance / Execution Agent Contract Tests
# ===========================================================================


class TestGovernanceAgentContract:
    """Verifies strict typed input/output contracts for Governance / Execution Agent."""

    def test_governance_validation_input_requires_all_agent_outputs(
        self, sample_twin, sample_matrix
    ):
        """GovernanceValidationInput requires twin, matrix, strategy, experience, and partnerships."""
        with pytest.raises(ValidationError) as exc:
            GovernanceValidationInput.model_validate({})
        errors = str(exc.value)
        assert "cultural_twin" in errors
        assert "cultural_matrix" in errors
        assert "strategy" in errors
        assert "experience_design" in errors
        assert "partnerships" in errors

    @pytest.mark.asyncio
    async def test_governance_rejects_invalid_input_types(self):
        """GovernanceAgent rejects invalid argument types across all public methods."""
        gov = GovernanceAgent()

        with pytest.raises(TypeError) as exc1:
            gov.plan("invalid_payload")  # type: ignore[arg-type]
        assert "Expected GovernanceValidationInput or dict" in str(exc1.value)

        with pytest.raises(TypeError) as exc2:
            await gov.validate_plan(12345)  # type: ignore[arg-type]
        assert "Expected GovernanceValidationInput or dict" in str(exc2.value)

        with pytest.raises(TypeError) as exc3:
            await gov.execute_plan("not_a_plan")  # type: ignore[arg-type]
        assert "Expected CulturalActivationPlan or dict" in str(exc3.value)

        with pytest.raises(TypeError) as exc4:
            gov.audit("not_a_plan", [])  # type: ignore[arg-type]
        assert "Expected CulturalActivationPlan or dict" in str(exc4.value)

    @pytest.mark.asyncio
    async def test_governance_plan_and_validation_outputs(
        self, sample_twin, sample_matrix
    ):
        """GovernanceAgent generates structured ExecutionPlan and GovernanceValidationOutput."""
        strategist = CulturalStrategist()
        strat_out = await strategist.execute(
            CulturalStrategyInput(
                cultural_twin=sample_twin, cultural_matrix=sample_matrix
            )
        )

        architect = ExperienceArchitect()
        arch_out = await architect.execute(
            ExperienceDesignInput(strategy=strat_out, cultural_matrix=sample_matrix)
        )

        partnership = PartnershipAgent()
        part_out = await partnership.execute(
            PartnershipInput(
                strategy=strat_out,
                experience_design=arch_out,
                cultural_matrix=sample_matrix,
            )
        )

        gov_input = GovernanceValidationInput(
            cultural_twin=sample_twin,
            cultural_matrix=sample_matrix,
            strategy=strat_out,
            experience_design=arch_out,
            partnerships=part_out,
        )

        gov = GovernanceAgent()

        # 1. PLAN Phase: ExecutionPlan contract
        exec_plan = gov.plan(gov_input)
        assert isinstance(exec_plan, ExecutionPlan)
        assert exec_plan.plan_id.startswith("exec_plan_")
        assert len(exec_plan.actions) >= 1
        assert exec_plan.estimated_cost
        assert isinstance(exec_plan.dependencies, dict)

        # 2. VALIDATE Phase: GovernanceValidationOutput contract
        gov_out = await gov.validate_plan(gov_input, execution_plan=exec_plan)
        assert isinstance(gov_out, GovernanceValidationOutput)
        assert isinstance(gov_out.is_valid, bool)
        assert isinstance(gov_out.provenance_verified, bool)
        assert 0.0 <= gov_out.readiness_score <= 1.0
        assert len(gov_out.compliance_checks) == 7

    def test_governance_validation_output_readiness_score_bounds(self):
        """GovernanceValidationOutput readiness_score must lie within [0.0, 1.0]."""
        with pytest.raises(ValidationError):
            GovernanceValidationOutput(
                is_valid=True, provenance_verified=True, readiness_score=1.5
            )
        with pytest.raises(ValidationError):
            GovernanceValidationOutput(
                is_valid=True, provenance_verified=True, readiness_score=-0.2
            )

    def test_governance_validate_task_provenance_strictly_enforced(self):
        """GovernanceAgent.validate_task_provenance strictly rejects missing keys or invalid IDs."""
        gov = GovernanceAgent()

        # Missing required provenance keys
        task_bad = ExecutionTask(
            task_id="task_01",
            action="Action",
            provenance={"source": "qloo"},  # Missing other 10 mandatory keys!
        )
        with pytest.raises(ProvenanceValidationError) as exc:
            gov.validate_task_provenance(task_bad)
        assert "missing mandatory provenance fields" in str(exc.value)

        # Invalid/unverified Qloo ID
        now = datetime.now(UTC).isoformat()
        task_invalid_id = ExecutionTask(
            task_id="task_02",
            action="Action",
            provenance={
                "source": "qloo",
                "source_id": "invalid_fake_id_999",
                "source_type": "artist",
                "query": "/v2/insights",
                "timestamp": now,
                "task_id": "task_02",
                "plan_id": "plan_01",
                "session_id": "sess_01",
                "approved_by": "curator",
                "approved_at": now,
                "execution_status": "EXECUTED",
            },
        )
        with pytest.raises(ProvenanceValidationError) as exc2:
            gov.validate_task_provenance(task_invalid_id)
        assert "references invalid/unverified Qloo ID" in str(exc2.value)

    @pytest.mark.asyncio
    async def test_governance_refuses_unapproved_execution(
        self, sample_twin, sample_matrix
    ):
        """GovernanceAgent refuses execution before explicit approval."""
        strategist = CulturalStrategist()
        strat_out = await strategist.execute(
            CulturalStrategyInput(
                cultural_twin=sample_twin, cultural_matrix=sample_matrix
            )
        )
        architect = ExperienceArchitect()
        arch_out = await architect.execute(
            ExperienceDesignInput(strategy=strat_out, cultural_matrix=sample_matrix)
        )
        partnership = PartnershipAgent()
        part_out = await partnership.execute(
            PartnershipInput(
                strategy=strat_out,
                experience_design=arch_out,
                cultural_matrix=sample_matrix,
            )
        )

        gov = GovernanceAgent()
        gov_input = GovernanceValidationInput(
            cultural_twin=sample_twin,
            cultural_matrix=sample_matrix,
            strategy=strat_out,
            experience_design=arch_out,
            partnerships=part_out,
        )
        gov_out = await gov.validate_plan(gov_input)

        plan = CulturalActivationPlan(
            plan_id="plan_contract_test",
            cultural_twin=sample_twin,
            cultural_matrix=sample_matrix,
            strategy=strat_out,
            experience_design=arch_out,
            partnerships=part_out,
            governance=gov_out,
        )

        with pytest.raises(UnapprovedExecutionError) as exc:
            await gov.execute_plan(plan, is_approved=False)
        assert "NEVER execute external actions before explicit approval" in str(
            exc.value
        )

    @pytest.mark.asyncio
    async def test_governance_deterministic_serialization(
        self, sample_twin, sample_matrix
    ):
        """ExecutionPlan, GovernanceValidationOutput, ExecutionSummary, and AuditReport round-trip via JSON."""
        strategist = CulturalStrategist()
        strat_out = await strategist.execute(
            CulturalStrategyInput(
                cultural_twin=sample_twin, cultural_matrix=sample_matrix
            )
        )
        architect = ExperienceArchitect()
        arch_out = await architect.execute(
            ExperienceDesignInput(strategy=strat_out, cultural_matrix=sample_matrix)
        )
        partnership = PartnershipAgent()
        part_out = await partnership.execute(
            PartnershipInput(
                strategy=strat_out,
                experience_design=arch_out,
                cultural_matrix=sample_matrix,
            )
        )

        gov = GovernanceAgent()
        gov_input = GovernanceValidationInput(
            cultural_twin=sample_twin,
            cultural_matrix=sample_matrix,
            strategy=strat_out,
            experience_design=arch_out,
            partnerships=part_out,
        )
        exec_plan = gov.plan(gov_input)
        gov_out = await gov.validate_plan(gov_input, execution_plan=exec_plan)

        # 1. ExecutionPlan serialization
        plan_json = exec_plan.model_dump_json()
        assert ExecutionPlan.model_validate_json(plan_json) == exec_plan

        # 2. GovernanceValidationOutput serialization
        gov_json = gov_out.model_dump_json()
        assert GovernanceValidationOutput.model_validate_json(gov_json) == gov_out

        # 3. ExecutionSummary & AuditReport serialization
        plan = CulturalActivationPlan(
            plan_id="plan_serde_test",
            cultural_twin=sample_twin,
            cultural_matrix=sample_matrix,
            strategy=strat_out,
            experience_design=arch_out,
            partnerships=part_out,
            governance=gov_out,
            execution_plan=exec_plan,
        )
        summary = await gov.execute_plan(plan, is_approved=True, approved_by="Curator")
        summary_json = summary.model_dump_json()
        restored_summary = ExecutionSummary.model_validate_json(summary_json)
        assert restored_summary.total_tasks == summary.total_tasks
        assert restored_summary.executed_tasks == summary.executed_tasks


# ===========================================================================
# 5. Workflow Engine Compatibility & Composition Contract
# ===========================================================================


class TestWorkflowEngineCompatibilityContract:
    """Verifies that all 4 agents compose seamlessly without silent coercion in the workflow engine."""

    @pytest.mark.asyncio
    async def test_end_to_end_agent_pipeline_composition(
        self, sample_twin, sample_matrix
    ):
        """Outputs from each agent pipe directly as valid typed inputs to downstream agents."""
        # Step 1: Cultural Strategist
        strategist = CulturalStrategist()
        strategy_input = CulturalStrategyInput(
            cultural_twin=sample_twin,
            cultural_matrix=sample_matrix,
        )
        strategy_output = await strategist.execute(strategy_input)
        assert isinstance(strategy_output, CulturalStrategyOutput)

        # Step 2: Experience Architect (consumes CulturalTwin, CulturalMatrix, CulturalStrategyOutput)
        architect = ExperienceArchitect()
        experience_input = ExperienceDesignInput(
            cultural_twin=sample_twin,
            cultural_matrix=sample_matrix,
            strategy=strategy_output,
        )
        experience_output = await architect.execute(experience_input)
        assert isinstance(experience_output, ExperienceDesignOutput)

        # Step 3: Partnership Agent (consumes CulturalTwin, CulturalMatrix, Strategy, Experience)
        partnership_agent = PartnershipAgent()
        partnership_input = PartnershipInput(
            cultural_twin=sample_twin,
            cultural_matrix=sample_matrix,
            strategy=strategy_output,
            experience_design=experience_output,
        )
        partnership_output = await partnership_agent.execute(partnership_input)
        assert isinstance(partnership_output, PartnershipOutput)

        # Step 4: Governance Agent (consumes all 3 agent outputs + Twin + Matrix)
        governance_agent = GovernanceAgent()
        gov_input = GovernanceValidationInput(
            cultural_twin=sample_twin,
            cultural_matrix=sample_matrix,
            strategy=strategy_output,
            experience_design=experience_output,
            partnerships=partnership_output,
        )
        exec_plan = governance_agent.plan(gov_input)
        gov_output = await governance_agent.validate_plan(
            gov_input, execution_plan=exec_plan
        )
        assert isinstance(gov_output, GovernanceValidationOutput)

        # Step 5: Composite CulturalActivationPlan
        activation_plan = CulturalActivationPlan(
            plan_id="plan_pipeline_composition_001",
            cultural_twin=sample_twin,
            cultural_matrix=sample_matrix,
            strategy=strategy_output,
            experience_design=experience_output,
            partnerships=partnership_output,
            governance=gov_output,
            execution_plan=exec_plan,
        )
        assert activation_plan.plan_id == "plan_pipeline_composition_001"

        # Step 6: Hash computation is deterministic and sensitive to content
        hash_1 = activation_plan.compute_hash()
        assert len(hash_1) == 64  # SHA256 hex string

        # Mutating strategy positioning statement changes hash
        activation_plan.strategy.positioning_statement = "Mutated statement"
        hash_2 = activation_plan.compute_hash()
        assert hash_1 != hash_2

    def test_cultural_activation_plan_rejects_missing_agent_output(
        self, sample_twin, sample_matrix
    ):
        """CulturalActivationPlan must reject missing any agent output without coercion."""
        with pytest.raises(ValidationError) as exc:
            CulturalActivationPlan(
                plan_id="plan_incomplete",
                cultural_twin=sample_twin,
                cultural_matrix=sample_matrix,
                # Missing strategy, experience_design, partnerships, governance!
            )  # type: ignore[call-arg]
        errors = str(exc.value)
        assert "strategy" in errors
        assert "experience_design" in errors
        assert "partnerships" in errors
        assert "governance" in errors
