"""The run queue ``outputs/queue/`` (US3.7, contract C3): first in, first out, at most 10 waiting runs.

One file per waiting run, named ``<position:03d>-<attempt_id>.json`` and holding ``v``, ``attempt_id``,
``config`` (the checked C2 config.json fields) and ``added_at``; an optional ``kind`` (``train`` or
``evaluate``) tells the worker which command to launch (readers ignore unknown fields, C3 common rules).
Positions run 1..n; removing an entry renames the files behind it, so they move up one place. Every
file is written atomically, and every change happens under an exclusive ``flock`` on
``outputs/queue/.lock``, so the service and the worker (two processes) never interleave changes. The
queue is always read from disk, so it survives a restart of either process (AC3.7.5).

This module never imports training or evaluation code (ADR-006).
"""

import fcntl
import json
import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from gsm8k.run_records.folder import atomic_write_text, utc_now
from gsm8k.run_records.paths import outputs_root

SCHEMA_VERSION = 1
MAX_WAITING = 10
QUEUE_FULL_MESSAGE = f"The queue is full ({MAX_WAITING} waiting)"
# C1 attempt id, reimplemented here (ADR-006: no import of gsm8k.cli).
ATTEMPT_ID_PATTERN = re.compile(r"^(?:q06|q17)-[a-z0-9]+-[a-z0-9]+-[0-9]+$")
_ENTRY_NAME = re.compile(r"^([0-9]{3})-((?:q06|q17)-[a-z0-9]+-[a-z0-9]+-[0-9]+)\.json$")
_LOCK_NAME = ".lock"


class QueueFull(Exception):
    """The queue already holds MAX_WAITING runs; nothing was added (AC3.7.3)."""

    def __init__(self, message: str = QUEUE_FULL_MESSAGE):
        super().__init__(message)


class NotQueued(LookupError):
    """No waiting run has this attempt id."""


@dataclass
class QueueEntry:
    position: int
    attempt_id: str
    config: dict
    added_at: str
    kind: str | None = None


def queue_dir(outputs: Path | None = None) -> Path:
    """``outputs/queue/`` (not created)."""
    root = Path(outputs) if outputs is not None else outputs_root()
    return root / "queue"


def _entry_path(qdir: Path, position: int, attempt_id: str) -> Path:
    return qdir / f"{position:03d}-{attempt_id}.json"


@contextmanager
def _locked(outputs: Path | None) -> Iterator[Path]:
    """Hold the queue's change lock; yields the queue folder (created when missing)."""
    qdir = queue_dir(outputs)
    qdir.mkdir(parents=True, exist_ok=True)
    fd = os.open(qdir / _LOCK_NAME, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            yield qdir
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _read_entry(path: Path, position: int, attempt_id: str) -> QueueEntry | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:  # renamed or removed while listing
        return None
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"Queue entry could not be read, skipped: {path} ({exc})", file=sys.stderr)
        return None
    if not isinstance(data, dict) or not isinstance(data.get("config"), dict):
        print(f"Queue entry is not in the queue format, skipped: {path}", file=sys.stderr)
        return None
    kind = data.get("kind")
    return QueueEntry(
        position=position,
        attempt_id=attempt_id,
        config=data["config"],
        added_at=str(data.get("added_at") or ""),
        kind=kind if isinstance(kind, str) else None,
    )


def _scan(qdir: Path) -> list[tuple[int, str, Path]]:
    try:
        names = os.listdir(qdir)
    except FileNotFoundError:
        return []
    found = []
    for name in names:
        match = _ENTRY_NAME.fullmatch(name)
        if match:
            found.append((int(match.group(1)), match.group(2), qdir / name))
    found.sort(key=lambda item: (item[0], item[1]))
    return found


def list_queue(outputs: Path | None = None) -> list[QueueEntry]:
    """The waiting runs in queue order, oldest first (AC3.7.5)."""
    entries = []
    for position, attempt_id, path in _scan(queue_dir(outputs)):
        entry = _read_entry(path, position, attempt_id)
        if entry is not None:
            entries.append(entry)
    return entries


def peek_head(outputs: Path | None = None) -> QueueEntry | None:
    """The oldest waiting run, or None when the queue is empty."""
    entries = list_queue(outputs)
    return entries[0] if entries else None


def _renumber(qdir: Path) -> None:
    """Rename the entries to positions 1..n in their current order (lowest first, so names never clash)."""
    for index, (position, attempt_id, path) in enumerate(_scan(qdir), start=1):
        if position != index:
            os.replace(path, _entry_path(qdir, index, attempt_id))


def add(attempt_id: str, config: dict, kind: str | None = None, outputs: Path | None = None) -> QueueEntry:
    """Add a checked run at the end of the queue (AC3.7.1).

    Raises ``QueueFull("The queue is full (10 waiting)")`` when MAX_WAITING runs already wait (nothing is
    added, AC3.7.3), ``ValueError`` for an attempt id that is not a C1 attempt id or is already waiting.
    """
    if not isinstance(attempt_id, str) or not ATTEMPT_ID_PATTERN.fullmatch(attempt_id):
        raise ValueError(f"Invalid attempt id: {attempt_id!r} (expected e.g. q06-sft-dev-1)")
    if not isinstance(config, dict):
        raise ValueError("A queue entry's config must be a mapping of C2 fields")
    with _locked(outputs) as qdir:
        current = _scan(qdir)
        if any(existing == attempt_id for _, existing, _ in current):
            raise ValueError(f"Run already waiting: {attempt_id}")
        if len(current) >= MAX_WAITING:
            raise QueueFull()
        position = (current[-1][0] if current else 0) + 1
        added_at = utc_now()
        content: dict = {
            "v": SCHEMA_VERSION,
            "attempt_id": attempt_id,
            "config": config,
            "added_at": added_at,
        }
        if kind is not None:
            content["kind"] = kind
        text = json.dumps(content, indent=2, ensure_ascii=False) + "\n"
        atomic_write_text(_entry_path(qdir, position, attempt_id), text)
    return QueueEntry(position=position, attempt_id=attempt_id, config=config, added_at=added_at, kind=kind)


def remove(attempt_id: str, outputs: Path | None = None) -> None:
    """Remove a waiting run; the runs behind it move up one place (AC3.7.4).

    Raises ``NotQueued`` (a ``LookupError``) when no waiting run has this attempt id.
    """
    with _locked(outputs) as qdir:
        matches = [path for _, existing, path in _scan(qdir) if existing == attempt_id]
        if not matches:
            raise NotQueued(f"No waiting run: {attempt_id}")
        for path in matches:
            path.unlink(missing_ok=True)
        _renumber(qdir)


def pop_head(outputs: Path | None = None) -> QueueEntry | None:
    """Remove and return the oldest waiting run, or None when the queue is empty."""
    with _locked(outputs) as qdir:
        for position, attempt_id, path in _scan(qdir):
            entry = _read_entry(path, position, attempt_id)
            if entry is None:
                continue
            path.unlink(missing_ok=True)
            _renumber(qdir)
            return entry
    return None
