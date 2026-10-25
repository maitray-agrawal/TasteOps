"""Unit tests for the 4 TasteOps Specialized Agents.

Verifies:
- Cultural Strategist output structure and provenance
- Experience Architect spatial/music programming
- Partnership Agent activation concepts
- Governance Agent provenance verification, hallucination rejection, and execution
"""

import pytest
import respx

from tasteops.agents.architect import ExperienceArchitect
from tasteops.agents.governance import GovernanceAgent, UnapprovedExecutionError
from tasteops.agents.partnership import PartnershipAgent
from tasteops.agents.strategist import CulturalStrategist
from tasteops.models.cultural_matrix import (
    CulturalMatrix,
    CulturalRecommendation,
    CulturalTwin,
    PhysicalSpaceBrief,
)
from tasteops.workflows.schemas import (
    CulturalActivationPlan,
    CulturalStrategyInput,
    ExecutionPlan,
    ExperienceDesignInput,
    GovernanceValidationInput,
    PartnershipInput,
)


@pytest.fixture
def sample_curated_matrix():
    return CulturalMatrix(
        artists=[
            CulturalRecommendation(
                id="ent_four_tet",
                name="Four Tet",
                type="artist",
                affinity=0.94,
                source_query="/v2/insights",
            ),
            CulturalRecommendation(
                id="ent_floating_points",
                name="Floating Points",
                type="artist",
                affinity=0.91,
                source_query="/v2/insights",
            ),
        ],
        brands=[
            CulturalRecommendation(
                id="ent_muji",
                name="Muji",
                type="brand",
                affinity=0.93,
                source_query="/v2/insights",
            ),
            CulturalRecommendation(
                id="ent_audio_technica",
                name="Audio-Technica",
                type="brand",
                affinity=0.89,
                source_query="/v2/insights",
            ),
        ],
        places=[
            CulturalRecommendation(
                id="ent_public_records",
                name="Public Records",
                type="place",
                affinity=0.95,
                source_query="/v2/insights",
            )
        ],
        books=[
            CulturalRecommendation(
                id="ent_in_praise_of_shadows",
                name="In Praise of Shadows",
                type="book",
                affinity=0.88,
                source_query="/v2/insights",
            )
        ],
    )


@pytest.fixture
def sample_twin():
    return CulturalTwin(
        business_type="Analog Listening Bar & Cafe",
        target_audience="Creative professionals and music purists",
        mood="Warm, minimalist, analog focus",
        anchor_entities=["ent_blue_bottle_123"],
        resolved_tags=["tag_jp_minimalism", "tag_lofi_beats"],
    )


