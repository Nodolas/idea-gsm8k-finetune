"""Prune old adapters: keep each model's best run and every finalist (US2.5, FR2.5, contract C4).

``gsm8k prune`` lists the adapter folders under ``checkpoints/`` it would delete and deletes nothing
(AC2.5.2); with ``--yes`` it deletes them (AC2.5.3). It keeps each model's best run (the highest dev
accuracy among the runs that trained an adapter, a tie going to the earlier row, AC2.5.1), every
finalist in ``results/finalists.json`` and the folder of the run that holds the GPU lock. A folder
with no row in the run log is deleted too, unless its run holds the lock. A run whose adapter folder
is already gone is reported as already pruned (AC2.5.4).

Safety: it only ever deletes directories directly under ``checkpoints_root()`` whose name is a valid
run id (never a symlink, never anything above that folder), never touches the run log or the
finalists file, and needs no GPU lock.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

from gsm8k._env import ROOT
from gsm8k.cli import EXIT_FAILED, EXIT_FINISHED
from gsm8k.run_records import lock, paths
from gsm8k.run_records.log import RunRow, read_rows

FINALISTS_DEFAULT: Path = ROOT / "results" / "finalists.json"

# Methods whose runs train an adapter of their own (saved to checkpoints/<run_id>/). A row with an
# adapter_run scores another run's adapter (best checkpoint, generalisation) and owns no folder.
ADAPTER_METHODS = ("sft", "grpo", "terse", "optuna", "selfcot")
BEST_DATA = "gsm8k-dev"
BEST_METRIC = "accuracy"


@dataclass
class PrunePlan:
    delete: list[Path]
    keep: list[str]
    already_gone: list[str]
    why_kept: dict[str, str] = field(default_factory=dict)


def read_finalists(path: Path) -> set[str]:
    """The finalists' run ids (C4). No file: no finalists; unreadable: ValueError naming the file."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return set()
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"Finalists file could not be read: {path} ({exc})") from exc
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise ValueError(f"Finalists file could not be read: {path} ({exc})") from exc
    entries = data.get("finalists") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise ValueError(f"Finalists file could not be read: {path} (no 'finalists' list)")
    run_ids: set[str] = set()
    for entry in entries:
        run_id = entry.get("run_id") if isinstance(entry, dict) else None
        if not isinstance(run_id, str) or not run_id:
            raise ValueError(f"Finalists file could not be read: {path} (an entry has no run_id)")
        run_ids.add(run_id)
    return run_ids


def _owns_adapter(row: RunRow) -> bool:
    return row.method in ADAPTER_METHODS and not row.adapter_run


def best_runs(rows: list[RunRow]) -> dict[str, RunRow]:
    """Per model, the adapter run with the highest dev accuracy; a tie goes to the earlier row."""
    best: dict[str, RunRow] = {}
    for row in rows:
        if row.data != BEST_DATA or row.metric != BEST_METRIC or not _owns_adapter(row):
            continue
        current = best.get(row.model)
        if current is None or row.value > current.value:
            best[row.model] = row
    return best


def _valid_run_id(run_id: str) -> bool:
    try:
        paths.check_run_id(run_id)
    except ValueError:
        return False
    return True


def active_run_id() -> str | None:
    """The run id of the run holding the GPU lock, or None when no run is active."""
    if lock.is_free():
        return None
    content = lock.read_lock()
    run_id = content.get("run_id") if content else None
    return run_id if isinstance(run_id, str) and run_id else None


def _adapter_folders(checkpoints: Path) -> dict[str, Path]:
    """Directories directly under checkpoints/ named by a valid run id (no symlinks, nothing else)."""
    root = checkpoints.resolve()
    folders: dict[str, Path] = {}
    if not checkpoints.is_dir():
        return folders
    for entry in sorted(checkpoints.iterdir()):
        if entry.is_symlink() or not entry.is_dir() or not _valid_run_id(entry.name):
            continue
        if entry.resolve().parent != root:
            continue
        folders[entry.name] = entry
    return folders


