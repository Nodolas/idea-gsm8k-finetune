"""Queue, launch, worker and stop of u4-run-service, part H2 (US3.2, US3.3, US3.4, US3.6, US3.7; C3-C5).

Launched runs are stubs: a tiny Python script written by each test into its temp folder. It takes the
C5 arguments (`<kind> --config --run-id --results --started-by`), holds the GPU lock through
`gsm8k.run_records.lock.GpuLock` like a real run, writes a metrics line, and waits until the test drops
a release marker (then appends one row to the temp results file, writes status finished and exits 0).
SIGTERM writes status stopped/130 and exits 130; a held lock exits 3. The stub is reached by pointing
`gsm8k.run_control.launch.build_argv` at it: the wrapper keeps the real builder's C5 arguments and only
swaps `python -m gsm8k` for the stub script.

Every test uses `tmp_project_dirs` and temp results and finalists files; nothing touches the project's
outputs/, checkpoints/, results/runs.csv or results/finalists.json, and no model loads. Every wait is
bounded, `run_worker(once=True)` always runs in a daemon thread with a timeout, and the fixture kills
leftover stub processes. The `gsm8k.run_control` modules are imported inside each test, so a missing
module fails each test on its own.

Assumptions: the test-split evaluation of a run has method `best` and names that run through its
adapter folder `checkpoints/<run_id>` (batch-3 Settled details, BR4.7); `confirm` returns an object with C6's
`attempt_id`, `state` and `position`; queue positions are compared relatively ("move up one place").
"""

import json
import os
import signal
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

from gsm8k._env import CACHE_DIRS, ROOT
from gsm8k.run_config import ConfigError, RunConfig, check_dials, to_dict
from gsm8k.run_records.folder import write_config
from gsm8k.run_records.lock import GpuLock, is_free, read_lock
from gsm8k.run_records.log import RunRow, append_row, read_rows

Q06 = "Qwen/Qwen3-0.6B-Base"
EVAL_DIALS = {"method": "base", "split": "dev", "limit": 5}
STEP_TIMEOUT = 20.0
WAIT_TIMEOUT = 10.0


# --- helpers --------------------------------------------------------------------------------------


def _wait_until(predicate, timeout: float = WAIT_TIMEOUT, what: str = "condition") -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    pytest.fail(f"Timed out after {timeout:.0f} s waiting for: {what}")


def _row(run_id: str, method: str = "base", data: str = "gsm8k-dev") -> RunRow:
    return RunRow(
        date="2026-11-01T10:00:00Z",
        run_id=run_id,
        model=Q06,
        method=method,
        data=data,
        metric="accuracy",
        value=0.5,
        minutes=1.0,
        config_hash="0" * 64,
    )


def _write_finalists(path: Path, run_ids: list[str]) -> None:
    content = {"v": 1, "finalists": [{"run_id": r, "marked_at": "2026-11-01T10:00:00Z"} for r in run_ids]}
    path.write_text(json.dumps(content), encoding="utf-8")


def _queue_ids() -> list[str]:
    from gsm8k.run_control import queue as run_queue

    return [entry.attempt_id for entry in run_queue.list_queue()]


def _row_ids(results: Path) -> list[str]:
    rows, _ = read_rows(results)
    return [row.run_id for row in rows]


def _lock_holder() -> str | None:
    if is_free():
        return None
    content = read_lock()
    return content.get("run_id") if content else None


def _attempt_dirs_with_status(outputs: Path) -> list[str]:
    return sorted(p.name for p in outputs.iterdir() if (p / "status.json").exists())


