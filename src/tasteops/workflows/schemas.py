"""Pydantic Schemas for Agent Inputs, Outputs, and Activation Plans.

Strict schemas ensuring all agent operations produce structured JSON,
maintain immutable provenance, and never invent entity IDs.
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from tasteops.models.cultural_matrix import (
    CulturalMatrix,
    CulturalRecommendation,
    CulturalTwin,
)

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


class ExperienceRecommendation(BaseModel):
    """A culturally vetted recommendation curated for physical space experience."""

    recommendation: str = Field(
        ..., description="Recommended entity name or item title"
    )
    qloo_evidence: dict[str, Any] = Field(
        ...,
        description="Immutable Qloo evidence: entity ID, URN/type, affinity score, source query",
    )
    cultural_rationale: str = Field(
        ...,
        description="Curatorial rationale explaining alignment with the space's cultural twin",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score reflecting Qloo affinity and curatorial fit",
    )
    expected_role: str = Field(
        ...,
        description="Expected spatial, acoustic, or experiential role in the physical space",
    )
    category: str = Field(
        default="general",
        description="Category e.g. artist, book, brand, place, movie, destination",
    )


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


class SonicIdentity(BaseModel):
    """Sonic and acoustic architecture for the physical space."""

    overview: str = Field(..., description="Overall sonic philosophy and sound profile")
    acoustic_profile: str = Field(
        ..., description="Frequency emphasis, dynamic range, and acoustic warmth"
    )
    playback_mediums: list[str] = Field(
        default_factory=list,
        description="e.g. ['Vinyl 33/45 RPM', 'Lossless 24-bit/96kHz digital']",
    )
    directives: list[str] = Field(
        default_factory=list,
        description="Curatorial directives for music volume, tempo, and vocal density",
    )
    curated_recommendations: list[ExperienceRecommendation] = Field(
        default_factory=list,
        description="Coherent, high-affinity musical artists vetted from Qloo",
    )
    dayparts: list[DaypartProgram] = Field(
        default_factory=list,
        description="Temporal atmosphere schedule and audio themes",
    )


class ReadingLibraryIdentity(BaseModel):
    """Curated editorial, book, and print publication identity."""

    overview: str = Field(
        ..., description="Editorial vision and publication curation philosophy"
    )
    curation_themes: list[str] = Field(
        default_factory=list,
        description="Core literary, design, and artistic subject axes",
    )
    curated_recommendations: list[ExperienceRecommendation] = Field(
        default_factory=list,
        description="Culturally aligned books, monographs, and journals from Qloo",
    )
    display_strategy: str = Field(
        ...,
        description="Physical integration of publications in communal tables and lounge shelving",
    )


class BrandEcosystem(BaseModel):
    """Tactile material, packaging, tableware, and brand partner ecosystem."""

    overview: str = Field(
        ..., description="Material philosophy and partner curation standards"
    )
    material_palette: list[str] = Field(
        default_factory=list,
        description="Approved physical textures, finishes, surfaces, and ceramics",
    )
    curated_recommendations: list[ExperienceRecommendation] = Field(
        default_factory=list,
        description="Vetted brand partners (tableware, lighting, amenities, audio hardware)",
    )
    partnership_criteria: list[str] = Field(
        default_factory=list,
        description="Standards for brand presence and subtle co-existence",
    )


class LocalExperienceEcosystem(BaseModel):
    """Neighborhood integration and local cultural place benchmark ecosystem."""

    overview: str = Field(
        ..., description="Spatial hospitality benchmarks and neighborhood synergy"
    )
    neighborhood_context: str = Field(
        ..., description="Local neighborhood cultural dynamic"
    )
    curated_recommendations: list[ExperienceRecommendation] = Field(
        default_factory=list,
        description="Benchmarked venues, places, and micro-destinations from Qloo",
    )
    community_synergies: list[str] = Field(
        default_factory=list,
        description="Potential cross-patronage and local community alignments",
    )


class ProgrammingActivation(BaseModel):
    """Specific cultural event or residency format."""

    title: str = Field(
        ..., description="Activation title (e.g. 'Deep Listening Sunday Salon')"
    )
    cadence: str = Field(
        ..., description="Frequency and timing (e.g. 'Weekly Sunday 18:00 - 21:00')"
    )
    format_description: str = Field(
        ..., description="Detailed narrative of patron experience"
    )
    featured_recommendations: list[ExperienceRecommendation] = Field(
        default_factory=list,
        description="Anchoring Qloo entities featured in the program",
    )
    target_audience: str = Field(
        ..., description="Specific subcultural patron segment targeted"
    )
    expected_outcome: str = Field(
        ..., description="Community dwell time, cultural credibility, brand affinity"
    )


class CulturalProgrammingIdeas(BaseModel):
    """Event architecture, residency programs, and recurring cultural activations."""

    overview: str = Field(..., description="Programming ethos and community rhythm")
    programming_pillars: list[str] = Field(
        default_factory=list, description="Thematic pillars guiding event curation"
    )
    activations: list[ProgrammingActivation] = Field(
        default_factory=list,
        description="Structured recurring and signature event concepts",
    )


class AtmosphereGuidelines(BaseModel):
    """Sensory, lighting, acoustic, and spatial parameters for physical execution."""

    sonic_parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Acoustic targets: decibel limits (SPL), sound insulation, acoustic dampening",
    )
    lighting_parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Lighting guidelines: color temperature (Kelvin), lux levels, natural light transition",
    )
    olfactory_and_thermal: dict[str, Any] = Field(
        default_factory=dict,
        description="Scent profile (e.g. cedar, hinoki, tea) and thermal comfort settings",
    )
    hospitality_tempo: str = Field(
        ...,
        description="Service choreography: greeting, dwell cadence, ordering rituals",
    )
    spatial_zones: list[SpatialZone] = Field(
        default_factory=list,
        description="Physical zone specifications and tactile elements",
    )
    sensory_pairings: list[str] = Field(
        default_factory=list,
        description="Cross-sensory pairings (beverage x audio x materiality)",
    )


class ExperienceDesignInput(BaseModel):
    """Input payload for Experience Architect agent."""

    cultural_twin: CulturalTwin | None = Field(
        default=None, description="Foundational cultural twin profile"
    )
    cultural_matrix: CulturalMatrix = Field(
        ..., description="Multi-domain cultural recommendations matrix"
    )
    strategy: CulturalStrategyOutput | None = Field(
        default=None, description="Optional strategic positioning output"
    )


class ExperienceDesignOutput(BaseModel):
    """Complete machine-readable cultural experience design for physical spaces."""

    # 1. Sonic Identity
    sonic_identity: SonicIdentity = Field(
        ..., description="Acoustic architecture and music curation"
    )
    # 2. Reading/Library Identity
    reading_library_identity: ReadingLibraryIdentity = Field(
        ..., description="Curated publication and monograph identity"
    )
    # 3. Brand Ecosystem
    brand_ecosystem: BrandEcosystem = Field(
        ..., description="Material craft, tableware, and brand partner ecosystem"
    )
    # 4. Local Experience Ecosystem
    local_experience_ecosystem: LocalExperienceEcosystem = Field(
        ..., description="Neighborhood integration and hospitality benchmarks"
    )
    # 5. Cultural Programming Ideas
    cultural_programming_ideas: CulturalProgrammingIdeas = Field(
        ..., description="Recurring event concepts and residency formats"
    )
    # 6. Atmosphere Guidelines
    atmosphere_guidelines: AtmosphereGuidelines = Field(
        ..., description="Sensory, lighting, acoustic, and spatial parameters"
    )

    # Provenance tracking
    provenance_entity_ids: list[str] = Field(
        default_factory=list,
        description="All verified Qloo entity IDs utilized in design",
    )

    # Backward-compatible fields
    music_curation_directives: list[str] = Field(
        default_factory=list, description="Sonic guidelines and genre balance"
    )
    daypart_programs: list[DaypartProgram] = Field(
        default_factory=list, description="Temporal atmosphere schedule"
    )
    spatial_zones: list[SpatialZone] = Field(
        default_factory=list, description="Physical zone design directives"
    )
    sensory_pairings: list[str] = Field(
        default_factory=list, description="Coffee, beverage, and aesthetic pairings"
    )


# ---------------------------------------------------------------------------
# Partnership Agent Schemas
# ---------------------------------------------------------------------------


class PartnershipScoreBreakdown(BaseModel):
    """Normalized 6-dimensional scoring model for brand partnerships (0 to 100)."""

    cultural_fit: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Alignment with cultural themes, mood, and positioning",
    )
    audience_fit: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Audience taste overlap and Qloo affinity",
    )
    brand_compatibility: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Brand synergy and venue business model compatibility",
    )
    context_fit: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Physical space feasibility and spatial footprint",
    )
    budget_fit: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Feasibility within budget constraints and operating tier",
    )
    novelty: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Curatorial freshness and subcultural distinction",
    )
    overall_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Normalized composite score from 0 to 100",
    )


class OutreachDraft(BaseModel):
    """Exploratory outreach draft for brand partnership development."""

    recipient_role: str = Field(
        default="Brand Partnerships / Cultural Marketing Lead",
        description="Target role or department",
    )
    subject: str = Field(..., description="Outreach subject line")
    opening_hook: str = Field(
        ...,
        description="Cultural hook citing verified audience taste overlap",
    )
    proposed_collaboration: str = Field(
        ..., description="Detailed physical collaboration concept"
    )
    value_proposition: str = Field(
        ..., description="Mutual value proposition for brand and physical venue"
    )
    call_to_action: str = Field(
        ..., description="Low-friction exploratory conversation invitation"
    )
    disclaimer: str = Field(
        default="Exploratory outreach draft only. No existing formal partnership or affiliation is claimed.",
        description="Ethical and legal guardrail disclaimer",
    )


class BrandPartnershipCandidate(BaseModel):
    """Curated brand partnership candidate with multi-dimensional scoring and outreach draft."""

    brand: str = Field(..., description="Brand name")
    brand_entity_id: str = Field(..., description="Verified Qloo entity ID")
    category: str = Field(..., description="Brand category or industry")
    score: float = Field(
        ..., ge=0.0, le=100.0, description="Normalized score from 0 to 100"
    )
    score_breakdown: PartnershipScoreBreakdown = Field(
        ..., description="6-dimensional scoring breakdown"
    )
    supporting_qloo_evidence: dict[str, Any] = Field(
        ..., description="Verifiable Qloo evidence backing this candidate"
    )
    partnership_concept: str = Field(
        ..., description="Physical space collaboration concept"
    )
    estimated_effort: str = Field(
        ...,
        description="Estimated operational effort level (Low/Medium/High) and rationale",
    )
    risk: str = Field(
        ...,
        description="Risk analysis including brand clash, operational, budget, or exclusivity considerations",
    )
    recommended_next_action: str = Field(
        ..., description="Recommended immediate next action"
    )
    outreach_draft: OutreachDraft = Field(
        ..., description="Draft outreach communication"
    )
    is_existing_partner: bool = Field(
        default=False,
        description="Explicit guardrail: False indicates no pre-existing partnership exists",
    )


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

    cultural_twin: CulturalTwin | None = Field(
        default=None, description="Structured CulturalTwin foundation"
    )
    cultural_matrix: CulturalMatrix = Field(
        ..., description="Verified candidate CulturalMatrix"
    )
    brand_results: list[CulturalRecommendation] | None = Field(
        default=None, description="Optional explicit Qloo brand results"
    )
    business_constraints: list[str] | None = Field(
        default=None, description="Operational and commercial constraints"
    )
    budget: str | None = Field(
        default=None, description="Operating budget tier or parameters"
    )
    strategy: CulturalStrategyOutput | None = Field(
        default=None, description="Optional upstream cultural strategy"
    )
    experience_design: ExperienceDesignOutput | None = Field(
        default=None, description="Optional upstream experience design"
    )


class PartnershipOutput(BaseModel):
    """Structured partnership activations output."""

    candidates: list[BrandPartnershipCandidate] = Field(
        default_factory=list,
        description="Top scored brand partnership candidates with Qloo evidence and outreach drafts",
    )
    partnerships: list[PartnershipActivation] = Field(
        default_factory=list, description="Ranked partnership activations"
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