def plan_prune(rows: list[RunRow], finalists: set[str], checkpoints: Path) -> PrunePlan:
    """What prune would delete and keep; it deletes nothing. The GPU lock holder's folder is kept."""
    checkpoints = Path(checkpoints)
    folders = _adapter_folders(checkpoints)

    why: dict[str, str] = {}
    for model, row in best_runs(rows).items():
        why[row.run_id] = f"best {model} run"
    for run_id in sorted(finalists):
        why.setdefault(run_id, "finalist")
    active = active_run_id()
    if active:
        why.setdefault(active, "run in progress (holds the GPU lock)")

    already_gone: list[str] = []
    for row in rows:
        if not _owns_adapter(row) or not _valid_run_id(row.run_id):
            continue
        if row.run_id not in folders and row.run_id not in already_gone:
            already_gone.append(row.run_id)

    keep = [run_id for run_id in folders if run_id in why]
    delete = [folder for run_id, folder in folders.items() if run_id not in why]
    return PrunePlan(
        delete=delete,
        keep=keep,
        already_gone=already_gone,
        why_kept={run_id: why[run_id] for run_id in keep},
    )


def _delete_folder(folder: Path, root: Path) -> None:
    """Delete one adapter folder after checking again that it lies directly under root."""
    if folder.is_symlink() or not folder.is_dir() or folder.resolve().parent != root:
        raise OSError(f"Refusing to delete {folder}: not an adapter folder directly under {root}")
    shutil.rmtree(folder)


def run_prune(args: argparse.Namespace) -> int:
    results = Path(args.results) if args.results is not None else paths.DEFAULT_RESULTS
    finalists_path = Path(args.finalists) if args.finalists is not None else FINALISTS_DEFAULT
    checkpoints = paths.checkpoints_root()
    try:
        finalists = read_finalists(finalists_path)
        rows, skipped = read_rows(results)
    except (ValueError, OSError) as exc:
        print(f"Prune stopped, nothing deleted: {exc}", file=sys.stderr)
        return EXIT_FAILED
    if skipped:
        print(f"Skipped {skipped} malformed row(s) in {results}", file=sys.stderr)

    plan = plan_prune(rows, finalists, checkpoints)

    for run_id in plan.keep:
        print(f"Keep {run_id}: {plan.why_kept.get(run_id, '')}")
    for run_id in plan.already_gone:
        print(f"Skip {run_id}: already pruned (no folder in {checkpoints})")

    if not args.yes:
        for folder in plan.delete:
            print(f"Would delete {folder} (run {folder.name})")
        print(
            f"Nothing deleted: {len(plan.delete)} adapter folder(s) would be deleted; "
            "run again with --yes to delete them."
        )
        return EXIT_FINISHED

    root = checkpoints.resolve()
    failed = 0
    for folder in plan.delete:
        try:
            _delete_folder(folder, root)
        except OSError as exc:
            failed += 1
            print(f"Could not delete {folder} (run {folder.name}): {exc}", file=sys.stderr)
        else:
            print(f"Deleted {folder} (run {folder.name})")
    print(f"Deleted {len(plan.delete) - failed} adapter folder(s); kept {len(plan.keep)}.")
    return EXIT_FAILED if failed else EXIT_FINISHED


def register(subparsers) -> None:
    parser = subparsers.add_parser(
        "prune",
        help="delete old adapters, keeping each model's best run and every finalist",
        description=(
            "List the adapter folders under checkpoints/ that are neither a model's best dev run, "
            "a finalist nor the run in progress; with --yes, delete them. The run log is never changed."
        ),
    )
    parser.add_argument("--yes", action="store_true", help="delete the listed folders")
    parser.add_argument("--results", type=Path, help="run log to read (default results/runs.csv)")
    parser.add_argument("--finalists", type=Path, help="finalists file (default results/finalists.json)")
    parser.set_defaults(func=run_prune)