STUB_SOURCE = """\
import os
import sys

ROOT = {root!r}
for _name, _rel in {cache_dirs!r}.items():
    os.environ[_name] = os.path.join(ROOT, _rel)
os.environ["GSM8K_OUTPUTS_DIR"] = {outputs!r}

import argparse
import json
import signal
import time
from pathlib import Path

from gsm8k.run_records import folder, lock, log

CONTROL = Path({control!r})
SAFE_BASE = Path({safe_base!r})

parser = argparse.ArgumentParser()
parser.add_argument("kind")
parser.add_argument("--config", required=True)
parser.add_argument("--run-id", required=True)
parser.add_argument("--results", required=True)
parser.add_argument("--started-by", default="terminal")
args, _extra = parser.parse_known_args()
run_id = args.run_id
(CONTROL / (run_id + ".argv.json")).write_text(json.dumps(sys.argv))
(CONTROL / (run_id + ".pid")).write_text(str(os.getpid()))
mode_file = CONTROL / (run_id + ".mode")
mode = mode_file.read_text().strip() if mode_file.exists() else "hold"


def wait_for(path, limit):
    end = time.monotonic() + limit
    while time.monotonic() < end:
        if path.exists():
            return True
        time.sleep(0.02)
    return False


if mode == "delay":
    wait_for(CONTROL / (run_id + ".go"), 20)
run_dir = Path(os.environ["GSM8K_OUTPUTS_DIR"]) / run_id
run_dir.mkdir(parents=True, exist_ok=True)
gpu = lock.GpuLock()
try:
    gpu.acquire(run_id, started_by=args.started_by)
except lock.LockHeld as exc:
    (CONTROL / (run_id + ".exit3")).write_text("1")
    print("A run is already active: %s" % exc.run_id, file=sys.stderr)
    sys.exit(3)


def on_term(signum, frame):
    folder.write_status(run_dir, run_id=run_id, status="stopped", exit_code=130, reason="Stopped by SIGTERM")
    gpu.release()
    os._exit(130)


signal.signal(signal.SIGTERM, signal.SIG_IGN if mode == "ignore_term" else on_term)
with open(run_dir / "metrics.jsonl", "a", encoding="utf-8") as fh:
    fh.write(json.dumps({{"v": 1, "step": 1, "total_steps": 10, "loss": 1.5}}) + "\\n")
(CONTROL / (run_id + ".held")).write_text("1")
wait_for(CONTROL / (run_id + ".release"), 30)
results = Path(args.results).resolve()
if results.is_relative_to(SAFE_BASE):
    log.append_row(
        results,
        log.RunRow(
            date=folder.utc_now(), run_id=run_id, model="Qwen/Qwen3-0.6B-Base", method="base",
            data="gsm8k-dev", metric="accuracy", value=0.5, minutes=0.1, config_hash="0" * 64,
        ),
    )
else:
    (CONTROL / (run_id + ".bad_results")).write_text(str(results))
folder.write_status(run_dir, run_id=run_id, status="finished", exit_code=0, reason=None)
gpu.release()
sys.exit(0)
"""


class StubRuns:
    """Writes the stub run script, points `launch.build_argv` at it, drives the worker and cleans up."""

    def __init__(self, dirs, base: Path, monkeypatch):
        from gsm8k.run_control import launch

        self.dirs = dirs
        self.control = base / "control"
        self.control.mkdir()
        stub_dir = base / "stub"
        stub_dir.mkdir()
        self.script = stub_dir / "stub_run.py"
        self.script.write_text(
            STUB_SOURCE.format(
                root=str(ROOT),
                cache_dirs=dict(CACHE_DIRS),
                outputs=str(dirs.outputs),
                control=str(self.control),
                safe_base=str(base.resolve()),
            ),
            encoding="utf-8",
        )
        self.real_build_argv = launch.build_argv
        script = self.script
        real = self.real_build_argv

        def stub_build_argv(kind, attempt_id, config_path, results):
            argv = real(kind, attempt_id, config_path, results)
            return [sys.executable, str(script), *argv[3:]]

        monkeypatch.setattr(launch, "build_argv", stub_build_argv)
        self.threads: list[threading.Thread] = []

    # control markers
    def set_mode(self, run_id: str, mode: str) -> None:
        (self.control / f"{run_id}.mode").write_text(mode)

    def release(self, run_id: str) -> None:
        (self.control / f"{run_id}.release").write_text("1")

    def go(self, run_id: str) -> None:
        (self.control / f"{run_id}.go").write_text("1")

    def launched(self, run_id: str) -> bool:
        return (self.control / f"{run_id}.argv.json").exists()

    def argv(self, run_id: str) -> list[str]:
        return json.loads((self.control / f"{run_id}.argv.json").read_text())

    def pid(self, run_id: str) -> int:
        return int((self.control / f"{run_id}.pid").read_text())

    def held(self, run_id: str) -> bool:
        return (self.control / f"{run_id}.held").exists() and _lock_holder() == run_id

    def wait_held(self, run_id: str) -> None:
        _wait_until(lambda: self.held(run_id), what=f"{run_id} to hold the lock")

    def finish(self, run_id: str) -> None:
        self.release(run_id)
        _wait_until(is_free, what=f"{run_id} to end and free the lock")

    # worker
    def start_step(self) -> threading.Thread:
        from gsm8k.run_control import worker

        thread = threading.Thread(
            target=worker.run_worker,
            kwargs={
                "outputs": self.dirs.outputs,
                "results": self.dirs.results,
                "poll_seconds": 0.05,
                "once": True,
            },
            daemon=True,
        )
        thread.start()
        self.threads.append(thread)
        return thread

    def step(self) -> None:
        """One worker step that must return (the lock is free or the step does nothing)."""
        thread = self.start_step()
        thread.join(STEP_TIMEOUT)
        assert not thread.is_alive(), "run_worker(once=True) did not return"

    def drive(self, until, what: str) -> None:
        """Run worker steps one after another until `until()` holds (bounded)."""
        deadline = time.monotonic() + STEP_TIMEOUT
        thread: threading.Thread | None = None
        while time.monotonic() < deadline:
            if until():
                return
            if thread is None or not thread.is_alive():
                thread = self.start_step()
            time.sleep(0.05)
        pytest.fail(f"Worker steps did not reach: {what}")

    def cleanup(self) -> None:
        from gsm8k.run_control import queue as run_queue

        qdir = run_queue.queue_dir()
        if qdir.is_dir():
            for entry in qdir.glob("*.json"):
                entry.unlink(missing_ok=True)
        for marker in self.control.glob("*.argv.json"):
            run_id = marker.name[: -len(".argv.json")]
            self.release(run_id)
            self.go(run_id)
        time.sleep(0.1)
        for pid_file in self.control.glob("*.pid"):
            pid = int(pid_file.read_text())
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                pass
        for thread in self.threads:
            thread.join(STEP_TIMEOUT)
        alive = [t for t in self.threads if t.is_alive()]
        bad = list(self.control.glob("*.bad_results"))
        assert not alive, "a run_worker(once=True) thread was still running at teardown"
        assert not bad, f"a stub run got a results path outside the test folder: {bad}"


