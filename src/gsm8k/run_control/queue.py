"""The run queue ``outputs/queue/`` (US3.7, contract C3): first in, first out, at most 10 waiting runs.

One file per waiting run, named ``<position:03d>-<attempt_id>.json`` and holding ``v``, ``attempt_id``,
``config`` (the checked C2 config.json fields) and ``added_at``; an optional ``kind`` (``train`` or
``evaluate``) tells the worker which command to launch (readers ignore unknown fields, C3 common rules).
Course runs (u12) add two optional keys: ``results`` (``outputs/course/runs.csv``, the run log the run
appends to, relative to the project's outputs root) and ``after`` (an attempt id whose row in that file the
entry waits for).
A key missing from an old entry file reads as None.
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
# A course attempt id (u12, contract C9): ``course-c05-qwen3-17-1``.
_PROJECT_ID = r"(?:q06|q17)-[a-z0-9]+-[a-z0-9]+-[0-9]+"
# The attempt number has no leading zero (they count from 1), so "course-c05-base-06" (no number) is refused.
_COURSE_ID = r"course-c[0-9]{2}-[a-z0-9-]+-[1-9][0-9]*"
ATTEMPT_ID_PATTERN = re.compile(rf"^(?:{_PROJECT_ID}|{_COURSE_ID})$")
_ENTRY_NAME = re.compile(rf"^([0-9]{{3}})-({_PROJECT_ID}|{_COURSE_ID})\.json$")
# The only `results` value an entry may carry besides None (C3, C9): the course run log.
COURSE_RESULTS = "outputs/course/runs.csv"
LOG_NAME = "queue.log"
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
    results: str | None = None
    after: str | None = None


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
    results = data.get("results")
    after = data.get("after")
    return QueueEntry(
        position=position,
        attempt_id=attempt_id,
        config=data["config"],
        added_at=str(data.get("added_at") or ""),
        kind=kind if isinstance(kind, str) else None,
        results=results if isinstance(results, str) else None,
        after=after if isinstance(after, str) else None,
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


def _check_entry(attempt_id: object, config: object, results: object, after: object) -> None:
    """Raise ValueError when an entry's fields are not valid (nothing is written by this check)."""
    if not isinstance(attempt_id, str) or not ATTEMPT_ID_PATTERN.fullmatch(attempt_id):
        raise ValueError(f"Invalid attempt id: {attempt_id!r} (expected e.g. q06-sft-dev-1)")
    if not isinstance(config, dict):
        raise ValueError("A queue entry's config must be a mapping of C2 fields")
    if results is not None and results != COURSE_RESULTS:
        raise ValueError(f"Invalid results file for a queue entry: {results!r} (expected {COURSE_RESULTS!r})")
    if after is not None and (not isinstance(after, str) or not ATTEMPT_ID_PATTERN.fullmatch(after)):
        raise ValueError(f"Invalid 'after' attempt id: {after!r}")


def _write_entry(
    qdir: Path,
    position: int,
    attempt_id: str,
    config: dict,
    kind: str | None,
    results: str | None,
    after: str | None,
) -> QueueEntry:
    added_at = utc_now()
    content: dict = {
        "v": SCHEMA_VERSION,
        "attempt_id": attempt_id,
        "config": config,
        "added_at": added_at,
    }
    if kind is not None:
        content["kind"] = kind
    if results is not None:
        content["results"] = results
    if after is not None:
        content["after"] = after
    text = json.dumps(content, indent=2, ensure_ascii=False) + "\n"
    atomic_write_text(_entry_path(qdir, position, attempt_id), text)
    return QueueEntry(
        position=position,
        attempt_id=attempt_id,
        config=config,
        added_at=added_at,
        kind=kind,
        results=results,
        after=after,
    )


def add(
    attempt_id: str,
    config: dict,
    kind: str | None = None,
    outputs: Path | None = None,
    *,
    results: str | None = None,
    after: str | None = None,
) -> QueueEntry:
    """Add a checked run at the end of the queue (AC3.7.1).

    Raises ``QueueFull("The queue is full (10 waiting)")`` when MAX_WAITING runs already wait (nothing is
    added, AC3.7.3), ``ValueError`` for an attempt id that is not a C1 or course attempt id, is already
    waiting, or a ``results`` other than None or ``outputs/course/runs.csv`` (AC12.4.1).
    """
    _check_entry(attempt_id, config, results, after)
    with _locked(outputs) as qdir:
        current = _scan(qdir)
        if any(existing == attempt_id for _, existing, _ in current):
            raise ValueError(f"Run already waiting: {attempt_id}")
        if len(current) >= MAX_WAITING:
            raise QueueFull()
        position = (current[-1][0] if current else 0) + 1
        return _write_entry(qdir, position, attempt_id, config, kind, results, after)


def add_all(entries: list[dict], outputs: Path | None = None) -> list[QueueEntry]:
    """Add several runs at the end of the queue, in order, all or none (AC12.4.1).

    Each item is a dict with ``attempt_id``, ``config`` and optionally ``kind``, ``results`` and ``after``.
    Raises ``QueueFull`` when they do not all fit under MAX_WAITING and ``ValueError`` for any bad or
    duplicate entry; in both cases nothing is written.
    """
    items = []
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("A queue entry must be a mapping with attempt_id and config")
        attempt_id, config = item.get("attempt_id"), item.get("config")
        results, after = item.get("results"), item.get("after")
        _check_entry(attempt_id, config, results, after)
        items.append((attempt_id, config, item.get("kind"), results, after))
    ids = [attempt_id for attempt_id, *_ in items]
    if len(set(ids)) != len(ids):
        raise ValueError("The same attempt id is in the list more than once")
    with _locked(outputs) as qdir:
        current = _scan(qdir)
        waiting = {existing for _, existing, _ in current}
        for attempt_id in ids:
            if attempt_id in waiting:
                raise ValueError(f"Run already waiting: {attempt_id}")
        if len(current) + len(items) > MAX_WAITING:
            raise QueueFull()
        position = current[-1][0] if current else 0
        added = []
        for attempt_id, config, kind, results, after in items:
            position += 1
            added.append(_write_entry(qdir, position, attempt_id, config, kind, results, after))
        return added


def append_log(message: str, outputs: Path | None = None) -> None:
    """Append one line to ``outputs/queue/queue.log`` (why an entry left the queue without running)."""
    qdir = queue_dir(outputs)
    qdir.mkdir(parents=True, exist_ok=True)
    line = f"{utc_now()} {message}".replace("\n", " ")
    with (qdir / LOG_NAME).open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


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