@pytest.mark.asyncio
async def test_cultural_strategist_transform_brief_success(mock_mcp_adapter):
    """Test Cultural Strategist transforms physical space brief into structured CulturalTwin."""
    adapter, mock_search, mock_tags, _ = mock_mcp_adapter

    async with respx.mock(
        base_url="https://hackathon.api.qloo.com", assert_all_called=False
    ) as mock_router:
        mock_router.get("/search").respond(status_code=200, json=mock_search)
        mock_router.get("/v2/tags").respond(status_code=200, json=mock_tags)

        strategist = CulturalStrategist(mcp_adapter=adapter)

        brief = PhysicalSpaceBrief(
            business_type="Analog Vinyl Listening Bar & Cafe",
            location={
                "latitude": 40.7484,
                "longitude": -73.9857,
                "radius_meters": 2000,
            },
            target_audience="Audiophiles, music collectors, and design purists aged 25-45",
            positioning="Japanese-inspired craft audio sanctuary",
            desired_mood="Warm, acoustic focus, minimalist, intimate",
            budget="High-end boutique",
            constraints=["SPL capped at 75dB", "No digital screens in seating zones"],
            anchor_entities=["Blue Bottle", "Japanese minimalism"],
        )

        twin = await strategist.transform_brief(brief)

        # 1. Output Schema Validation
        assert isinstance(twin, CulturalTwin)
        assert twin.business_type == "Analog Vinyl Listening Bar & Cafe"
        assert twin.audience_profile
        assert "Audiophiles" in twin.audience_profile
        assert len(twin.cultural_themes) >= 3
        assert twin.mood_profile
        assert "Analog warmth" in twin.mood_profile
        assert twin.anchor_entities == ["Blue Bottle", "Japanese minimalism"]

        # 2. Verified Entity Resolution & Provenance (Never invented)
        assert len(twin.resolved_entities) == 1
        resolved_ent = twin.resolved_entities[0]
        assert resolved_ent.id == "ent_blue_bottle_123"
        assert resolved_ent.name == "Blue Bottle Coffee"
        assert resolved_ent.type == "place"
        assert resolved_ent.confidence > 0.0

        # 3. Cultural Reasoning: Explains why each cultural signal matters
        assert resolved_ent.why_it_matters
        assert "Blue Bottle Coffee" in resolved_ent.why_it_matters
        assert "ent_blue_bottle_123" in twin.signal_explanations

        # 4. Verified Tag Resolution
        assert "tag_jp_minimalism" in twin.resolved_tags
        assert len(twin.resolved_tag_details) == 1
        resolved_tag = twin.resolved_tag_details[0]
        assert resolved_tag.id == "tag_jp_minimalism"
        assert resolved_tag.name == "Japanese Minimalism"
        assert resolved_tag.why_it_matters
        assert "tag_jp_minimalism" in twin.signal_explanations

        # 5. Cultural Constraints and Exclusions
        assert len(twin.cultural_constraints) >= 3
        assert any("75dB" in c for c in twin.cultural_constraints)
        assert len(twin.exclusions) >= 3
        assert any("Top 40" in e for e in twin.exclusions)

        # 6. Confidence Score
        assert 0.0 <= twin.confidence <= 1.0

        # 7. Zero Recommendations Generated Yet (Foundation only)
        assert not hasattr(twin, "artists")
        assert not hasattr(twin, "brands")


@pytest.mark.asyncio
async def test_cultural_strategist_never_invents_qloo_ids(mock_mcp_adapter):
    """Test Cultural Strategist never fabricates IDs for unresolvable terms."""
    adapter, _, _, _ = mock_mcp_adapter

    # Return empty results for unknown entities
    async with respx.mock(
        base_url="https://hackathon.api.qloo.com", assert_all_called=False
    ) as mock_router:
        mock_router.get("/search").respond(status_code=200, json={"results": []})
        mock_router.get("/v2/tags").respond(status_code=200, json={"results": []})

        strategist = CulturalStrategist(mcp_adapter=adapter)

        brief = PhysicalSpaceBrief(
            business_type="Speakeasy",
            anchor_entities=[
                "FabricatedImaginaryVenueX999",
                "UnknownAestheticMotifZ123",
            ],
        )

        twin = await strategist.transform_brief(brief)

        # Zero hallucinated entities or tags
        assert twin.resolved_entities == []
        assert twin.resolved_tags == []
        assert twin.resolved_tag_details == []
        assert twin.anchor_entities == [
            "FabricatedImaginaryVenueX999",
            "UnknownAestheticMotifZ123",
        ]


@pytest.mark.asyncio
async def test_cultural_strategist(sample_twin, sample_curated_matrix):
    """Test Cultural Strategist produces structured positioning and valid pillars."""
    agent = CulturalStrategist()
    payload = CulturalStrategyInput(
        cultural_twin=sample_twin, cultural_matrix=sample_curated_matrix
    )

    output = await agent.execute(payload)

    assert output.positioning_statement
    assert "Analog Listening Bar & Cafe" in output.positioning_statement
    assert len(output.cultural_pillars) >= 3
    assert len(output.target_subcultures) >= 2
    assert len(output.affinity_themes) >= 2

    # Verify provenance: all referenced pillar IDs exist in twin anchors or matrix
    valid_ids = {
        "ent_blue_bottle_123",
        "ent_four_tet",
        "ent_floating_points",
        "ent_muji",
        "ent_audio_technica",
        "ent_public_records",
        "ent_in_praise_of_shadows",
    }
    for pillar in output.cultural_pillars:
        for eid in pillar.aligned_entity_ids:
            assert eid in valid_ids


