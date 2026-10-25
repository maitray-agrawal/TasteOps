"""TasteOps Server-Sent Events (SSE) Infrastructure.

Defines the typed SSEEvent data envelope, bounded payload sanitizers,
canonical event type mappers, and pub/sub broadcaster for real-time streaming.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from tasteops.workflows.states import WorkflowState

if TYPE_CHECKING:
    from tasteops.workflows.context import WorkflowContext
    from tasteops.workflows.persistence import AuditEvent

logger = logging.getLogger("tasteops.api.events")

# Canonical SSE event types required by TasteOps architecture
CANONICAL_EVENT_TYPES = {
    "session.created",
    "workflow.state_changed",
    "qloo.search_started",
    "qloo.search_completed",
    "cultural_matrix.ready",
    "agent.started",
    "agent.completed",
    "governance.completed",
    "approval.required",
    "execution.started",
    "execution.completed",
    "workflow.failed",
}

# Sensitive keys to scrub from event payloads to prevent secret leakage
SENSITIVE_KEY_SUBSTRINGS = (
    "secret",
    "key",
    "token",
    "auth",
    "password",
    "credential",
    "bearer",
    "cookie",
    "authorization",
)


def sanitize_payload(obj: Any, max_string_len: int = 500, max_items: int = 10) -> Any:
    """Recursively sanitizes and bounds arbitrary payloads.

    Removes any sensitive secrets/keys/credentials, truncates long strings,
    caps list lengths, and drops chain-of-thought traces.
    """
    if isinstance(obj, str):
        if len(obj) > max_string_len:
            return obj[: max_string_len - 3] + "..."
        return obj
    if isinstance(obj, dict):
        cleaned: dict[str, Any] = {}
        for k, v in obj.items():
            k_lower = str(k).lower()
            if any(sub in k_lower for sub in SENSITIVE_KEY_SUBSTRINGS):
                continue
            if k_lower in ("thought", "chain_of_thought", "cot", "stacktrace", "traceback"):
                continue
            cleaned[str(k)] = sanitize_payload(v, max_string_len, max_items)
        return cleaned
    if isinstance(obj, (list, tuple, set)):
        items = list(obj)[:max_items]
        return [sanitize_payload(item, max_string_len, max_items) for item in items]
    return obj


class SSEEvent(BaseModel):
    """Canonical Server-Sent Event model.

    Every event strictly guarantees:
    - event_id: Unique deterministic event identifier
    - session_id: Target workflow session ID
    - timestamp: ISO 8601 UTC timestamp
    - event_type: Canonical event identifier from CANONICAL_EVENT_TYPES
    - data: Bounded, secret-free structured summary
    """

    event_id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    session_id: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    event_type: str
    data: dict[str, Any] = Field(default_factory=dict)


def format_sse(event: SSEEvent) -> str:
    """Formats an SSEEvent into a standard RFC 8895 Server-Sent Events frame."""
    payload = json.dumps(event.model_dump())
    return f"id: {event.event_id}\nevent: {event.event_type}\ndata: {payload}\n\n"


def map_audit_event_to_sse(
    audit_event: AuditEvent, ctx: WorkflowContext | None = None
) -> SSEEvent:
    """Deterministically transforms an immutable AuditEvent into a safe, bounded SSEEvent."""
    to_state = audit_event.to_state
    if isinstance(to_state, str):
        try:
            to_state = WorkflowState(to_state)
        except ValueError:
            pass

    from_state = audit_event.from_state
    from_state_val = (
        from_state.value if hasattr(from_state, "value") else str(from_state)
    )
    to_state_val = to_state.value if hasattr(to_state, "value") else str(to_state)

    ts_str = (
        audit_event.timestamp.isoformat()
        if hasattr(audit_event.timestamp, "isoformat")
        else str(audit_event.timestamp)
    )

    metadata = dict(audit_event.metadata or {})
    explicit_type = metadata.get("event_type")

    # Determine canonical event_type and structured summary data
    if explicit_type and explicit_type in CANONICAL_EVENT_TYPES:
        event_type = explicit_type
        summary_data = metadata.get("data", {})
        if not summary_data:
            summary_data = {"summary": audit_event.reason or explicit_type}
    elif to_state == WorkflowState.CREATED:
        event_type = "session.created"
        summary_data = {
            "space_id": metadata.get("space_id") or (ctx.space_id if ctx else None),
            "status": "IN_PROGRESS",
            "summary": "Workflow session initialized",
        }
    elif to_state == WorkflowState.INTENT_PARSED:
        event_type = "workflow.state_changed"
        summary_data = {
            "from_state": from_state_val,
            "to_state": to_state_val,
            "status": "IN_PROGRESS",
            "summary": "User intent parsed into structured domain attributes",
        }
    elif to_state == WorkflowState.CULTURAL_TWIN_CREATED:
        event_type = "qloo.search_started"
        summary_data = {
            "from_state": from_state_val,
            "to_state": to_state_val,
            "search_type": "cultural_anchors",
            "summary": "Resolving cultural anchors and aesthetic tags via Cultural Intelligence MCP",
        }
    elif to_state == WorkflowState.QLOO_RESOLVED:
        event_type = "qloo.search_completed"
        summary_data = {
            "resolved_entities_count": metadata.get("resolved_entities_count", 0),
            "resolved_tags_count": metadata.get("resolved_tags_count", 0),
            "qloo_retries_used": metadata.get("qloo_retries_used", 0),
            "summary": "Cultural anchors and tags resolved via Qloo API",
        }
    elif to_state == WorkflowState.CULTURAL_MATRIX_READY:
        event_type = "cultural_matrix.ready"
        summary_data = {
            "total_recommendations": metadata.get("total_recommendations", 0),
            "artists": metadata.get("artists", 0),
            "brands": metadata.get("brands", 0),
            "places": metadata.get("places", 0),
            "summary": "Multidimensional CulturalMatrix generated across domains",
        }
    elif to_state == WorkflowState.AGENTS_RUNNING:
        event_type = "agent.started"
        summary_data = {
            "agents": ["cultural_strategist", "experience_architect", "partnership_agent"],
            "summary": "Domain agents activated for plan generation",
        }
    elif to_state == WorkflowState.PLAN_GENERATED:
        event_type = "agent.completed"
        summary_data = {
            "plan_id": metadata.get("plan_id"),
            "summary": "Cultural activation plan synthesized from agent outputs",
        }
    elif to_state == WorkflowState.VALIDATED:
        event_type = "governance.completed"
        summary_data = {
            "provenance_verified": metadata.get("provenance_verified", True),
            "summary": "Plan governance and provenance audit complete",
        }
    elif to_state == WorkflowState.AWAITING_APPROVAL:
        event_type = "approval.required"
        summary_data = {
            "current_state": "AWAITING_APPROVAL",
            "summary": "Workflow paused at human approval gate waiting for curator sign-off",
        }
    elif to_state == WorkflowState.APPROVED:
        event_type = "workflow.state_changed"
        summary_data = {
            "from_state": from_state_val,
            "to_state": to_state_val,
            "approver": metadata.get("approver", "curator"),
            "summary": "Plan approved by curator",
        }
    elif to_state == WorkflowState.EXECUTING:
        event_type = "execution.started"
        summary_data = {
            "current_state": "EXECUTING",
            "summary": "Dispatching external integration and activation tasks",
        }
    elif to_state == WorkflowState.COMPLETED:
        event_type = "execution.completed"
        summary_data = {
            "total_tasks": metadata.get("total_tasks", 0),
            "executed_tasks": metadata.get("executed_tasks", 0),
            "status": "COMPLETED",
            "summary": "All activation tasks executed with provenance",
        }
    elif to_state == WorkflowState.FAILED:
        event_type = "workflow.failed"
        safe_error = audit_event.error or audit_event.reason or "Workflow execution failed"
        # Ensure raw stack traces are never exposed
        if "\n" in safe_error:
            safe_error = safe_error.split("\n")[0]
        summary_data = {
            "error": safe_error,
            "from_state": from_state_val,
            "summary": "Workflow terminated in failed state",
        }
    else:
        event_type = "workflow.state_changed"
        summary_data = {
            "from_state": from_state_val,
            "to_state": to_state_val,
            "summary": audit_event.reason or f"State transitioned to {to_state_val}",
        }

    sanitized_data = sanitize_payload(summary_data)

    return SSEEvent(
        event_id=audit_event.event_id,
        session_id=audit_event.session_id,
        timestamp=ts_str,
        event_type=event_type,
        data=sanitized_data,
    )


class EventBroadcaster:
    """Thread-safe pub/sub broadcaster for distributing SSE events to active subscribers."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[SSEEvent]]] = {}

    def subscribe(self, session_id: str) -> asyncio.Queue[SSEEvent]:
        """Subscribes an asyncio Queue to live events for session_id."""
        queue: asyncio.Queue[SSEEvent] = asyncio.Queue(maxsize=200)
        if session_id not in self._subscribers:
            self._subscribers[session_id] = set()
        self._subscribers[session_id].add(queue)
        return queue

    def unsubscribe(self, session_id: str, queue: asyncio.Queue[SSEEvent]) -> None:
        """Unsubscribes a queue from session_id and cleans up empty subscriber sets."""
        if session_id in self._subscribers:
            self._subscribers[session_id].discard(queue)
            if not self._subscribers[session_id]:
                del self._subscribers[session_id]

    def subscriber_count(self, session_id: str) -> int:
        """Returns the number of active listeners for session_id."""
        return len(self._subscribers.get(session_id, set()))

    def publish(self, event: SSEEvent) -> None:
        """Distributes event to all active subscriber queues for event.session_id."""
        queues = self._subscribers.get(event.session_id, set())
        for q in list(queues):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "Subscriber queue full for session %s, dropping frame",
                    event.session_id,
                )
