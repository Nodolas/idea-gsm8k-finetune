"""The run-queue worker, ``gsm8k worker`` (US3.7, US3.3; contracts C3, C5; ADR-004, ADR-006).

A loop: when the GPU lock is free and the queue has a head, launch the head with
``launch.build_argv`` as its own process in a new session (so it outlives the worker, the service
and the browser, AC3.2.2), with its output appended to ``outputs/<attempt_id>/run.log``. Then wait
until that process holds the lock and only then remove the queue entry (C3). A launch that exits 3
(another run took the lock first, for example one started from the terminal) leaves the entry at the
head, and the worker waits until the lock is free again (AC3.7.6). Any other exit before the lock was
seen held also removes the entry, so a broken run never blocks the queue; when that run wrote no
``status.json``, the worker writes one (failed, or stopped for SIGTERM or SIGINT) naming the exit code.
After a run ends, the next waiting run starts (AC3.7.2).

Course runs (u12): an entry with ``results`` ``outputs/course/runs.csv`` launches with ``--results
<outputs root>/course/runs.csv``. An entry with ``after`` waits (and so do the entries behind it) until that
attempt has a row in the entry's results file; when that attempt failed or was stopped, or finished with no
row, the entry is removed and a line naming both ids is appended to ``outputs/queue/queue.log`` (AC12.3.3).

This PC's GPU is shared with other projects (charter rule 3: one GPU run at a time across projects).
Before it launches the head, the worker runs ``scripts/run-detached.sh --check``: while another long run
or a GPU process is on this PC (exit 3), or nvidia-smi fails (exit 4), it launches nothing, logs what holds
the GPU once and checks again at most every ``GPU_RECHECK_SECONDS`` (AC3.7.7). A check that cannot run
leaves the lock to decide.

The worker never imports training or evaluation code; runs are separate ``gsm8k`` processes (ADR-006).
"""

import json
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from gsm8k._env import ROOT
from gsm8k.run_control import launch
from gsm8k.run_control import queue as run_queue
from gsm8k.run_records import folder
from gsm8k.run_records.lock import is_free, read_lock
from gsm8k.run_records.log import read_rows
from gsm8k.run_records.paths import DEFAULT_RESULTS, outputs_root

EXIT_LOCKED = 3
EXIT_STOPPED = 130
# How often a fresh launch is checked for holding the lock: short, so the queue entry goes away as soon
# as the run holds the lock (C3). The wait is bounded by LAUNCH_TIMEOUT_SECONDS.
HOLD_POLL_SECONDS = 0.002
LAUNCH_TIMEOUT_SECONDS = 900.0
# After a launch holds the lock (and its entry is gone), the step watches it this long before it returns,
# so a run that dies at once is not reported as started.
SETTLE_SECONDS = 0.2
# scripts/run-detached.sh --check (AC3.7.7): 3 = another long run or GPU process is on this PC,
# 4 = nvidia-smi failed (a check that times out counts as 4).
GPU_CHECK = ROOT / "scripts" / "run-detached.sh"
EXIT_GPU_BUSY = 3
EXIT_GPU_CHECK_FAILED = 4
GPU_CHECK_TIMEOUT_SECONDS = 30.0
# While the GPU is busy the check (pgrep and nvidia-smi) runs at most this often.
GPU_RECHECK_SECONDS = 10.0


