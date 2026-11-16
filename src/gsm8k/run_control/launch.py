"""Starting a run in two steps (US3.2, US3.6; contracts C2, C3, C5).

``check_run`` checks the dials, refuses what may not run (an invalid dial with its range, AC3.2.4; the
test split for training or tuning, AC3.6.4; a test-split evaluation of a run that is not a finalist,
AC3.6.2, AC3.6.5), picks the attempt id (AC3.2.3) and returns a summary with the changes against the
last run of the same model and method, the estimate and the exact command. It launches nothing
(AC3.2.1); the checked run is kept in memory under its check id for 10 minutes. ``confirm`` writes
``outputs/<attempt_id>/config.json`` and adds the run to the queue; the worker (``gsm8k worker``)
launches it as its own process when the GPU lock is free (AC3.2.2, AC3.3.1, AC3.7.1). A test-split
evaluation needs a second confirmation (AC3.6.3).

``build_argv`` is the C5 command line of a launch, always an argument list built from the project's own
entry points (AC3.2.5). It is read as a module attribute at call time, so tests can point it at a stub.
This module never imports training or evaluation code (ADR-006).
"""

import json
import math
import shlex
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from gsm8k import estimates, run_config
from gsm8k.estimates import Estimate
from gsm8k.run_control import finalists, queue, runs
from gsm8k.run_records import paths
from gsm8k.run_records.folder import atomic_write_text
from gsm8k.run_records.lock import is_free
from gsm8k.run_records.log import read_rows

KINDS = ("train", "evaluate")  # the kinds ``check_run`` accepts (/runs/check)
COT_KIND = "cot-generate"  # c22's cotgen run (u12): launched by the worker only, never checked as a run
LAUNCH_KINDS = (*KINDS, COT_KIND)
CHECK_TTL_SECONDS = 600.0  # C6: a check expires after 10 minutes
SECOND_CONFIRMATION_MESSAGE = "A test-split evaluation needs a second confirmation"
# Problems per evaluation split, for the estimate when no limit is set.
SPLIT_SIZES = {"dev": 500, "test": 1319, "gsmplus-testmini": 2400, "gsmsym-p1": 5000}
# The split part of a C1 base id ("<model>-<method>-<split>"); the harness evaluator scores test as "harness".
_SPLIT_IDS = {"dev": "dev", "test": "test", "gsmplus-testmini": "gsmplus", "gsmsym-p1": "gsmsym"}
_MODEL_IDS = {"Qwen/Qwen3-0.6B-Base": "q06", "Qwen/Qwen3-1.7B-Base": "q17"}
# Fields that never count as a change (C2: the identity of the attempt and the schema version).
_NOT_COMPARED = ("run_id", "v")


class UnknownCheck(LookupError):
    """No checked run has this check id; nothing is launched (AC3.2.4)."""


class CheckExpired(LookupError):
    """The checked run is older than 10 minutes, or its attempt id was taken since; check again (C6)."""


class SecondConfirmationNeeded(ValueError):
    """A test-split evaluation was confirmed without the second confirmation; nothing is queued (AC3.6.3)."""

    def __init__(self, message: str = SECOND_CONFIRMATION_MESSAGE):
        super().__init__(message)


@dataclass
class CheckedRun:
    check_id: str
    attempt_id: str
    model: str
    method: str
    command: str
    argv: list[str]
    estimate: Estimate
    changes: dict
    config: dict
    kind: str = "evaluate"
    needs_second_confirmation: bool = False
    test_confirmed: bool = False
    results: Path | None = None
    finalists: Path | None = None
    outputs: Path | None = None
    created: float = field(default_factory=time.monotonic)


@dataclass
class ConfirmResult:
    attempt_id: str
    state: (
        str  # "started" (the worker starts it now: the lock is free and nothing waits before it) or "queued"
    )
    position: int


_checks: dict[str, CheckedRun] = {}
_checks_lock = threading.Lock()


def build_argv(kind: str, attempt_id: str, config_path: Path, results: Path) -> list[str]:
    """The C5 launch command: ``python -m gsm8k <kind> --config ... --run-id ... --results ...
    --started-by worker`` as an argument list, never a shell string (AC3.2.5)."""
    if kind not in LAUNCH_KINDS:
        raise ValueError(f"kind must be one of {', '.join(LAUNCH_KINDS)}, got {kind!r}")
    return [
        sys.executable,
        "-m",
        "gsm8k",
        kind,
        "--config",
        str(config_path),
        "--run-id",
        attempt_id,
        "--results",
        str(results),
        "--started-by",
        "worker",
    ]