@pytest.fixture
def stub_runs(tmp_project_dirs, tmp_path, monkeypatch):
    harness = StubRuns(tmp_project_dirs, tmp_path, monkeypatch)
    try:
        yield harness
    finally:
        harness.cleanup()


@pytest.fixture
def finalists_path(tmp_path) -> Path:
    return tmp_path / "results" / "finalists.json"


def _check(dials: dict, dirs, finalists: Path, kind: str = "evaluate"):
    from gsm8k.run_control import launch

    return launch.check_run(dict(dials), kind=kind, results=dirs.results, finalists=finalists)


def _check_and_confirm(dials: dict, dirs, finalists: Path, kind: str = "evaluate"):
    from gsm8k.run_control import launch

    checked = _check(dials, dirs, finalists, kind)
    return checked, launch.confirm(checked.check_id)


def _sft_run_with_adapter(dirs, run_id: str = "q06-sft-dev-1") -> Path:
    """A finished sft run: its row, its config.json and its adapter folder under checkpoints/."""
    append_row(dirs.results, _row(run_id, method="sft"))
    run_folder = dirs.outputs / run_id
    run_folder.mkdir()
    write_config(run_folder, RunConfig(run_id=run_id, method="sft", train_examples=50))
    adapter = dirs.checkpoints / run_id
    adapter.mkdir()
    (adapter / "adapter_config.json").write_text("{}", encoding="utf-8")
    return adapter


# --- US3.2: start a run in two steps ---------------------------------------------------------------


def test_AC3_2_1_check_returns_summary_and_launches_nothing(tmp_project_dirs, finalists_path):
    from gsm8k.estimates import Estimate
    from gsm8k.run_control import launch

    checked = _check(EVAL_DIALS, tmp_project_dirs, finalists_path)

    assert isinstance(checked, launch.CheckedRun)
    assert isinstance(checked.check_id, str) and checked.check_id
    assert checked.attempt_id == "q06-base-dev-1"
    assert checked.model == Q06
    assert checked.method == "base"
    assert isinstance(checked.changes, dict)
    assert isinstance(checked.estimate, Estimate)
    assert isinstance(checked.command, str)
    assert "--run-id" in checked.command and "q06-base-dev-1" in checked.command
    assert isinstance(checked.argv, list) and all(isinstance(a, str) for a in checked.argv)
    assert "q06-base-dev-1" in checked.argv
    assert checked.config["limit"] == 5
    # launches nothing: no queue entry, no run folder, the lock stays free
    assert _queue_ids() == []
    assert not (tmp_project_dirs.outputs / "q06-base-dev-1").exists()
    assert is_free()


def test_AC3_2_1_changes_are_against_the_last_run_of_same_model_and_method(tmp_project_dirs, finalists_path):
    previous = "q06-base-dev-1"
    append_row(tmp_project_dirs.results, _row(previous))
    (tmp_project_dirs.outputs / previous).mkdir()
    write_config(tmp_project_dirs.outputs / previous, RunConfig(run_id=previous, limit=10))

    checked = _check(EVAL_DIALS, tmp_project_dirs, finalists_path)

    assert checked.attempt_id == "q06-base-dev-2"
    assert "limit" in checked.changes
    assert "model" not in checked.changes
    assert "method" not in checked.changes
    assert _queue_ids() == []


