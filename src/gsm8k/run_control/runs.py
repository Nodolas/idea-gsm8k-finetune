"""The run list and the next attempt id (US3.1, contracts C1, C2 and C6).

Every run appears once: the run log rows grouped by run id, plus run folders in ``outputs/`` that have
no row (failed, stopped, running or waiting runs). ``queue/`` and ``run.lock`` are not runs. A run
folder whose id waits in the queue lists as ``queued``.

Each run carries the C6 Run fields as changed 2026-11-07: ``data`` (its last row's), ``adapter_run``,
``test_accuracy`` (its own ``gsm8k-test`` row, else the latest ``gsm8k-test`` row whose ``adapter_run``
is this run, else for a ``base`` dev run its model's latest ``base`` ``gsm8k-test`` row with an empty
``adapter_run``), ``gain`` (dev accuracy minus the dev accuracy of the model's latest ``base``
``gsm8k-dev`` run; None for that baseline and for runs without a dev score) and ``started_at`` (the
row date minus its minutes, or the GPU lock's ``started_at`` for the active run). "Latest" is the last
in run log order. This module never imports training or evaluation code (ADR-006).
"""

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from gsm8k.run_control import queue as run_queue
from gsm8k.run_records.lock import is_free, read_lock
from gsm8k.run_records.log import RunRow, read_rows
from gsm8k.run_records.paths import RUN_ID_PATTERN, outputs_root

# C1 base id ("<model>-<method>-<split>"); an attempt id is "<base id>-<n>"
# (``^(q06|q17)-[a-z0-9]+-[a-z0-9]+-[0-9]+$``).
BASE_ID_PATTERN = re.compile(r"(?:q06|q17)-[a-z0-9]+-[a-z0-9]+")
DEV_DATA = "gsm8k-dev"
TEST_DATA = "gsm8k-test"
ACCURACY = "accuracy"
BASE_METHOD = "base"
_ISO_SECONDS = "%Y-%m-%dT%H:%M:%SZ"


@dataclass
class RunSummary:
    run_id: str
    model: str | None
    method: str | None
    dev_accuracy: float | None
    test_accuracy: float | None
    minutes: float | None
    date: str | None
    status: str | None
    data: str | None = None
    adapter_run: str | None = None
    gain: float | None = None
    started_at: str | None = None


