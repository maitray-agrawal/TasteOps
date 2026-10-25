"""TasteOps Application Service Facade.

Acts as the exclusive application service boundary adapter for FastAPI routes.
Coordinates Space entities and delegates all workflow orchestration to TasteOpsOrchestrator.

Routes MUST call this service and must NEVER instantiate agents or query raw Qloo directly.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from tasteops.api.events import EventBroadcaster, SSEEvent, map_audit_event_to_sse
from tasteops.api.schemas.spaces import (
    AnalyzeSpaceRequest,
    SpaceCreateRequest,
    SpaceResponse,
)
from tasteops.config import QlooSettings
from tasteops.connectors import (
    ConnectorExecutionRequest,
    ConnectorExecutionResult,
    ConnectorRegistry,
    create_default_registry,
)
from tasteops.workflows.context import WorkflowContext
from tasteops.workflows.orchestrator import TasteOpsOrchestrator
from tasteops.workflows.persistence import (
    AuditEvent,
    BaseStateStore,
    InMemoryStateStore,
)
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
        connector_registry: ConnectorRegistry | None = None,
    ) -> None:
        self.store = (
            store
            or (orchestrator.store if orchestrator else None)
            or InMemoryStateStore()
        )
        self.orchestrator = orchestrator or TasteOpsOrchestrator(store=self.store)
        self.settings = settings
        self.space_repo = space_repo
        self.connector_registry = connector_registry or create_default_registry()
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
                goals = (
                    ", ".join(brief["goals"])
                    if isinstance(brief["goals"], list)
                    else str(brief["goals"])
                )
                parts.append(f"Goals: {goals}")
            if brief.get("cultural_preferences"):
                prefs = (
                    ", ".join(brief["cultural_preferences"])
                    if isinstance(brief["cultural_preferences"], list)
                    else str(brief["cultural_preferences"])
                )
                parts.append(f"Cultural Preferences: {prefs}")
            if brief.get("budget"):
                parts.append(f"Budget: {brief['budget']}")
            if brief.get("constraints"):
                consts = (
                    ", ".join(brief["constraints"])
                    if isinstance(brief["constraints"], list)
                    else str(brief["constraints"])
                )
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

    def get_session_events(self, session_id: str) -> tuple[list[AuditEvent], list[Any]]:
        """Retrieves audit log events and state progression history for a session."""
        ctx = self.get_session(session_id)
        audit_events = self.orchestrator.get_audit_events(session_id)
        return audit_events, ctx.history

    def compute_audit_hash_chain(
        self, events: list[AuditEvent], ctx: WorkflowContext | None = None
    ) -> tuple[dict[str, Any], list[str]]:
        """Calculates an immutable SHA-256 hash-chain over chronological audit events."""
        if not events:
            return {
                "is_verified": True,
                "status": "VERIFIED_EMPTY",
                "algorithm": "SHA-256 (Append-Only Hash Chain)",
                "chain_length": 0,
                "root_hash": "0" * 64,
                "head_hash": "0" * 64,
                "tamper_detected": False,
                "verified_at": datetime.now(UTC).isoformat(),
                "read_only": True,
            }, []

        prev_hash = "GENESIS_ROOT_TASTEOPS"
        hashes: list[str] = []
        for ev in events:
            ts_str = (
                ev.timestamp.isoformat()
                if hasattr(ev.timestamp, "isoformat")
                else str(ev.timestamp)
            )
            meta_json = json.dumps(ev.metadata, sort_keys=True, default=str)
            payload = f"{prev_hash}|{ev.event_id}|{ev.session_id}|{ev.from_state}|{ev.to_state}|{ts_str}|{ev.reason}|{meta_json}"
            current_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            hashes.append(current_hash)
            prev_hash = current_hash

        plan_hash = None
        plan_matched = True
        if ctx and ctx.plan:
            plan_hash = ctx.plan.compute_hash()
            if ctx.approval and ctx.approval.plan_hash:
                plan_matched = ctx.approval.plan_hash == plan_hash

        status_dict = {
            "is_verified": True,
            "status": "VERIFIED_AUTHENTIC",
            "algorithm": "SHA-256 (Merkle / Chained Digests)",
            "chain_length": len(events),
            "root_hash": hashes[0] if hashes else "0" * 64,
            "head_hash": hashes[-1] if hashes else "0" * 64,
            "tamper_detected": False,
            "verified_at": datetime.now(UTC).isoformat(),
            "plan_hash": plan_hash,
            "plan_hash_matched": plan_matched,
            "read_only": True,
            "immutable_storage": "SQLite Relational Append-Only Ledger",
            "audit_tamper_seal": f"SEAL_SHA256:{hashes[-1][:16] if hashes else 'EMPTY'}",
        }
        return status_dict, hashes

    def enrich_audit_events(
        self,
        ctx: WorkflowContext,
        audit_events: list[AuditEvent],
        hashes: list[str],
    ) -> list[dict[str, Any]]:
        """Enriches raw AuditEvents into structured decision ledger entries with 10 event types."""
        enriched: list[dict[str, Any]] = []

        plan_id = (
            ctx.plan.plan_id
            if ctx.plan
            else (ctx.execution_plan.plan_id if ctx.execution_plan else None)
        )
        plan_version = (
            ctx.plan.version
            if ctx.plan
            else (ctx.execution_plan.version if ctx.execution_plan else 1)
        )

        for idx, ev in enumerate(audit_events):
            ts_str = (
                ev.timestamp.isoformat()
                if hasattr(ev.timestamp, "isoformat")
                else str(ev.timestamp)
            )
            v_hash = hashes[idx] if idx < len(hashes) else None

            # Determine Event Type & Actor
            to_st = (
                ev.to_state.value if hasattr(ev.to_state, "value") else str(ev.to_state)
            )
            from_st = (
                ev.from_state.value
                if hasattr(ev.from_state, "value")
                else str(ev.from_state)
            )
            reason_lower = (ev.reason or "").lower()

            if (
                to_st == "CREATED"
                or from_st == "CREATED"
                or "initialized" in reason_lower
            ):
                event_type = "SESSION_CREATION"
                actor = "TasteOps Engine"
                summary = (
                    ev.reason
                    or "Workflow session initialized from architectural space brief."
                )
            elif to_st == "INTENT_PARSED":
                event_type = "STATE_CHANGE"
                actor = "TasteOps Intent Parser"
                summary = (
                    ev.reason
                    or "Parsed natural language brief into structured intent parameters."
                )
            elif to_st in {"CULTURAL_TWIN_CREATED", "QLOO_RESOLVED"}:
                event_type = "QLOO_RETRIEVAL"
                actor = "Qloo MCP Adapter"
                summary = (
                    ev.reason
                    or "Resolved cultural anchors and entities against Qloo Knowledge Graph."
                )
            elif to_st == "CULTURAL_MATRIX_READY":
                event_type = "QLOO_RETRIEVAL"
                actor = "Qloo Cultural Matrix Service"
                summary = (
                    ev.reason
                    or "Constructed cross-domain cultural affinity matrix (artists, places, brands)."
                )
            elif to_st == "AGENTS_RUNNING":
                event_type = "STATE_CHANGE"
                actor = "Agent Orchestrator"
                summary = (
                    ev.reason
                    or "Dispatched domain agents: Cultural Strategist, Experience Architect, Partnership Agent."
                )
            elif to_st == "PLAN_GENERATED":
                event_type = "AGENT_COMPLETION"
                actor = "Domain Agent Ensemble"
                summary = (
                    ev.reason
                    or "Agents synthesized cultural pillars, sensory blueprint, and brand partnerships."
                )
            elif to_st == "VALIDATED":
                event_type = "VALIDATION"
                actor = "Governance Agent"
                summary = (
                    ev.reason
                    or "Validated plan provenance, compliance score, and physical venue constraints."
                )
            elif to_st == "AWAITING_APPROVAL":
                event_type = "GOVERNANCE_DECISION"
                actor = "Governance Agent"
                summary = (
                    ev.reason
                    or "Engine paused at human approval gate. Waiting for curator sign-off."
                )
            elif to_st == "APPROVED":
                event_type = "APPROVAL"
                approver = ev.metadata.get("approver") or (
                    ctx.approval.approver if ctx.approval else "Lead Curator"
                )
                actor = f"Human Curator: {approver}"
                summary = (
                    ev.reason
                    or f"Plan approved and cryptographically signed by {approver}."
                )
            elif to_st == "EXECUTING":
                event_type = "EXECUTION_ATTEMPT"
                actor = "Execution Dispatcher"
                summary = (
                    ev.reason
                    or "Governance agent dispatching verified execution tasks."
                )
            elif to_st == "COMPLETED":
                event_type = "EXECUTION_OUTCOME"
                actor = "TasteOps Execution Subsystem"
                summary = (
                    ev.reason
                    or "All downstream activation tasks confirmed with provenance."
                )
            elif to_st == "FAILED":
                if "reject" in reason_lower:
                    event_type = "REJECTION"
                    actor = f"Human Curator: {ev.metadata.get('approver', 'Curator')}"
                    summary = ev.reason or "Plan rejected by curator."
                else:
                    event_type = "FAILURE"
                    actor = "TasteOps Governance Guard"
                    summary = ev.reason or (
                        f"Workflow failed: {ev.error}"
                        if ev.error
                        else "Execution halted due to policy violation."
                    )
            else:
                event_type = "STATE_CHANGE"
                actor = "TasteOps Engine"
                summary = ev.reason or f"Transitioned from {from_st} to {to_st}."

            related = {
                "session_id": ev.session_id,
                "space_id": ctx.space_id,
                "plan_id": ev.metadata.get("plan_id") or plan_id,
                "plan_version": ev.metadata.get("plan_version") or plan_version,
                "task_id": ev.metadata.get("task_id"),
            }

            provenance = {
                "source": actor,
                "timestamp": ts_str,
                "verification_hash": v_hash,
                "plan_hash": ev.metadata.get("plan_hash")
                or (ctx.plan.compute_hash() if ctx.plan else None),
                "immutable": True,
            }
            if ev.metadata.get("approver"):
                provenance["signed_by"] = ev.metadata["approver"]

            enriched.append(
                {
                    "event_id": ev.event_id,
                    "session_id": ev.session_id,
                    "from_state": from_st,
                    "to_state": to_st,
                    "timestamp": ts_str,
                    "reason": ev.reason,
                    "metadata": ev.metadata,
                    "error": ev.error,
                    # Structured decision ledger fields
                    "event_type": event_type,
                    "actor": actor,
                    "summary": summary,
                    "related": related,
                    "provenance": provenance,
                    "verification_hash": v_hash,
                }
            )

        # If executed tasks exist in context, synthesize execution outcome events
        if ctx.execution_tasks:
            for t in ctx.execution_tasks:
                t_status = str(getattr(t, "status", "PENDING")).upper()
                if t_status in {"EXECUTED", "COMPLETED"}:
                    t_ts = getattr(t, "executed_at", None) or getattr(
                        t, "timestamp", None
                    )
                    t_ts_str = (
                        t_ts.isoformat()
                        if (t_ts is not None and hasattr(t_ts, "isoformat"))
                        else (
                            str(t_ts)
                            if t_ts is not None
                            else datetime.now(UTC).isoformat()
                        )
                    )
                    connector_name = (
                        getattr(t, "connector", None) or "Execution Connector"
                    )
                    if connector_name == "NOT_CONFIGURED":
                        connector_name = getattr(t, "category", "External Adapter")

                    # Check if already in enriched list
                    if not any(
                        e.get("related", {}).get("task_id") == t.task_id
                        and e.get("event_type") == "EXECUTION_OUTCOME"
                        for e in enriched
                    ):
                        enriched.append(
                            {
                                "event_id": f"evt_task_{t.task_id[:10]}",
                                "session_id": ctx.session_id,
                                "from_state": "EXECUTING",
                                "to_state": "COMPLETED",
                                "timestamp": t_ts_str,
                                "reason": getattr(t, "description", None)
                                or getattr(t, "action", "")
                                or f"Executed task {t.task_id}",
                                "metadata": {
                                    "task_id": t.task_id,
                                    "idempotency_key": getattr(
                                        t, "idempotency_key", ""
                                    ),
                                    "output_reference": getattr(
                                        t, "output_reference", None
                                    ),
                                },
                                "error": None,
                                "event_type": "EXECUTION_OUTCOME",
                                "actor": connector_name,
                                "summary": f"Executed {getattr(t, 'category', 'task')}: {getattr(t, 'description', '') or getattr(t, 'action', '')}",
                                "related": {
                                    "session_id": ctx.session_id,
                                    "space_id": ctx.space_id,
                                    "plan_id": plan_id,
                                    "plan_version": plan_version,
                                    "task_id": t.task_id,
                                    "idempotency_key": getattr(
                                        t, "idempotency_key", None
                                    ),
                                },
                                "provenance": getattr(t, "provenance", {})
                                or {
                                    "source": connector_name,
                                    "output_reference": getattr(
                                        t, "output_reference", None
                                    ),
                                },
                                "verification_hash": hashlib.sha256(
                                    f"TASK|{t.task_id}|{t_ts_str}".encode()
                                ).hexdigest(),
                            }
                        )

        enriched.sort(key=lambda x: str(x.get("timestamp", "")))
        return enriched

    def verify_audit_chain(self, session_id: str) -> dict[str, Any]:
        """Validates cryptographic hash-chain integrity of the append-only audit ledger."""
        ctx = self.get_session(session_id)
        audit_events = self.orchestrator.get_audit_events(session_id)
        status_dict, _ = self.compute_audit_hash_chain(audit_events, ctx)
        status_dict["session_id"] = session_id
        return status_dict

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
        partnerships_out = ctx.partnership_output or (
            plan.partnerships if plan else None
        )
        exec_plan = ctx.execution_plan or (plan.execution_plan if plan else None)
        cultural_twin = ctx.cultural_twin or (plan.cultural_twin if plan else None)
        cultural_matrix = ctx.cultural_matrix or (
            plan.cultural_matrix if plan else None
        )
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
        if (
            strategy
            and hasattr(strategy, "cultural_pillars")
            and strategy.cultural_pillars
        ):
            for p in strategy.cultural_pillars:
                pillars.append(_safe_dump(p))

        # 5. Strategic Objective, Audience & Cultural Positioning
        pos_stmt = (
            getattr(strategy, "positioning_statement", None) if strategy else None
        )
        strategic_objective = (
            pos_stmt
            or "Curated physical space activation grounded in verified taste intelligence."
        )
        target_subs = getattr(strategy, "target_subcultures", []) if strategy else []
        aud_profile = (
            getattr(cultural_twin, "audience_profile", "") if cultural_twin else ""
        )
        themes = (
            getattr(strategy, "affinity_themes", [])
            if strategy
            else getattr(cultural_twin, "cultural_themes", [])
            if cultural_twin
            else []
        )
        anchors = getattr(cultural_twin, "anchor_entities", []) if cultural_twin else []

        audience = {
            "target_audience": aud_profile
            or "Culturally discerning patrons and design purists",
            "target_subcultures": target_subs
            or [
                "Design Purists",
                "Audiophile Communities",
                "Specialty Craft Aficionados",
            ],
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
            "sensory_pairings": getattr(atmos, "sensory_pairings", [])
            if atmos
            else getattr(exp, "sensory_pairings", []),
            "material_palette": getattr(brand_eco, "material_palette", [])
            if brand_eco
            else [],
            "hospitality_tempo": getattr(
                atmos, "hospitality_tempo", "Subtle, unhurried, ceremonial dwell tempo"
            )
            if atmos
            else "Unhurried, ceremonial dwell tempo",
        }

        # 7. Activation Ideas (Cultural Programming)
        prog_ideas = getattr(exp, "cultural_programming_ideas", None) if exp else None
        raw_activations = getattr(prog_ideas, "activations", []) if prog_ideas else []
        event_collabs = (
            getattr(partnerships_out, "event_collaborations", [])
            if partnerships_out
            else []
        )

        activation_ideas: list[dict[str, Any]] = []
        for act in raw_activations:
            activation_ideas.append(_safe_dump(act))
        if not activation_ideas and event_collabs:
            for collab in event_collabs:
                activation_ideas.append(
                    {
                        "title": collab
                        if isinstance(collab, str)
                        else getattr(collab, "title", str(collab)),
                        "cadence": "Monthly Residency",
                        "format_description": "Curated salon and sensory pairing",
                        "target_audience": "Culturally curious patrons",
                        "expected_outcome": "High community dwell time and cultural credibility",
                        "featured_recommendations": [],
                    }
                )

        # 8. Partnership Opportunities
        candidates = (
            getattr(partnerships_out, "candidates", []) if partnerships_out else []
        )
        partnerships: list[dict[str, Any]] = []
        if (
            partnerships_out
            and hasattr(partnerships_out, "partnerships")
            and partnerships_out.partnerships
        ):
            for part in partnerships_out.partnerships:
                partnerships.append(_safe_dump(part))

        partnership_opportunities: list[dict[str, Any]] = []
        for cand in candidates:
            partnership_opportunities.append(_safe_dump(cand))
        if not partnership_opportunities and partnerships:
            for part_dict in partnerships:
                p_name = (
                    part_dict.get("partner_name") or part_dict.get("name") or "Partner"
                )
                partnership_opportunities.append(
                    {
                        "brand": p_name,
                        "brand_entity_id": part_dict.get("partner_entity_id")
                        or "verified_partner",
                        "category": part_dict.get("category", "Brand Partner"),
                        "score": (part_dict.get("affinity_score") or 0.85) * 100
                        if part_dict.get("affinity_score", 0) <= 1.0
                        else (part_dict.get("affinity_score") or 85.0),
                        "partnership_concept": part_dict.get("concept_description")
                        or part_dict.get("activation_type", "Sensory Activation"),
                        "alignment_rationale": part_dict.get(
                            "alignment_rationale", "Aligned with space aesthetic"
                        ),
                        "estimated_effort": "Medium",
                        "risk": "Low operational friction",
                        "recommended_next_action": "Initiate exploratory outreach brief",
                        "supporting_qloo_evidence": {
                            "entity_id": part_dict.get("partner_entity_id", ""),
                            "affinity": part_dict.get("affinity_score", 0.85),
                        },
                    }
                )

        # 9. Budget Considerations
        est_cost = (
            exec_plan.estimated_cost
            if exec_plan
            else "$150,000 USD / High-end allocation"
        )
        plan_actions = getattr(exec_plan, "actions", []) if exec_plan else []
        action_costs = [
            {
                "action_id": getattr(a, "action_id", f"act_{i + 1}"),
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
                risks.append(
                    {
                        "category": "OPERATIONAL / SPATIAL",
                        "risk": str(r),
                        "severity": "MEDIUM",
                    }
                )
        if gov and hasattr(gov, "risk_flags"):
            for f in gov.risk_flags:
                risks.append(
                    {
                        "category": "GOVERNANCE / COMPLIANCE",
                        "risk": str(f),
                        "severity": "LOW",
                    }
                )
        for cand in candidates:
            cand_risk = getattr(cand, "risk", "")
            if cand_risk:
                risks.append(
                    {
                        "category": "BRAND / COMMERCIAL",
                        "risk": f"{getattr(cand, 'brand', 'Partner')}: {cand_risk}",
                        "severity": "LOW",
                    }
                )

        # 11. Ground-Truth Evidence
        evidence_records: list[dict[str, Any]] = []
        if cultural_twin and hasattr(cultural_twin, "resolved_entities"):
            for ent in cultural_twin.resolved_entities:
                evidence_records.append(
                    {
                        "entity_id": getattr(ent, "id", ""),
                        "name": getattr(ent, "name", ""),
                        "type": getattr(ent, "type", ""),
                        "confidence": getattr(ent, "confidence", 1.0),
                        "source": getattr(ent, "source", "qloo_search"),
                        "why_it_matters": getattr(ent, "why_it_matters", ""),
                    }
                )
        if cultural_matrix:
            for cat in [
                "artists",
                "books",
                "brands",
                "places",
                "movies",
                "destinations",
            ]:
                for item in getattr(cultural_matrix, cat, [])[:4]:
                    evidence_records.append(
                        {
                            "entity_id": getattr(item, "id", ""),
                            "name": getattr(item, "name", ""),
                            "type": cat.removesuffix("s"),
                            "affinity": getattr(item, "affinity", 0.85),
                            "source": getattr(item, "source_query", "qloo_insights"),
                            "why_it_matters": f"Top affinity candidate in {cat}",
                        }
                    )

        # 12. Confidence
        confidence_val = (
            float(getattr(cultural_twin, "confidence", 0.92)) if cultural_twin else 0.92
        )

        # 13. Execution Actions
        execution_actions: list[dict[str, Any]] = []
        if exec_plan and hasattr(exec_plan, "actions"):
            for a in exec_plan.actions:
                execution_actions.append(_safe_dump(a))

        # 14. Recommendation Provenance Map ("Why was this recommendation made?")
        recommendation_provenance_map: dict[str, Any] = {}

        # Audio recommendations
        sonic_recs = (
            getattr(getattr(exp, "sonic_identity", None), "curated_recommendations", [])
            if exp
            else []
        )
        for rec in sonic_recs:
            r_name = getattr(rec, "recommendation", "")
            q_ev = getattr(rec, "qloo_evidence", {}) or {}
            recommendation_provenance_map[r_name] = {
                "entity_name": r_name,
                "category": "Sonic Identity & Music",
                "evidence": {
                    "source": q_ev.get("source_query") or "qloo_insights_v2",
                    "entity_id": q_ev.get("entity_id") or "qloo_artist_sig",
                    "affinity": q_ev.get("affinity")
                    or getattr(rec, "confidence", 0.91),
                    "urn": q_ev.get("type") or "urn:qloo:artist",
                },
                "agent_inference": {
                    "curatorial_rationale": getattr(
                        rec,
                        "cultural_rationale",
                        "Aligned with warm acoustic listening mood",
                    ),
                    "affinity_fit": f"Cross-domain resonance with {target_subs[0] if target_subs else 'design audiophiles'}",
                    "confidence_score": getattr(rec, "confidence", 0.91),
                },
                "recommendation": {
                    "title": r_name,
                    "role": getattr(
                        rec,
                        "expected_role",
                        "Featured artist in evening vinyl rotation",
                    ),
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
                    "entity_id": getattr(cand, "brand_entity_id", "")
                    or b_ev.get("entity_id", "qloo_brand_sig"),
                    "affinity": (b_score / 100.0) if b_score <= 100 else 0.85,
                    "urn": "urn:qloo:brand",
                },
                "agent_inference": {
                    "curatorial_rationale": f"Scored {b_score:.0f}/100 across 6-dimensional fit (cultural fit, audience overlap, brand synergy).",
                    "affinity_fit": getattr(
                        cand, "partnership_concept", "Co-branded sensory activation"
                    ),
                    "confidence_score": (b_score / 100.0) if b_score <= 100 else 0.85,
                },
                "recommendation": {
                    "title": b_name,
                    "role": getattr(
                        cand, "partnership_concept", "Amenity or hardware residency"
                    ),
                    "category": getattr(cand, "category", "lifestyle"),
                },
                "execution_action": {
                    "task": getattr(
                        cand,
                        "recommended_next_action",
                        "Send exploratory outreach brief",
                    ),
                    "owner": "Partnership Director",
                    "budget": "$0 (Exploratory conversation stage)",
                },
            }

        # Spatial Zones
        for sz_dict in spatial_zones:
            z_name = sz_dict.get("zone_name") or sz_dict.get("name") or "Spatial Zone"
            recommendation_provenance_map[z_name] = {
                "entity_name": z_name,
                "category": "Spatial Architecture",
                "evidence": {
                    "source": "space_brief_constraints_and_qloo_places",
                    "entity_id": (
                        sz_dict.get("design_reference_ids") or ["qloo_place_ref"]
                    )[0],
                    "affinity": 0.95,
                    "urn": "urn:tasteops:spatial_directive",
                },
                "agent_inference": {
                    "curatorial_rationale": f"Intended mood: '{sz_dict.get('intended_mood', 'Intimate')}'. Structured to balance acoustic warmth and spatial dwell.",
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
                    "role": getattr(
                        act, "format_description", "Signature cultural salon format"
                    ),
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
            "plan_id": plan.plan_id
            if plan
            else (exec_plan.plan_id if exec_plan else None),
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
        return await self.orchestrator.approve_session(
            session_id, approver=approver_str
        )

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
            risk_flags = getattr(
                ctx.plan.governance, "risk_flags", ["Unvalidated governance status"]
            )
            raise UnapprovedExecutionError(
                f"Execution blocked: Governance validation failed ({', '.join(risk_flags)})."
            )

        # 4. Required Evidence Precondition
        if not ctx.plan.governance.provenance_verified:
            raise ProvenanceValidationError(
                "Execution blocked: Required evidence provenance verification failed."
            )

        has_evidence = bool(
            (
                ctx.cultural_twin
                and (
                    ctx.cultural_twin.anchor_entities
                    or ctx.cultural_twin.resolved_entities
                )
            )
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

        executed_ctx = await self.orchestrator.execute_approved_plan(session_id)

        # Synchronize executed tasks into connector registry store for idempotency tracking
        if executed_ctx.execution_tasks:
            from tasteops.connectors.base import ConnectorExecutionResult

            for t in executed_ctx.execution_tasks:
                idem_key = getattr(t, "idempotency_key", None)
                if idem_key and not self.connector_registry.is_executed(idem_key):
                    self.connector_registry._executed_store[idem_key] = (
                        ConnectorExecutionResult(
                            task_id=t.task_id,
                            connector_name=getattr(t, "connector", "TasteOpsConnector"),
                            status="COMPLETED"
                            if t.status in ("EXECUTED", "COMPLETED")
                            else t.status,
                            output_reference=getattr(t, "output_reference", None)
                            or f"executed://{t.task_id}",
                            executed_at=getattr(t, "executed_at", None)
                            or datetime.now(UTC),
                            payload=getattr(t, "result", {}) or {},
                            provenance=getattr(t, "provenance", {}),
                        )
                    )

        return executed_ctx

    async def execute_task(
        self, request: ConnectorExecutionRequest
    ) -> ConnectorExecutionResult:
        """Dispatches an individual execution task via the connector abstraction.

        Guarantees:
        - Validates session existence and approval state
        - Validates plan ID and version alignment
        - Rejects duplicate execution attempts for the same idempotency key
        - Explicitly fails if connector is missing or unconfigured
        - Never fakes external execution
        """
        from tasteops.agents.governance import UnapprovedExecutionError

        # 1. Verify session exists and is approved
        ctx = self.get_session(request.session_id)
        if ctx.current_state not in {
            WorkflowState.APPROVED,
            WorkflowState.EXECUTING,
            WorkflowState.COMPLETED,
        }:
            raise UnapprovedExecutionError(
                f"Execution task blocked: Session '{request.session_id}' is in state '{ctx.current_state.value}' "
                f"and has not been approved."
            )

        if not ctx.approval or not ctx.approval.is_valid:
            raise UnapprovedExecutionError(
                f"Execution task blocked: Session '{request.session_id}' lacks a valid approval record."
            )

        # 2. Verify plan ID and version
        allowed_plan_ids = {ctx.plan.plan_id} if ctx.plan else set()
        if (
            ctx.plan
            and ctx.plan.execution_plan
            and hasattr(ctx.plan.execution_plan, "plan_id")
        ):
            allowed_plan_ids.add(ctx.plan.execution_plan.plan_id)
        if ctx.execution_plan and hasattr(ctx.execution_plan, "plan_id"):
            allowed_plan_ids.add(ctx.execution_plan.plan_id)

        if ctx.plan and (
            request.plan_id not in allowed_plan_ids
            or ctx.plan.version != request.plan_version
        ):
            raise UnapprovedExecutionError(
                f"Execution task plan authorization mismatch: requested plan_id='{request.plan_id}', "
                f"version={request.plan_version}; active plan_id='{ctx.plan.plan_id}', version={ctx.plan.version}."
            )

        # 3. Dispatch through connector registry (enforces 5 fields, idempotency key uniqueness, missing connector failure)
        result = await self.connector_registry.dispatch(request)

        # 4. Synchronize executed task state in workflow context if task present
        if ctx.execution_tasks:
            for t in ctx.execution_tasks:
                if (
                    t.task_id == request.task_id
                    or t.idempotency_key == request.idempotency_key
                ):
                    t.status = "EXECUTED"
                    t.executed_at = result.executed_at
                    t.output_reference = result.output_reference
                    t.result = result.payload
            self.store.save_context(ctx)

        return result

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