@pytest.mark.asyncio
async def test_experience_architect(sample_twin, sample_curated_matrix):
    """Test Experience Architect produces sonic directives, dayparts, and zones."""
    strategist = CulturalStrategist()
    strat_output = await strategist.execute(
        CulturalStrategyInput(
            cultural_twin=sample_twin, cultural_matrix=sample_curated_matrix
        )
    )

    architect = ExperienceArchitect()
    arch_output = await architect.execute(
        ExperienceDesignInput(
            strategy=strat_output, cultural_matrix=sample_curated_matrix
        )
    )

    assert len(arch_output.music_curation_directives) >= 3
    assert len(arch_output.daypart_programs) == 3
    assert len(arch_output.spatial_zones) == 3
    assert len(arch_output.sensory_pairings) >= 2

    # Check daypart structure
    morning = arch_output.daypart_programs[0]
    assert morning.title == "Morning Ritual & Focus"
    assert "07:00" in morning.time_window
    assert len(morning.featured_artist_ids) >= 1


@pytest.mark.asyncio
async def test_experience_architect_full_experience_design(
    sample_twin, sample_curated_matrix
):
    """Test Experience Architect generates all 6 core domains with structured recommendations."""
    architect = ExperienceArchitect()
    arch_output = await architect.design_experience(
        cultural_twin=sample_twin, cultural_matrix=sample_curated_matrix
    )

    # 1. Sonic Identity
    assert arch_output.sonic_identity.overview
    assert arch_output.sonic_identity.acoustic_profile
    assert len(arch_output.sonic_identity.curated_recommendations) >= 1
    assert len(arch_output.sonic_identity.directives) >= 3
    assert len(arch_output.sonic_identity.dayparts) == 3

    # 2. Reading/Library Identity
    assert arch_output.reading_library_identity.overview
    assert len(arch_output.reading_library_identity.curation_themes) >= 2
    assert len(arch_output.reading_library_identity.curated_recommendations) >= 1
    assert arch_output.reading_library_identity.display_strategy

    # 3. Brand Ecosystem
    assert arch_output.brand_ecosystem.overview
    assert len(arch_output.brand_ecosystem.material_palette) >= 3
    assert len(arch_output.brand_ecosystem.curated_recommendations) >= 1
    assert len(arch_output.brand_ecosystem.partnership_criteria) >= 2

    # 4. Local Experience Ecosystem
    assert arch_output.local_experience_ecosystem.overview
    assert arch_output.local_experience_ecosystem.neighborhood_context
    assert len(arch_output.local_experience_ecosystem.curated_recommendations) >= 1
    assert len(arch_output.local_experience_ecosystem.community_synergies) >= 2

    # 5. Cultural Programming Ideas
    assert arch_output.cultural_programming_ideas.overview
    assert len(arch_output.cultural_programming_ideas.programming_pillars) >= 2
    assert len(arch_output.cultural_programming_ideas.activations) >= 2
    activation = arch_output.cultural_programming_ideas.activations[0]
    assert activation.title
    assert activation.cadence
    assert activation.format_description
    assert activation.expected_outcome

    # 6. Atmosphere Guidelines
    assert arch_output.atmosphere_guidelines.sonic_parameters
    assert arch_output.atmosphere_guidelines.lighting_parameters
    assert arch_output.atmosphere_guidelines.olfactory_and_thermal
    assert arch_output.atmosphere_guidelines.hospitality_tempo
    assert len(arch_output.atmosphere_guidelines.spatial_zones) == 3

    # 7. Check Every Recommendation conforms to strict schema
    all_recs = (
        arch_output.sonic_identity.curated_recommendations
        + arch_output.reading_library_identity.curated_recommendations
        + arch_output.brand_ecosystem.curated_recommendations
        + arch_output.local_experience_ecosystem.curated_recommendations
    )
    assert len(all_recs) >= 4
    for rec in all_recs:
        assert rec.recommendation
        assert rec.qloo_evidence
        assert "entity_id" in rec.qloo_evidence or "id" in rec.qloo_evidence
        assert rec.cultural_rationale
        assert 0.0 <= rec.confidence <= 1.0
        assert rec.expected_role

    # 8. Machine-Readable: Dumps to valid dictionary / JSON
    data = arch_output.model_dump()
    assert isinstance(data, dict)
    assert "sonic_identity" in data
    assert "reading_library_identity" in data
    assert "brand_ecosystem" in data
    assert "local_experience_ecosystem" in data
    assert "cultural_programming_ideas" in data
    assert "atmosphere_guidelines" in data


