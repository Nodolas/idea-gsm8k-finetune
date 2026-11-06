"""Run records of u1: paths, run log (C1), run folder (C2), GPU lock (C3); rules BR5.1, BR5.3, BR5.4.

These helpers have no criterion of their own in u1, so each test is named after the closest u1
criterion. Every write goes to the temp folders of `tmp_project_dirs`, never the project's
outputs/, checkpoints/ or results/runs.csv.
"""

import csv
import json
import os
import re
import subprocess
import sys

import pytest

from gsm8k._env import ROOT
from gsm8k.run_config import RunConfig, read_config
from gsm8k.run_records.folder import (
    append_prediction,
    atomic_write_text,
    run_already_happened,
    write_config,
    write_status,
    write_timings,
)
from gsm8k.run_records.lock import GpuLock, LockHeld, is_free, lock_path, read_lock
from gsm8k.run_records.log import COLUMNS, RunRow, append_row, has_run_id, read_rows
from gsm8k.run_records.paths import (
    DEFAULT_RESULTS,
    check_run_id,
    checkpoints_root,
    outputs_root,
    resolve_adapter,
    run_dir,
)

RUN_ID = "q06-base-dev-1"
UTC_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
C1_COLUMNS = [
    "date",
    "run_id",
    "model",
    "method",
    "data",
    "metric",
    "value",
    "minutes",
    "config_hash",
    "adapter_run",
]


def _row(run_id: str = RUN_ID, value: float = 0.3333) -> RunRow:
    return RunRow(
        date="2026-11-06T10:00:00Z",
        run_id=run_id,
        model="Qwen/Qwen3-0.6B-Base",
        method="base",
        data="gsm8k-dev",
        metric="accuracy",
        value=value,
        minutes=1.5,
        config_hash="a" * 64,
    )


# --- paths ---


def test_AC1_4_1_paths_follow_the_temp_project_dirs(tmp_project_dirs):
    assert outputs_root() == tmp_project_dirs.outputs
    assert checkpoints_root() == tmp_project_dirs.checkpoints
    assert run_dir(RUN_ID) == tmp_project_dirs.outputs / RUN_ID
    assert DEFAULT_RESULTS == ROOT / "results" / "runs.csv"


def test_AC1_4_1_paths_default_to_project_folders(monkeypatch):
    monkeypatch.delenv("GSM8K_OUTPUTS_DIR", raising=False)
    monkeypatch.delenv("GSM8K_CHECKPOINTS_DIR", raising=False)
    assert outputs_root() == ROOT / "outputs"
    assert checkpoints_root() == ROOT / "checkpoints"


@pytest.mark.parametrize("run_id", ["q06-base-dev-1", "q17-sft-test-12", "adhoc-20261101-201530"])
def test_AC1_4_3_check_run_id_accepts_attempt_and_adhoc_ids(run_id):
    check_run_id(run_id)


@pytest.mark.parametrize("run_id", ["", "../etc", "a/b", "Q06-BASE-DEV-1", "q06 base dev 1", "-q06"])
def test_AC1_4_3_check_run_id_rejects_unsafe_ids(run_id, tmp_project_dirs):
    with pytest.raises(ValueError):
        check_run_id(run_id)
    with pytest.raises(ValueError):
        run_dir(run_id)


def test_AC1_4_6_resolve_adapter_inside_checkpoints(tmp_project_dirs):
    adapter = tmp_project_dirs.checkpoints / "q06-sft-dev-1"
    adapter.mkdir()
    assert resolve_adapter(str(adapter)) == adapter.resolve()


def test_AC1_4_6_resolve_adapter_missing_names_the_path(tmp_project_dirs):
    missing = tmp_project_dirs.checkpoints / "q06-sft-dev-9"
    with pytest.raises(FileNotFoundError) as exc:
        resolve_adapter(str(missing))
    assert "Adapter not found" in str(exc.value)
    assert str(missing) in str(exc.value)


def test_AC1_4_6_resolve_adapter_outside_checkpoints_is_refused(tmp_project_dirs, tmp_path):
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    with pytest.raises(ValueError):
        resolve_adapter(str(outside))
    link = tmp_project_dirs.checkpoints / "sneaky"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        resolve_adapter(str(link))


# --- run log (C1) ---


def test_AC1_4_3_columns_are_in_c1_order():
    assert list(COLUMNS) == C1_COLUMNS


def test_AC1_4_3_append_row_writes_header_and_one_line(tmp_project_dirs):
    path = tmp_project_dirs.results
    append_row(path, _row())
    with path.open(newline="", encoding="utf-8") as f:
        lines = list(csv.reader(f))
    assert lines[0] == C1_COLUMNS
    assert len(lines) == 2
    record = dict(zip(C1_COLUMNS, lines[1], strict=True))
    assert record["run_id"] == RUN_ID
    assert record["model"] == "Qwen/Qwen3-0.6B-Base"
    assert record["data"] == "gsm8k-dev"
    assert float(record["value"]) == pytest.approx(0.3333)
    assert float(record["minutes"]) == pytest.approx(1.5)
    assert record["config_hash"] == "a" * 64
    assert record["adapter_run"] == ""
    assert path.read_text(encoding="utf-8").endswith("\n")