def run_gpu_check() -> tuple[int, str]:
    """``scripts/run-detached.sh --check`` (AC3.7.7): ``(0, "")`` when no other long run or GPU process is on
    this PC, ``(3, <its busy lines>)`` when one is, ``(4, <message>)`` when nvidia-smi failed or the check
    timed out (a hung nvidia-smi), and ``(-1, <why>)`` when the check cannot run at all."""
    try:
        done = subprocess.run(
            [str(GPU_CHECK), "--check"],
            cwd=str(ROOT),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=GPU_CHECK_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return EXIT_GPU_CHECK_FAILED, f"GPU check timed out after {GPU_CHECK_TIMEOUT_SECONDS:g} s"
    except OSError as exc:
        return -1, f"GPU check could not run: {exc}"
    return done.returncode, done.stderr.strip() or done.stdout.strip()


# Read as a module attribute at call time, so tests can point it at a stub (like launch.build_argv).
gpu_check = run_gpu_check


@dataclass
class _Launch:
    attempt_id: str
    process: subprocess.Popen
    run_dir: Path


class Worker:
    """One worker's state: the launch it waits on and the child processes it still has to reap."""

    def __init__(self, outputs: Path | None = None, results: Path | None = None):
        self.explicit_outputs = outputs is not None
        self.outputs = Path(outputs) if outputs is not None else outputs_root()
        self.results = Path(results) if results is not None else DEFAULT_RESULTS
        self.pending: _Launch | None = None
        self.children: list[subprocess.Popen] = []
        self.stopping = threading.Event()
        self.gpu_recheck_at = 0.0  # time.monotonic() before which a busy GPU is not checked again
        self.gpu_note: str | None = None  # the last GPU message logged, so the same one is logged once

    @property
    def lock_file(self) -> Path:
        return self.outputs / "run.lock"

    def _holds_lock(self, attempt_id: str) -> bool:
        if is_free(self.lock_file):
            return False
        content = read_lock(self.lock_file)
        return bool(content) and content.get("run_id") == attempt_id

    def _reap(self) -> None:
        self.children = [child for child in self.children if child.poll() is None]

    def _launch(self, entry: run_queue.QueueEntry) -> _Launch | None:
        attempt_id = entry.attempt_id
        kind = (
            entry.kind
            if entry.kind in launch.LAUNCH_KINDS
            else launch.kind_for_method(entry.config.get("method"))
        )
        run_dir = self.outputs / attempt_id
        run_dir.mkdir(parents=True, exist_ok=True)
        config_path = run_dir / "config.json"
        if not config_path.exists():  # an entry added without confirm: the worker writes its config.json
            text = json.dumps(entry.config, indent=2, ensure_ascii=False) + "\n"
            folder.atomic_write_text(config_path, text)
        argv = launch.build_argv(kind, attempt_id, config_path, self._results_for(entry))
        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"
        if self.explicit_outputs:
            env["GSM8K_OUTPUTS_DIR"] = str(self.outputs)
        log_fd = os.open(run_dir / "run.log", os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            process = subprocess.Popen(
                argv,
                shell=False,
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=log_fd,
                stderr=subprocess.STDOUT,
                cwd=str(ROOT),
                env=env,
            )
        except OSError as exc:
            print(f"Run {attempt_id} could not be launched: {exc}", file=sys.stderr)
            return None
        finally:
            os.close(log_fd)
        self.children.append(process)
        print(f"Launched {attempt_id} (pid {process.pid}): {kind}", file=sys.stderr)
        return _Launch(attempt_id=attempt_id, process=process, run_dir=run_dir)

    def _results_for(self, entry: run_queue.QueueEntry) -> Path:
        """The run log a launched entry appends to: the course file for the course value, else the default."""
        if entry.results == run_queue.COURSE_RESULTS:
            return self.outputs / "course" / "runs.csv"
        return self.results

    def _has_row(self, results: Path, attempt_id: str) -> bool:
        try:
            rows, _ = read_rows(results)
        except OSError as exc:
            print(f"Run log could not be read, the entry keeps waiting: {exc}", file=sys.stderr)
            return False
        return any(row.run_id == attempt_id for row in rows)

    def _after_state(self, entry: run_queue.QueueEntry) -> str | None:
        """None when the entry may launch; ``"wait"`` while its ``after`` attempt has no row and has not ended
        badly; otherwise the reason the entry is removed (AC12.3.3)."""
        after = entry.after
        if not after:
            return None
        if self._has_row(self._results_for(entry), after):
            return None
        status = None
        try:
            data = json.loads((self.outputs / after / "status.json").read_text(encoding="utf-8"))
            status = data.get("status") if isinstance(data, dict) else None
        except (OSError, UnicodeDecodeError, ValueError):
            pass
        if status in ("failed", "stopped"):
            return f"that run {status}"
        if status == "finished":
            return "that run finished without a result row"
        return "wait"

    def _head_ready(self) -> run_queue.QueueEntry | None:
        """The head of the queue when it may launch now; entries whose ``after`` attempt ended without a row
        are removed first (with a queue.log line). A head still waiting for its ``after`` attempt blocks the
        ones behind it."""
        while True:
            head = run_queue.peek_head(self.outputs)
            if head is None:
                return None
            state = self._after_state(head)
            if state is None:
                return head
            if state == "wait":
                return None
            message = f"Removed {head.attempt_id} from the queue: it waited for {head.after}, but {state}"
            run_queue.append_log(message, self.outputs)
            print(message, file=sys.stderr)
            self._remove_entry(head.attempt_id)

    def _gpu_free(self) -> bool:
        """AC3.7.7: no other long run or GPU process is on this PC, so the head may start."""
        now = time.monotonic()
        if now < self.gpu_recheck_at:
            return False
        code, text = gpu_check()
        if code in (EXIT_GPU_BUSY, EXIT_GPU_CHECK_FAILED):
            self.gpu_recheck_at = now + GPU_RECHECK_SECONDS
            if text != self.gpu_note:
                print(f"The GPU is not free; the next run waits at the head: {text}", file=sys.stderr)
            self.gpu_note = text
            return False
        self.gpu_recheck_at = 0.0
        note = None if code == 0 else f"GPU check failed (exit {code}); the lock alone decides: {text}"
        if note is not None and note != self.gpu_note:
            print(note, file=sys.stderr)
        self.gpu_note = note
        return True

    def _remove_entry(self, attempt_id: str) -> None:
        try:
            run_queue.remove(attempt_id, outputs=self.outputs)
        except LookupError:  # removed meanwhile
            pass

    def _ended_early(self, pending: _Launch, code: int) -> None:
        """The launch exited before it was seen holding the lock (exit code not 3)."""
        self._remove_entry(pending.attempt_id)
        if (pending.run_dir / "status.json").exists():
            return  # the run held the lock briefly and recorded its own end
        stopped = code in (EXIT_STOPPED, -signal.SIGTERM, -signal.SIGINT)
        reason = f"The run process exited with code {code} before it started; see run.log"
        folder.write_status(
            pending.run_dir,
            run_id=pending.attempt_id,
            status="stopped" if stopped else "failed",
            exit_code=EXIT_STOPPED if stopped else (code if code > 0 else 1),
            reason=reason,
        )
        print(f"Run {pending.attempt_id} ended with code {code} before it held the lock", file=sys.stderr)

    def _settle(self, started: _Launch) -> None:
        settle_end = time.monotonic() + SETTLE_SECONDS
        while time.monotonic() < settle_end and not self.stopping.is_set():
            if started.process.poll() is not None:
                return
            time.sleep(HOLD_POLL_SECONDS * 10)

    def _wait_pending(self, timeout: float) -> None:
        """Wait (bounded) until the pending launch holds the lock or exits, and settle its queue entry."""
        pending = self.pending
        if pending is None:
            return
        deadline = time.monotonic() + timeout
        while True:
            if self._holds_lock(pending.attempt_id):
                self._remove_entry(pending.attempt_id)  # C3: only now does the entry leave the queue
                self.pending = None
                self._settle(pending)
                return
            code = pending.process.poll()
            if code is not None:
                self.pending = None
                if code == EXIT_LOCKED:  # AC3.7.6: back at the head; wait for the lock
                    print(
                        f"Run {pending.attempt_id} found the lock held; it waits at the head", file=sys.stderr
                    )
                else:
                    self._ended_early(pending, code)
                return
            if time.monotonic() >= deadline or self.stopping.is_set():
                return
            time.sleep(HOLD_POLL_SECONDS)

    def step(self, timeout: float = LAUNCH_TIMEOUT_SECONDS) -> None:
        """One step: settle a pending launch, or launch the queue head when the lock and the GPU are free."""
        self._reap()
        if self.pending is None:
            if not is_free(self.lock_file):
                return
            head = self._head_ready()
            if head is None:
                return
            if not self._gpu_free():  # AC3.7.7: another project's run, or other GPU use
                return
            self.pending = self._launch(head)
        self._wait_pending(timeout)


def run_worker(
    *,
    outputs: Path | None = None,
    results: Path | None = None,
    poll_seconds: float = 1.0,
    once: bool = False,
) -> int:
    """Start queued runs one at a time while the GPU lock is free and no other long run or GPU process is
    on this PC (AC3.7.7); ``once`` does a single step (tests).

    Returns 0 when stopped by SIGTERM or SIGINT (the runs it launched keep going).
    """
    worker = Worker(outputs=outputs, results=results)
    if once:
        worker.step()
        return 0

    previous = None
    if threading.current_thread() is threading.main_thread():

        def _on_term(signum, frame):
            worker.stopping.set()

        previous = signal.signal(signal.SIGTERM, _on_term)
    print(f"Worker started: queue {run_queue.queue_dir(worker.outputs)}", file=sys.stderr)
    try:
        while not worker.stopping.is_set():
            try:
                worker.step()
            except Exception as exc:  # a long-lived loop: report and carry on
                print(f"Worker step failed: {exc}", file=sys.stderr)
            worker.stopping.wait(poll_seconds)
    except KeyboardInterrupt:
        pass
    finally:
        if previous is not None:
            signal.signal(signal.SIGTERM, previous)
    print("Worker stopped", file=sys.stderr)
    return 0
