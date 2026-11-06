"""Runs, status and finalists of u4-run-service, part H1 (US3.1, US3.3, US3.5, US3.6; contracts C1-C4).

Every test builds its own fake data in temp folders (`tmp_project_dirs`): a run log written with
`gsm8k.run_records.log.append_row`, run folders with config.json, status.json and run.log, lock
content in `outputs/run.lock`, and a temp finalists file in the C4 shape. Nothing touches the
project's outputs/, checkpoints/, results/runs.csv or results/finalists.json, and no model loads.
The `gsm8k.run_control` modules are imported inside each test, so a missing module fails each test
on its own.

Status choice (batch-3 Interfaces, left open there): `current_status(...)` reports a run whose
process ended without finishing as `state == "IDLE"` plus a `last_run` attribute, a `RunStatus`
with state FAILED and reason "The run process ended without finishing".
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from gsm8k.run_config import RunConfig, to_dict
from gsm8k.run_records.folder import write_status
from gsm8k.run_records.lock import read_lock
from gsm8k.run_records.log import RunRow, append_row

Q06 = "Qwen/Qwen3-0.6B-Base"
Q17 = "Qwen/Qwen3-1.7B-Base"
ENDED_WITHOUT_FINISHING = "The run process ended without finishing"


def _row(run_id, model, method, data, value, minutes, date, metric="accuracy", adapter_run=""):
    return RunRow(
        date=date,
        run_id=run_id,
        model=model,
        method=method,
        data=data,
        metric=metric,
        value=value,
        minutes=minutes,
        config_hash="0" * 64,
        adapter_run=adapter_run,
    )


def _run_folder(outputs: Path, run_id: str, *, model=Q06, method="sft", split="dev") -> Path:
    """A run folder with its config.json (C2), as the launcher writes it before the run starts."""
    folder = outputs / run_id
    folder.mkdir(parents=True, exist_ok=True)
    cfg = RunConfig(run_id=run_id, model=model, method=method, split=split)
    (folder / "config.json").write_text(json.dumps(to_dict(cfg), indent=2) + "\n", encoding="utf-8")
    return folder


def _write_log(folder: Path, lines: list[str]) -> None:
    (folder / "run.log").write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")


def _by_id(runs) -> dict:
    ids = [run.run_id for run in runs]
    assert len(ids) == len(set(ids)), f"a run appears more than once: {ids}"
    return {run.run_id: run for run in runs}


# --- AC3.1.1 run list, and the next attempt id ---------------------------------------------------


def test_AC3_1_1_lists_every_run_once_from_rows_and_folders(tmp_project_dirs):
    from gsm8k.run_control.runs import list_runs

    results, outputs = tmp_project_dirs.results, tmp_project_dirs.outputs
    append_row(
        results, _row("q06-base-dev-1", Q06, "base", "gsm8k-dev", 0.3123, 41.24, "2026-11-01T10:00:00Z")
    )
    append_row(results, _row("q06-sft-dev-1", Q06, "sft", "gsm8k-dev", 0.4567, 95.0, "2026-11-02T11:00:00Z"))
    append_row(
        results,
        _row("q17-best-test-1", Q17, "best", "gsm8k-test", 0.6512, 120.5, "2026-11-03T12:00:00Z"),
    )
    # Run folders: one with a row (listed once), one failed run without a row (listed from its folder).
    _run_folder(outputs, "q06-sft-dev-1")
    write_status(
        outputs / "q06-sft-dev-1", run_id="q06-sft-dev-1", status="finished", exit_code=0, reason=None
    )
    failed = _run_folder(outputs, "q17-sft-dev-1", model=Q17, method="sft")
    write_status(failed, run_id="q17-sft-dev-1", status="failed", exit_code=1, reason="GPU out of memory")
    # Not run folders: the queue folder and the lock file.
    (outputs / "queue").mkdir()
    (outputs / "run.lock").write_text("", encoding="utf-8")

    runs, skipped = list_runs(results, outputs)

    assert skipped == 0
    by_id = _by_id(runs)
    assert set(by_id) == {"q06-base-dev-1", "q06-sft-dev-1", "q17-best-test-1", "q17-sft-dev-1"}

    base = by_id["q06-base-dev-1"]
    assert (base.model, base.method) == (Q06, "base")
    assert base.dev_accuracy == pytest.approx(0.3123)
    assert base.test_accuracy is None
    assert base.minutes == pytest.approx(41.2)
    assert base.date == "2026-11-01T10:00:00Z"

    sft = by_id["q06-sft-dev-1"]
    assert (sft.model, sft.method) == (Q06, "sft")
    assert sft.dev_accuracy == pytest.approx(0.4567)
    assert sft.minutes == pytest.approx(95.0)
    assert sft.date == "2026-11-02T11:00:00Z"

    test_run = by_id["q17-best-test-1"]
    assert (test_run.model, test_run.method) == (Q17, "best")
    assert test_run.test_accuracy == pytest.approx(0.6512)
    assert test_run.dev_accuracy is None
    assert test_run.minutes == pytest.approx(120.5)
    assert test_run.date == "2026-11-03T12:00:00Z"

    no_row = by_id["q17-sft-dev-1"]
    assert (no_row.model, no_row.method) == (Q17, "sft")
    assert no_row.dev_accuracy is None
    assert no_row.test_accuracy is None
    assert no_row.status == "failed"


def test_AC3_1_1_next_attempt_id_starts_at_one(tmp_project_dirs):
    from gsm8k.run_control.runs import next_attempt_id

    assert (
        next_attempt_id("q06-sft-dev", tmp_project_dirs.results, tmp_project_dirs.outputs) == "q06-sft-dev-1"
    )


def test_AC3_1_1_next_attempt_id_counts_rows_folders_and_queue(tmp_project_dirs):
    from gsm8k.run_control.runs import next_attempt_id

    results, outputs = tmp_project_dirs.results, tmp_project_dirs.outputs
    append_row(results, _row("q06-sft-dev-1", Q06, "sft", "gsm8k-dev", 0.4, 10.0, "2026-11-01T10:00:00Z"))
    append_row(results, _row("q06-sft-dev-2", Q06, "sft", "gsm8k-dev", 0.4, 10.0, "2026-11-01T11:00:00Z"))
    # Other base ids never count, even with higher numbers.
    append_row(results, _row("q06-base-dev-9", Q06, "base", "gsm8k-dev", 0.3, 10.0, "2026-11-01T12:00:00Z"))
    append_row(results, _row("q17-sft-dev-8", Q17, "sft", "gsm8k-dev", 0.6, 10.0, "2026-11-01T13:00:00Z"))

    assert next_attempt_id("q06-sft-dev", results, outputs) == "q06-sft-dev-3"

    # A run folder without a row (a failed or running attempt) counts.
    _run_folder(outputs, "q06-sft-dev-4")
    assert next_attempt_id("q06-sft-dev", results, outputs) == "q06-sft-dev-5"

    # A queued attempt counts; numbers compare as numbers, not text.
    queued = ["q06-sft-dev-10", "q06-base-dev-20"]
    assert next_attempt_id("q06-sft-dev", results, outputs, queue_ids=queued) == "q06-sft-dev-11"


# --- AC3.1.3 malformed rows are skipped and counted ----------------------------------------------


def test_AC3_1_3_skips_one_malformed_row_and_counts_it(tmp_project_dirs):
    from gsm8k.run_control.runs import list_runs

    results = tmp_project_dirs.results
    append_row(results, _row("q06-base-dev-1", Q06, "base", "gsm8k-dev", 0.31, 40.0, "2026-11-01T10:00:00Z"))
    with results.open("a", encoding="utf-8") as f:
        f.write(
            "2026-11-01T11:00:00Z,q06-sft-dev-1,Qwen/Qwen3-0.6B-Base,sft,gsm8k-dev,accuracy,not-a-number\n"
        )
    append_row(results, _row("q06-sft-dev-2", Q06, "sft", "gsm8k-dev", 0.45, 90.0, "2026-11-01T12:00:00Z"))

    runs, skipped = list_runs(results, tmp_project_dirs.outputs)

    assert skipped == 1
    assert set(_by_id(runs)) == {"q06-base-dev-1", "q06-sft-dev-2"}


# --- AC3.1.4 no file, unreadable file ------------------------------------------------------------


def test_AC3_1_4_no_results_file_gives_empty_list(tmp_project_dirs):
    from gsm8k.run_control.runs import list_runs

    assert not tmp_project_dirs.results.exists()
    runs, skipped = list_runs(tmp_project_dirs.results, tmp_project_dirs.outputs)
    assert runs == []
    assert skipped == 0


def test_AC3_1_4_unreadable_results_file_raises_error_naming_it(tmp_project_dirs):
    from gsm8k.run_control.runs import list_runs

    results = tmp_project_dirs.results
    results.mkdir()  # a folder where the run log should be: it cannot be read as a file
    with pytest.raises(OSError) as excinfo:
        list_runs(results, tmp_project_dirs.outputs)
    assert str(results) in str(excinfo.value)


# --- AC3.3.3 lock free but its content still names a run -----------------------------------------


def _crash_holding_lock(run_id: str) -> None:
    """A process takes the GPU lock like a real run and dies without releasing it (the kernel frees
    the lock; the content stays)."""
    code = (
        "import os\n"
        "from gsm8k.run_records.lock import GpuLock\n"
        f"GpuLock().acquire({run_id!r}, 'worker')\n"
        "os._exit(1)\n"
    )
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert done.returncode == 1, done.stderr


def test_AC3_3_3_free_lock_naming_unfinished_run_reads_idle_with_failed_last_run(tmp_project_dirs):
    from gsm8k.run_control.status import RunStatus, current_status

    outputs = tmp_project_dirs.outputs
    _run_folder(outputs, "q06-sft-dev-1")  # config.json only: the run never wrote status.json
    _crash_holding_lock("q06-sft-dev-1")
    content = read_lock(outputs / "run.lock")
    assert content is not None and content["run_id"] == "q06-sft-dev-1"

    status = current_status(outputs)

    assert status.state == "IDLE"
    assert isinstance(status.last_run, RunStatus)
    assert status.last_run.state == "FAILED"
    assert status.last_run.run_id == "q06-sft-dev-1"
    assert status.last_run.reason == ENDED_WITHOUT_FINISHING


def test_AC3_3_3_free_lock_naming_run_with_status_file_is_not_reported_failed(tmp_project_dirs):
    from gsm8k.run_control.status import current_status

    outputs = tmp_project_dirs.outputs
    folder = _run_folder(outputs, "q06-sft-dev-2")
    write_status(folder, run_id="q06-sft-dev-2", status="finished", exit_code=0, reason=None)
    lock = {
        "v": 1,
        "run_id": "q06-sft-dev-2",
        "pid": 999999,
        "started_at": "2026-11-01T10:00:00Z",
        "started_by": "worker",
    }
    (outputs / "run.lock").write_text(json.dumps(lock) + "\n", encoding="utf-8")

    status = current_status(outputs)

    assert status.state == "IDLE"
    last = getattr(status, "last_run", None)
    assert last is None or last.reason != ENDED_WITHOUT_FINISHING


# --- AC3.5.1 nonzero exit: FAILED with reason and last 20 log lines ------------------------------


def test_AC3_5_1_failed_run_shows_reason_and_last_20_log_lines(tmp_project_dirs):
    from gsm8k.run_control.status import run_status

    outputs = tmp_project_dirs.outputs
    folder = _run_folder(outputs, "q06-sft-dev-1")
    _write_log(folder, [f"log line {i}" for i in range(1, 31)])
    write_status(folder, run_id="q06-sft-dev-1", status="failed", exit_code=1, reason="ValueError: bad batch")

    status = run_status("q06-sft-dev-1", outputs)

    assert status.state == "FAILED"
    assert status.run_id == "q06-sft-dev-1"
    assert status.reason == "ValueError: bad batch"
    assert status.log_tail == [f"log line {i}" for i in range(11, 31)]


def test_AC3_5_1_short_log_shows_every_line_and_finished_run_is_not_failed(tmp_project_dirs):
    from gsm8k.run_control.status import run_status

    outputs = tmp_project_dirs.outputs
    failed = _run_folder(outputs, "q06-sft-dev-2")
    _write_log(failed, ["starting", "Traceback (most recent call last):", "KeyError: 'answer'"])
    write_status(failed, run_id="q06-sft-dev-2", status="failed", exit_code=1, reason="KeyError: 'answer'")

    status = run_status("q06-sft-dev-2", outputs)
    assert status.state == "FAILED"
    assert status.log_tail == ["starting", "Traceback (most recent call last):", "KeyError: 'answer'"]

    finished = _run_folder(outputs, "q06-sft-dev-3")
    _write_log(finished, ["done"])
    write_status(finished, run_id="q06-sft-dev-3", status="finished", exit_code=0, reason=None)
    assert run_status("q06-sft-dev-3", outputs).state == "FINISHED"


# --- AC3.5.2 CUDA out of memory -------------------------------------------------------------------


def test_AC3_5_2_cuda_out_of_memory_in_log_reads_gpu_out_of_memory(tmp_project_dirs):
    from gsm8k.run_control.status import run_status

    outputs = tmp_project_dirs.outputs
    folder = _run_folder(outputs, "q17-sft-dev-1", model=Q17)
    _write_log(
        folder,
        [
            "step 3/100 loss 1.23",
            "Traceback (most recent call last):",
            '  File "train.py", line 10, in step',
            "torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 2.00 GiB. GPU 0 has a total "
            "capacity of 7.66 GiB of which 1.10 GiB is free.",
        ],
    )
    write_status(folder, run_id="q17-sft-dev-1", status="failed", exit_code=1, reason="Unexpected error")

    status = run_status("q17-sft-dev-1", outputs)

    assert status.state == "FAILED"
    assert status.reason == "GPU out of memory"


# --- AC3.5.3 unreadable run log -------------------------------------------------------------------


def test_AC3_5_3_unreadable_run_log_names_the_file(tmp_project_dirs):
    from gsm8k.run_control.status import run_status

    outputs = tmp_project_dirs.outputs
    folder = _run_folder(outputs, "q06-sft-dev-1")
    log_path = folder / "run.log"
    log_path.mkdir()  # a folder where the log should be: it cannot be read
    write_status(folder, run_id="q06-sft-dev-1", status="failed", exit_code=1, reason="RuntimeError: boom")

    status = run_status("q06-sft-dev-1", outputs)

    assert status.state == "FAILED"
    assert "Run log could not be read" in status.reason
    assert str(log_path) in status.reason


# --- AC3.6.1 mark and unmark finalists ------------------------------------------------------------


def test_AC3_6_1_mark_saves_run_id_and_unmark_removes_it(tmp_project_dirs):
    from gsm8k.run_control.finalists import check_test_split_allowed, list_finalists, mark, unmark

    results = tmp_project_dirs.results
    append_row(results, _row("q06-sft-dev-1", Q06, "sft", "gsm8k-dev", 0.45, 90.0, "2026-11-01T10:00:00Z"))
    append_row(results, _row("q06-sft-dev-2", Q06, "sft", "gsm8k-dev", 0.47, 91.0, "2026-11-01T11:00:00Z"))
    path = results.parent / "finalists.json"

    mark(path, "q06-sft-dev-1", results)
    assert list_finalists(path) == ["q06-sft-dev-1"]
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["v"] == 1
    assert [entry["run_id"] for entry in data["finalists"]] == ["q06-sft-dev-1"]
    assert all(isinstance(entry["marked_at"], str) and entry["marked_at"] for entry in data["finalists"])

    mark(path, "q06-sft-dev-1", results)  # marking twice keeps one entry
    mark(path, "q06-sft-dev-2", results)
    assert sorted(list_finalists(path)) == ["q06-sft-dev-1", "q06-sft-dev-2"]
    check_test_split_allowed("q06-sft-dev-1", path)  # a finalist may be scored on test

    unmark(path, "q06-sft-dev-1")
    assert list_finalists(path) == ["q06-sft-dev-2"]
    with pytest.raises(ValueError, match="Only finalists can be scored on the test split"):
        check_test_split_allowed("q06-sft-dev-1", path)

    # Atomic writes leave no temp file behind.
    assert sorted(p.name for p in path.parent.iterdir()) == ["finalists.json", "runs.csv"]


def test_AC3_6_1_mark_refuses_run_not_in_run_log(tmp_project_dirs):
    from gsm8k.run_control.finalists import mark

    results = tmp_project_dirs.results
    append_row(results, _row("q06-sft-dev-1", Q06, "sft", "gsm8k-dev", 0.45, 90.0, "2026-11-01T10:00:00Z"))
    path = results.parent / "finalists.json"

    with pytest.raises((ValueError, LookupError)):
        mark(path, "q06-sft-dev-7", results)
    assert not path.exists()


# --- AC3.6.5 no finalists file, unreadable finalists file ----------------------------------------


def test_AC3_6_5_no_finalists_file_means_no_finalists(tmp_project_dirs):
    from gsm8k.run_control.finalists import check_test_split_allowed, list_finalists

    path = tmp_project_dirs.results.parent / "finalists.json"
    assert list_finalists(path) == []
    with pytest.raises(ValueError, match="Only finalists can be scored on the test split"):
        check_test_split_allowed("q06-sft-dev-1", path)


def test_AC3_6_5_unreadable_finalists_file_names_it_and_blocks_test_split(tmp_project_dirs):
    from gsm8k.run_control.finalists import check_test_split_allowed, list_finalists

    path = tmp_project_dirs.results.parent / "finalists.json"
    path.write_text('{"v": 1, "finalists": [{"run_id": "q06-sft-dev-1"', encoding="utf-8")  # cut short

    with pytest.raises(ValueError) as listed:
        list_finalists(path)
    assert str(path) in str(listed.value)

    with pytest.raises(ValueError) as checked:
        check_test_split_allowed("q06-sft-dev-1", path)
    assert str(path) in str(checked.value)
    assert "Only finalists" not in str(checked.value)