def test_AC3_2_2_confirm_launches_separate_process_in_new_session(
    stub_runs, tmp_project_dirs, finalists_path
):
    checked, _ = _check_and_confirm(EVAL_DIALS, tmp_project_dirs, finalists_path)
    attempt = checked.attempt_id
    assert attempt == "q06-base-dev-1"
    config_path = tmp_project_dirs.outputs / attempt / "config.json"
    assert json.loads(config_path.read_text(encoding="utf-8"))["run_id"] == attempt

    stub_runs.drive(lambda: stub_runs.held(attempt), f"{attempt} to hold the lock")

    pid = stub_runs.pid(attempt)
    assert pid != os.getpid()
    assert read_lock()["pid"] == pid
    # its own session: it keeps going when the service (the caller) or the browser goes away
    assert os.getsid(pid) == pid
    assert os.getsid(pid) != os.getsid(0)
    argv = stub_runs.argv(attempt)
    assert argv[argv.index("--run-id") + 1] == attempt
    assert argv[argv.index("--started-by") + 1] == "worker"
    assert Path(argv[argv.index("--config") + 1]).resolve() == config_path.resolve()
    assert Path(argv[argv.index("--results") + 1]).resolve() == tmp_project_dirs.results.resolve()
    # the worker step returned and the run is still going
    time.sleep(0.3)
    assert stub_runs.held(attempt)

    stub_runs.finish(attempt)
    _wait_until(lambda: attempt in _row_ids(tmp_project_dirs.results), what="the stub's row")


def test_AC3_2_3_attempt_id_is_one_more_than_highest(tmp_project_dirs, finalists_path):
    append_row(tmp_project_dirs.results, _row("q06-sft-dev-1", method="sft"))
    append_row(tmp_project_dirs.results, _row("q06-sft-dev-2", method="sft"))
    dials = {"method": "sft", "train_examples": 50}

    checked = _check(dials, tmp_project_dirs, finalists_path, kind="train")
    assert checked.attempt_id == "q06-sft-dev-3"

    # a queued attempt counts too (held lock: nothing launches)
    holder = GpuLock()
    holder.acquire("q06-base-dev-9")
    try:
        from gsm8k.run_control import launch

        launch.confirm(checked.check_id)
        assert _queue_ids() == ["q06-sft-dev-3"]
        assert _check(dials, tmp_project_dirs, finalists_path, kind="train").attempt_id == "q06-sft-dev-4"
    finally:
        holder.release()


def test_AC3_2_4_invalid_dial_is_rejected_with_dial_and_range(tmp_project_dirs, finalists_path):
    with pytest.raises(ConfigError) as exc:
        _check({"method": "sft", "learning_rate": 1.0}, tmp_project_dirs, finalists_path, kind="train")
    message = str(exc.value)
    assert "learning_rate" in message
    assert "0.0005" in message  # the allowed range's upper bound
    with pytest.raises(ConfigError, match="lora_rank"):
        _check({"method": "sft", "lora_rank": 7}, tmp_project_dirs, finalists_path, kind="train")
    with pytest.raises(ConfigError, match="no_such_dial"):
        _check({"no_such_dial": 1}, tmp_project_dirs, finalists_path)
    assert _queue_ids() == []
    assert [p.name for p in tmp_project_dirs.outputs.iterdir() if p.name != "queue"] == []


def test_AC3_2_4_confirm_with_unknown_check_launches_nothing(stub_runs, tmp_project_dirs, finalists_path):
    from gsm8k.run_control import launch

    _check(EVAL_DIALS, tmp_project_dirs, finalists_path)  # a real check exists, but is not named
    try:
        launch.confirm("no-such-check-id")
    except (LookupError, ValueError):
        pass
    assert _queue_ids() == []
    assert not (tmp_project_dirs.outputs / "q06-base-dev-1").exists()
    stub_runs.step()
    assert list(stub_runs.control.glob("*.argv.json")) == []
    assert is_free()


def test_AC3_2_5_build_argv_is_an_argument_list_of_project_entry_points(tmp_path):
    from gsm8k.run_control import launch

    config_path = tmp_path / "x; rm -rf y" / "config.json"
    results = tmp_path / "r && echo z" / "runs.csv"
    for kind in ("train", "evaluate"):
        argv = launch.build_argv(kind, "q06-sft-dev-1", config_path, results)
        assert isinstance(argv, list) and all(isinstance(a, str) for a in argv)
        assert argv[:4] == [sys.executable, "-m", "gsm8k", kind]
        assert argv[argv.index("--config") + 1] == str(config_path)
        assert argv[argv.index("--run-id") + 1] == "q06-sft-dev-1"
        assert argv[argv.index("--results") + 1] == str(results)
        assert argv[argv.index("--started-by") + 1] == "worker"