@pytest.mark.asyncio
async def test_experience_architect_exclusion_filtering(sample_curated_matrix):
    """Test Experience Architect rejects Qloo recommendations violating cultural exclusions."""
    twin_with_exclusions = CulturalTwin(
        business_type="Minimalist Tea House",
        exclusions=["Muji", "Commercial pop"],
        anchor_entities=["ent_blue_bottle_123"],
    )

    architect = ExperienceArchitect()
    arch_output = await architect.design_experience(
        cultural_twin=twin_with_exclusions, cultural_matrix=sample_curated_matrix
    )

    # Muji must be rejected because it matches exclusion 'Muji'
    brand_names = [
        r.recommendation for r in arch_output.brand_ecosystem.curated_recommendations
    ]
    assert "Muji" not in brand_names


@pytest.mark.asyncio
async def test_partnership_agent(sample_twin, sample_curated_matrix):
    """Test Partnership Agent structures activations from verified Qloo brand recommendations."""
    strategist = CulturalStrategist()
    strat_output = await strategist.execute(
        CulturalStrategyInput(
            cultural_twin=sample_twin, cultural_matrix=sample_curated_matrix
        )
    )

    architect = ExperienceArchitect()
    arch_output = await architect.execute(
        ExperienceDesignInput(
            strategy=strat_output, cultural_matrix=sample_curated_matrix
        )
    )

    partnership_agent = PartnershipAgent()
    part_output = await partnership_agent.execute(
        PartnershipInput(
            strategy=strat_output,
            experience_design=arch_output,
            cultural_matrix=sample_curated_matrix,
        )
    )

    assert len(part_output.partnerships) >= 2
    assert len(part_output.event_collaborations) >= 2

    # Verify each partner uses verified Qloo ID
    partner1 = part_output.partnerships[0]
    assert partner1.partner_name in ["Muji", "Audio-Technica"]
    assert partner1.partner_entity_id in ["ent_muji", "ent_audio_technica"]
    assert partner1.affinity_score > 0.8


