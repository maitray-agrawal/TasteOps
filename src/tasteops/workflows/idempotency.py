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


class StorageUnavailableError(RuntimeError):
    """Raised when atomic execution reservations or durable records cannot be accessed due to storage unavailability."""


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
            raw = storage_root.strip().strip("'\"")
            p = Path(raw)
            if not p.is_absolute():
                if Path("/app").is_dir():
                    p = Path("/app") / p
                else:
                    p = Path.cwd() / p
            self.base_dir = (p / ".idempotency").resolve()
        else:
            raw = str(base_dir).strip().strip("'\"")
            self.base_dir = Path(raw).resolve()

        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.warning(
                "Could not create idempotency store directory %s: %s",
                self.base_dir,
                exc,
            )

    def check_storage_ready(self) -> None:
        """Verifies that the idempotency storage directory exists and is writable."""
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            probe_file = (
                self.base_dir / f".probe_check_{os.getpid()}_{time.time_ns()}.tmp"
            )
            probe_file.write_text("probe", encoding="utf-8")
            probe_file.unlink(missing_ok=True)
        except (PermissionError, FileNotFoundError, OSError) as exc:
            logger.error(
                "Execution storage is unavailable at '%s': %s", self.base_dir, exc
            )
            raise StorageUnavailableError(
                f"Execution storage is unavailable at '{self.base_dir}': {exc}"
            ) from exc

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
        try:
            if not path.exists():
                return None
        except (PermissionError, OSError) as exc:
            raise StorageUnavailableError(
                f"Cannot inspect idempotency outcome at '{path}': {exc}"
            ) from exc

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return ExecutionTask.model_validate(data)
        except (PermissionError, OSError) as exc:
            raise StorageUnavailableError(
                f"Cannot read idempotency outcome at '{path}': {exc}"
            ) from exc
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

        Raises:
            StorageUnavailableError: if the storage directory cannot be accessed, written, or created.
        """
        if not idempotency_key:
            return True

        # Ensure base directory exists
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError) as exc:
            logger.error(
                "Cannot access idempotency directory '%s': %s",
                self.base_dir,
                exc,
            )
            raise StorageUnavailableError(
                f"Idempotency storage unavailable at '{self.base_dir}': {exc}"
            ) from exc

        sanitized = self._sanitize_key(idempotency_key)
        outcome_path = self._get_outcome_path(sanitized)
        try:
            if outcome_path.exists():
                return False
        except (PermissionError, OSError) as exc:
            raise StorageUnavailableError(
                f"Cannot inspect outcome path '{outcome_path}': {exc}"
            ) from exc

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
            except FileExistsError:
                return False
            except FileNotFoundError:
                # Concurrency race: previous worker finished and unlinked the lock
                # before or during stat(). Do NOT raise StorageUnavailableError.
                try:
                    if outcome_path.exists():
                        return False
                except (PermissionError, OSError) as exc:
                    raise StorageUnavailableError(
                        f"Cannot inspect outcome path '{outcome_path}': {exc}"
                    ) from exc
                return False
            except (PermissionError, OSError) as exc:
                raise StorageUnavailableError(
                    f"Error managing reservation lock file '{lock_path}': {exc}"
                ) from exc
            except Exception as exc:
                logger.debug("Failed breaking stale lock: %s", exc)
                return False
            return False
        except (PermissionError, FileNotFoundError, OSError) as exc:
            logger.error(
                "Storage failure while acquiring reservation lock for '%s' at %s: %s",
                idempotency_key,
                lock_path,
                exc,
            )
            raise StorageUnavailableError(
                f"Storage unavailable for idempotency lock '{idempotency_key}': {exc}"
            ) from exc
        except Exception as exc:
            logger.error(
                "Unexpected failure acquiring atomic reservation lock for %s: %s",
                idempotency_key,
                exc,
            )
            raise StorageUnavailableError(
                f"Failed acquiring reservation lock for '{idempotency_key}': {exc}"
            ) from exc

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
            StorageUnavailableError: if storage is inaccessible or lock cannot be written.
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
        except (PermissionError, FileNotFoundError, OSError) as exc:
            logger.error(
                "Storage failure while persisting durable idempotency outcome for %s: %s",
                idempotency_key,
                exc,
            )
            raise StorageUnavailableError(
                f"Failed to persist durable idempotency outcome for '{idempotency_key}': {exc}"
            ) from exc
        except Exception as exc:
            logger.error(
                "Failed to persist durable idempotency outcome for %s: %s",
                idempotency_key,
                exc,
            )
            raise StorageUnavailableError(
                f"Failed to persist durable idempotency outcome for '{idempotency_key}': {exc}"
            ) from exc
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
