"""Run status (US3.3, US3.5; contract C3): the overall status from the GPU lock and one run's status
from its folder.

The overall state is RUNNING while a process holds the lock, else IDLE. A free lock whose content still
names a run without ``status.json`` means that run's process ended without finishing: the state reads
IDLE and ``last_run`` holds that run as FAILED (AC3.3.3). This module never imports training or
evaluation code (ADR-006).
"""

import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from gsm8k.run_records.lock import is_free, read_lock
from gsm8k.run_records.paths import RUN_ID_PATTERN, outputs_root

IDLE = "IDLE"
RUNNING = "RUNNING"
FAILED = "FAILED"
STOPPED = "STOPPED"
FINISHED = "FINISHED"
STATES = (IDLE, RUNNING, FAILED, STOPPED, FINISHED)

LOG_TAIL_LINES = 20
ENDED_WITHOUT_FINISHING = "The run process ended without finishing"
GPU_OUT_OF_MEMORY = "GPU out of memory"
_OOM_MARKERS = ("CUDA out of memory", "OutOfMemoryError")
_STATUS_STATES = {"finished": FINISHED, "stopped": STOPPED, "failed": FAILED}


@dataclass
class RunStatus:
    state: str
    run_id: str | None
    reason: str | None = None
    log_tail: list[str] = field(default_factory=list)
    started_at: str | None = None
    last_run: "RunStatus | None" = None


def _outputs(outputs: Path | None) -> Path:
    return Path(outputs) if outputs is not None else outputs_root()


def _read_log(path: Path) -> tuple[list[str], bool, str | None]:
    """(last 20 lines without newlines, whether any line reports CUDA out of memory, error text).

    A missing log is an empty log (a run started from a terminal writes none); any other read error
    gives "Run log could not be read: <path>" (AC3.5.3).
    """
    tail: deque[str] = deque(maxlen=LOG_TAIL_LINES)
    out_of_memory = False
    try:
        with path.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                text = line.rstrip("\r\n")
                tail.append(text)
                if not out_of_memory and any(marker in text for marker in _OOM_MARKERS):
                    out_of_memory = True
    except FileNotFoundError:
        return [], False, None
    except OSError:
        return list(tail), out_of_memory, f"Run log could not be read: {path}"
    return list(tail), out_of_memory, None


def _lock_state(outputs: Path) -> tuple[bool, dict | None]:
    path = outputs / "run.lock"
    return not is_free(path), read_lock(path)


def current_status(outputs: Path | None = None) -> RunStatus:
    """The overall status: RUNNING with the lock holder's run id (AC3.3.4), else IDLE; ``last_run``
    is the run the free lock still names, FAILED with "The run process ended without finishing" when
    it has no status.json (AC3.3.3), else its own status."""
    outputs = _outputs(outputs)
    held, content = _lock_state(outputs)
    run_id = content.get("run_id") if content else None
    started_at = content.get("started_at") if content else None
    if not isinstance(run_id, str) or not RUN_ID_PATTERN.fullmatch(run_id):
        run_id = None

    if held:
        tail: list[str] = []
        if run_id is not None:
            tail, _, _ = _read_log(outputs / run_id / "run.log")
        return RunStatus(state=RUNNING, run_id=run_id, log_tail=tail, started_at=started_at)

    last_run = None
    if run_id is not None:
        if (outputs / run_id / "status.json").exists():
            last_run = run_status(run_id, outputs)
        else:
            tail, _, _ = _read_log(outputs / run_id / "run.log")
            last_run = RunStatus(
                state=FAILED,
                run_id=run_id,
                reason=ENDED_WITHOUT_FINISHING,
                log_tail=tail,
                started_at=started_at,
            )
    return RunStatus(state=IDLE, run_id=None, last_run=last_run)


def run_status(run_id: str, outputs: Path | None = None) -> RunStatus:
    """One run's status from ``outputs/<run_id>/status.json`` and its ``run.log``.

    Status ``failed`` or a nonzero exit code (other than a stop) is FAILED with the reason and the last
    20 log lines (AC3.5.1); a CUDA out-of-memory line in the log makes the reason "GPU out of memory"
    (AC3.5.2); an unreadable log makes it "Run log could not be read: <path>" (AC3.5.3); ``stopped`` is
    STOPPED (AC3.4.1). Without status.json the run is RUNNING while it holds the lock, FAILED when the
    free lock still names it (AC3.3.3), else IDLE (not started yet). Raises ``ValueError`` for an
    invalid run id and ``LookupError`` when the run has no folder.
    """
    if not isinstance(run_id, str) or not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError(f"Invalid run id: {run_id!r}")
    outputs = _outputs(outputs)
    folder = outputs / run_id
    if not folder.is_dir():
        raise LookupError(f"Run not found: {run_id}")

    held, content = _lock_state(outputs)
    names_this_run = bool(content) and content.get("run_id") == run_id
    started_at = content.get("started_at") if names_this_run else None
    tail, out_of_memory, log_error = _read_log(folder / "run.log")

    status_path = folder / "status.json"
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        status = None
    except (OSError, UnicodeDecodeError, ValueError):
        return RunStatus(
            state=FAILED,
            run_id=run_id,
            reason=f"Run status could not be read: {status_path}",
            log_tail=tail,
            started_at=started_at,
        )
    if status is not None and not isinstance(status, dict):
        return RunStatus(
            state=FAILED,
            run_id=run_id,
            reason=f"Run status could not be read: {status_path}",
            log_tail=tail,
            started_at=started_at,
        )

    if status is None:
        if held and names_this_run:
            state, reason = RUNNING, None
        elif names_this_run:
            state, reason = FAILED, ENDED_WITHOUT_FINISHING
        else:
            state, reason = IDLE, None
        if log_error is not None:
            reason = log_error
        return RunStatus(state=state, run_id=run_id, reason=reason, log_tail=tail, started_at=started_at)

    exit_code = status.get("exit_code")
    state = _STATUS_STATES.get(status.get("status"))
    if state is None:
        state = FINISHED if exit_code == 0 else FAILED
    elif state == FINISHED and isinstance(exit_code, int) and exit_code != 0:
        state = FAILED
    reason = status.get("reason") if isinstance(status.get("reason"), str) else None
    if state == FAILED and out_of_memory:
        reason = GPU_OUT_OF_MEMORY
    if log_error is not None:
        reason = log_error
    return RunStatus(state=state, run_id=run_id, reason=reason, log_tail=tail, started_at=started_at)
