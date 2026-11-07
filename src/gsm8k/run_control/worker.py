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
            entry.kind if entry.kind in launch.KINDS else launch.kind_for_method(entry.config.get("method"))
        )
        run_dir = self.outputs / attempt_id
        run_dir.mkdir(parents=True, exist_ok=True)
        config_path = run_dir / "config.json"
        if not config_path.exists():  # an entry added without confirm: the worker writes its config.json
            text = json.dumps(entry.config, indent=2, ensure_ascii=False) + "\n"
            folder.atomic_write_text(config_path, text)
        argv = launch.build_argv(kind, attempt_id, config_path, self.results)
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
        """One step: settle a pending launch, or launch the queue head when the lock is free."""
        self._reap()
        if self.pending is None:
            if not is_free(self.lock_file):
                return
            head = run_queue.peek_head(self.outputs)
            if head is None:
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
    """Start queued runs one at a time while the GPU lock is free; ``once`` does a single step (tests).

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
