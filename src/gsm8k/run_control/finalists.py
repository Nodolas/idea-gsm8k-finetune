"""Finalists, the runs allowed on the test split (US3.6, contract C4 ``results/finalists.json``).

No file means no finalists; an unreadable file raises ``ValueError`` naming the file, so no test-split
evaluation can start (AC3.6.5). Writes are atomic. This module never imports training or evaluation
code (ADR-006).
"""

import json
from pathlib import Path

from gsm8k._env import ROOT
from gsm8k.run_records.folder import atomic_write_text, utc_now
from gsm8k.run_records.log import read_rows

FINALISTS_DEFAULT: Path = ROOT / "results" / "finalists.json"
SCHEMA_VERSION = 1
NOT_A_FINALIST = "Only finalists can be scored on the test split"


def _read_entries(path: Path) -> list[dict]:
    """The C4 finalist entries; a missing file has none, anything unreadable raises ValueError."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"Finalists file could not be read: {path} ({exc})") from exc
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise ValueError(f"Finalists file could not be read: {path} ({exc})") from exc
    entries = data.get("finalists") if isinstance(data, dict) else None
    if not isinstance(entries, list) or not all(
        isinstance(entry, dict) and isinstance(entry.get("run_id"), str) for entry in entries
    ):
        raise ValueError(f"Finalists file could not be read: {path} (not the finalists format)")
    return entries


def _write_entries(path: Path, entries: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"v": SCHEMA_VERSION, "finalists": entries}
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def list_finalists(path: Path = FINALISTS_DEFAULT) -> list[str]:
    """The finalists' run ids in marking order (AC3.6.5)."""
    return [entry["run_id"] for entry in _read_entries(path)]


def mark(path: Path, run_id: str, results: Path) -> None:
    """Save run_id as a finalist with ``marked_at`` (AC3.6.1); marking twice keeps one entry.

    Raises ``LookupError`` when the run has no row in the run log (C4), ``OSError`` when the run log
    cannot be read and ``ValueError`` when the finalists file cannot be read.
    """
    entries = _read_entries(path)
    rows, _ = read_rows(Path(results))
    if not any(row.run_id == run_id for row in rows):
        raise LookupError(f"Run not found in the run log: {run_id}")
    if any(entry["run_id"] == run_id for entry in entries):
        return
    entries.append({"run_id": run_id, "marked_at": utc_now()})
    _write_entries(path, entries)


def unmark(path: Path, run_id: str) -> None:
    """Remove run_id from the finalists (AC3.6.1); a run that is not a finalist changes nothing."""
    entries = _read_entries(path)
    kept = [entry for entry in entries if entry["run_id"] != run_id]
    if len(kept) != len(entries):
        _write_entries(path, kept)


def check_test_split_allowed(run_id: str, path: Path = FINALISTS_DEFAULT) -> None:
    """Raise ``ValueError("Only finalists can be scored on the test split")`` unless run_id is a
    finalist (AC3.6.2), or the unreadable-file ``ValueError`` naming the file (AC3.6.5)."""
    if run_id not in list_finalists(path):
        raise ValueError(NOT_A_FINALIST)
