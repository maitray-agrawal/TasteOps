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

        # Extract spatial zones
        spatial_zones: list[dict[str, Any]] = []
        if exp and hasattr(exp, "spatial_zones") and exp.spatial_zones:
            for zone in exp.spatial_zones:
                spatial_zones.append(
                    zone.model_dump() if hasattr(zone, "model_dump") else dict(zone)
                )

        # Extract soundscape design
        soundscape: dict[str, Any] | None = None
        if exp and hasattr(exp, "sonic_identity") and exp.sonic_identity:
            soundscape = (
                exp.sonic_identity.model_dump()
                if hasattr(exp.sonic_identity, "model_dump")
                else dict(exp.sonic_identity)
            )
        elif exp and hasattr(exp, "soundscape_design") and exp.soundscape_design:
            soundscape = (
                exp.soundscape_design.model_dump()
                if hasattr(exp.soundscape_design, "model_dump")
                else dict(exp.soundscape_design)
            )

        # Extract lighting design
        lighting: dict[str, Any] | None = None
        if exp and hasattr(exp, "atmosphere_guidelines") and exp.atmosphere_guidelines:
            lighting = (
                exp.atmosphere_guidelines.model_dump()
                if hasattr(exp.atmosphere_guidelines, "model_dump")
                else dict(exp.atmosphere_guidelines)
            )
        elif exp and hasattr(exp, "lighting_design") and exp.lighting_design:
            lighting = (
                exp.lighting_design.model_dump()
                if hasattr(exp.lighting_design, "model_dump")
                else dict(exp.lighting_design)
            )

        # Extract cultural pillars
        pillars: list[dict[str, Any]] = []
        if strategy and hasattr(strategy, "cultural_pillars") and strategy.cultural_pillars:
            for p in strategy.cultural_pillars:
                pillars.append(p.model_dump() if hasattr(p, "model_dump") else dict(p))

        # Extract partnerships
        partnerships: list[dict[str, Any]] = []
        if partnerships_out and hasattr(partnerships_out, "partnerships") and partnerships_out.partnerships:
            for part in partnerships_out.partnerships:
                partnerships.append(
                    part.model_dump() if hasattr(part, "model_dump") else dict(part)
                )

        # Extract programming calendar
        programming: list[dict[str, Any]] = []
        if exp and hasattr(exp, "cultural_programming_ideas") and exp.cultural_programming_ideas:
            prog_data = (
                exp.cultural_programming_ideas.model_dump()
                if hasattr(exp.cultural_programming_ideas, "model_dump")
                else dict(exp.cultural_programming_ideas)
            )
            programming = prog_data.get("signature_events", []) or [prog_data]

        plan_hash = None
        if exec_plan and hasattr(exec_plan, "plan_hash") and exec_plan.plan_hash:
            plan_hash = exec_plan.plan_hash
        elif plan:
            plan_hash = plan.compute_hash()

        return {
            "session_id": ctx.session_id,
            "space_id": ctx.space_id,
            "state": ctx.current_state.value,
            "plan_id": plan.plan_id if plan else (exec_plan.plan_id if exec_plan else None),
            "plan_hash": plan_hash,
            "estimated_cost": exec_plan.estimated_cost if exec_plan else None,
            "experience_narrative": (
                strategy.positioning_statement if strategy else None
            ),
            "spatial_zones": spatial_zones,
            "soundscape_design": soundscape,
            "lighting_design": lighting,
            "cultural_pillars": pillars,
            "partnerships": partnerships,
            "programming_calendar": programming,
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
        """Dispatches verified execution tasks with idempotency guarantees."""
        ctx = self.get_session(session_id)
        if ctx.current_state != WorkflowState.APPROVED:
            from tasteops.agents.governance import UnapprovedExecutionError

            raise UnapprovedExecutionError(
                f"Cannot execute session '{session_id}' in state '{ctx.current_state.value}'. "
                f"Session must be explicitly approved by a human curator first."
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