@pytest.mark.asyncio
async def test_partnership_agent_scoring_and_candidate_structure(
    sample_twin, sample_curated_matrix
):
    """Test Partnership Agent computes 6-dimensional scores, outreach drafts, and never claims active partnerships."""
    partnership_agent = PartnershipAgent()

    # Pass explicit CulturalTwin, brand_results, business_constraints, and budget
    part_output = await partnership_agent.identify_partnerships(
        cultural_twin=sample_twin,
        brand_results=sample_curated_matrix.brands,
        business_constraints=[
            "Maintain acoustic dampening under 75dB",
            "No overt corporate signage",
        ],
        budget="Medium Tier ($50k buildout)",
        cultural_matrix=sample_curated_matrix,
    )

    assert len(part_output.candidates) >= 2

    for candidate in part_output.candidates:
        # 1. Basic brand and score properties
        assert candidate.brand in ["Muji", "Audio-Technica"]
        assert candidate.brand_entity_id in ["ent_muji", "ent_audio_technica"]
        assert 0.0 <= candidate.score <= 100.0

        # 2. 6-Dimensional score breakdown
        breakdown = candidate.score_breakdown
        assert 0.0 <= breakdown.cultural_fit <= 100.0
        assert 0.0 <= breakdown.audience_fit <= 100.0
        assert 0.0 <= breakdown.brand_compatibility <= 100.0
        assert 0.0 <= breakdown.context_fit <= 100.0
        assert 0.0 <= breakdown.budget_fit <= 100.0
        assert 0.0 <= breakdown.novelty <= 100.0
        assert breakdown.overall_score == candidate.score

        # 3. Supporting Qloo evidence
        assert (
            candidate.supporting_qloo_evidence["entity_id"] == candidate.brand_entity_id
        )
        assert candidate.supporting_qloo_evidence["affinity"] > 0.80
        assert candidate.supporting_qloo_evidence["source_query"] == "/v2/insights"

        # 4. Editorial and operational details
        assert len(candidate.partnership_concept) > 20
        assert any(
            candidate.estimated_effort.startswith(prefix)
            for prefix in ["Low", "Medium", "High"]
        )
        assert len(candidate.risk) > 20
        assert len(candidate.recommended_next_action) > 20

        # 5. Exploratory outreach draft (DO NOT claim that a real partnership exists)
        assert candidate.is_existing_partner is False
        draft = candidate.outreach_draft
        assert draft.recipient_role
        assert candidate.brand in draft.subject
        assert (
            str(round(candidate.supporting_qloo_evidence["affinity"] * 100))
            in draft.opening_hook
        )
        assert draft.proposed_collaboration
        assert draft.value_proposition
        assert draft.call_to_action
        assert "Exploratory outreach draft only" in draft.disclaimer
        assert "No existing formal partnership" in draft.disclaimer


@pytest.mark.asyncio
async def test_partnership_agent_exclusion_filtering(
    sample_twin, sample_curated_matrix
):
    """Test Partnership Agent omits candidates matching cultural exclusions."""
    # Add Muji to exclusions
    twin_with_exclusions = sample_twin.model_copy(deep=True)
    twin_with_exclusions.exclusions = ["Muji", "Fast Fashion"]

    partnership_agent = PartnershipAgent()
    part_output = await partnership_agent.identify_partnerships(
        cultural_twin=twin_with_exclusions,
        brand_results=sample_curated_matrix.brands,
        cultural_matrix=sample_curated_matrix,
    )

    candidate_names = [c.brand for c in part_output.candidates]
    assert "Muji" not in candidate_names
    assert "Audio-Technica" in candidate_names


@pytest.mark.asyncio
async def test_governance_agent_validates_clean_plan(
    sample_twin, sample_curated_matrix
):
    """Test Governance Agent audits plan with 100% verified provenance and approves."""
    strategist = CulturalStrategist()
    strat_output = await strategist.execute(
        CulturalStrategyInput(
            cultural_twin=sample_twin, cultural_matrix=sample_curated_matrix
        )
    )

    architect = ExperienceArchitect()
    arch_output = await architect.execute(
        ExperienceDesignInput(
            strategy=strat_output, cultural_matrix=sample_curated_matrix
        )
    )

    partnership_agent = PartnershipAgent()
    part_output = await partnership_agent.execute(
        PartnershipInput(
            strategy=strat_output,
            experience_design=arch_output,
            cultural_matrix=sample_curated_matrix,
        )
    )

    governance = GovernanceAgent()
    gov_output = await governance.validate_plan(
        GovernanceValidationInput(
            cultural_twin=sample_twin,
            cultural_matrix=sample_curated_matrix,
            strategy=strat_output,
            experience_design=arch_output,
            partnerships=part_output,
        )
    )

    assert gov_output.is_valid is True
    assert gov_output.provenance_verified is True
    assert gov_output.unverified_entity_ids == []
    assert gov_output.readiness_score == 1.0