def test_AC3_2_5_shell_characters_reach_the_run_as_one_argument(
    stub_runs, tmp_project_dirs, tmp_path, finalists_path
):
    victim = tmp_path / "victim"
    victim.write_text("keep", encoding="utf-8")
    weird = tmp_path / f"res; rm -rf {victim.name} ; echo" / "runs.csv"
    weird.parent.mkdir()
    tmp_project_dirs.results = weird  # the worker passes this run log path to the launched run

    checked, _ = _check_and_confirm(EVAL_DIALS, tmp_project_dirs, finalists_path)
    attempt = checked.attempt_id
    stub_runs.drive(lambda: stub_runs.held(attempt), f"{attempt} to hold the lock")

    argv = stub_runs.argv(attempt)
    assert argv[argv.index("--results") + 1] == str(weird)
    stub_runs.finish(attempt)
    _wait_until(lambda: weird.exists() and attempt in _row_ids(weird), what="the row in the odd path")
    assert victim.read_text(encoding="utf-8") == "keep"


# --- US3.3: one GPU run at a time ------------------------------------------------------------------


def test_AC3_3_1_second_start_is_queued_not_launched(stub_runs, tmp_project_dirs, finalists_path):
    first, _ = _check_and_confirm(EVAL_DIALS, tmp_project_dirs, finalists_path)
    stub_runs.drive(lambda: stub_runs.held(first.attempt_id), "the first run to hold the lock")

    second, result = _check_and_confirm(EVAL_DIALS, tmp_project_dirs, finalists_path)
    assert second.attempt_id == "q06-base-dev-2"
    assert result.state == "queued"
    assert _queue_ids() == [second.attempt_id]

    stub_runs.start_step()
    time.sleep(0.6)
    assert not stub_runs.launched(second.attempt_id)
    assert _lock_holder() == first.attempt_id
    assert _queue_ids() == [second.attempt_id]


def test_AC3_3_2_terminal_evaluate_refuses_while_lock_held(tmp_project_dirs, capsys):
    from gsm8k.cli import main

    results = tmp_project_dirs.results
    holder = GpuLock()
    holder.acquire("q06-sft-dev-1", started_by="worker")
    try:
        argv = ["evaluate", "--split", "dev", "--limit", "1", "--run-id", "q06-base-dev-1"]
        rc = main([*argv, "--results", str(results)])
    finally:
        holder.release()
    text = "".join(capsys.readouterr())
    assert rc == 3
    assert "A run is already active" in text
    assert "q06-sft-dev-1" in text
    assert not results.exists()
    assert not (tmp_project_dirs.outputs / "q06-base-dev-1").exists()


# --- US3.4: stop a run -----------------------------------------------------------------------------