def test_AC1_4_3_second_append_adds_one_line_and_no_second_header(tmp_project_dirs):
    path = tmp_project_dirs.results
    append_row(path, _row())
    append_row(path, _row("q06-base-dev-2", 0.5))
    with path.open(newline="", encoding="utf-8") as f:
        lines = list(csv.reader(f))
    assert len(lines) == 3
    assert lines[0] == C1_COLUMNS
    assert [line[1] for line in lines[1:]] == [RUN_ID, "q06-base-dev-2"]


def test_AC1_4_3_read_rows_returns_rows_and_skipped_count(tmp_project_dirs):
    path = tmp_project_dirs.results
    append_row(path, _row())
    append_row(path, _row("q06-base-dev-2", 0.5))
    rows, skipped = read_rows(path)
    assert skipped == 0
    assert [r.run_id for r in rows] == [RUN_ID, "q06-base-dev-2"]
    assert float(rows[1].value) == pytest.approx(0.5)
    assert rows[0].adapter_run == ""


def test_AC1_4_3_read_rows_skips_and_counts_malformed_rows(tmp_project_dirs):
    path = tmp_project_dirs.results
    good = (
        "2026-11-06T10:00:00Z,q06-base-dev-1,Qwen/Qwen3-0.6B-Base,base,gsm8k-dev,accuracy,0.3333,1.5,"
        + "a" * 64
        + ","
    )
    short = "2026-11-06T10:00:00Z,q06-base-dev-2,Qwen/Qwen3-0.6B-Base"
    bad_number = good.replace("q06-base-dev-1", "q06-base-dev-3").replace(",0.3333,", ",abc,")
    bad_enum = good.replace("q06-base-dev-1", "q06-base-dev-4").replace("Qwen/Qwen3-0.6B-Base", "gpt2")
    path.write_text(
        "\n".join([",".join(C1_COLUMNS), good, short, bad_number, bad_enum]) + "\n", encoding="utf-8"
    )
    rows, skipped = read_rows(path)
    assert [r.run_id for r in rows] == [RUN_ID]
    assert skipped == 3


def test_AC1_4_3_read_rows_missing_file_is_empty_log(tmp_project_dirs):
    assert read_rows(tmp_project_dirs.results) == ([], 0)


def test_AC1_4_3_read_rows_unreadable_file_names_the_file(tmp_project_dirs):
    path = tmp_project_dirs.results
    path.mkdir()  # a folder where the file should be cannot be read as a log
    with pytest.raises(OSError) as exc:
        read_rows(path)
    assert str(path) in str(exc.value)


def test_AC1_4_3_has_run_id(tmp_project_dirs):
    path = tmp_project_dirs.results
    assert has_run_id(path, RUN_ID) is False
    append_row(path, _row())
    assert has_run_id(path, RUN_ID) is True
    assert has_run_id(path, "q06-base-dev-2") is False


# --- run folder (C2, BR5.3, BR5.4) ---


def test_AC1_4_4_atomic_write_text_writes_and_leaves_no_temp_files(tmp_path):
    path = tmp_path / "status.json"
    atomic_write_text(path, "first")
    atomic_write_text(path, "second")
    assert path.read_text(encoding="utf-8") == "second"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["status.json"]