@pytest.mark.asyncio
async def test_governance_agent_rejects_hallucinated_ids(
    sample_twin, sample_curated_matrix
):
    """Zero-hallucination test: If any agent fabricates an unverified ID, governance strictly fails the plan."""
    strategist = CulturalStrategist()
    strat_output = await strategist.execute(
        CulturalStrategyInput(
            cultural_twin=sample_twin, cultural_matrix=sample_curated_matrix
        )
    )

    architect = ExperienceArchitect()
    arch_output = await architect.execute(
        ExperienceDesignInput(
            strategy=strat_output, cultural_matrix=sample_curated_matrix
        )
    )

    partnership_agent = PartnershipAgent()
    part_output = await partnership_agent.execute(
        PartnershipInput(
            strategy=strat_output,
            experience_design=arch_output,
            cultural_matrix=sample_curated_matrix,
        )
    )

    # Inject an unverified, hallucinated entity ID into the first pillar
    strat_output.cultural_pillars[0].aligned_entity_ids.append(
        "hallucinated_fake_id_99999"
    )

    governance = GovernanceAgent()
    gov_output = await governance.validate_plan(
        GovernanceValidationInput(
            cultural_twin=sample_twin,
            cultural_matrix=sample_curated_matrix,
            strategy=strat_output,
            experience_design=arch_output,
            partnerships=part_output,
        )
    )

    # Must fail provenance audit
    assert gov_output.is_valid is False
    assert gov_output.provenance_verified is False
    assert "hallucinated_fake_id_99999" in gov_output.unverified_entity_ids
    assert any("Provenance violation" in flag for flag in gov_output.risk_flags)


@pytest.mark.asyncio
async def test_governance_agent_creates_execution_plan_and_dependencies(
    sample_twin, sample_curated_matrix
):
    """Test Governance Agent converts cultural recommendations into a structured ExecutionPlan."""
    strategist = CulturalStrategist()
    strat_output = await strategist.execute(
        CulturalStrategyInput(
            cultural_twin=sample_twin, cultural_matrix=sample_curated_matrix
        )
    )

    architect = ExperienceArchitect()
    arch_output = await architect.execute(
        ExperienceDesignInput(
            strategy=strat_output, cultural_matrix=sample_curated_matrix
        )
    )

    partnership_agent = PartnershipAgent()
    part_output = await partnership_agent.execute(
        PartnershipInput(
            strategy=strat_output,
            experience_design=arch_output,
            cultural_matrix=sample_curated_matrix,
        )
    )

    governance = GovernanceAgent()
    gov_input = GovernanceValidationInput(
        cultural_twin=sample_twin,
        cultural_matrix=sample_curated_matrix,
        strategy=strat_output,
        experience_design=arch_output,
        partnerships=part_output,
    )

    # 1. Generate ExecutionPlan
    exec_plan = governance.plan(gov_input)
    assert isinstance(exec_plan, ExecutionPlan)
    assert len(exec_plan.actions) >= 4
    assert exec_plan.estimated_cost
    assert "$12,500" in exec_plan.estimated_cost
    assert len(exec_plan.risks) >= 2
    assert "General Manager" in exec_plan.approvals_required
    assert "Cultural Curator" in exec_plan.approvals_required
    assert len(exec_plan.evidence) >= 1

    # 2. Check dependencies structure
    assert "act_sonic_01" in exec_plan.dependencies
    assert "act_brand_01" in exec_plan.dependencies
    assert "act_sonic_01" in exec_plan.dependencies["act_brand_01"]