def test_AC3_4_1_stop_ends_run_stopped_metrics_kept_no_row(stub_runs, tmp_project_dirs, finalists_path):
    from gsm8k.run_control import stop
    from gsm8k.run_control.status import run_status

    checked, _ = _check_and_confirm(EVAL_DIALS, tmp_project_dirs, finalists_path)
    attempt = checked.attempt_id
    stub_runs.drive(lambda: stub_runs.held(attempt), f"{attempt} to hold the lock")
    run_folder = tmp_project_dirs.outputs / attempt

    message = stop.stop_active(outputs=tmp_project_dirs.outputs, grace_seconds=5.0)
    assert "No run is active" not in message
    _wait_until(is_free, what="the stopped run to free the lock")

    status = json.loads((run_folder / "status.json").read_text(encoding="utf-8"))
    assert status["status"] == "stopped"
    assert status["exit_code"] == 130
    assert run_status(attempt, outputs=tmp_project_dirs.outputs).state == "STOPPED"
    metrics = (run_folder / "metrics.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(metrics) == 1 and json.loads(metrics[0])["step"] == 1
    assert attempt not in _row_ids(tmp_project_dirs.results)


def test_AC3_4_2_lock_free_after_stop_and_new_run_can_start(stub_runs, tmp_project_dirs, finalists_path):
    from gsm8k.run_control import stop

    first, _ = _check_and_confirm(EVAL_DIALS, tmp_project_dirs, finalists_path)
    stub_runs.drive(lambda: stub_runs.held(first.attempt_id), "the first run to hold the lock")
    stop.stop_active(outputs=tmp_project_dirs.outputs, grace_seconds=5.0)
    _wait_until(is_free, what="the lock to be free after stop")

    second, _ = _check_and_confirm(EVAL_DIALS, tmp_project_dirs, finalists_path)
    stub_runs.drive(lambda: stub_runs.held(second.attempt_id), "a new run to start after the stop")
    stub_runs.finish(second.attempt_id)


def test_AC3_4_2_run_ignoring_sigterm_is_killed_after_grace(stub_runs, tmp_project_dirs, finalists_path):
    from gsm8k.run_control import stop

    checked, _ = _check_and_confirm(EVAL_DIALS, tmp_project_dirs, finalists_path)
    attempt = checked.attempt_id
    stub_runs.set_mode(attempt, "ignore_term")
    stub_runs.drive(lambda: stub_runs.held(attempt), f"{attempt} to hold the lock")

    stop.stop_active(outputs=tmp_project_dirs.outputs, grace_seconds=0.5)
    _wait_until(is_free, what="SIGKILL after the grace period to free the lock")
    assert attempt not in _row_ids(tmp_project_dirs.results)
    taker = GpuLock()
    taker.acquire("q06-base-dev-9")
    taker.release()


def test_AC3_4_3_stop_when_idle_says_no_run_is_active(tmp_project_dirs):
    from gsm8k.run_control import stop
    from gsm8k.run_records.lock import lock_path

    assert "No run is active" in stop.stop_active(outputs=tmp_project_dirs.outputs, grace_seconds=0.2)

    # a free lock whose content still names an ended run: still nothing active, nothing changes
    stale = json.dumps(
        {"v": 1, "run_id": "q06-sft-dev-1", "pid": 999999, "started_at": "x", "started_by": "worker"}
    )
    lock_path().write_text(stale + "\n", encoding="utf-8")
    assert "No run is active" in stop.stop_active(outputs=tmp_project_dirs.outputs, grace_seconds=0.2)
    assert lock_path().read_text(encoding="utf-8") == stale + "\n"
    assert _queue_ids() == []


# --- US3.6: finalists only on test -------------------------------------------------------------------


def test_AC3_6_2_test_evaluation_of_non_finalist_is_refused(tmp_project_dirs, finalists_path):
    adapter = _sft_run_with_adapter(tmp_project_dirs)
    dials = {"method": "best", "split": "test", "adapter_path": str(adapter)}

    with pytest.raises((ValueError, ConfigError), match="Only finalists can be scored on the test split"):
        _check(dials, tmp_project_dirs, finalists_path)
    _write_finalists(finalists_path, ["q06-other-dev-1"])
    with pytest.raises((ValueError, ConfigError), match="Only finalists can be scored on the test split"):
        _check(dials, tmp_project_dirs, finalists_path)
    assert _queue_ids() == []


def test_AC3_6_3_finalist_test_evaluation_needs_second_confirmation(
    stub_runs, tmp_project_dirs, finalists_path
):
    from gsm8k.run_control import launch

    adapter = _sft_run_with_adapter(tmp_project_dirs)
    _write_finalists(finalists_path, ["q06-sft-dev-1"])
    dials = {"method": "best", "split": "test", "adapter_path": str(adapter)}

    checked = _check(dials, tmp_project_dirs, finalists_path)
    attempt = checked.attempt_id
    assert attempt == "q06-best-test-1"
    try:
        launch.confirm(checked.check_id)
    except (ValueError, LookupError, PermissionError):
        pass
    assert _queue_ids() == []
    stub_runs.step()
    assert not stub_runs.launched(attempt)

    checked = _check(dials, tmp_project_dirs, finalists_path)
    assert checked.attempt_id == attempt
    launch.confirm(checked.check_id, second_confirmation=True)
    stub_runs.drive(lambda: stub_runs.held(attempt), "the finalist's test evaluation to start")
    stub_runs.finish(attempt)


@pytest.mark.parametrize("method", ["sft", "optuna"])
def test_AC3_6_4_training_or_tuning_on_test_split_is_refused(tmp_project_dirs, finalists_path, method):
    _write_finalists(finalists_path, ["q06-sft-dev-1"])
    with pytest.raises(ConfigError, match="never used for training or tuning"):
        _check(
            {"method": method, "split": "test", "train_examples": 50},
            tmp_project_dirs,
            finalists_path,
            "train",
        )
    assert _queue_ids() == []
    assert [p.name for p in tmp_project_dirs.outputs.iterdir() if p.name != "queue"] == []


# --- US3.7: the queue ------------------------------------------------------------------------------


def test_AC3_7_1_start_while_active_is_queued_with_attempt_id_and_position(
    stub_runs, tmp_project_dirs, finalists_path
):
    from gsm8k.run_control import queue as run_queue

    holder = GpuLock()
    holder.acquire("q06-base-dev-9", started_by="terminal")
    try:
        checked, result = _check_and_confirm(EVAL_DIALS, tmp_project_dirs, finalists_path)
        assert result.attempt_id == checked.attempt_id == "q06-base-dev-1"
        assert result.state == "queued"
        entries = run_queue.list_queue()
        assert [e.attempt_id for e in entries] == ["q06-base-dev-1"]
        assert result.position == entries[0].position
        assert entries[0].config["run_id"] == "q06-base-dev-1"
        config = json.loads((tmp_project_dirs.outputs / "q06-base-dev-1" / "config.json").read_text("utf-8"))
        assert config["run_id"] == "q06-base-dev-1"

        stub_runs.start_step()
        time.sleep(0.6)
        assert list(stub_runs.control.glob("*.argv.json")) == []
        assert _lock_holder() == "q06-base-dev-9"
    finally:
        holder.release()
    stub_runs.drive(lambda: stub_runs.held("q06-base-dev-1"), "the queued run to start once the lock is free")
    stub_runs.finish("q06-base-dev-1")


def test_AC3_7_2_worker_starts_oldest_waiting_run_and_others_move_up(
    stub_runs, tmp_project_dirs, finalists_path
):
    from gsm8k.run_control import queue as run_queue

    first, _ = _check_and_confirm(EVAL_DIALS, tmp_project_dirs, finalists_path)
    stub_runs.drive(lambda: stub_runs.held(first.attempt_id), "the first run to hold the lock")
    second, _ = _check_and_confirm(EVAL_DIALS, tmp_project_dirs, finalists_path)
    third, _ = _check_and_confirm(EVAL_DIALS, tmp_project_dirs, finalists_path)
    before = {e.attempt_id: e.position for e in run_queue.list_queue()}
    assert list(before) == [second.attempt_id, third.attempt_id]
    assert before[second.attempt_id] < before[third.attempt_id]

    stub_runs.finish(first.attempt_id)  # the active run ends (finished)
    stub_runs.drive(lambda: stub_runs.held(second.attempt_id), "the oldest waiting run to start")

    after = run_queue.list_queue()
    assert [e.attempt_id for e in after] == [third.attempt_id]
    assert after[0].position == before[third.attempt_id] - 1
    assert not stub_runs.launched(third.attempt_id)

    # a stopped run counts as ended too: the last waiting run starts next
    from gsm8k.run_control import stop

    stop.stop_active(outputs=tmp_project_dirs.outputs, grace_seconds=5.0)
    _wait_until(is_free, what="the second run to stop")
    stub_runs.drive(lambda: stub_runs.held(third.attempt_id), "the next waiting run to start after a stop")
    assert run_queue.list_queue() == []
    stub_runs.finish(third.attempt_id)


def test_AC3_7_2_entry_removed_only_after_launched_run_holds_lock(
    stub_runs, tmp_project_dirs, finalists_path
):
    checked, _ = _check_and_confirm(EVAL_DIALS, tmp_project_dirs, finalists_path)
    attempt = checked.attempt_id
    stub_runs.set_mode(attempt, "delay")  # the launched run waits before it takes the lock

    thread = stub_runs.start_step()
    _wait_until(lambda: stub_runs.launched(attempt), what="the worker to launch the run")
    time.sleep(0.4)
    assert _queue_ids() == [attempt]  # C3: not removed while the process does not hold the lock
    assert is_free()

    stub_runs.go(attempt)
    thread.join(STEP_TIMEOUT)
    assert not thread.is_alive(), "run_worker(once=True) did not return"
    assert stub_runs.held(attempt)
    assert _queue_ids() == []
    stub_runs.finish(attempt)


def test_AC3_7_3_queue_full_at_ten_refuses_and_adds_nothing(tmp_project_dirs, finalists_path):
    from gsm8k.run_control import queue as run_queue

    assert run_queue.MAX_WAITING == 10
    holder = GpuLock()
    holder.acquire("q06-base-dev-99")
    try:
        for _ in range(10):
            _check_and_confirm(EVAL_DIALS, tmp_project_dirs, finalists_path)
        waiting = _queue_ids()
        assert len(waiting) == 10

        eleventh = _check(EVAL_DIALS, tmp_project_dirs, finalists_path)
        from gsm8k.run_control import launch

        with pytest.raises(run_queue.QueueFull, match=r"The queue is full \(10 waiting\)"):
            launch.confirm(eleventh.check_id)
        assert _queue_ids() == waiting

        config = to_dict(check_dials(EVAL_DIALS, run_id="q06-base-dev-50"))
        with pytest.raises(run_queue.QueueFull, match=r"The queue is full \(10 waiting\)"):
            run_queue.add("q06-base-dev-50", config)
        assert _queue_ids() == waiting
        assert len(list(run_queue.queue_dir().glob("*.json"))) == 10
    finally:
        holder.release()


def test_AC3_7_4_removed_run_leaves_queue_never_starts_no_row(stub_runs, tmp_project_dirs, finalists_path):
    from gsm8k.run_control import queue as run_queue

    holder = GpuLock()
    holder.acquire("q06-base-dev-99")
    try:
        x, _ = _check_and_confirm(EVAL_DIALS, tmp_project_dirs, finalists_path)
        y, _ = _check_and_confirm(EVAL_DIALS, tmp_project_dirs, finalists_path)
        z, _ = _check_and_confirm(EVAL_DIALS, tmp_project_dirs, finalists_path)
        before = {e.attempt_id: e.position for e in run_queue.list_queue()}

        run_queue.remove(y.attempt_id)

        after = run_queue.list_queue()
        assert [e.attempt_id for e in after] == [x.attempt_id, z.attempt_id]
        assert after[0].position == before[x.attempt_id]
        assert after[1].position == before[y.attempt_id]  # z moved up one place
        names = sorted(p.name for p in run_queue.queue_dir().glob("*.json"))
        assert not any(y.attempt_id in name for name in names)
        assert len(names) == 2
    finally:
        holder.release()

    stub_runs.drive(lambda: stub_runs.held(x.attempt_id), "x to start")
    stub_runs.finish(x.attempt_id)
    stub_runs.drive(lambda: stub_runs.held(z.attempt_id), "z to start")
    stub_runs.finish(z.attempt_id)
    stub_runs.step()  # the queue is empty now: nothing more starts
    assert not stub_runs.launched(y.attempt_id)
    rows = _row_ids(tmp_project_dirs.results)
    assert y.attempt_id not in rows
    assert sorted(rows) == sorted([x.attempt_id, z.attempt_id])
    assert y.attempt_id not in _attempt_dirs_with_status(tmp_project_dirs.outputs)


def test_AC3_7_5_queue_survives_restart_in_same_order(tmp_project_dirs):
    from gsm8k.run_control import queue as run_queue

    assert run_queue.queue_dir() == tmp_project_dirs.outputs / "queue"
    ids = ["q06-base-dev-1", "q06-sft-dev-4", "q06-base-dev-2"]
    for attempt in ids:
        entry = run_queue.add(attempt, to_dict(check_dials({"limit": 5}, run_id=attempt)))
        assert entry.attempt_id == attempt
    entries = run_queue.list_queue()
    for entry in entries:  # C3 file name and content
        path = run_queue.queue_dir() / f"{entry.position:03d}-{entry.attempt_id}.json"
        content = json.loads(path.read_text(encoding="utf-8"))
        assert content["v"] == 1
        assert content["attempt_id"] == entry.attempt_id
        assert content["config"]["run_id"] == entry.attempt_id
        assert isinstance(content["added_at"], str) and content["added_at"]

    code = textwrap.dedent(
        """
        import json
        from gsm8k.run_control import queue
        print(json.dumps([[e.position, e.attempt_id] for e in queue.list_queue()]))
        """
    )
    env = dict(os.environ, GSM8K_OUTPUTS_DIR=str(tmp_project_dirs.outputs))
    for name, rel in CACHE_DIRS.items():
        env[name] = str(ROOT / rel)
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=60)
    assert done.returncode == 0, done.stderr
    fresh = json.loads(done.stdout.strip().splitlines()[-1])
    assert fresh == [[e.position, e.attempt_id] for e in entries]
    assert [attempt for _, attempt in fresh] == ids