def kind_for_method(method: str) -> str:
    """``train`` for a training or tuning method (``run_config.TRAINING_METHODS``), ``cot-generate`` for the
    self-taught reasoning generation (``cotgen``), else ``evaluate``."""
    if method == run_config.COT_METHOD:
        return COT_KIND
    return "train" if method in run_config.TRAINING_METHODS else "evaluate"


def base_id(cfg: run_config.RunConfig) -> str:
    """The C1 base id ``<model>-<method>-<split>`` of a checked configuration."""
    split = "harness" if cfg.evaluator == "lm-eval-harness" and cfg.split == "test" else _SPLIT_IDS[cfg.split]
    return f"{_MODEL_IDS[cfg.model]}-{cfg.method}-{split}"


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _iso_mtime(path: Path) -> str:
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(path.stat().st_mtime))
    except OSError:
        return ""


def _attempt_number(run_id: str) -> int:
    tail = run_id.rsplit("-", 1)[-1]
    return int(tail) if tail.isdigit() else 0


def _last_config(model: str, method: str, results: Path, outputs: Path, exclude: str) -> dict | None:
    """The config.json of the last run of the same model and method: the run folder whose run ended
    latest (its newest run-log row, else its status.json, else its config.json's time)."""
    row_dates: dict[str, str] = {}
    rows, _ = read_rows(results)
    for row in rows:
        if row.date > row_dates.get(row.run_id, ""):
            row_dates[row.run_id] = row.date
    best: tuple[str, int, str] | None = None
    best_config: dict | None = None
    try:
        folders = [p for p in outputs.iterdir() if p.is_dir() and paths.RUN_ID_PATTERN.fullmatch(p.name)]
    except OSError:
        folders = []
    for folder in folders:
        if folder.name == exclude:
            continue
        config_path = folder / "config.json"
        config = _read_json(config_path)
        if config is None or config.get("model") != model or config.get("method") != method:
            continue
        status = _read_json(folder / "status.json") or {}
        date = row_dates.get(folder.name) or str(status.get("ended_at") or "") or _iso_mtime(config_path)
        key = (date, _attempt_number(folder.name), folder.name)
        if best is None or key > best:
            best, best_config = key, config
    return best_config


def _changes(new: dict, old: dict | None) -> dict:
    """``{field: {"old": ..., "new": ...}}`` for every C2 field that differs (not run_id or v)."""
    if old is None:
        return {}
    return {
        name: {"old": old.get(name), "new": value}
        for name, value in new.items()
        if name not in _NOT_COMPARED and old.get(name) != value
    }


def _estimate(cfg: run_config.RunConfig, kind: str, outputs: Path) -> Estimate:
    if kind == "train":
        examples = run_config.TRAIN_SPLIT_SIZE if cfg.train_examples == "all" else int(cfg.train_examples)
        steps = math.ceil(examples / cfg.batch_size) * cfg.epochs
        return estimates.estimate_training(cfg.model, steps, outputs)
    problems = SPLIT_SIZES.get(cfg.split, SPLIT_SIZES["test"])
    if cfg.limit is not None:
        problems = min(problems, cfg.limit)
    return estimates.estimate_evaluation(cfg.model, problems * max(1, cfg.vote_samples), outputs)


def _check_adapter(cfg: run_config.RunConfig) -> Path | None:
    if cfg.adapter_path is None:
        return None
    try:
        return paths.resolve_adapter(cfg.adapter_path)
    except (FileNotFoundError, ValueError) as exc:
        raise run_config.ConfigError(
            f"adapter_path must be an adapter folder under checkpoints/: {exc}"
        ) from exc


def _check_test_split(cfg: run_config.RunConfig, adapter: Path | None, finalists_path: Path) -> None:
    """A test-split evaluation scores the run named by its adapter folder, which must be a finalist
    (AC3.6.2); an unreadable finalists file blocks it too (AC3.6.5)."""
    if cfg.split != "test":
        return
    if adapter is None:
        raise ValueError(finalists.NOT_A_FINALIST)
    finalists.check_test_split_allowed(adapter.name, finalists_path)


def _prune_expired(now: float) -> None:
    for check_id in [cid for cid, c in _checks.items() if now - c.created > CHECK_TTL_SECONDS]:
        del _checks[check_id]


