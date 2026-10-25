"""TasteOps Relational Database Connection & Transaction Manager.

Provides robust SQLite database connections with:
- PRAGMA foreign_keys = ON enforcement
- WAL (Write-Ahead Logging) journal mode for concurrent read/write safety
- Strict atomic transaction boundaries with automated rollback on error
- Thread-safe connection management
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from tasteops.persistence.schema import SCHEMA_DDL

logger = logging.getLogger("tasteops.persistence.database")


class Database:
    """Manages SQLite database lifecycle, schema initialization, and atomic transactions."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        self._lock = threading.RLock()
        self._is_memory = self.db_path == ":memory:"

        # For file-based databases, ensure parent directory exists
        if not self._is_memory:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # Single persistent connection for :memory: databases (so tables persist across transactions)
        # or thread-safe shared connection
        self._conn: sqlite3.Connection | None = None
        self._init_connection()
        self.init_schema()

    def _init_connection(self) -> None:
        """Initializes connection with required pragmas."""
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            isolation_level=None,  # Autocommit mode by default; manual transactions via BEGIN/COMMIT
        )
        conn.row_factory = sqlite3.Row
        # Enforce foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON;")
        if not self._is_memory:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
        self._conn = conn

    def get_connection(self) -> sqlite3.Connection:
        """Returns the active connection, reconnecting if needed."""
        with self._lock:
            if self._conn is None:
                self._init_connection()
            return self._conn  # type: ignore[return-value]

    def init_schema(self) -> None:
        """Initializes all relational tables and indexes."""
        with self._lock:
            conn = self.get_connection()
            conn.executescript(SCHEMA_DDL)
            logger.info(
                "Initialized TasteOps relational database schema (%s)", self.db_path
            )

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Cursor]:
        """Provides an atomic transaction boundary with automated rollback on error."""
        with self._lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE;")
            try:
                yield cursor
                cursor.execute("COMMIT;")
            except Exception as exc:
                cursor.execute("ROLLBACK;")
                logger.error("Transaction rolled back due to error: %s", exc)
                raise
            finally:
                cursor.close()

    def close(self) -> None:
        """Closes the underlying database connection."""
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None