def test_AC3_7_6_worker_waits_while_terminal_run_holds_lock(stub_runs, tmp_project_dirs, finalists_path):
    holder = GpuLock()
    holder.acquire("q06-base-dev-9", started_by="terminal")
    try:
        checked, _ = _check_and_confirm(EVAL_DIALS, tmp_project_dirs, finalists_path)
        attempt = checked.attempt_id
        stub_runs.start_step()
        time.sleep(0.6)
        assert not stub_runs.launched(attempt)
        assert _queue_ids() == [attempt]
        assert _lock_holder() == "q06-base-dev-9"
    finally:
        holder.release()
    stub_runs.drive(lambda: stub_runs.held(attempt), "the waiting run to start once the terminal run ends")
    assert _queue_ids() == []
    stub_runs.finish(attempt)


def test_AC3_7_6_launch_that_exits_3_goes_back_to_head_and_waits(stub_runs, tmp_project_dirs, finalists_path):
    first, _ = _check_and_confirm(EVAL_DIALS, tmp_project_dirs, finalists_path)
    second, _ = _check_and_confirm(EVAL_DIALS, tmp_project_dirs, finalists_path)
    attempt = first.attempt_id
    stub_runs.set_mode(attempt, "delay")

    thread = stub_runs.start_step()
    _wait_until(lambda: stub_runs.launched(attempt), what="the worker to launch the run")
    holder = GpuLock()  # a terminal run takes the lock between the worker's check and the launch
    holder.acquire("q06-base-dev-9", started_by="terminal")
    try:
        stub_runs.go(attempt)
        _wait_until(lambda: (stub_runs.control / f"{attempt}.exit3").exists(), what="the launch to exit 3")
        time.sleep(0.4)
        assert _queue_ids() == [attempt, second.attempt_id]  # back at the head, order kept
        assert _lock_holder() == "q06-base-dev-9"
        (stub_runs.control / f"{attempt}.argv.json").unlink()
        time.sleep(0.6)
        assert not stub_runs.launched(attempt)  # no relaunch while the terminal run holds the lock
    finally:
        holder.release()
    thread.join(STEP_TIMEOUT)
    stub_runs.drive(lambda: stub_runs.held(attempt), "the run to start once the lock is free")
    assert _queue_ids() == [second.attempt_id]
    stub_runs.finish(attempt)