def check_run(
    dials: dict,
    *,
    kind: str,
    results: Path,
    finalists: Path,
    outputs: Path | None = None,
    test_confirmed: bool = False,
) -> CheckedRun:
    """Step one of a start: check and summarise; launches and writes nothing (AC3.2.1).

    Raises ``run_config.ConfigError`` naming the dial and its range (AC3.2.4) or the test-split rule for
    training and tuning (AC3.6.4), ``ValueError("Only finalists can be scored on the test split")``
    (AC3.6.2) or the unreadable-finalists ``ValueError`` naming the file (AC3.6.5), and ``OSError`` when
    the run log cannot be read.
    """
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {', '.join(KINDS)}, got {kind!r}")
    if not isinstance(dials, dict):
        raise run_config.ConfigError("Dials must be given as a mapping of field names to values")
    given = {name: value for name, value in dials.items() if name != "run_id"}
    cfg = run_config.check_dials(given)
    if kind == "train" and cfg.method not in run_config.TRAINING_METHODS:
        listed = ", ".join(run_config.TRAINING_METHODS)
        raise run_config.ConfigError(f"method must be one of {listed} for a training run, got {cfg.method!r}")
    adapter = _check_adapter(cfg)
    _check_test_split(cfg, adapter, Path(finalists))

    outputs_path = Path(outputs) if outputs is not None else paths.outputs_root()
    results = Path(results)
    waiting = [entry.attempt_id for entry in queue.list_queue(outputs_path)]
    attempt_id = runs.next_attempt_id(base_id(cfg), results, outputs_path, queue_ids=waiting)
    cfg.run_id = attempt_id
    config = run_config.to_dict(cfg)

    previous = _last_config(cfg.model, cfg.method, results, outputs_path, exclude=attempt_id)
    argv = build_argv(kind, attempt_id, outputs_path / attempt_id / "config.json", results)
    checked = CheckedRun(
        check_id=uuid.uuid4().hex,
        attempt_id=attempt_id,
        model=cfg.model,
        method=cfg.method,
        command=shlex.join(argv),
        argv=list(argv),
        estimate=_estimate(cfg, kind, outputs_path),
        changes=_changes(config, previous),
        config=config,
        kind=kind,
        needs_second_confirmation=cfg.split == "test",
        test_confirmed=test_confirmed,
        results=results,
        finalists=Path(finalists),
        outputs=outputs_path,
    )
    with _checks_lock:
        _prune_expired(time.monotonic())
        _checks[checked.check_id] = checked
    return checked


def get_check(check_id: str) -> CheckedRun:
    """The checked run with this id; ``UnknownCheck`` or ``CheckExpired`` (both ``LookupError``)."""
    with _checks_lock:
        checked = _checks.get(check_id)
        if checked is None:
            raise UnknownCheck(f"No checked run with this id: {check_id}")
        if time.monotonic() - checked.created > CHECK_TTL_SECONDS:
            del _checks[check_id]
            raise CheckExpired("The check is older than 10 minutes; check the run again")
    return checked


def confirm(check_id: str, *, second_confirmation: bool = False) -> ConfirmResult:
    """Step two: write ``outputs/<attempt_id>/config.json`` and queue the checked run (AC3.2.2,
    AC3.7.1); the worker starts it as soon as the GPU lock is free and nothing waits before it.

    Launches and queues nothing when the check id is unknown or expired (``LookupError``, AC3.2.4), for a
    test-split evaluation without the second confirmation (``SecondConfirmationNeeded``, AC3.6.3) or a run
    that is no longer a finalist (``ValueError``), or when the queue is full (``queue.QueueFull``, AC3.7.3).
    """
    checked = get_check(check_id)
    if checked.needs_second_confirmation:
        if not (second_confirmation or checked.test_confirmed):
            raise SecondConfirmationNeeded()
        cfg = run_config.from_dict(checked.config)  # the finalist may have been unmarked since the check
        _check_test_split(cfg, _check_adapter(cfg), checked.finalists)

    outputs_path = checked.outputs if checked.outputs is not None else paths.outputs_root()
    attempt_id = checked.attempt_id
    waiting = queue.list_queue(outputs_path)
    if len(waiting) >= queue.MAX_WAITING:
        raise queue.QueueFull()
    run_folder = outputs_path / attempt_id
    if any(entry.attempt_id == attempt_id for entry in waiting) or run_folder.exists():
        with _checks_lock:
            _checks.pop(check_id, None)
        raise CheckExpired(f"Attempt id {attempt_id} was taken since the check; check the run again")

    run_folder.mkdir(parents=True)
    config_path = run_folder / "config.json"
    atomic_write_text(config_path, json.dumps(checked.config, indent=2, ensure_ascii=False) + "\n")
    try:
        entry = queue.add(attempt_id, checked.config, kind=checked.kind, outputs=outputs_path)
    except BaseException:
        config_path.unlink(missing_ok=True)
        try:
            run_folder.rmdir()
        except OSError:
            pass
        raise
    with _checks_lock:
        _checks.pop(check_id, None)

    free = is_free(outputs_path / "run.lock")
    state = "started" if free and entry.position == 1 else "queued"
    return ConfirmResult(attempt_id=attempt_id, state=state, position=entry.position)
