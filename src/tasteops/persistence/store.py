"""TasteOps SQLite State Store Implementation.

Implements BaseStateStore interface using the relational Database and SQLiteSessionRepository.
Enables plug-and-play transactional database persistence for WorkflowEngine and TasteOpsOrchestrator.
"""

from __future__ import annotations

import logging
from pathlib import Path

from tasteops.persistence.database import Database
from tasteops.persistence.session_repository import SQLiteSessionRepository
from tasteops.workflows.context import WorkflowContext
from tasteops.workflows.persistence import AuditEvent, BaseStateStore

logger = logging.getLogger("tasteops.persistence.store")


class SQLiteStateStore(BaseStateStore):
    """ACID-compliant SQLite relational state store for TasteOps workflows."""

    def __init__(self, db_or_path: Database | str | Path = ":memory:") -> None:
        super().__init__()
        if isinstance(db_or_path, Database):
            self.db = db_or_path
        else:
            self.db = Database(db_or_path)
        self.repo = SQLiteSessionRepository(self.db)

    def save_transition(self, event: AuditEvent, ctx: WorkflowContext) -> None:
        """Atomically persists state transition, audit event, and full session artifacts."""
        if event not in ctx.audit_events:
            ctx.audit_events.append(event)
        self.repo.save_session(ctx)
        self.repo.save_audit_event(event)
        self._notify_listeners(event, ctx)

    def save_context(self, ctx: WorkflowContext) -> None:
        """Persists full session state snapshot across normalized tables."""
        self.repo.save_session(ctx)

    def load_context(self, session_id: str) -> WorkflowContext | None:
        """Loads and reconstructs typed WorkflowContext from the database."""
        return self.repo.load_session(session_id)

    def get_audit_events(self, session_id: str) -> list[AuditEvent]:
        """Retrieves ordered audit log events from the audit ledger table."""
        return self.repo.get_audit_events(session_id)
