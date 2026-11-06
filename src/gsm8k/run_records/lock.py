"""The GPU lock ``outputs/run.lock`` (contract C3, BR5.1).

Holding the lock means holding an exclusive ``flock`` on the file for the process's whole life; the
kernel frees it when the process ends, also on a crash. The holder writes its content (for display
only) right after taking the lock and clears it on a clean release. Nothing ever renames or deletes
the lock file. Linux only.
"""

import fcntl
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from gsm8k.run_records.paths import outputs_root

SCHEMA_VERSION = 1


def lock_path() -> Path:
    return outputs_root() / "run.lock"


class LockHeld(Exception):
    """Another process holds the GPU lock; ``run_id`` is the holder's run as read from the file."""

    def __init__(self, run_id: str | None):
        self.run_id = run_id
        super().__init__(f"A run is already active: {run_id if run_id else 'unknown'}")


def read_lock(path: Path | None = None) -> dict | None:
    """The lock content, or None when the file is missing, cleared or not a JSON object."""
    path = Path(path) if path is not None else lock_path()
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    if not text.strip():
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def is_free(path: Path | None = None) -> bool:
    """True when no process holds the lock (take it and at once release it)."""
    path = Path(path) if path is not None else lock_path()
    try:
        fd = os.open(path, os.O_RDONLY)
    except FileNotFoundError:
        return True
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return False
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)
        return True
    finally:
        os.close(fd)


class GpuLock:
    """The GPU lock for this process.

    Use ``acquire``/``release``, or a ``with`` block (``with GpuLock() as lock: lock.acquire(...)``;
    giving ``run_id`` to the constructor makes the ``with`` block acquire on entry). Each acquire opens
    its own file descriptor, so a second holder conflicts even within one process.
    """

    def __init__(self, run_id: str | None = None, started_by: str = "terminal"):
        self._fd: int | None = None
        self._run_id = run_id
        self._started_by = started_by

    @property
    def held(self) -> bool:
        return self._fd is not None

    def acquire(self, run_id: str, started_by: str = "terminal") -> None:
        """Take the lock or raise LockHeld naming the holder's run; then write the content."""
        if self._fd is not None:
            raise RuntimeError("This GpuLock is already held")
        path = lock_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            holder = read_lock(path)
            raise LockHeld(holder.get("run_id") if holder else None) from None
        except BaseException:
            os.close(fd)
            raise
        self._fd = fd
        content = {
            "v": SCHEMA_VERSION,
            "run_id": run_id,
            "pid": os.getpid(),
            "started_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "started_by": started_by,
        }
        data = (json.dumps(content) + "\n").encode("utf-8")
        os.ftruncate(fd, 0)
        os.pwrite(fd, data, 0)
        os.fsync(fd)

    def release(self) -> None:
        """Clear the content and free the lock; does nothing when not held."""
        fd = self._fd
        if fd is None:
            return
        self._fd = None
        try:
            os.ftruncate(fd, 0)
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

    def __enter__(self) -> "GpuLock":
        if self._run_id is not None:
            self.acquire(self._run_id, self._started_by)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()
