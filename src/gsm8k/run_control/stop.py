"""Stopping the active run (US3.4, FR3.5; contracts C3, C5).

The active run is the process holding the GPU lock; its pid comes from the lock content. It gets
SIGTERM, and SIGKILL when it still holds the lock after the grace period (30 s by default, C5). A run
that handles SIGTERM writes its own ``status.json`` (stopped, exit code 130) and no row (AC3.4.1); the
kernel frees the lock when the process ends (AC3.4.2). With no active run nothing changes and the
answer is "No run is active" (AC3.4.3), also when the free lock file still names an ended run.

This module never imports training or evaluation code (ADR-006).
"""

import os
import signal
import time
from pathlib import Path

from gsm8k.run_records.lock import is_free, read_lock
from gsm8k.run_records.paths import outputs_root

NO_ACTIVE_RUN = "No run is active"
GRACE_SECONDS = 30.0
_POLL_SECONDS = 0.05
_KILL_WAIT_SECONDS = 10.0
_CONTENT_WAIT_SECONDS = 1.0


def _holder(lock_file: Path) -> dict | None:
    """The lock content while the lock is held (briefly waiting for a fresh holder to write it)."""
    deadline = time.monotonic() + _CONTENT_WAIT_SECONDS
    while True:
        if is_free(lock_file):
            return None
        content = read_lock(lock_file)
        if content and isinstance(content.get("pid"), int):
            return content
        if time.monotonic() >= deadline:
            return {}
        time.sleep(_POLL_SECONDS)


def _ended(lock_file: Path, run_id: str | None) -> bool:
    """The run no longer holds the lock (free, or held by another run)."""
    if is_free(lock_file):
        return True
    content = read_lock(lock_file)
    return bool(content) and content.get("run_id") != run_id


def _wait_ended(lock_file: Path, run_id: str | None, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while not _ended(lock_file, run_id):
        if time.monotonic() >= deadline:
            return False
        time.sleep(_POLL_SECONDS)
    return True


def _kill(pid: int) -> None:
    """SIGKILL the run; its whole process group when it leads one (a worker launch does)."""
    try:
        if os.getpgid(pid) == pid:
            os.killpg(pid, signal.SIGKILL)
        else:
            os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def stop_active(outputs: Path | None = None, grace_seconds: float = GRACE_SECONDS) -> str:
    """Stop the run holding the GPU lock and wait (bounded) until it has let the lock go.

    Returns "No run is active" when nothing holds the lock (nothing changes), else a sentence naming the
    stopped run. Raises ``RuntimeError`` when the holder cannot be signalled (unknown pid, this very
    process, or no permission).
    """
    root = Path(outputs) if outputs is not None else outputs_root()
    lock_file = root / "run.lock"
    content = _holder(lock_file)
    if content is None:
        return NO_ACTIVE_RUN
    run_id = content.get("run_id")
    pid = content.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        raise RuntimeError(f"The active run's process id is unknown (lock file {lock_file})")
    if pid == os.getpid():
        raise RuntimeError(f"The active run {run_id} is this process; it cannot stop itself")
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        _wait_ended(lock_file, run_id, _KILL_WAIT_SECONDS)
        return f"Run {run_id} had already ended"
    except PermissionError as exc:
        raise RuntimeError(f"The active run {run_id} (pid {pid}) cannot be signalled: {exc}") from exc
    if _wait_ended(lock_file, run_id, grace_seconds):
        return f"Run {run_id} stopped"
    _kill(pid)
    if not _wait_ended(lock_file, run_id, _KILL_WAIT_SECONDS):
        raise RuntimeError(f"Run {run_id} (pid {pid}) still holds the lock after SIGKILL")
    return f"Run {run_id} killed after {grace_seconds:g} s without stopping"
