"""The run list and the next attempt id (US3.1, contracts C1 and C2).

Every run appears once: the run log rows grouped by run id, plus run folders in ``outputs/`` that have
no row (failed, stopped, running or waiting runs). ``queue/`` and ``run.lock`` are not runs.
This module never imports training or evaluation code (ADR-006).
"""

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from gsm8k.run_records.lock import is_free, read_lock
from gsm8k.run_records.log import RunRow, read_rows
from gsm8k.run_records.paths import RUN_ID_PATTERN, outputs_root

# C1 base id ("<model>-<method>-<split>"); an attempt id is "<base id>-<n>"
# (``^(q06|q17)-[a-z0-9]+-[a-z0-9]+-[0-9]+$``).
BASE_ID_PATTERN = re.compile(r"(?:q06|q17)-[a-z0-9]+-[a-z0-9]+")


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


def _active_run_id(outputs: Path) -> str | None:
    """The run id of the process holding the GPU lock, or None when the lock is free."""
    path = outputs / "run.lock"
    if is_free(path):
        return None
    content = read_lock(path)
    return content.get("run_id") if content else None


def _folder_status(folder: Path, active: str | None) -> str | None:
    status = _read_json(folder / "status.json")
    if status is not None and isinstance(status.get("status"), str):
        return status["status"]
    if active is not None and folder.name == active:
        return "running"
    return None


def _summary_from_rows(run_id: str, rows: list[RunRow]) -> RunSummary:
    first, last = rows[0], rows[-1]
    dev = [row.value for row in rows if row.data == "gsm8k-dev" and row.metric == "accuracy"]
    test = [row.value for row in rows if row.data == "gsm8k-test" and row.metric == "accuracy"]
    return RunSummary(
        run_id=run_id,
        model=first.model,
        method=first.method,
        dev_accuracy=dev[-1] if dev else None,
        test_accuracy=test[-1] if test else None,
        minutes=last.minutes,
        date=last.date,
        status="finished",
    )


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

    active = _active_run_id(outputs)
    folders = {folder.name: folder for folder in _run_folders(outputs)}

    runs: list[RunSummary] = []
    for run_id, run_rows in grouped.items():
        summary = _summary_from_rows(run_id, run_rows)
        folder = folders.get(run_id)
        if folder is not None:
            summary.status = _folder_status(folder, active) or summary.status
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
                status=_folder_status(folder, active),
            )
        )
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
