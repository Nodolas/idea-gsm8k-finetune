"""Queue, worker and prune for course runs, part Q of u12-learning-course (US12.3, US12.4; C3).

Covers AC12.4.1 (the queue entry's `results` field and the worker's `--results`; course attempt ids),
AC12.3.3 (the worker side of the `after` rule) and AC12.4.6 (prune leaves `course-*` folders alone).

The worker launches nothing real: `launch.build_argv` is replaced by a wrapper that records the argument
list the real builder makes and returns a no-op command, so no model loads and no GPU is used (the
autouse fixture in conftest.py keeps the GPU check free). Every test uses `tmp_project_dirs`; nothing
touches the project's outputs/, checkpoints/ or results/runs.csv.

Assumptions: the course results file is `<outputs root>/course/runs.csv` (the entry's `outputs/course/
runs.csv` is relative to the project's outputs root, so a temporary outputs folder works); an entry
whose `after` attempt has no row and no ended status keeps waiting; `outputs/queue/queue.log` gets one
line per removed entry that names the entry's attempt id and the `after` attempt id.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import pytest

from gsm8k.run_records.folder import write_status
from gsm8k.run_records.log import RunRow, append_row

Q06 = "Qwen/Qwen3-0.6B-Base"
COURSE_RESULTS = "outputs/course/runs.csv"
COURSE_ID_A = "course-c05-qwen3-17-1"
COURSE_ID_B = "course-c01-base-06-2"
COTGEN_ID = "course-c22-cotgen-1"
SELFCOT_ID = "course-c22-selfcot-1"
EVAL_CONFIG = {"method": "base", "split": "dev", "limit": 100}
SFT_CONFIG = {"method": "selfcot", "split": "dev", "limit": 100}


# --- helpers --------------------------------------------------------------------------------------


def _queue_ids(outputs: Path) -> list[str]:
    from gsm8k.run_control import queue as run_queue

    return [entry.attempt_id for entry in run_queue.list_queue(outputs)]


def _entry_files(outputs: Path) -> list[Path]:
    qdir = outputs / "queue"
    return sorted(qdir.glob("*.json")) if qdir.is_dir() else []


def _course_row(run_id: str, method: str = "cotgen") -> RunRow:
    return RunRow(
        date="2026-11-10T10:00:00Z",
        run_id=run_id,
        model=Q06,
        method=method,
        data="gsm8k-train" if method == "cotgen" else "gsm8k-dev",
        metric="kept_fraction" if method == "cotgen" else "accuracy",
        value=0.5,
        minutes=1.0,
        config_hash="0" * 64,
    )


def _course_results(outputs: Path) -> Path:
    return outputs / "course" / "runs.csv"


def _queue_log(outputs: Path) -> list[str]:
    path = outputs / "queue" / "queue.log"
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


class Launches:
    """Stands in for `launch.build_argv`: records each real argument list, runs a no-op command."""

    def __init__(self, monkeypatch):
        from gsm8k.run_control import launch

        self.argvs: list[list[str]] = []
        real = launch.build_argv
        recorder = self

        def recording_build_argv(kind, attempt_id, config_path, results):
            argv = real(kind, attempt_id, config_path, results)
            recorder.argvs.append(argv)
            return [sys.executable, "-c", "pass"]

        monkeypatch.setattr(launch, "build_argv", recording_build_argv)

    def run_ids(self) -> list[str]:
        return [argv[argv.index("--run-id") + 1] for argv in self.argvs]

    def results_of(self, run_id: str) -> str:
        argv = self.argvs[self.run_ids().index(run_id)]
        return argv[argv.index("--results") + 1]


@pytest.fixture
def launches(tmp_project_dirs, monkeypatch) -> Launches:
    return Launches(monkeypatch)


def _worker(dirs):
    from gsm8k.run_control import worker

    return worker.Worker(outputs=dirs.outputs, results=dirs.results)


def _steps(worker, count: int = 1) -> None:
    for _ in range(count):
        worker.step(timeout=10.0)


# --- AC12.4.1: the queue entry's results ---------------------------------------------------------


def test_AC12_4_1_queue_entry_keeps_results(tmp_project_dirs):
    from gsm8k.run_control import queue as run_queue

    entry = run_queue.add(
        COURSE_ID_A, dict(EVAL_CONFIG), "evaluate", tmp_project_dirs.outputs, results=COURSE_RESULTS
    )
    assert entry.results == COURSE_RESULTS
    assert entry.after is None
    files = _entry_files(tmp_project_dirs.outputs)
    assert [f.name for f in files] == [f"001-{COURSE_ID_A}.json"]
    assert json.loads(files[0].read_text(encoding="utf-8"))["results"] == COURSE_RESULTS
    listed = run_queue.list_queue(tmp_project_dirs.outputs)
    assert [(e.attempt_id, e.results, e.after) for e in listed] == [(COURSE_ID_A, COURSE_RESULTS, None)]


def test_AC12_4_1_queue_entry_results_defaults_to_none(tmp_project_dirs):
    from gsm8k.run_control import queue as run_queue

    entry = run_queue.add("q06-base-dev-1", dict(EVAL_CONFIG), "evaluate", tmp_project_dirs.outputs)
    assert entry.results is None
    assert entry.after is None
    data = json.loads(_entry_files(tmp_project_dirs.outputs)[0].read_text(encoding="utf-8"))
    assert data.get("results") is None
    assert data.get("after") is None
    listed = run_queue.list_queue(tmp_project_dirs.outputs)
    assert (listed[0].results, listed[0].after) == (None, None)


def test_AC12_4_1_queue_entry_keeps_after(tmp_project_dirs):
    from gsm8k.run_control import queue as run_queue

    run_queue.add(
        SELFCOT_ID,
        dict(SFT_CONFIG),
        "train",
        tmp_project_dirs.outputs,
        results=COURSE_RESULTS,
        after=COTGEN_ID,
    )
    data = json.loads(_entry_files(tmp_project_dirs.outputs)[0].read_text(encoding="utf-8"))
    assert data["after"] == COTGEN_ID
    listed = run_queue.list_queue(tmp_project_dirs.outputs)
    assert (listed[0].results, listed[0].after) == (COURSE_RESULTS, COTGEN_ID)


@pytest.mark.parametrize(
    "results",
    [
        "results/runs.csv",
        "outputs/other.csv",
        "outputs/course/runs.csv.bak",
        "/tmp/runs.csv",
        "../outputs/course/runs.csv",
        "",
    ],
)
def test_AC12_4_1_any_other_results_value_is_refused_and_writes_nothing(tmp_project_dirs, results):
    from gsm8k.run_control import queue as run_queue

    with pytest.raises(ValueError):
        run_queue.add(COURSE_ID_A, dict(EVAL_CONFIG), "evaluate", tmp_project_dirs.outputs, results=results)
    assert _entry_files(tmp_project_dirs.outputs) == []
    assert run_queue.list_queue(tmp_project_dirs.outputs) == []


def test_AC12_4_1_old_entry_file_without_results_and_after_reads_as_none(tmp_project_dirs):
    from gsm8k.run_control import queue as run_queue

    qdir = tmp_project_dirs.outputs / "queue"
    qdir.mkdir()
    old = {
        "v": 1,
        "attempt_id": "q06-base-dev-1",
        "config": dict(EVAL_CONFIG),
        "added_at": "2026-11-01T10:00:00Z",
    }
    (qdir / "001-q06-base-dev-1.json").write_text(json.dumps(old), encoding="utf-8")
    (qdir / "002-q17-sft-dev-1.json").write_text(
        json.dumps({**old, "attempt_id": "q17-sft-dev-1", "kind": "train"}), encoding="utf-8"
    )
    listed = run_queue.list_queue(tmp_project_dirs.outputs)
    assert [(e.attempt_id, e.results, e.after) for e in listed] == [
        ("q06-base-dev-1", None, None),
        ("q17-sft-dev-1", None, None),
    ]
    head = run_queue.peek_head(tmp_project_dirs.outputs)
    assert head is not None and (head.results, head.after) == (None, None)


@pytest.mark.parametrize("attempt_id", [COURSE_ID_A, COURSE_ID_B, "course-c20-qlora-12", SELFCOT_ID])
def test_AC12_4_1_course_attempt_ids_are_accepted_by_the_queue(tmp_project_dirs, attempt_id):
    from gsm8k.run_control import queue as run_queue

    entry = run_queue.add(
        attempt_id, dict(EVAL_CONFIG), "evaluate", tmp_project_dirs.outputs, results=COURSE_RESULTS
    )
    assert entry.attempt_id == attempt_id
    assert _queue_ids(tmp_project_dirs.outputs) == [attempt_id]
    run_queue.remove(attempt_id, outputs=tmp_project_dirs.outputs)
    assert _queue_ids(tmp_project_dirs.outputs) == []


@pytest.mark.parametrize(
    "attempt_id", ["course-c5-base-06-1", "course-c05-base-06", "course-c05-Base-1", "course-1"]
)
def test_AC12_4_1_malformed_course_attempt_ids_are_refused(tmp_project_dirs, attempt_id):
    from gsm8k.run_control import queue as run_queue

    with pytest.raises(ValueError):
        run_queue.add(
            attempt_id, dict(EVAL_CONFIG), "evaluate", tmp_project_dirs.outputs, results=COURSE_RESULTS
        )
    assert _entry_files(tmp_project_dirs.outputs) == []


def _item(attempt_id, *, results=COURSE_RESULTS, after=None, kind="evaluate", config=None):
    return {
        "attempt_id": attempt_id,
        "config": dict(config or EVAL_CONFIG),
        "kind": kind,
        "results": results,
        "after": after,
    }


def test_AC12_4_1_add_all_adds_every_entry_in_order(tmp_project_dirs):
    from gsm8k.run_control import queue as run_queue

    items = [
        _item(COTGEN_ID, kind="evaluate"),
        _item(SELFCOT_ID, kind="train", after=COTGEN_ID, config=SFT_CONFIG),
    ]
    added = run_queue.add_all(items, tmp_project_dirs.outputs)
    assert [e.attempt_id for e in added] == [COTGEN_ID, SELFCOT_ID]
    assert [e.position for e in added] == [1, 2]
    listed = run_queue.list_queue(tmp_project_dirs.outputs)
    assert [(e.attempt_id, e.kind, e.results, e.after) for e in listed] == [
        (COTGEN_ID, "evaluate", COURSE_RESULTS, None),
        (SELFCOT_ID, "train", COURSE_RESULTS, COTGEN_ID),
    ]


def test_AC12_4_1_add_all_fills_the_queue_to_exactly_the_maximum(tmp_project_dirs):
    from gsm8k.run_control import queue as run_queue

    for n in range(1, 8):
        run_queue.add(f"q06-base-dev-{n}", dict(EVAL_CONFIG), "evaluate", tmp_project_dirs.outputs)
    items = [_item(f"course-c05-qwen3-17-{n}") for n in range(1, 4)]
    run_queue.add_all(items, tmp_project_dirs.outputs)
    assert len(run_queue.list_queue(tmp_project_dirs.outputs)) == run_queue.MAX_WAITING


def test_AC12_4_1_add_all_adds_nothing_when_they_would_exceed_the_maximum(tmp_project_dirs):
    from gsm8k.run_control import queue as run_queue

    for n in range(1, 9):
        run_queue.add(f"q06-base-dev-{n}", dict(EVAL_CONFIG), "evaluate", tmp_project_dirs.outputs)
    before = [f.name for f in _entry_files(tmp_project_dirs.outputs)]
    items = [_item(f"course-c05-qwen3-17-{n}") for n in range(1, 4)]  # 8 + 3 > 10
    with pytest.raises(run_queue.QueueFull):
        run_queue.add_all(items, tmp_project_dirs.outputs)
    assert [f.name for f in _entry_files(tmp_project_dirs.outputs)] == before
    assert len(run_queue.list_queue(tmp_project_dirs.outputs)) == 8


def test_AC12_4_1_add_all_with_one_bad_entry_adds_none(tmp_project_dirs):
    from gsm8k.run_control import queue as run_queue

    for bad in (_item(COURSE_ID_B, results="results/runs.csv"), _item("not-an-attempt-id")):
        items = [_item(COURSE_ID_A), bad, _item("course-c05-qwen3-17-2")]
        with pytest.raises(ValueError):
            run_queue.add_all(items, tmp_project_dirs.outputs)
        assert _entry_files(tmp_project_dirs.outputs) == []
        assert run_queue.list_queue(tmp_project_dirs.outputs) == []


def test_AC12_4_1_worker_passes_results_of_a_course_entry_as_the_course_runs_file(tmp_project_dirs, launches):
    from gsm8k.run_control import queue as run_queue

    run_queue.add(
        COURSE_ID_A, dict(EVAL_CONFIG), "evaluate", tmp_project_dirs.outputs, results=COURSE_RESULTS
    )
    _steps(_worker(tmp_project_dirs))
    assert launches.run_ids() == [COURSE_ID_A]
    assert launches.results_of(COURSE_ID_A) == str(tmp_project_dirs.outputs / "course" / "runs.csv")
    assert launches.argvs[0][launches.argvs[0].index("--started-by") + 1] == "worker"
    assert (
        tmp_project_dirs.outputs / COURSE_ID_A / "config.json"
    ).exists()  # the run folder is outputs/<id>/


def test_AC12_4_1_worker_passes_its_default_results_for_a_normal_entry(tmp_project_dirs, launches):
    from gsm8k.run_control import queue as run_queue

    run_queue.add("q06-base-dev-1", dict(EVAL_CONFIG), "evaluate", tmp_project_dirs.outputs)
    _steps(_worker(tmp_project_dirs))
    assert launches.run_ids() == ["q06-base-dev-1"]
    assert launches.results_of("q06-base-dev-1") == str(tmp_project_dirs.results)


# --- AC12.3.3 worker side: the `after` rule -------------------------------------------------------


def _queue_selfcot_after_cotgen(dirs, *, behind: str | None = None) -> None:
    from gsm8k.run_control import queue as run_queue

    run_queue.add(
        SELFCOT_ID, dict(SFT_CONFIG), "train", dirs.outputs, results=COURSE_RESULTS, after=COTGEN_ID
    )
    if behind:
        run_queue.add(behind, dict(EVAL_CONFIG), "evaluate", dirs.outputs, results=COURSE_RESULTS)


def test_AC12_3_3_worker_waits_for_after_row(tmp_project_dirs, launches):
    _queue_selfcot_after_cotgen(tmp_project_dirs, behind=COURSE_ID_A)
    worker = _worker(tmp_project_dirs)
    _steps(worker, 3)
    assert launches.argvs == []  # neither the entry nor the one behind it launches
    assert _queue_ids(tmp_project_dirs.outputs) == [SELFCOT_ID, COURSE_ID_A]
    assert _queue_log(tmp_project_dirs.outputs) == []

    # the awaited attempt is running (a status.json is not there yet, or says running): still waiting
    (tmp_project_dirs.outputs / COTGEN_ID).mkdir()
    _steps(worker, 2)
    assert launches.argvs == []
    assert _queue_ids(tmp_project_dirs.outputs) == [SELFCOT_ID, COURSE_ID_A]


def test_AC12_3_3_row_in_another_results_file_does_not_release_the_entry(tmp_project_dirs, launches):
    _queue_selfcot_after_cotgen(tmp_project_dirs)
    append_row(tmp_project_dirs.results, _course_row(COTGEN_ID))  # results/runs.csv, not the entry's file
    _steps(_worker(tmp_project_dirs), 2)
    assert launches.argvs == []
    assert _queue_ids(tmp_project_dirs.outputs) == [SELFCOT_ID]


def test_AC12_3_3_worker_launches_once_the_after_row_exists(tmp_project_dirs, launches):
    _queue_selfcot_after_cotgen(tmp_project_dirs)
    worker = _worker(tmp_project_dirs)
    _steps(worker, 2)
    assert launches.argvs == []

    append_row(_course_results(tmp_project_dirs.outputs), _course_row(COTGEN_ID))
    _steps(worker, 2)
    assert launches.run_ids() == [SELFCOT_ID]
    assert launches.results_of(SELFCOT_ID) == str(_course_results(tmp_project_dirs.outputs))
    assert _queue_ids(tmp_project_dirs.outputs) == []
    assert _queue_log(tmp_project_dirs.outputs) == []  # a launch is not a removal with a reason


def test_AC12_3_3_entry_behind_an_after_entry_waits_with_it_then_follows(tmp_project_dirs, launches):
    _queue_selfcot_after_cotgen(tmp_project_dirs, behind=COURSE_ID_A)
    worker = _worker(tmp_project_dirs)
    append_row(_course_results(tmp_project_dirs.outputs), _course_row(COTGEN_ID))
    _steps(worker, 4)
    assert launches.run_ids() == [SELFCOT_ID, COURSE_ID_A]  # in queue order
    assert _queue_ids(tmp_project_dirs.outputs) == []


@pytest.mark.parametrize("status", ["failed", "stopped"])
def test_AC12_3_3_entry_is_removed_when_the_after_attempt_failed_or_stopped(
    tmp_project_dirs, launches, status
):
    _queue_selfcot_after_cotgen(tmp_project_dirs)
    run_dir = tmp_project_dirs.outputs / COTGEN_ID
    run_dir.mkdir()
    write_status(run_dir, run_id=COTGEN_ID, status=status, exit_code=1, reason="it ended")
    _steps(_worker(tmp_project_dirs), 2)
    assert launches.argvs == []
    assert _queue_ids(tmp_project_dirs.outputs) == []
    lines = [line for line in _queue_log(tmp_project_dirs.outputs) if SELFCOT_ID in line]
    assert len(lines) == 1
    assert COTGEN_ID in lines[0]


def test_AC12_3_3_entry_is_removed_when_the_after_attempt_finished_without_a_row(tmp_project_dirs, launches):
    _queue_selfcot_after_cotgen(tmp_project_dirs)
    run_dir = tmp_project_dirs.outputs / COTGEN_ID
    run_dir.mkdir()
    write_status(run_dir, run_id=COTGEN_ID, status="finished", exit_code=0, reason=None)
    _steps(_worker(tmp_project_dirs), 2)
    assert launches.argvs == []
    assert _queue_ids(tmp_project_dirs.outputs) == []
    lines = [line for line in _queue_log(tmp_project_dirs.outputs) if SELFCOT_ID in line]
    assert len(lines) == 1 and COTGEN_ID in lines[0]


def test_AC12_3_3_finished_attempt_with_a_row_releases_the_entry_instead_of_removing_it(
    tmp_project_dirs, launches
):
    _queue_selfcot_after_cotgen(tmp_project_dirs)
    run_dir = tmp_project_dirs.outputs / COTGEN_ID
    run_dir.mkdir()
    write_status(run_dir, run_id=COTGEN_ID, status="finished", exit_code=0, reason=None)
    append_row(_course_results(tmp_project_dirs.outputs), _course_row(COTGEN_ID))
    _steps(_worker(tmp_project_dirs), 2)
    assert launches.run_ids() == [SELFCOT_ID]
    assert _queue_log(tmp_project_dirs.outputs) == []


def test_AC12_3_3_removed_entry_no_longer_blocks_the_ones_behind_it(tmp_project_dirs, launches):
    _queue_selfcot_after_cotgen(tmp_project_dirs, behind=COURSE_ID_A)
    run_dir = tmp_project_dirs.outputs / COTGEN_ID
    run_dir.mkdir()
    write_status(run_dir, run_id=COTGEN_ID, status="failed", exit_code=1, reason="it failed")
    _steps(_worker(tmp_project_dirs), 4)
    assert launches.run_ids() == [COURSE_ID_A]  # the selfcot entry never launched
    assert _queue_ids(tmp_project_dirs.outputs) == []
    assert any(SELFCOT_ID in line and COTGEN_ID in line for line in _queue_log(tmp_project_dirs.outputs))


# --- AC12.4.6 prune side --------------------------------------------------------------------------

COURSE_FOLDERS = ("course-c21-sft-1", "course-c21-sft-2", "course-c23-grpo-1", "course-c20-qlora-1")


def _course_ids_valid(monkeypatch):
    """Part M makes course attempt ids valid run ids (paths.RUN_ID_PATTERN); prune must leave them alone
    either way, so the test makes them valid itself and does not wait for part M."""
    import re

    from gsm8k.run_records import paths

    monkeypatch.setattr(
        paths,
        "RUN_ID_PATTERN",
        re.compile(
            r"(?:(?:q06|q17)-[a-z0-9]+-[a-z0-9]+-[0-9]+|adhoc-[0-9]{8}-[0-9]{6}"
            r"|course-c[0-9]{2}-[a-z0-9-]+-[0-9]+)"
        ),
    )


def _make_course_folders(dirs) -> None:
    for run_id in COURSE_FOLDERS:
        adapter = dirs.checkpoints / run_id
        adapter.mkdir()
        (adapter / "adapter_model.safetensors").write_bytes(b"\x00" * 16)
        run_dir = dirs.outputs / run_id
        run_dir.mkdir()
        (run_dir / "status.json").write_text("{}", encoding="utf-8")
    (dirs.outputs / "course").mkdir()
    (dirs.outputs / "course" / "runs.csv").write_text("date,run_id\n", encoding="utf-8")


def _other_adapter(dirs, run_id: str = "q06-sft-dev-9") -> Path:
    folder = dirs.checkpoints / run_id
    folder.mkdir()
    (folder / "adapter_model.safetensors").write_bytes(b"\x00" * 16)
    return folder


def _prune_args(dirs, yes: bool) -> argparse.Namespace:
    finalists = dirs.results.parent / "finalists.json"
    finalists.write_text(json.dumps({"v": 1, "finalists": []}) + "\n", encoding="utf-8")
    return argparse.Namespace(yes=yes, results=dirs.results, finalists=finalists)


def test_AC12_4_6_prune_leaves_course_folders(tmp_project_dirs, monkeypatch, capsys):
    from gsm8k import prune

    _course_ids_valid(monkeypatch)
    _make_course_folders(tmp_project_dirs)
    orphan = _other_adapter(tmp_project_dirs)  # a normal adapter with no row: prune deletes it
    append_row(tmp_project_dirs.results, _course_row("q06-base-dev-1", method="base"))
    log_before = tmp_project_dirs.results.read_bytes()

    code = prune.run_prune(_prune_args(tmp_project_dirs, yes=True))

    capsys.readouterr()
    assert code == 0
    assert not orphan.exists()  # prune still prunes what it prunes
    for run_id in COURSE_FOLDERS:
        assert (tmp_project_dirs.checkpoints / run_id / "adapter_model.safetensors").exists()
        assert (tmp_project_dirs.outputs / run_id / "status.json").exists()
    assert (tmp_project_dirs.outputs / "course" / "runs.csv").exists()
    assert tmp_project_dirs.results.read_bytes() == log_before


def test_AC12_4_6_plan_prune_never_lists_course_folders_to_delete(tmp_project_dirs, monkeypatch):
    from gsm8k import prune
    from gsm8k.run_records.log import read_rows

    _course_ids_valid(monkeypatch)
    _make_course_folders(tmp_project_dirs)
    _other_adapter(tmp_project_dirs)
    rows, _ = read_rows(tmp_project_dirs.results)
    plan = prune.plan_prune(rows, set(), tmp_project_dirs.checkpoints)
    assert {Path(p).name for p in plan.delete} == {"q06-sft-dev-9"}


def test_AC12_4_6_prune_without_yes_does_not_name_course_folders(tmp_project_dirs, monkeypatch, capsys):
    from gsm8k import prune

    _course_ids_valid(monkeypatch)
    _make_course_folders(tmp_project_dirs)
    _other_adapter(tmp_project_dirs)

    code = prune.run_prune(_prune_args(tmp_project_dirs, yes=False))

    out = capsys.readouterr().out
    assert code == 0
    assert "q06-sft-dev-9" in out
    would_delete = [line for line in out.splitlines() if line.startswith("Would delete")]
    assert len(would_delete) == 1 and "q06-sft-dev-9" in would_delete[0]  # no line for a course folder
    for run_id in COURSE_FOLDERS:
        assert (tmp_project_dirs.checkpoints / run_id).is_dir()


# --- AC12.3.3: c22's cotgen entry runs as `gsm8k cot-generate` ----------------------------------------

COTGEN_CONFIG = {"method": "cotgen", "split": "train", "limit": 100}


def _assert_cot_generate_launch(launches, outputs: Path) -> None:
    assert launches.run_ids() == [COTGEN_ID]
    argv = launches.argvs[0]
    assert argv[1:3] == ["-m", "gsm8k"]
    assert argv[3] == "cot-generate"
    assert argv[argv.index("--config") + 1] == str(outputs / COTGEN_ID / "config.json")
    assert argv[argv.index("--run-id") + 1] == COTGEN_ID
    assert launches.results_of(COTGEN_ID) == str(outputs / "course" / "runs.csv")


def test_AC12_3_3_worker_launches_cotgen_entry_as_cot_generate(tmp_project_dirs, launches):
    from gsm8k.run_control import queue as run_queue

    run_queue.add(
        COTGEN_ID, dict(COTGEN_CONFIG), "cot-generate", tmp_project_dirs.outputs, results=COURSE_RESULTS
    )
    _steps(_worker(tmp_project_dirs))
    _assert_cot_generate_launch(launches, tmp_project_dirs.outputs)


def test_AC12_3_3_cotgen_entry_without_kind_launches_as_cot_generate(tmp_project_dirs, launches):
    from gsm8k.run_control import queue as run_queue

    run_queue.add(COTGEN_ID, dict(COTGEN_CONFIG), None, tmp_project_dirs.outputs, results=COURSE_RESULTS)
    _steps(_worker(tmp_project_dirs))
    _assert_cot_generate_launch(launches, tmp_project_dirs.outputs)


# --- AC12.3.3: removing the awaited entry removes the entries waiting for it (changes.md 2026-11-16) ---


def _queue_cotgen_selfcot_and_unrelated(outputs: Path) -> None:
    from gsm8k.run_control import queue as run_queue

    run_queue.add(COTGEN_ID, dict(COTGEN_CONFIG), "cot-generate", outputs, results=COURSE_RESULTS)
    run_queue.add(SELFCOT_ID, dict(SFT_CONFIG), "train", outputs, results=COURSE_RESULTS, after=COTGEN_ID)
    run_queue.add(COURSE_ID_A, dict(EVAL_CONFIG), "evaluate", outputs, results=COURSE_RESULTS)


def _assert_awaiting_entry_went_with_it(outputs: Path) -> None:
    from gsm8k.run_control import queue as run_queue

    listed = run_queue.list_queue(outputs)
    assert [(e.attempt_id, e.position) for e in listed] == [(COURSE_ID_A, 1)]  # the unrelated entry moved up
    lines = [line for line in _queue_log(outputs) if SELFCOT_ID in line]
    assert len(lines) == 1
    assert COTGEN_ID in lines[0]


def test_AC12_3_3_removing_the_awaited_entry_removes_the_entries_waiting_for_it(tmp_project_dirs):
    from gsm8k.run_control import queue as run_queue

    _queue_cotgen_selfcot_and_unrelated(tmp_project_dirs.outputs)
    run_queue.remove(COTGEN_ID, outputs=tmp_project_dirs.outputs)
    _assert_awaiting_entry_went_with_it(tmp_project_dirs.outputs)


def test_AC12_3_3_deleting_the_awaited_entry_through_the_service_removes_the_waiting_one(tmp_project_dirs):
    from fastapi.testclient import TestClient

    from gsm8k.service.app import create_app

    _queue_cotgen_selfcot_and_unrelated(tmp_project_dirs.outputs)
    app = create_app(
        results=tmp_project_dirs.results,
        finalists=tmp_project_dirs.results.parent / "finalists.json",
        outputs=tmp_project_dirs.outputs,
    )
    with TestClient(app) as client:
        response = client.delete(f"/api/v1/queue/{COTGEN_ID}")
    assert response.status_code == 204, response.text
    _assert_awaiting_entry_went_with_it(tmp_project_dirs.outputs)


def test_AC12_3_3_entry_waits_while_the_after_attempt_is_still_queued(tmp_project_dirs, launches):
    from gsm8k.run_control import queue as run_queue

    _queue_selfcot_after_cotgen(tmp_project_dirs)
    # the awaited attempt is still in the queue, behind the entry: it will run, so the entry waits
    run_queue.add(
        COTGEN_ID, dict(COTGEN_CONFIG), "cot-generate", tmp_project_dirs.outputs, results=COURSE_RESULTS
    )
    _steps(_worker(tmp_project_dirs), 3)
    assert launches.argvs == []
    assert _queue_ids(tmp_project_dirs.outputs) == [SELFCOT_ID, COTGEN_ID]
    assert _queue_log(tmp_project_dirs.outputs) == []


def test_AC12_3_3_entry_waits_while_the_after_attempt_holds_the_lock(tmp_project_dirs, launches):
    from gsm8k.run_records.lock import GpuLock

    _queue_selfcot_after_cotgen(tmp_project_dirs)
    holder = GpuLock()
    holder.acquire(COTGEN_ID)  # it runs now, before it has made its run folder
    try:
        _steps(_worker(tmp_project_dirs), 3)
        assert launches.argvs == []
        assert _queue_ids(tmp_project_dirs.outputs) == [SELFCOT_ID]
        assert _queue_log(tmp_project_dirs.outputs) == []
    finally:
        holder.release()


# --- AC12.3.3: the worker taking the awaited entry off the queue is not a removal that cascades ---------

HOLD_STUB = """\
import sys
import time
from pathlib import Path

