"""Pydantic Schemas for Agent Inputs, Outputs, and Activation Plans.

Strict schemas ensuring all agent operations produce structured JSON,
maintain immutable provenance, and never invent entity IDs.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from tasteops.models.cultural_matrix import CulturalMatrix, CulturalTwin

# ---------------------------------------------------------------------------
# Cultural Strategist Schemas
# ---------------------------------------------------------------------------


class CulturalPillar(BaseModel):
    """Core thematic pillar guiding the space's cultural identity."""

    name: str = Field(..., description="Title of the cultural pillar")
    description: str = Field(..., description="Narrative rationale and resonance")
    aligned_entity_ids: list[str] = Field(
        default_factory=list,
        description="Verified Qloo entity IDs anchoring this pillar",
    )
    aligned_tag_ids: list[str] = Field(
        default_factory=list, description="Verified Qloo tag IDs anchoring this pillar"
    )


class CulturalStrategyInput(BaseModel):
    """Input payload for Cultural Strategist agent."""

    cultural_twin: CulturalTwin
    cultural_matrix: CulturalMatrix


class CulturalStrategyOutput(BaseModel):
    """Structured strategic output from Cultural Strategist agent."""

    positioning_statement: str = Field(
        ..., description="Strategic cultural positioning narrative"
    )
    cultural_pillars: list[CulturalPillar] = Field(
        ..., min_length=1, description="Strategic identity pillars"
    )
    target_subcultures: list[str] = Field(
        ..., description="Specific subcultural communities targeted"
    )
    affinity_themes: list[str] = Field(..., description="Cross-domain affinity themes")
    provenance_entity_ids: list[str] = Field(
        ..., description="Verified Qloo entity IDs backing this strategy"
    )


# ---------------------------------------------------------------------------
# Experience Architect Schemas
# ---------------------------------------------------------------------------


class DaypartProgram(BaseModel):
    """Atmospheric and sonic programming for a time-of-day window."""

    time_window: str = Field(
        ...,
        description="e.g. '07:00 - 12:00 (Morning Focus)', '18:00 - 00:00 (Night Listening)'",
    )
    title: str = Field(..., description="Daypart concept name")
    atmosphere: str = Field(..., description="Ambient vibe and lighting directives")
    audio_theme: str = Field(..., description="Music style and acoustic focus")
    featured_artist_ids: list[str] = Field(
        default_factory=list, description="Verified Qloo artist IDs"
    )


class SpatialZone(BaseModel):
    """Zoning directive for a specific area of the physical venue."""

    zone_name: str = Field(
        ..., description="e.g. 'Main Counter', 'Mezzanine Listening Lounge'"
    )
    intended_mood: str = Field(..., description="Target feeling and interaction tempo")
    design_reference_ids: list[str] = Field(
        default_factory=list, description="Verified Qloo brand or place IDs"
    )
    tactile_elements: list[str] = Field(
        default_factory=list, description="Physical materials, lighting, scents"
    )


class ExperienceDesignInput(BaseModel):
    """Input payload for Experience Architect agent."""

    strategy: CulturalStrategyOutput
    cultural_matrix: CulturalMatrix


class ExperienceDesignOutput(BaseModel):
    """Structured spatial, audio, and atmospheric design output."""

    music_curation_directives: list[str] = Field(
        ..., description="Sonic guidelines and genre balance"
    )
    daypart_programs: list[DaypartProgram] = Field(
        ..., min_length=1, description="Temporal atmosphere schedule"
    )
    spatial_zones: list[SpatialZone] = Field(
        ..., min_length=1, description="Physical zone design directives"
    )
    sensory_pairings: list[str] = Field(
        ..., description="Coffee, beverage, and aesthetic pairings"
    )
    provenance_entity_ids: list[str] = Field(
        ..., description="Verified Qloo entity IDs utilized in design"
    )


# ---------------------------------------------------------------------------
# Partnership Agent Schemas
# ---------------------------------------------------------------------------


