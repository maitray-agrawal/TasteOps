"""TasteOps Application-Facing Orchestrator Service.

Provides a unified, minimal facade for FastAPI and frontend integration:
- create_session()
- run_until_approval()
- approve_session()
- reject_session()
- execute_approved_plan()
- get_session_state()
- get_audit_events()

Encapsulates all internal agent orchestration, deterministic state machine transitions,
cryptographic approval binding, and idempotency guarantees.
"""

from __future__ import annotations

import logging
from typing import Any

from tasteops.agents.mcp_adapter import CulturalIntelligenceMCPAdapter
from tasteops.workflows.context import WorkflowContext
from tasteops.workflows.engine import WorkflowEngine
from tasteops.workflows.persistence import (
    AuditEvent,
    BaseStateStore,
    InMemoryStateStore,
)
from tasteops.workflows.states import WorkflowState

logger = logging.getLogger("tasteops.workflows.orchestrator")


class TasteOpsOrchestrator:
    """Application-facing orchestration service coordinating agents and state machine."""

    def __init__(
        self,
        engine: WorkflowEngine | None = None,
        store: BaseStateStore | None = None,
        mcp_adapter: CulturalIntelligenceMCPAdapter | None = None,
        connector_registry: Any | None = None,
    ) -> None:
        from tasteops.connectors import ConnectorRegistry, create_default_registry

        self.store = store or InMemoryStateStore()
        self.connector_registry: ConnectorRegistry = connector_registry or (
            getattr(engine, "connector_registry", None) or create_default_registry()
        )
        self.engine = engine or WorkflowEngine(
            mcp_adapter=mcp_adapter,
            store=self.store,
            connector_registry=self.connector_registry,
        )
        if (
            engine is not None
            and hasattr(self.engine, "connector_registry")
            and connector_registry is not None
        ):
            self.engine.connector_registry = connector_registry
        self._active_sessions: dict[str, WorkflowContext] = {}

    def _resolve_context(
        self, session_id_or_ctx: str | WorkflowContext
    ) -> WorkflowContext:
        """Resolves session context from active memory or persistent state store."""
        if isinstance(session_id_or_ctx, WorkflowContext):
            self._active_sessions[session_id_or_ctx.session_id] = session_id_or_ctx
            return session_id_or_ctx

        session_id = str(session_id_or_ctx)
        if session_id in self._active_sessions:
            return self._active_sessions[session_id]

        loaded = self.engine.store.load_context(session_id)
        if loaded is not None:
            self._active_sessions[session_id] = loaded
            return loaded

        raise KeyError(
            f"Workflow session '{session_id}' not found in active cache or state store."
        )

    def create_session(
        self,
        user_input: str,
        space_id: str | None = None,
        hints: dict[str, Any] | None = None,
    ) -> WorkflowContext:
        """Initializes a new physical space cultural activation workflow session."""
        ctx = self.engine.initialize_session(
            raw_intent=user_input,
            parsed_hints=hints,
            space_id=space_id,
        )
        self._active_sessions[ctx.session_id] = ctx
        logger.info(
            "Created orchestration session %s (space: %s)",
            ctx.session_id,
            space_id,
        )
        return ctx

    async def run_until_approval(
        self,
        session_id: str | WorkflowContext,
        hints: dict[str, Any] | None = None,
        take_per_category: int = 10,
    ) -> WorkflowContext:
        """Drives the workflow pipeline forward until the Human Approval Gate is reached."""
        ctx = self._resolve_context(session_id)

        if ctx.current_state == WorkflowState.CREATED:
            await self.engine.parse_intent(ctx, parsed_data=hints)
            if ctx.current_state == WorkflowState.FAILED:
                return ctx

        if ctx.current_state == WorkflowState.INTENT_PARSED:
            await self.engine.create_cultural_twin(ctx)
            if ctx.current_state == WorkflowState.FAILED:
                return ctx

        if ctx.current_state == WorkflowState.CULTURAL_TWIN_CREATED:
            await self.engine.resolve_qloo_anchors(ctx)
            if ctx.current_state == WorkflowState.FAILED:
                return ctx

        if ctx.current_state == WorkflowState.QLOO_RESOLVED:
            await self.engine.fetch_cultural_matrix(
                ctx, take_per_category=take_per_category
            )
            if ctx.current_state == WorkflowState.FAILED:
                return ctx

        if ctx.current_state == WorkflowState.CULTURAL_MATRIX_READY:
            await self.engine.run_agents_and_generate_plan(ctx)
            if ctx.current_state == WorkflowState.FAILED:
                return ctx

        while (
            ctx.current_state == WorkflowState.PLAN_GENERATED
            and ctx.validation_cycle_count <= self.engine.max_validation_cycles
        ):
            await self.engine.validate_and_await_approval(ctx)
            if ctx.current_state in {
                WorkflowState.AWAITING_APPROVAL,
                WorkflowState.FAILED,
            }:
                break

        return ctx

    async def approve_session(
        self,
        session_id: str | WorkflowContext,
        approver: str = "human_curator",
    ) -> WorkflowContext:
        """Records human curator approval with cryptographic plan hash binding."""
        ctx = self._resolve_context(session_id)
        await self.engine.approve_plan(ctx, approver=approver)
        return ctx

    async def reject_session(
        self,
        session_id: str | WorkflowContext,
        reason: str = "Curator rejected plan",
    ) -> WorkflowContext:
        """Transitions workflow to FAILED following curator rejection and invalidates approvals."""
        ctx = self._resolve_context(session_id)
        await self.engine.reject_plan(ctx, reason=reason)
        return ctx

    async def execute_approved_plan(
        self,
        session_id: str | WorkflowContext,
    ) -> WorkflowContext:
        """Dispatches verified execution tasks with idempotency and provenance enforcement."""
        ctx = self._resolve_context(session_id)
        await self.engine.execute_plan(ctx)
        return ctx

    def get_session_state(self, session_id: str | WorkflowContext) -> WorkflowContext:
        """Retrieves the full typed context for a given session."""
        return self._resolve_context(session_id)

    def get_audit_events(self, session_id: str) -> list[AuditEvent]:
        """Retrieves all persisted audit log events for a given session."""
        events = self.engine.store.get_audit_events(session_id)
        if not events and session_id in self._active_sessions:
            return self._active_sessions[session_id].audit_events
        return events