import gsm8k  # sets the in-folder caches first
from gsm8k.run_records import lock

run_id = sys.argv[sys.argv.index("--run-id") + 1]
gpu = lock.GpuLock()
gpu.acquire(run_id)
Path({held!r}).write_text("1")
end = time.monotonic() + 30
while time.monotonic() < end and not Path({release!r}).exists():
    time.sleep(0.02)
gpu.release()
"""


def _queue_cotgen_then_selfcot(outputs: Path) -> None:
    from gsm8k.run_control import queue as run_queue

    run_queue.add(COTGEN_ID, dict(COTGEN_CONFIG), "cot-generate", outputs, results=COURSE_RESULTS)
    run_queue.add(SELFCOT_ID, dict(SFT_CONFIG), "train", outputs, results=COURSE_RESULTS, after=COTGEN_ID)


def test_AC12_3_3_launching_the_awaited_entry_keeps_the_entry_waiting_for_it(
    tmp_project_dirs, tmp_path, monkeypatch
):
    from gsm8k.run_control import launch
    from gsm8k.run_records.lock import is_free

    held, release = tmp_path / "held", tmp_path / "release"
    script = tmp_path / "hold_stub.py"
    script.write_text(HOLD_STUB.format(held=str(held), release=str(release)), encoding="utf-8")
    recorded: list[list[str]] = []
    real = launch.build_argv

    def holding_build_argv(kind, attempt_id, config_path, results):
        recorded.append(real(kind, attempt_id, config_path, results))
        return [sys.executable, str(script)] + recorded[-1][3:]

    monkeypatch.setattr(launch, "build_argv", holding_build_argv)
    _queue_cotgen_then_selfcot(tmp_project_dirs.outputs)
    try:
        _worker(tmp_project_dirs).step(timeout=20.0)  # returns once cotgen holds the lock
        assert held.exists() and not is_free()
        run_ids = [argv[argv.index("--run-id") + 1] for argv in recorded]
        assert run_ids == [COTGEN_ID]
        assert _queue_ids(tmp_project_dirs.outputs) == [SELFCOT_ID]
        assert not [line for line in _queue_log(tmp_project_dirs.outputs) if SELFCOT_ID in line]
    finally:
        release.write_text("1")
        deadline = time.monotonic() + 10
        while not is_free() and time.monotonic() < deadline:
            time.sleep(0.02)


def test_AC12_3_3_an_awaited_entry_that_exits_before_the_lock_keeps_the_entry_waiting_for_it(
    tmp_project_dirs, launches
):
    _queue_cotgen_then_selfcot(tmp_project_dirs.outputs)
    _worker(tmp_project_dirs).step(timeout=10.0)  # the launch exits before it holds the lock
    assert launches.run_ids() == [COTGEN_ID]
    assert _queue_ids(tmp_project_dirs.outputs) == [SELFCOT_ID]  # no cascade from this removal
    assert not [line for line in _queue_log(tmp_project_dirs.outputs) if SELFCOT_ID in line]
