"""Unit tests for the 4 TasteOps Specialized Agents.

Verifies:
- Cultural Strategist output structure and provenance
- Experience Architect spatial/music programming
- Partnership Agent activation concepts
- Governance Agent provenance verification, hallucination rejection, and execution
"""

import pytest

from tasteops.agents.architect import ExperienceArchitect
from tasteops.agents.governance import GovernanceAgent
from tasteops.agents.partnership import PartnershipAgent
from tasteops.agents.strategist import CulturalStrategist
from tasteops.models.cultural_matrix import (
    CulturalMatrix,
    CulturalRecommendation,
    CulturalTwin,
)
from tasteops.workflows.schemas import (
    CulturalStrategyInput,
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