def _read_json(path: Path) -> dict | None:
    """A JSON object from path, or None when the file is missing, unreadable or not an object."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _run_folders(outputs: Path) -> list[Path]:
    """Run folders in outputs/ (names that are run ids), sorted by name; a missing outputs/ has none."""
    try:
        entries = list(outputs.iterdir())
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise OSError(f"Run folders could not be read: {outputs} ({exc})") from exc
    return sorted(
        (entry for entry in entries if entry.is_dir() and RUN_ID_PATTERN.fullmatch(entry.name)),
        key=lambda entry: entry.name,
    )


def _active_lock(outputs: Path) -> dict | None:
    """The GPU lock content of the process holding it (``{}`` when unreadable), or None when free."""
    path = outputs / "run.lock"
    if is_free(path):
        return None
    return read_lock(path) or {}


def _queued_ids(outputs: Path) -> set[str]:
    """The attempt ids waiting in ``outputs/queue/``; an unreadable queue has none."""
    try:
        return {entry.attempt_id for entry in run_queue.list_queue(outputs)}
    except (OSError, ValueError):
        return set()


def _started_at(date: str | None, minutes: float | None) -> str | None:
    """``date`` minus ``minutes`` as ISO UTC to the second, or None when either cannot be read."""
    if not isinstance(date, str) or not isinstance(minutes, int | float) or isinstance(minutes, bool):
        return None
    try:
        end = datetime.fromisoformat(date.strip().replace("Z", "+00:00"))
        start = end - timedelta(seconds=round(minutes * 60))
    except (ValueError, OverflowError):
        return None
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    return start.astimezone(UTC).strftime(_ISO_SECONDS)


def _is_accuracy_on(row: RunRow, data: str) -> bool:
    return row.data == data and row.metric == ACCURACY


def _folder_status(
    folder: Path, active: str | None, queued: set[str] | frozenset = frozenset()
) -> str | None:
    status = _read_json(folder / "status.json")
    if status is not None and isinstance(status.get("status"), str):
        return status["status"]
    if active is not None and folder.name == active:
        return "running"
    if folder.name in queued:
        return "queued"
    return None


def _summary_from_rows(run_id: str, rows: list[RunRow]) -> RunSummary:
    first, last = rows[0], rows[-1]
    dev = [row.value for row in rows if _is_accuracy_on(row, DEV_DATA)]
    test = [row.value for row in rows if _is_accuracy_on(row, TEST_DATA)]
    adapters = [row.adapter_run for row in rows if row.adapter_run]
    return RunSummary(
        run_id=run_id,
        model=first.model,
        method=first.method,
        dev_accuracy=dev[-1] if dev else None,
        test_accuracy=test[-1] if test else None,
        minutes=last.minutes,
        date=last.date,
        status="finished",
        data=last.data,
        adapter_run=adapters[-1] if adapters else None,
        started_at=_started_at(last.date, last.minutes),
    )


def _join_scores(runs: list[RunSummary], rows: list[RunRow]) -> None:
    """Fill the joined ``test_accuracy`` and the ``gain`` of every run in place (C6, 2026-11-07)."""
    adapter_test: dict[str, float] = {}  # adapter run id -> latest gsm8k-test accuracy naming it
    base_test: dict[str, float] = {}  # model -> latest base gsm8k-test accuracy without adapter
    baseline_id: dict[str, str] = {}  # model -> run id of its latest base gsm8k-dev run
    for row in rows:
        if _is_accuracy_on(row, TEST_DATA):
            if row.adapter_run:
                adapter_test[row.adapter_run] = row.value
            elif row.method == BASE_METHOD:
                base_test[row.model] = row.value
        elif _is_accuracy_on(row, DEV_DATA) and row.method == BASE_METHOD:
            baseline_id[row.model] = row.run_id

    by_id = {run.run_id: run for run in runs}
    for run in runs:
        if run.test_accuracy is None:
            if run.run_id in adapter_test:
                run.test_accuracy = adapter_test[run.run_id]
            elif run.method == BASE_METHOD and run.dev_accuracy is not None and run.model in base_test:
                run.test_accuracy = base_test[run.model]
        baseline = by_id.get(baseline_id.get(run.model or "", ""))
        if (
            run.dev_accuracy is not None
            and baseline is not None
            and baseline.dev_accuracy is not None
            and baseline.run_id != run.run_id
        ):
            run.gain = run.dev_accuracy - baseline.dev_accuracy


def list_runs(results: Path, outputs: Path | None = None) -> tuple[list[RunSummary], int]:
    """Every run once and the number of skipped malformed rows (AC3.1.1, AC3.1.3).

    No run log yet gives an empty list (AC3.1.4); an unreadable run log raises ``OSError`` naming the
    file (AC3.1.4). Runs with rows come first in log order, then folders without a row by name.
    """
    outputs = Path(outputs) if outputs is not None else outputs_root()
    rows, skipped = read_rows(Path(results))
    grouped: dict[str, list[RunRow]] = {}
    for row in rows:
        grouped.setdefault(row.run_id, []).append(row)

    lock = _active_lock(outputs)
    active = lock.get("run_id") if lock is not None else None
    active = active if isinstance(active, str) else None
    lock_started = lock.get("started_at") if lock is not None else None
    lock_started = lock_started if isinstance(lock_started, str) else None
    folders = {folder.name: folder for folder in _run_folders(outputs)}
    queued = _queued_ids(outputs) if folders else set()

    runs: list[RunSummary] = []
    for run_id, run_rows in grouped.items():
        summary = _summary_from_rows(run_id, run_rows)
        folder = folders.get(run_id)
        if folder is not None:
            summary.status = _folder_status(folder, active, queued) or summary.status
        runs.append(summary)

    for run_id, folder in folders.items():
        if run_id in grouped:
            continue
        config = _read_json(folder / "config.json") or {}
        status = _read_json(folder / "status.json") or {}
        runs.append(
            RunSummary(
                run_id=run_id,
                model=config.get("model") if isinstance(config.get("model"), str) else None,
                method=config.get("method") if isinstance(config.get("method"), str) else None,
                dev_accuracy=None,
                test_accuracy=None,
                minutes=None,
                date=status.get("ended_at") if isinstance(status.get("ended_at"), str) else None,
                status=_folder_status(folder, active, queued),
            )
        )

    _join_scores(runs, rows)
    if active is not None:
        for run in runs:
            if run.run_id == active:
                run.started_at = lock_started
    return runs, skipped


def next_attempt_id(
    base_id: str,
    results: Path,
    outputs: Path | None = None,
    queue_ids: Iterable[str] = (),
) -> str:
    """``<base id>-<n>`` with n one more than the highest attempt of base_id among the run log rows,
    the run folders and the queued ids (numbers compare as numbers; AC3.2.3)."""
    if not isinstance(base_id, str) or not BASE_ID_PATTERN.fullmatch(base_id):
        raise ValueError(f"Invalid base id: {base_id!r} (expected e.g. q06-sft-dev)")
    outputs = Path(outputs) if outputs is not None else outputs_root()
    pattern = re.compile(rf"^{re.escape(base_id)}-([0-9]+)$")

    rows, _ = read_rows(Path(results))
    candidates = [row.run_id for row in rows]
    candidates += [folder.name for folder in _run_folders(outputs)]
    candidates += list(queue_ids)

    highest = 0
    for candidate in candidates:
        match = pattern.match(candidate) if isinstance(candidate, str) else None
        if match:
            highest = max(highest, int(match.group(1)))
    return f"{base_id}-{highest + 1}"