@pytest.mark.asyncio
async def test_governance_agent_refuses_execution_before_approval(
    sample_twin, sample_curated_matrix
):
    """Strict Gate Test: The agent must NEVER execute external actions before explicit approval."""
    strategist = CulturalStrategist()
    strat_output = await strategist.execute(
        CulturalStrategyInput(
            cultural_twin=sample_twin, cultural_matrix=sample_curated_matrix
        )
    )

    architect = ExperienceArchitect()
    arch_output = await architect.execute(
        ExperienceDesignInput(
            strategy=strat_output, cultural_matrix=sample_curated_matrix
        )
    )

    partnership_agent = PartnershipAgent()
    part_output = await partnership_agent.execute(
        PartnershipInput(
            strategy=strat_output,
            experience_design=arch_output,
            cultural_matrix=sample_curated_matrix,
        )
    )

    governance = GovernanceAgent()
    gov_input = GovernanceValidationInput(
        cultural_twin=sample_twin,
        cultural_matrix=sample_curated_matrix,
        strategy=strat_output,
        experience_design=arch_output,
        partnerships=part_output,
    )
    gov_output = await governance.validate_plan(gov_input)

    plan = CulturalActivationPlan(
        plan_id="plan_test_unapproved_123",
        cultural_twin=sample_twin,
        cultural_matrix=sample_curated_matrix,
        strategy=strat_output,
        experience_design=arch_output,
        partnerships=part_output,
        governance=gov_output,
    )

    # Explicitly attempt execution with is_approved=False
    with pytest.raises(UnapprovedExecutionError) as exc_info:
        await governance.execute_plan(plan, is_approved=False)

    assert "NEVER execute external actions before explicit approval" in str(
        exc_info.value
    )


@pytest.mark.asyncio
async def test_governance_agent_executes_tasks_with_provenance_and_audit(
    sample_twin, sample_curated_matrix
):
    """Test Governance Agent generates execution tasks with task_id, action, owner, input, status, timestamp, provenance, and audit."""
    strategist = CulturalStrategist()
    strat_output = await strategist.execute(
        CulturalStrategyInput(
            cultural_twin=sample_twin, cultural_matrix=sample_curated_matrix
        )
    )

    architect = ExperienceArchitect()
    arch_output = await architect.execute(
        ExperienceDesignInput(
            strategy=strat_output, cultural_matrix=sample_curated_matrix
        )
    )

    partnership_agent = PartnershipAgent()
    part_output = await partnership_agent.execute(
        PartnershipInput(
            strategy=strat_output,
            experience_design=arch_output,
            cultural_matrix=sample_curated_matrix,
        )
    )

    from tasteops.connectors import create_configured_mock_registry

    governance = GovernanceAgent(connector_registry=create_configured_mock_registry())
    gov_input = GovernanceValidationInput(
        cultural_twin=sample_twin,
        cultural_matrix=sample_curated_matrix,
        strategy=strat_output,
        experience_design=arch_output,
        partnerships=part_output,
    )
    gov_output = await governance.validate_plan(gov_input)

    plan = CulturalActivationPlan(
        plan_id="plan_test_approved_456",
        cultural_twin=sample_twin,
        cultural_matrix=sample_curated_matrix,
        strategy=strat_output,
        experience_design=arch_output,
        partnerships=part_output,
        governance=gov_output,
    )

    # Execute with explicit approval
    summary = await governance.execute_plan(
        plan, is_approved=True, approved_by="Curator: Maitray Agrawal"
    )

    assert summary.total_tasks >= 3
    assert summary.executed_tasks == summary.total_tasks
    assert summary.failed_tasks == 0

    # Verify every execution task has: task_id, action, owner, input, status, timestamp, provenance
    for task in summary.tasks:
        assert task.task_id.startswith("task_")
        assert len(task.action) > 10
        assert task.owner in [
            "Audio Curator",
            "Partnership Director",
            "Spatial Designer",
        ]
        assert isinstance(task.input, dict)
        assert task.status == "EXECUTED"
        assert task.timestamp is not None
        assert isinstance(task.provenance, dict)
        assert "entity_id" in task.provenance or "zone" in task.provenance
        assert task.provenance["approved_by"] == "Curator: Maitray Agrawal"

    # Verify post-execution audit report
    assert summary.audit_report is not None
    audit = summary.audit_report
    assert audit.audit_id.startswith("audit_")
    assert audit.plan_id == "plan_test_approved_456"
    assert audit.approval_verified is True
    assert audit.provenance_violations == 0
    assert audit.unsupported_actions_blocked == 0
    assert audit.compliance_status == "COMPLIANT"
    assert len(audit.findings) >= 2