def test_AC1_4_4_atomic_write_text_never_leaves_half_written_file(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text("old", encoding="utf-8")

    def fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", fail)
    monkeypatch.setattr(os, "rename", fail)
    with pytest.raises(OSError):
        atomic_write_text(path, "new content")
    assert path.read_text(encoding="utf-8") == "old"


def test_AC1_4_4_write_timings_saves_seconds_per_problem(tmp_project_dirs):
    folder = run_dir(RUN_ID)
    folder.mkdir(parents=True)
    write_timings(folder, seconds_per_problem=2.5, peak_gpu_memory_gb=0.0)
    data = json.loads((folder / "timings.json").read_text(encoding="utf-8"))
    assert data["v"] == 1
    assert data["seconds_per_problem"] == pytest.approx(2.5)
    assert data["seconds_per_step"] is None
    assert data["peak_gpu_memory_gb"] == pytest.approx(0.0)


def test_AC1_4_5_write_config_round_trips_through_read_config(tmp_project_dirs):
    folder = run_dir(RUN_ID)
    folder.mkdir(parents=True)
    cfg = RunConfig(run_id=RUN_ID, limit=3, max_new_tokens=256)
    write_config(folder, cfg)
    data = json.loads((folder / "config.json").read_text(encoding="utf-8"))
    assert data["v"] == 1
    assert data["run_id"] == RUN_ID
    assert data["max_new_tokens"] == 256
    assert read_config(folder / "config.json") == cfg


def test_AC1_4_1_append_prediction_writes_one_line_per_problem(tmp_project_dirs):
    folder = run_dir(RUN_ID)
    folder.mkdir(parents=True)
    first = {
        "problem_id": "gsm8k-train-1",
        "output": " #### 7",
        "predicted": "7",
        "gold": "7",
        "correct": True,
    }
    second = {
        "problem_id": "gsm8k-train-2",
        "output": "no idea",
        "predicted": None,
        "gold": "3",
        "correct": False,
    }
    append_prediction(folder, first)
    append_prediction(folder, second)
    lines = (folder / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == first
    assert json.loads(lines[1]) == second


def test_AC1_4_1_write_status_records_end_of_run(tmp_project_dirs):
    folder = run_dir(RUN_ID)
    folder.mkdir(parents=True)
    write_status(folder, run_id=RUN_ID, status="finished", exit_code=0, reason=None)
    data = json.loads((folder / "status.json").read_text(encoding="utf-8"))
    assert data["v"] == 1
    assert data["run_id"] == RUN_ID
    assert data["status"] == "finished"
    assert data["exit_code"] == 0
    assert data["reason"] is None
    assert UTC_TIME.match(data["ended_at"])


def test_AC1_4_3_run_already_happened(tmp_project_dirs):
    folder = run_dir(RUN_ID)
    assert run_already_happened(folder) is False  # no folder
    folder.mkdir(parents=True)
    assert run_already_happened(folder) is False  # empty folder
    write_config(folder, RunConfig(run_id=RUN_ID))
    assert run_already_happened(folder) is False  # only the launcher's config.json (BR4.8)
    append_prediction(
        folder,
        {"problem_id": "gsm8k-train-1", "output": "", "predicted": None, "gold": "1", "correct": False},
    )
    assert run_already_happened(folder) is True

    other = run_dir("q06-base-dev-2")
    other.mkdir()
    write_status(other, run_id="q06-base-dev-2", status="failed", exit_code=1, reason="GPU out of memory")
    assert run_already_happened(other) is True


# --- GPU lock (C3, BR5.1) ---

_HOLDER = """
import os, sys
from gsm8k.run_records.lock import GpuLock
lock = GpuLock()
lock.acquire(sys.argv[1], started_by="worker")
print("ready", flush=True)
sys.stdin.readline()
os._exit(0)  # no release: the kernel must free the lock when the process ends
"""

_PROBE = """
import sys
from gsm8k.run_records.lock import GpuLock, LockHeld, is_free
print("free" if is_free() else "held")
try:
    GpuLock().acquire("q06-base-dev-9")
except LockHeld as exc:
    print("refused", exc.run_id)
else:
    print("acquired")
"""


def _run_probe() -> list[str]:
    done = subprocess.run([sys.executable, "-c", _PROBE], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    return done.stdout.split()


def test_AC1_4_1_lock_path_is_in_outputs(tmp_project_dirs):
    assert lock_path() == tmp_project_dirs.outputs / "run.lock"


def test_AC1_4_1_lock_free_without_holder(tmp_project_dirs):
    assert is_free() is True
    assert read_lock() is None


def test_AC1_4_1_lock_records_holder_and_refuses_another_process(tmp_project_dirs):
    lock = GpuLock()
    lock.acquire(RUN_ID)
    try:
        content = read_lock()
        assert content is not None
        assert content["v"] == 1
        assert content["run_id"] == RUN_ID
        assert content["pid"] == os.getpid()
        assert content["started_by"] == "terminal"
        assert UTC_TIME.match(content["started_at"])
        assert read_lock(lock_path()) == content
        assert _run_probe() == ["held", "refused", RUN_ID]
    finally:
        lock.release()
    assert read_lock() is None  # a clean release clears the content
    assert is_free() is True


def test_AC1_4_1_lock_held_by_another_process_refuses_here(tmp_project_dirs):
    holder = subprocess.Popen(
        [sys.executable, "-c", _HOLDER, "q17-sft-dev-3"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout.readline().strip() == "ready", holder.stderr.read()
        assert is_free() is False
        content = read_lock()
        assert content["run_id"] == "q17-sft-dev-3"
        assert content["pid"] == holder.pid
        assert content["started_by"] == "worker"
        with pytest.raises(LockHeld) as exc:
            GpuLock().acquire(RUN_ID)
        assert exc.value.run_id == "q17-sft-dev-3"
    finally:
        holder.stdin.close()
        holder.wait(timeout=60)
    # The holder ended without releasing: the kernel freed the lock, the stale content stays.
    assert is_free() is True
    lock = GpuLock()
    lock.acquire(RUN_ID)
    try:
        assert read_lock()["run_id"] == RUN_ID
    finally:
        lock.release()