class PartnershipActivation(BaseModel):
    """A concrete brand or creator activation concept."""

    partner_name: str = Field(..., description="Brand or creator name")
    partner_entity_id: str = Field(..., description="Verified Qloo entity ID")
    category: str = Field(
        ...,
        description="Category (e.g. audio-hardware, specialty-roaster, apparel, literature)",
    )
    activation_type: str = Field(
        ...,
        description="e.g. 'Hardware Residency', 'Retail Display', 'Co-branded Merchandise'",
    )
    concept_description: str = Field(..., description="Detailed collaboration concept")
    affinity_score: float = Field(
        ..., ge=0.0, le=1.0, description="Qloo cultural affinity score"
    )
    alignment_rationale: str = Field(
        ..., description="Why this partner resonates with the space audience"
    )


class PartnershipInput(BaseModel):
    """Input payload for Partnership Agent."""

    strategy: CulturalStrategyOutput
    experience_design: ExperienceDesignOutput
    cultural_matrix: CulturalMatrix


class PartnershipOutput(BaseModel):
    """Structured partnership activations output."""

    partnerships: list[PartnershipActivation] = Field(
        ..., min_length=1, description="Ranked partnership activations"
    )
    event_collaborations: list[str] = Field(
        default_factory=list, description="Pop-up and event ideas"
    )
    provenance_entity_ids: list[str] = Field(
        ..., description="Verified Qloo entity IDs backing partnerships"
    )


# ---------------------------------------------------------------------------
# Governance & Execution Schemas
# ---------------------------------------------------------------------------


class ComplianceCheck(BaseModel):
    """Single compliance or constraint audit check."""

    rule_name: str = Field(
        ...,
        description="Constraint audited (e.g. 'provenance_integrity', 'spatial_boundary')",
    )
    passed: bool = Field(..., description="Whether constraint was satisfied")
    detail: str = Field(..., description="Audit finding or validation message")


class GovernanceValidationInput(BaseModel):
    """Input payload for Governance Agent validation."""

    cultural_twin: CulturalTwin
    cultural_matrix: CulturalMatrix
    strategy: CulturalStrategyOutput
    experience_design: ExperienceDesignOutput
    partnerships: PartnershipOutput


class GovernanceValidationOutput(BaseModel):
    """Validation audit, provenance verification, and approval readiness."""

    is_valid: bool = Field(
        ..., description="True if plan satisfies all constraints and provenance checks"
    )
    provenance_verified: bool = Field(
        ..., description="True if 100% of referenced entity IDs originate from Qloo"
    )
    compliance_checks: list[ComplianceCheck] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    unverified_entity_ids: list[str] = Field(
        default_factory=list, description="Any entity IDs failing provenance audit"
    )
    readiness_score: float = Field(
        ..., ge=0.0, le=1.0, description="Readiness score for human approval"
    )


class ExecutionTask(BaseModel):
    """Single concrete action item executed upon plan approval."""

    task_id: str
    category: (
        str  # e.g. "spotify_playlist_seed", "partner_outreach_brief", "spatial_spec"
    )
    description: str
    target_partner_or_artist: str
    target_entity_id: str
    status: str = "PENDING"  # PENDING, EXECUTED, FAILED
    executed_at: datetime | None = None
    output_reference: str | None = None


class ExecutionSummary(BaseModel):
    """Summary of executed activations."""

    total_tasks: int
    executed_tasks: int
    failed_tasks: int
    tasks: list[ExecutionTask]
    completed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Complete Activation Plan Schema
# ---------------------------------------------------------------------------


class CulturalActivationPlan(BaseModel):
    """Holistic physical space activation plan synthesized across all agents."""

    plan_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    cultural_twin: CulturalTwin
    cultural_matrix: CulturalMatrix
    strategy: CulturalStrategyOutput
    experience_design: ExperienceDesignOutput
    partnerships: PartnershipOutput
    governance: GovernanceValidationOutput
    execution_summary: ExecutionSummary | None = None
