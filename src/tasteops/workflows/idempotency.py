"""Durable and Atomic Task Idempotency Store.

Provides cross-process task reservations and durable outcome persistence for
multi-worker deployments (e.g. uvicorn --workers 2) using atomic filesystem operations.

Guarantees:
1. Atomic reservation via exclusive file creation (O_CREAT | O_EXCL) prevents
   concurrent workers from dispatching duplicate external calls.
2. Immediate outcome persistence closes the crash window between provider success
   and session-level context persistence.
3. Fail-safe behavior across worker boundaries.

Deployment Boundary Note:
Multi-process single-host deployments are safely protected via shared-disk filesystem
locking. On multi-container or distributed multi-host deployments without a shared
persistent store (such as Redis or PostgreSQL), distributed exactly-once execution
cannot be claimed; systems must rely on provider-side idempotency keys and fail safely.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import time
from pathlib import Path

from tasteops.workflows.schemas import ExecutionTask

logger = logging.getLogger("tasteops.workflows.idempotency")

SAFE_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")


class DurableIdempotencyStore:
    """Filesystem-backed atomic reservation and durable task outcome store."""

    def __init__(self, base_dir: Path | str | None = None) -> None:
        if base_dir is None:
            storage_root = (
                os.getenv("TASTEOPS_STORAGE_DIR")
                or os.getenv("TASTEOPS_STORAGE_PATH")
                or os.getenv("STORAGE_DIR")
                or "storage/workflows"
            )
            self.base_dir = Path(storage_root) / ".idempotency"
        else:
            self.base_dir = Path(base_dir)

        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.warning(
                "Could not create idempotency store directory %s: %s",
                self.base_dir,
                exc,
            )

    def _sanitize_key(self, idempotency_key: str) -> str:
        """Sanitizes idempotency key to prevent path traversal."""
        cleaned = re.sub(r"[^a-zA-Z0-9_\-]", "_", idempotency_key)
        return cleaned[:128]

    def _get_outcome_path(self, sanitized_key: str) -> Path:
        return self.base_dir / f"{sanitized_key}.json"

    def _get_lock_path(self, sanitized_key: str) -> Path:
        return self.base_dir / f"{sanitized_key}.lock"

    def get_outcome(self, idempotency_key: str) -> ExecutionTask | None:
        """Retrieves a previously completed or staged execution task if it exists."""
        if not idempotency_key:
            return None

        sanitized = self._sanitize_key(idempotency_key)
        path = self._get_outcome_path(sanitized)
        if not path.exists():
            return None

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return ExecutionTask.model_validate(data)
        except Exception as exc:
            logger.error("Error reading durable idempotency record %s: %s", path, exc)
            return None

    def reserve(
        self,
        idempotency_key: str,
        worker_id: str | None = None,
        stale_timeout_sec: float = 60.0,
    ) -> bool:
        """Atomically acquires an execution reservation for idempotency_key.

        Returns:
            True if reservation was acquired; False if already completed or actively in-flight.
        """
        if not idempotency_key:
            return True

        sanitized = self._sanitize_key(idempotency_key)
        outcome_path = self._get_outcome_path(sanitized)
        if outcome_path.exists():
            return False

        lock_path = self._get_lock_path(sanitized)
        worker_ident = worker_id or f"worker_pid_{os.getpid()}"

        try:
            # Atomic file creation using OS-level exclusive creation flag
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "worker_id": worker_ident,
                        "timestamp": time.time(),
                        "idempotency_key": idempotency_key,
                        "status": "IN_PROGRESS",
                    },
                    f,
                )
            return True
        except FileExistsError:
            # Check if lock is stale (e.g. previous worker crashed mid-flight)
            try:
                mtime = lock_path.stat().st_mtime
                if time.time() - mtime > stale_timeout_sec:
                    logger.warning(
                        "Found stale execution reservation lock for '%s' (stale > %ss). Breaking lock.",
                        idempotency_key,
                        stale_timeout_sec,
                    )
                    lock_path.unlink(missing_ok=True)
                    # Retry once
                    fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        json.dump(
                            {
                                "worker_id": worker_ident,
                                "timestamp": time.time(),
                                "idempotency_key": idempotency_key,
                                "status": "IN_PROGRESS",
                            },
                            f,
                        )
                    return True
            except Exception as exc:
                logger.debug("Failed breaking stale lock: %s", exc)
            return False
        except Exception as exc:
            logger.warning(
                "Error acquiring atomic reservation lock for %s: %s",
                idempotency_key,
                exc,
            )
            return False

    async def async_reserve_or_wait(
        self,
        idempotency_key: str,
        timeout_sec: float = 5.0,
        worker_id: str | None = None,
    ) -> tuple[bool, ExecutionTask | None]:
        """Atomically reserves key or awaits outcome if concurrently in flight.

        Returns:
            (True, None) if this caller acquired the reservation lock and should execute.
            (False, task) if the outcome is already available (or completed while waiting).

        Raises:
            TimeoutError: if reservation remains locked by another worker and no outcome is produced within timeout_sec.
        """
        import asyncio

        outcome = self.get_outcome(idempotency_key)
        if outcome is not None:
            return (False, outcome)

        if self.reserve(idempotency_key, worker_id=worker_id):
            return (True, None)

        # Concurrently in flight by another worker: await outcome
        start_time = time.time()
        while time.time() - start_time < timeout_sec:
            await asyncio.sleep(0.05)
            outcome = self.get_outcome(idempotency_key)
            if outcome is not None:
                return (False, outcome)

        raise TimeoutError(
            f"Execution reservation for '{idempotency_key}' timed out waiting for concurrent worker outcome."
        )

    def save_outcome(self, idempotency_key: str, task: ExecutionTask) -> None:
        """Atomically persists task outcome and releases any in-flight reservation lock."""
        if not idempotency_key:
            return

        sanitized = self._sanitize_key(idempotency_key)
        outcome_path = self._get_outcome_path(sanitized)
        lock_path = self._get_lock_path(sanitized)

        try:
            # Write via atomic rename to ensure readers never see partial content
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=str(self.base_dir),
                delete=False,
                encoding="utf-8",
                suffix=".tmp",
            ) as tmp:
                tmp.write(task.model_dump_json(indent=2))
                tmp_name = tmp.name

            os.replace(tmp_name, str(outcome_path))
        except Exception as exc:
            logger.error(
                "Failed to persist durable idempotency outcome for %s: %s",
                idempotency_key,
                exc,
            )
        finally:
            try:
                lock_path.unlink(missing_ok=True)
            except Exception as exc:
                logger.debug("Failed cleaning up lock %s: %s", lock_path, exc)

    def release_reservation(self, idempotency_key: str) -> None:
        """Releases an in-flight reservation lock if task failed without an outcome."""
        if not idempotency_key:
            return

        sanitized = self._sanitize_key(idempotency_key)
        lock_path = self._get_lock_path(sanitized)
        try:
            lock_path.unlink(missing_ok=True)
        except Exception as exc:
            logger.debug("Failed releasing reservation lock %s: %s", lock_path, exc)
