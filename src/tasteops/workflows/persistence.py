"""TasteOps State Persistence & Audit Event Logging.

Persists workflow transitions, execution snapshots, and immutable audit events.
Guarantees every state change is recorded and auditable.
"""

from __future__ import annotations

import json
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from tasteops.workflows.states import WorkflowState

if TYPE_CHECKING:
    from tasteops.workflows.context import WorkflowContext

logger = logging.getLogger("tasteops.workflows.persistence")


class AuditEvent(BaseModel):
    """Immutable audit record for every workflow state transition and event."""

    event_id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    session_id: str
    from_state: WorkflowState
    to_state: WorkflowState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reason: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class BaseStateStore(ABC):
    """Abstract storage interface for persisting workflow context and audit events."""

    @abstractmethod
    def save_transition(self, event: AuditEvent, ctx: WorkflowContext) -> None:
        """Persists a single state transition and its accompanying audit event."""

    @abstractmethod
    def save_context(self, ctx: WorkflowContext) -> None:
        """Persists a full snapshot of the workflow context."""

    @abstractmethod
    def load_context(self, session_id: str) -> WorkflowContext | None:
        """Loads a workflow context by session_id."""

    @abstractmethod
    def get_audit_events(self, session_id: str) -> list[AuditEvent]:
        """Retrieves all persisted audit events for a session."""


class InMemoryStateStore(BaseStateStore):
    """In-memory state store for tests and fast ephemeral execution."""

    def __init__(self) -> None:
        self._contexts: dict[str, Any] = {}
        self._events: dict[str, list[AuditEvent]] = {}

    def save_transition(self, event: AuditEvent, ctx: WorkflowContext) -> None:
        if ctx.session_id not in self._events:
            self._events[ctx.session_id] = []
        self._events[ctx.session_id].append(event)
        self.save_context(ctx)

    def save_context(self, ctx: WorkflowContext) -> None:
        self._contexts[ctx.session_id] = ctx.model_copy(deep=True)

    def load_context(self, session_id: str) -> WorkflowContext | None:
        return self._contexts.get(session_id)

    def get_audit_events(self, session_id: str) -> list[AuditEvent]:
        return list(self._events.get(session_id, []))


class FileStateStore(BaseStateStore):
    """Persistent filesystem store writing JSON snapshots and audit event logs."""

    def __init__(self, base_dir: Path | str = "storage/workflows") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._in_memory_fallback = InMemoryStateStore()

    def _get_session_dir(self, session_id: str) -> Path:
        session_dir = self.base_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir

    def save_transition(self, event: AuditEvent, ctx: WorkflowContext) -> None:
        self._in_memory_fallback.save_transition(event, ctx)
        try:
            s_dir = self._get_session_dir(ctx.session_id)
            events_file = s_dir / "audit_events.jsonl"
            with open(events_file, "a", encoding="utf-8") as f:
                f.write(event.model_dump_json() + "\n")

            self.save_context(ctx)
        except Exception as exc:
            logger.warning(
                "Failed to persist state to disk for session %s: %s",
                ctx.session_id,
                exc,
            )

    def save_context(self, ctx: WorkflowContext) -> None:
        self._in_memory_fallback.save_context(ctx)
        try:
            s_dir = self._get_session_dir(ctx.session_id)
            state_file = s_dir / "workflow_state.json"
            with open(state_file, "w", encoding="utf-8") as f:
                f.write(ctx.model_dump_json(indent=2))
        except Exception as exc:
            logger.warning(
                "Failed to write workflow snapshot for session %s: %s",
                ctx.session_id,
                exc,
            )

    def load_context(self, session_id: str) -> WorkflowContext | None:
        # Check in-memory first
        in_mem = self._in_memory_fallback.load_context(session_id)
        if in_mem:
            return in_mem

        state_file = self.base_dir / session_id / "workflow_state.json"
        if not state_file.exists():
            return None

        try:
            from tasteops.workflows.context import WorkflowContext

            with open(state_file, encoding="utf-8") as f:
                data = json.load(f)
            return WorkflowContext.model_validate(data)
        except Exception as exc:
            logger.error("Error loading workflow context from %s: %s", state_file, exc)
            return None

    def get_audit_events(self, session_id: str) -> list[AuditEvent]:
        events = self._in_memory_fallback.get_audit_events(session_id)
        if events:
            return events

        events_file = self.base_dir / session_id / "audit_events.jsonl"
        if not events_file.exists():
            return []

        loaded: list[AuditEvent] = []
        try:
            with open(events_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        loaded.append(AuditEvent.model_validate_json(line))
        except Exception as exc:
            logger.error("Error loading audit events from %s: %s", events_file, exc)
        return loaded
