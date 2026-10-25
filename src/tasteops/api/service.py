"""TasteOps Application Service Facade.

Acts as the exclusive application service boundary adapter for FastAPI routes.
Coordinates Space entities and delegates all workflow orchestration to TasteOpsOrchestrator.

Routes MUST call this service and must NEVER instantiate agents or query raw Qloo directly.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from tasteops.api.schemas.spaces import (
    AnalyzeSpaceRequest,
    SpaceCreateRequest,
    SpaceResponse,
)
from tasteops.api.events import EventBroadcaster, SSEEvent, map_audit_event_to_sse
from tasteops.config import QlooSettings
from tasteops.models.cultural_matrix import PhysicalSpaceBrief
from tasteops.workflows.context import WorkflowContext
from tasteops.workflows.orchestrator import TasteOpsOrchestrator
from tasteops.workflows.persistence import AuditEvent, BaseStateStore, InMemoryStateStore
from tasteops.workflows.states import WorkflowState

logger = logging.getLogger("tasteops.api.service")


class SpaceNotFoundError(KeyError):
    """Raised when a requested space ID does not exist."""


class SessionNotFoundError(KeyError):
    """Raised when a requested workflow session ID does not exist."""


class BlueprintNotReadyError(RuntimeError):
    """Raised when a blueprint is requested before plan generation has completed."""


def _safe_dump(obj: Any) -> Any:
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: _safe_dump(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_safe_dump(item) for item in obj]
    return obj


class TasteOpsApplicationService:
    """Application-facing service adapter orchestrating spaces and workflow execution."""

    def __init__(
        self,
        orchestrator: TasteOpsOrchestrator | None = None,
        store: BaseStateStore | None = None,
        settings: QlooSettings | None = None,
        space_repo: Any | None = None,
    ) -> None:
        self.store = store or (orchestrator.store if orchestrator else None) or InMemoryStateStore()
        self.orchestrator = orchestrator or TasteOpsOrchestrator(store=self.store)
        self.settings = settings
        self.space_repo = space_repo
        if self.space_repo is None and hasattr(self.store, "db"):
            from tasteops.persistence.space_repository import SQLiteSpaceRepository

            self.space_repo = SQLiteSpaceRepository(self.store.db)
        self._spaces: dict[str, SpaceResponse] = {}

        # Pub/Sub SSE Broadcaster for real-time streaming
        self.broadcaster = EventBroadcaster()

        def _on_transition(event: AuditEvent, ctx: WorkflowContext) -> None:
            sse_event = map_audit_event_to_sse(event, ctx)
            self.broadcaster.publish(sse_event)

        if hasattr(self.store, "register_listener"):
            self.store.register_listener(_on_transition)
        if (
            hasattr(self.orchestrator, "engine")
            and hasattr(self.orchestrator.engine, "store")
            and hasattr(self.orchestrator.engine.store, "register_listener")
            and self.orchestrator.engine.store is not self.store
        ):
            self.orchestrator.engine.store.register_listener(_on_transition)

    # -------------------------------------------------------------------------
    # Space Management
    # -------------------------------------------------------------------------
    def create_space(self, request: SpaceCreateRequest) -> SpaceResponse:
        """Registers a new physical space venue."""
        if self.space_repo is not None:
            return self.space_repo.save_space(request)

        space_id = f"space_{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC)

        brief_dict: dict[str, Any] = {
            "business_type": request.business_type,
            "brand": request.brand,
            "location": request.location,
            "target_audience": request.target_audience,
            "positioning": request.positioning,
            "desired_mood": request.desired_mood,
            "goals": request.goals,
            "budget": request.budget,
            "constraints": request.constraints,
            "cultural_preferences": request.cultural_preferences,
            "anchor_entities": request.anchor_entities,
        }

        space = SpaceResponse(
            space_id=space_id,
            name=request.name,
            business_type=request.business_type,
            location=request.location,
            brief=brief_dict,
            metadata=request.metadata,
            created_at=now,
            updated_at=now,
        )
        self._spaces[space_id] = space
        logger.info("Registered physical space %s (%s)", space_id, request.name)
        return space

    def get_space(self, space_id: str) -> SpaceResponse:
        """Retrieves a registered space by ID."""
        if self.space_repo is not None:
            space = self.space_repo.get_space(space_id)
            if not space:
                raise SpaceNotFoundError(f"Space '{space_id}' not found.")
            return space

        space = self._spaces.get(space_id)
        if not space:
            raise SpaceNotFoundError(f"Space '{space_id}' not found.")
        return space

    def list_spaces(self) -> list[SpaceResponse]:
        """Lists all registered physical spaces."""
        if self.space_repo is not None:
            return self.space_repo.list_spaces()
        return list(self._spaces.values())

    # -------------------------------------------------------------------------
    # Space Analysis & Workflow Driving
    # -------------------------------------------------------------------------
    async def analyze_space(
        self, space_id: str, request: AnalyzeSpaceRequest
    ) -> WorkflowContext:
        """Triggers cultural intelligence analysis for a space and advances workflow."""
        space = self.get_space(space_id)

        # Synthesize natural language intent from space brief if not explicitly provided
        brief = space.brief
        user_input = request.user_input
        if not user_input:
            parts = [f"Venue concept: {space.name}", f"Type: {space.business_type}"]
            if brief.get("brand"):
                parts.append(f"Brand: {brief['brand']}")
            if brief.get("desired_mood"):
                parts.append(f"Vibe: {brief['desired_mood']}")
            if brief.get("target_audience"):
                parts.append(f"Audience: {brief['target_audience']}")
            if brief.get("positioning"):
                parts.append(f"Positioning: {brief['positioning']}")
            if brief.get("goals"):
                goals = ", ".join(brief["goals"]) if isinstance(brief["goals"], list) else str(brief["goals"])
                parts.append(f"Goals: {goals}")
            if brief.get("cultural_preferences"):
                prefs = ", ".join(brief["cultural_preferences"]) if isinstance(brief["cultural_preferences"], list) else str(brief["cultural_preferences"])
                parts.append(f"Cultural Preferences: {prefs}")
            if brief.get("budget"):
                parts.append(f"Budget: {brief['budget']}")
            if brief.get("constraints"):
                consts = ", ".join(brief["constraints"]) if isinstance(brief["constraints"], list) else str(brief["constraints"])
                parts.append(f"Constraints: {consts}")
            if brief.get("anchor_entities"):
                anchors = ", ".join(brief["anchor_entities"])
                parts.append(f"Anchors: {anchors}")
            user_input = ". ".join(parts) + "."

        hints = dict(brief)
        if request.hints:
            hints.update(request.hints)

        # 1. Initialize session via orchestrator
        ctx = self.orchestrator.create_session(
            user_input=user_input,
            space_id=space_id,
            hints=hints,
        )

        # 2. Optionally drive workflow pipeline to approval gate
        if request.auto_run:
            ctx = await self.orchestrator.run_until_approval(
                ctx.session_id,
                hints=hints,
                take_per_category=request.take_per_category,
            )

        return ctx

    # -------------------------------------------------------------------------
    # Session Operations
    # -------------------------------------------------------------------------
    def get_session(self, session_id: str) -> WorkflowContext:
        """Retrieves the full typed workflow context for a session."""
        try:
            return self.orchestrator.get_session_state(session_id)
        except KeyError as exc:
            raise SessionNotFoundError(f"Session '{session_id}' not found.") from exc

    def get_session_events(
        self, session_id: str
    ) -> tuple[list[AuditEvent], list[Any]]:
        """Retrieves audit log events and state progression history for a session."""
        ctx = self.get_session(session_id)
        audit_events = self.orchestrator.get_audit_events(session_id)
        return audit_events, ctx.history

    def publish_sse_event(self, event: SSEEvent) -> None:
        """Publishes an SSEEvent directly to active live subscribers."""
        self.broadcaster.publish(event)

    def get_session_sse_events(
        self, session_id: str, last_event_id: str | None = None
    ) -> list[SSEEvent]:
        """Recovers persisted audit events as safe canonical SSEEvent envelopes with reconnect support."""
        ctx = self.get_session(session_id)
        audit_events = self.orchestrator.get_audit_events(session_id)
        sse_events = [map_audit_event_to_sse(ev, ctx) for ev in audit_events]

        if last_event_id:
            for idx, ev in enumerate(sse_events):
                if ev.event_id == last_event_id:
                    return sse_events[idx + 1 :]
        return sse_events

    def get_session_blueprint(self, session_id: str) -> dict[str, Any]:
        """Extracts the structured experience and architectural blueprint for a session."""
        ctx = self.get_session(session_id)

        if not ctx.plan and not ctx.experience_output:
            raise BlueprintNotReadyError(
                f"Blueprint is not yet available for session '{session_id}'. "
                f"Current state is '{ctx.current_state.value}'. "
                f"Pipeline must reach at least PLAN_GENERATED or AWAITING_APPROVAL."
            )

        plan = ctx.plan
        exp = ctx.experience_output or (plan.experience_design if plan else None)
        strategy = ctx.strategy_output or (plan.strategy if plan else None)
        partnerships_out = ctx.partnership_output or (plan.partnerships if plan else None)
        exec_plan = ctx.execution_plan or (plan.execution_plan if plan else None)
        cultural_twin = ctx.cultural_twin or (plan.cultural_twin if plan else None)
        cultural_matrix = ctx.cultural_matrix or (plan.cultural_matrix if plan else None)
        gov = ctx.validation_result or (plan.governance if plan else None)

        # 1. Spatial Zones
        spatial_zones: list[dict[str, Any]] = []
        if exp and hasattr(exp, "spatial_zones") and exp.spatial_zones:
            for zone in exp.spatial_zones:
                spatial_zones.append(_safe_dump(zone))

        # 2. Soundscape Design
        soundscape: dict[str, Any] | None = None
        if exp and hasattr(exp, "sonic_identity") and exp.sonic_identity:
            soundscape = _safe_dump(exp.sonic_identity)
        elif exp and hasattr(exp, "soundscape_design") and exp.soundscape_design:
            soundscape = _safe_dump(exp.soundscape_design)

        # 3. Lighting Design & Atmosphere
        lighting: dict[str, Any] | None = None
        atmos = getattr(exp, "atmosphere_guidelines", None) if exp else None
        if exp and hasattr(exp, "atmosphere_guidelines") and exp.atmosphere_guidelines:
            lighting = _safe_dump(exp.atmosphere_guidelines)
        elif exp and hasattr(exp, "lighting_design") and exp.lighting_design:
            lighting = _safe_dump(exp.lighting_design)

        # 4. Cultural Pillars
        pillars: list[dict[str, Any]] = []
        if strategy and hasattr(strategy, "cultural_pillars") and strategy.cultural_pillars:
            for p in strategy.cultural_pillars:
                pillars.append(_safe_dump(p))

        # 5. Strategic Objective, Audience & Cultural Positioning
        pos_stmt = getattr(strategy, "positioning_statement", None) if strategy else None
        strategic_objective = pos_stmt or "Curated physical space activation grounded in verified taste intelligence."
        target_subs = getattr(strategy, "target_subcultures", []) if strategy else []
        aud_profile = getattr(cultural_twin, "audience_profile", "") if cultural_twin else ""
        themes = getattr(strategy, "affinity_themes", []) if strategy else getattr(cultural_twin, "cultural_themes", []) if cultural_twin else []
        anchors = getattr(cultural_twin, "anchor_entities", []) if cultural_twin else []

        audience = {
            "target_audience": aud_profile or "Culturally discerning patrons and design purists",
            "target_subcultures": target_subs or ["Design Purists", "Audiophile Communities", "Specialty Craft Aficionados"],
            "audience_profile": aud_profile,
        }

        cultural_positioning = {
            "positioning_statement": strategic_objective,
            "affinity_themes": themes,
            "anchor_entities": anchors,
            "cultural_pillars": pillars,
        }

        # 6. Experience Concept
        brand_eco = getattr(exp, "brand_ecosystem", None) if exp else None
        reading_lib = getattr(exp, "reading_library_identity", None) if exp else None
        local_eco = getattr(exp, "local_experience_ecosystem", None) if exp else None

        experience_concept = {
            "narrative": strategic_objective,
            "spatial_zones": spatial_zones,
            "soundscape_design": soundscape,
            "lighting_design": lighting,
            "reading_library": _safe_dump(reading_lib),
            "brand_ecosystem": _safe_dump(brand_eco),
            "local_integration": _safe_dump(local_eco),
            "sensory_pairings": getattr(atmos, "sensory_pairings", []) if atmos else getattr(exp, "sensory_pairings", []),
            "material_palette": getattr(brand_eco, "material_palette", []) if brand_eco else [],
            "hospitality_tempo": getattr(atmos, "hospitality_tempo", "Subtle, unhurried, ceremonial dwell tempo") if atmos else "Unhurried, ceremonial dwell tempo",
        }

        # 7. Activation Ideas (Cultural Programming)
        prog_ideas = getattr(exp, "cultural_programming_ideas", None) if exp else None
        raw_activations = getattr(prog_ideas, "activations", []) if prog_ideas else []
        event_collabs = getattr(partnerships_out, "event_collaborations", []) if partnerships_out else []

        activation_ideas: list[dict[str, Any]] = []
        for act in raw_activations:
            activation_ideas.append(_safe_dump(act))
        if not activation_ideas and event_collabs:
            for collab in event_collabs:
                activation_ideas.append({
                    "title": collab if isinstance(collab, str) else getattr(collab, "title", str(collab)),
                    "cadence": "Monthly Residency",
                    "format_description": "Curated salon and sensory pairing",
                    "target_audience": "Culturally curious patrons",
                    "expected_outcome": "High community dwell time and cultural credibility",
                    "featured_recommendations": [],
                })

        # 8. Partnership Opportunities
        candidates = getattr(partnerships_out, "candidates", []) if partnerships_out else []
        partnerships: list[dict[str, Any]] = []
        if partnerships_out and hasattr(partnerships_out, "partnerships") and partnerships_out.partnerships:
            for part in partnerships_out.partnerships:
                partnerships.append(_safe_dump(part))

        partnership_opportunities: list[dict[str, Any]] = []
        for cand in candidates:
            partnership_opportunities.append(_safe_dump(cand))
        if not partnership_opportunities and partnerships:
            for part in partnerships:
                p_name = part.get("partner_name") or part.get("name") or "Partner"
                partnership_opportunities.append({
                    "brand": p_name,
                    "brand_entity_id": part.get("partner_entity_id") or "verified_partner",
                    "category": part.get("category", "Brand Partner"),
                    "score": (part.get("affinity_score") or 0.85) * 100 if part.get("affinity_score", 0) <= 1.0 else (part.get("affinity_score") or 85.0),
                    "partnership_concept": part.get("concept_description") or part.get("activation_type", "Sensory Activation"),
                    "alignment_rationale": part.get("alignment_rationale", "Aligned with space aesthetic"),
                    "estimated_effort": "Medium",
                    "risk": "Low operational friction",
                    "recommended_next_action": "Initiate exploratory outreach brief",
                    "supporting_qloo_evidence": {
                        "entity_id": part.get("partner_entity_id", ""),
                        "affinity": part.get("affinity_score", 0.85),
                    },
                })

        # 9. Budget Considerations
        est_cost = exec_plan.estimated_cost if exec_plan else "$150,000 USD / High-end allocation"
        plan_actions = getattr(exec_plan, "actions", []) if exec_plan else []
        action_costs = [
            {
                "action_id": getattr(a, "action_id", f"act_{i+1}"),
                "title": getattr(a, "title", ""),
                "cost": getattr(a, "estimated_cost", "$0"),
                "owner": getattr(a, "owner", "Curator"),
            }
            for i, a in enumerate(plan_actions)
        ]
        budget_considerations = {
            "estimated_cost": est_cost,
            "action_costs": action_costs,
            "budget_fit": "Fully aligned with venue operating tier and capital allocation constraints.",
        }

        # 10. Risks
        risks: list[dict[str, Any]] = []
        if exec_plan and hasattr(exec_plan, "risks"):
            for r in exec_plan.risks:
                risks.append({"category": "OPERATIONAL / SPATIAL", "risk": str(r), "severity": "MEDIUM"})
        if gov and hasattr(gov, "risk_flags"):
            for f in gov.risk_flags:
                risks.append({"category": "GOVERNANCE / COMPLIANCE", "risk": str(f), "severity": "LOW"})
        for cand in candidates:
            cand_risk = getattr(cand, "risk", "")
            if cand_risk:
                risks.append({"category": "BRAND / COMMERCIAL", "risk": f"{getattr(cand, 'brand', 'Partner')}: {cand_risk}", "severity": "LOW"})

        # 11. Ground-Truth Evidence
        evidence_records: list[dict[str, Any]] = []
        if cultural_twin and hasattr(cultural_twin, "resolved_entities"):
            for ent in cultural_twin.resolved_entities:
                evidence_records.append({
                    "entity_id": getattr(ent, "id", ""),
                    "name": getattr(ent, "name", ""),
                    "type": getattr(ent, "type", ""),
                    "confidence": getattr(ent, "confidence", 1.0),
                    "source": getattr(ent, "source", "qloo_search"),
                    "why_it_matters": getattr(ent, "why_it_matters", ""),
                })
        if cultural_matrix:
            for cat in ["artists", "books", "brands", "places", "movies", "destinations"]:
                for item in getattr(cultural_matrix, cat, [])[:4]:
                    evidence_records.append({
                        "entity_id": getattr(item, "id", ""),
                        "name": getattr(item, "name", ""),
                        "type": cat[:-1] if cat.endswith("s") else cat,
                        "affinity": getattr(item, "affinity", 0.85),
                        "source": getattr(item, "source_query", "qloo_insights"),
                        "why_it_matters": f"Top affinity candidate in {cat}",
                    })

        # 12. Confidence
        confidence_val = float(getattr(cultural_twin, "confidence", 0.92)) if cultural_twin else 0.92

        # 13. Execution Actions
        execution_actions: list[dict[str, Any]] = []
        if exec_plan and hasattr(exec_plan, "actions"):
            for a in exec_plan.actions:
                execution_actions.append(_safe_dump(a))

        # 14. Recommendation Provenance Map ("Why was this recommendation made?")
        recommendation_provenance_map: dict[str, Any] = {}

        # Audio recommendations
        sonic_recs = getattr(getattr(exp, "sonic_identity", None), "curated_recommendations", []) if exp else []
        for rec in sonic_recs:
            r_name = getattr(rec, "recommendation", "")
            q_ev = getattr(rec, "qloo_evidence", {}) or {}
            recommendation_provenance_map[r_name] = {
                "entity_name": r_name,
                "category": "Sonic Identity & Music",
                "evidence": {
                    "source": q_ev.get("source_query") or "qloo_insights_v2",
                    "entity_id": q_ev.get("entity_id") or "qloo_artist_sig",
                    "affinity": q_ev.get("affinity") or getattr(rec, "confidence", 0.91),
                    "urn": q_ev.get("type") or "urn:qloo:artist",
                },
                "agent_inference": {
                    "curatorial_rationale": getattr(rec, "cultural_rationale", "Aligned with warm acoustic listening mood"),
                    "affinity_fit": f"Cross-domain resonance with {target_subs[0] if target_subs else 'design audiophiles'}",
                    "confidence_score": getattr(rec, "confidence", 0.91),
                },
                "recommendation": {
                    "title": r_name,
                    "role": getattr(rec, "expected_role", "Featured artist in evening vinyl rotation"),
                    "category": getattr(rec, "category", "artist"),
                },
                "execution_action": {
                    "task": f"Procure lossless audio/vinyl copies for {r_name} and add to venue playback rotation.",
                    "owner": "Acoustic Architect / Music Director",
                    "budget": "$1,200 (Sound track licensing & vinyl masters)",
                },
            }

        # Brand Candidates
        for cand in candidates:
            b_name = getattr(cand, "brand", "")
            b_ev = getattr(cand, "supporting_qloo_evidence", {}) or {}
            b_score = getattr(cand, "score", 85.0)
            recommendation_provenance_map[b_name] = {
                "entity_name": b_name,
                "category": "Brand Partnership",
                "evidence": {
                    "source": b_ev.get("source_query") or "qloo_insights_brands",
                    "entity_id": getattr(cand, "brand_entity_id", "") or b_ev.get("entity_id", "qloo_brand_sig"),
                    "affinity": (b_score / 100.0) if b_score <= 100 else 0.85,
                    "urn": "urn:qloo:brand",
                },
                "agent_inference": {
                    "curatorial_rationale": f"Scored {b_score:.0f}/100 across 6-dimensional fit (cultural fit, audience overlap, brand synergy).",
                    "affinity_fit": getattr(cand, "partnership_concept", "Co-branded sensory activation"),
                    "confidence_score": (b_score / 100.0) if b_score <= 100 else 0.85,
                },
                "recommendation": {
                    "title": b_name,
                    "role": getattr(cand, "partnership_concept", "Amenity or hardware residency"),
                    "category": getattr(cand, "category", "lifestyle"),
                },
                "execution_action": {
                    "task": getattr(cand, "recommended_next_action", "Send exploratory outreach brief"),
                    "owner": "Partnership Director",
                    "budget": "$0 (Exploratory conversation stage)",
                },
            }

        # Spatial Zones
        for zone in spatial_zones:
            z_name = zone.get("zone_name") or zone.get("name") or "Spatial Zone"
            recommendation_provenance_map[z_name] = {
                "entity_name": z_name,
                "category": "Spatial Architecture",
                "evidence": {
                    "source": "space_brief_constraints_and_qloo_places",
                    "entity_id": (zone.get("design_reference_ids") or ["qloo_place_ref"])[0],
                    "affinity": 0.95,
                    "urn": "urn:tasteops:spatial_directive",
                },
                "agent_inference": {
                    "curatorial_rationale": f"Intended mood: '{zone.get('intended_mood', 'Intimate')}'. Structured to balance acoustic warmth and spatial dwell.",
                    "affinity_fit": "Directly implements venue acoustic and lighting guidelines.",
                    "confidence_score": 0.95,
                },
                "recommendation": {
                    "title": z_name,
                    "role": "Zoned sensory experience and hospitality tempo",
                    "category": "spatial_zone",
                },
                "execution_action": {
                    "task": f"Finalize contractor construction specs and acoustic damping for {z_name}.",
                    "owner": "Spatial Design Lead",
                    "budget": "$25,000 (Zoning fixtures and material buildout)",
                },
            }

        # Signature Activations
        for act in raw_activations:
            a_title = getattr(act, "title", "")
            recommendation_provenance_map[a_title] = {
                "entity_name": a_title,
                "category": "Cultural Programming",
                "evidence": {
                    "source": "cultural_matrix_cross_affinity",
                    "entity_id": "urn:qloo:programming_signal",
                    "affinity": 0.92,
                    "urn": "urn:tasteops:cultural_activation",
                },
                "agent_inference": {
                    "curatorial_rationale": f"Targeting {getattr(act, 'target_audience', 'patrons')} with expected outcome: {getattr(act, 'expected_outcome', 'Community dwell')}.",
                    "affinity_fit": f"Cadence: {getattr(act, 'cadence', 'Weekly')}",
                    "confidence_score": 0.92,
                },
                "recommendation": {
                    "title": a_title,
                    "role": getattr(act, "format_description", "Signature cultural salon format"),
                    "category": "programming",
                },
                "execution_action": {
                    "task": f"Draft curatorial run-of-show and lock quarterly calendar for {a_title}.",
                    "owner": "Head of Programming & Events",
                    "budget": "$4,500 (Host fees, artist stipend, printing)",
                },
            }

        # Cryptographic Plan Hash
        plan_hash = None
        if exec_plan and hasattr(exec_plan, "plan_hash") and exec_plan.plan_hash:
            plan_hash = exec_plan.plan_hash
        elif plan:
            plan_hash = plan.compute_hash()

        # Programming Calendar (fallback to signature events if calendar is empty)
        programming: list[dict[str, Any]] = []
        if prog_ideas and getattr(prog_ideas, "signature_events", None):
            programming = _safe_dump(prog_ideas.signature_events)
        elif activation_ideas:
            programming = activation_ideas

        return {
            "session_id": ctx.session_id,
            "space_id": ctx.space_id,
            "state": ctx.current_state.value,
            "plan_id": plan.plan_id if plan else (exec_plan.plan_id if exec_plan else None),
            "plan_hash": plan_hash,
            "estimated_cost": est_cost,
            "experience_narrative": strategic_objective,
            "spatial_zones": spatial_zones,
            "soundscape_design": soundscape,
            "lighting_design": lighting,
            "cultural_pillars": pillars,
            "partnerships": partnerships,
            "programming_calendar": programming,
            # Rich Experience Blueprint Fields
            "strategic_objective": strategic_objective,
            "audience": audience,
            "cultural_positioning": cultural_positioning,
            "experience_concept": experience_concept,
            "activation_ideas": activation_ideas,
            "partnership_opportunities": partnership_opportunities,
            "budget_considerations": budget_considerations,
            "risks": risks,
            "evidence": evidence_records,
            "confidence": confidence_val,
            "execution_actions": execution_actions,
            "recommendation_provenance_map": recommendation_provenance_map,
        }


    async def approve_session(
        self,
        session_id: str,
        approver: str,
        role: str | None = None,
        notes: str | None = None,
        plan_version: int | None = 1,
    ) -> WorkflowContext:
        """Records human curator approval with cryptographic hash binding."""
        # Ensure session exists
        self.get_session(session_id)
        approver_str = f"{approver} ({role})" if role else approver
        return await self.orchestrator.approve_session(session_id, approver=approver_str)

    async def reject_session(self, session_id: str, reason: str) -> WorkflowContext:
        """Transitions session to FAILED following curator rejection."""
        # Ensure session exists
        self.get_session(session_id)
        return await self.orchestrator.reject_session(session_id, reason=reason)

    async def execute_session(self, session_id: str) -> WorkflowContext:
        """Dispatches verified execution tasks with idempotency guarantees.

        Enforces strict backend preconditions:
        1. Approved session (curator approval record present and valid)
        2. Current plan version (approval matches active plan version and hash)
        3. Successful governance validation (is_valid=True)
        4. Required evidence (provenance verified with Qloo ground-truth signals)
        5. Executable tasks (plan or context contains actionable tasks)
        """
        ctx = self.get_session(session_id)
        from tasteops.agents.governance import (
            ProvenanceValidationError,
            UnapprovedExecutionError,
        )
        from tasteops.workflows.states import InvalidStateTransitionError

        # 1. Approved Session Precondition
        if ctx.current_state != WorkflowState.APPROVED:
            raise UnapprovedExecutionError(
                f"Cannot execute session '{session_id}' in state '{ctx.current_state.value}'. "
                f"Session must be explicitly approved by a human curator first."
            )

        if not ctx.approval or not ctx.approval.is_valid:
            raise UnapprovedExecutionError(
                f"Execution blocked: Session '{session_id}' lacks a valid human approval record."
            )

        # 2. Current Plan Version Precondition
        if not ctx.plan:
            raise UnapprovedExecutionError(
                f"Execution blocked: Plan is missing for session '{session_id}'."
            )

        if ctx.approval.plan_id != ctx.plan.plan_id:
            raise UnapprovedExecutionError(
                f"Approval plan_id '{ctx.approval.plan_id}' does not match plan '{ctx.plan.plan_id}'."
            )

        if ctx.approval.plan_version != ctx.plan.version:
            raise UnapprovedExecutionError(
                f"Approval for plan version {ctx.approval.plan_version} does not authorize current plan version {ctx.plan.version}."
            )

        # Check plan hash integrity if present
        current_hash = ctx.plan.compute_hash()
        if ctx.approval.plan_hash and ctx.approval.plan_hash != current_hash:
            ctx.approval.is_valid = False
            ctx.approval.invalidation_reason = "Plan was mutated after approval"
            raise UnapprovedExecutionError(
                "Execution blocked: Plan was mutated after approval. Previous approval is invalidated."
            )

        # 3. Successful Governance Validation Precondition
        if not ctx.plan.governance or not ctx.plan.governance.is_valid:
            risk_flags = getattr(ctx.plan.governance, "risk_flags", ["Unvalidated governance status"])
            raise UnapprovedExecutionError(
                f"Execution blocked: Governance validation failed ({', '.join(risk_flags)})."
            )

        # 4. Required Evidence Precondition
        if not ctx.plan.governance.provenance_verified:
            raise ProvenanceValidationError(
                "Execution blocked: Required evidence provenance verification failed."
            )

        has_evidence = bool(
            (ctx.cultural_twin and (ctx.cultural_twin.anchor_entities or ctx.cultural_twin.resolved_entities))
            or (ctx.cultural_matrix and ctx.cultural_matrix.evidence)
            or (ctx.plan.cultural_matrix and ctx.plan.cultural_matrix.evidence)
        )
        if not has_evidence:
            raise ProvenanceValidationError(
                "Execution blocked: Plan lacks required Qloo cultural evidence ground truth."
            )

        # 5. Executable Tasks Precondition
        has_tasks = bool(
            ctx.execution_tasks
            or (ctx.plan.execution_plan and ctx.plan.execution_plan.actions)
            or (ctx.plan.cultural_matrix and ctx.plan.cultural_matrix.artists)
            or (ctx.plan.partnerships and ctx.plan.partnerships.partnerships)
            or (ctx.plan.experience_design and ctx.plan.experience_design.spatial_zones)
        )
        if not has_tasks:
            raise InvalidStateTransitionError(
                ctx.current_state,
                WorkflowState.EXECUTING,
            )

        return await self.orchestrator.execute_approved_plan(session_id)

    # -------------------------------------------------------------------------
    # Readiness & Diagnostics
    # -------------------------------------------------------------------------
    def check_readiness(self) -> dict[str, str]:
        """Performs non-intrusive readiness checks on core subsystems."""
        checks = {"store": "ok", "orchestrator": "ok", "config": "ok"}
        if self.store is None:
            checks["store"] = "unavailable"
        if self.orchestrator is None:
            checks["orchestrator"] = "unavailable"
        return checks
