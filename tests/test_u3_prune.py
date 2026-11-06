"""Prune of u3-sft (US2.5, FR2.5, contract C4): keep each model's best run and every finalist.

Every test builds its own fake data in temp folders (`tmp_project_dirs`): a run log written with
`gsm8k.run_records.log.append_row`, dummy adapter folders under the temp checkpoints, and a temp
finalists file in the C4 shape. Nothing touches the project's checkpoints/, outputs/,
results/runs.csv or results/finalists.json. `gsm8k.prune` is imported inside each test, so a missing
module fails each test on its own.
"""

import json
from pathlib import Path

from gsm8k.run_records.log import RunRow, append_row, read_rows

Q06 = "Qwen/Qwen3-0.6B-Base"
Q17 = "Qwen/Qwen3-1.7B-Base"

# (run_id, model, method, data, value, adapter_run), in run-log order.
ROWS = (
    ("q06-base-dev-1", Q06, "base", "gsm8k-dev", 0.5000, ""),  # highest q06 dev value, but no adapter
    ("q06-sft-dev-1", Q06, "sft", "gsm8k-dev", 0.4000, ""),
    ("q06-sft-dev-2", Q06, "sft", "gsm8k-dev", 0.4500, ""),  # q06 best: ties with -3, comes first
    ("q06-sft-dev-3", Q06, "sft", "gsm8k-dev", 0.4500, ""),  # the finalist in the C4 file
    ("q17-base-dev-1", Q17, "base", "gsm8k-dev", 0.7000, ""),
    ("q17-sft-dev-1", Q17, "sft", "gsm8k-dev", 0.6000, ""),  # q17 best on dev
    ("q17-sft-dev-2", Q17, "sft", "gsm8k-dev", 0.5500, ""),
    # A test-split score of q17-sft-dev-2's adapter: never counts for the best run (dev accuracy only).
    ("q17-sfttest-test-1", Q17, "sft", "gsm8k-test", 0.9900, "q17-sft-dev-2"),
)
ADAPTER_RUNS = ("q06-sft-dev-1", "q06-sft-dev-2", "q06-sft-dev-3", "q17-sft-dev-1", "q17-sft-dev-2")
FINALIST = "q06-sft-dev-3"
KEPT = {"q06-sft-dev-2", "q06-sft-dev-3", "q17-sft-dev-1"}
DELETED = {"q06-sft-dev-1", "q17-sft-dev-2"}


def _row(run_id, model, method, data, value, adapter_run, n):
    return RunRow(
        date=f"2026-11-0{1 + n // 9}T{10 + n % 9:02d}:00:00Z",
        run_id=run_id,
        model=model,
        method=method,
        data=data,
        metric="accuracy",
        value=value,
        minutes=12.0,
        config_hash=f"{n:064x}",
        adapter_run=adapter_run,
    )


def _write_log(path: Path, rows=ROWS) -> Path:
    for n, spec in enumerate(rows):
        append_row(path, _row(*spec, n))
    return path


def _make_adapter(checkpoints: Path, run_id: str) -> Path:
    folder = checkpoints / run_id
    folder.mkdir(parents=True)
    (folder / "adapter_model.safetensors").write_bytes(b"\x00" * 64)
    (folder / "adapter_config.json").write_text('{"r": 16}\n', encoding="utf-8")
    return folder


def _write_finalists(path: Path, run_ids) -> Path:
    data = {"v": 1, "finalists": [{"run_id": r, "marked_at": "2026-11-05T09:00:00Z"} for r in run_ids]}
    path.write_text(json.dumps(data) + "\n", encoding="utf-8")
    return path


def _setup(dirs, finalists=(FINALIST,)):
    results = _write_log(dirs.results)
    for run_id in ADAPTER_RUNS:
        _make_adapter(dirs.checkpoints, run_id)
    finalists_path = dirs.results.parent / "finalists.json"
    if finalists is not None:
        _write_finalists(finalists_path, finalists)
    return results, finalists_path


def _present(checkpoints: Path) -> set[str]:
    return {p.name for p in checkpoints.iterdir() if p.is_dir()}


def _prune_cli(results: Path, finalists: Path, *extra: str) -> int:
    from gsm8k import cli

    return cli.main(["prune", "--results", str(results), "--finalists", str(finalists), *extra])


# AC2.5.1 best run per model


def test_AC2_5_1_best_run_is_highest_dev_accuracy_per_model(tmp_project_dirs):
    from gsm8k import prune

    rows, skipped = read_rows(_write_log(tmp_project_dirs.results))
    assert skipped == 0
    best = prune.best_runs(rows)
    assert best[Q06].run_id == "q06-sft-dev-2"
    assert best[Q17].run_id == "q17-sft-dev-1"  # the 0.99 test-split row never counts


def test_AC2_5_1_tie_goes_to_the_earlier_run(tmp_project_dirs):
    from gsm8k import prune

    rows = [
        ("q06-sft-dev-5", Q06, "sft", "gsm8k-dev", 0.3000, ""),
        ("q06-sft-dev-7", Q06, "sft", "gsm8k-dev", 0.4200, ""),
        ("q06-sft-dev-4", Q06, "sft", "gsm8k-dev", 0.4200, ""),
        ("q06-sft-dev-6", Q06, "sft", "gsm8k-dev", 0.4200, ""),
    ]
    read, _ = read_rows(_write_log(tmp_project_dirs.results, rows))
    assert prune.best_runs(read)[Q06].run_id == "q06-sft-dev-7"


def test_AC2_5_1_base_rows_are_never_best(tmp_project_dirs):
    from gsm8k import prune

    rows = [
        ("q06-base-dev-1", Q06, "base", "gsm8k-dev", 0.9000, ""),
        ("q06-sft-dev-1", Q06, "sft", "gsm8k-dev", 0.1000, ""),
        ("q17-base-dev-1", Q17, "base", "gsm8k-dev", 0.8000, ""),
    ]
    read, _ = read_rows(_write_log(tmp_project_dirs.results, rows))
    best = prune.best_runs(read)
    assert best[Q06].run_id == "q06-sft-dev-1"
    assert best.get(Q17) is None  # a model with only base rows has no best run
    assert all(row.method != "base" for row in best.values())


# AC2.5.2 without --yes: list only


def test_AC2_5_2_without_yes_lists_and_deletes_nothing(tmp_project_dirs, capsys):
    results, finalists = _setup(tmp_project_dirs)
    log_before = results.read_bytes()

    code = _prune_cli(results, finalists)

    out = capsys.readouterr().out
    assert code == 0
    for run_id in DELETED:
        assert run_id in out, f"{run_id} should be listed as a folder prune would delete"
    assert _present(tmp_project_dirs.checkpoints) == set(ADAPTER_RUNS)
    for run_id in ADAPTER_RUNS:
        assert (tmp_project_dirs.checkpoints / run_id / "adapter_model.safetensors").exists()
    assert results.read_bytes() == log_before


def test_AC2_5_2_plan_prune_names_the_folders_to_delete(tmp_project_dirs):
    from gsm8k import prune

    results, finalists = _setup(tmp_project_dirs)
    rows, _ = read_rows(results)
    plan = prune.plan_prune(rows, prune.read_finalists(finalists), tmp_project_dirs.checkpoints)
    assert {Path(p).name for p in plan.delete} == DELETED
    assert KEPT <= set(plan.keep)
    assert plan.already_gone == []
    assert _present(tmp_project_dirs.checkpoints) == set(ADAPTER_RUNS)  # planning deletes nothing


# AC2.5.3 with --yes: delete all but best runs and finalists, run log unchanged


def test_AC2_5_3_with_yes_keeps_best_runs_and_finalists_only(tmp_project_dirs):
    results, finalists = _setup(tmp_project_dirs)
    log_before = results.read_bytes()
    finalists_before = finalists.read_bytes()

    code = _prune_cli(results, finalists, "--yes")

    assert code == 0
    assert _present(tmp_project_dirs.checkpoints) == KEPT
    for run_id in KEPT:
        assert (tmp_project_dirs.checkpoints / run_id / "adapter_model.safetensors").exists()
    assert results.read_bytes() == log_before
    assert finalists.read_bytes() == finalists_before


def test_AC2_5_3_read_finalists_reads_the_c4_file(tmp_path):
    from gsm8k import prune

    path = _write_finalists(tmp_path / "finalists.json", ["q06-sft-dev-3", "q17-sft-dev-2"])
    assert prune.read_finalists(path) == {"q06-sft-dev-3", "q17-sft-dev-2"}


def test_AC2_5_3_no_finalists_file_means_no_finalists(tmp_project_dirs, tmp_path):
    from gsm8k import prune

    missing = tmp_path / "nowhere" / "finalists.json"
    assert prune.read_finalists(missing) == set()

    results, _ = _setup(tmp_project_dirs, finalists=None)
    code = _prune_cli(results, missing, "--yes")
    assert code == 0
    # Without finalists only each model's best run stays; the former finalist goes too.
    assert _present(tmp_project_dirs.checkpoints) == {"q06-sft-dev-2", "q17-sft-dev-1"}
    assert not missing.exists()


def test_AC2_5_3_unreadable_finalists_file_names_it_and_deletes_nothing(tmp_project_dirs, capsys):
    from gsm8k import prune

    results, finalists = _setup(tmp_project_dirs, finalists=None)
    finalists.write_text('{"v": 1, "finalists": [', encoding="utf-8")
    log_before = results.read_bytes()

    try:
        prune.read_finalists(finalists)
    except ValueError as exc:
        assert str(finalists) in str(exc)
    else:
        raise AssertionError("an unreadable finalists file must raise ValueError")

    code = _prune_cli(results, finalists, "--yes")
    captured = capsys.readouterr()
    assert code != 0
    assert str(finalists) in captured.err + captured.out
    assert _present(tmp_project_dirs.checkpoints) == set(ADAPTER_RUNS)
    assert results.read_bytes() == log_before


def test_AC2_5_3_never_deletes_outside_the_checkpoints_folder(tmp_project_dirs, tmp_path):
    from gsm8k import prune

    results, finalists = _setup(tmp_project_dirs)
    # A row whose run id would point above checkpoints/ (read_rows does not check the pattern).
    victim = tmp_path / "victim"
    victim.mkdir()
    (victim / "adapter_model.safetensors").write_bytes(b"keep me")
    append_row(results, _row("../victim", Q06, "sft", "gsm8k-dev", 0.0100, "", 20))
    # Files beside the adapters: the run folders, the run log and a loose file in checkpoints/.
    run_folder = tmp_project_dirs.outputs / "q06-sft-dev-1"
    run_folder.mkdir()
    (run_folder / "config.json").write_text("{}\n", encoding="utf-8")
    loose = tmp_project_dirs.checkpoints / "notes.txt"
    loose.write_text("not an adapter folder\n", encoding="utf-8")
    log_before = results.read_bytes()

    # Whatever the plan holds lies directly under checkpoints/ (refusing the bad row is fine too).
    rows, _ = read_rows(results)
    root = tmp_project_dirs.checkpoints.resolve()
    try:
        plan = prune.plan_prune(rows, prune.read_finalists(finalists), tmp_project_dirs.checkpoints)
    except ValueError:
        plan = None
    if plan is not None:
        for path in plan.delete:
            assert Path(path).resolve().parent == root, f"{path} is not directly under {root}"

    try:  # refusing the bad row (exit code or error) is fine; deleting outside checkpoints/ is not
        _prune_cli(results, finalists, "--yes")
    except ValueError:
        pass

    assert (victim / "adapter_model.safetensors").read_bytes() == b"keep me"
    assert (run_folder / "config.json").exists()
    assert loose.exists()
    assert results.read_bytes() == log_before
    assert finalists.exists()
    assert tmp_project_dirs.checkpoints.is_dir()


# AC2.5.4 already pruned


def test_AC2_5_4_missing_adapter_folder_is_reported_already_pruned(tmp_project_dirs, capsys):
    from gsm8k import prune

    results, finalists = _setup(tmp_project_dirs)
    (tmp_project_dirs.checkpoints / "q17-sft-dev-2" / "adapter_model.safetensors").unlink()
    (tmp_project_dirs.checkpoints / "q17-sft-dev-2" / "adapter_config.json").unlink()
    (tmp_project_dirs.checkpoints / "q17-sft-dev-2").rmdir()

    rows, _ = read_rows(results)
    plan = prune.plan_prune(rows, prune.read_finalists(finalists), tmp_project_dirs.checkpoints)
    assert "q17-sft-dev-2" in plan.already_gone
    assert all(Path(p).name != "q17-sft-dev-2" for p in plan.delete)

    code = _prune_cli(results, finalists, "--yes")
    out = capsys.readouterr().out
    assert code == 0
    assert "already pruned" in out.lower()
    assert any("q17-sft-dev-2" in line and "already pruned" in line.lower() for line in out.splitlines())
    assert _present(tmp_project_dirs.checkpoints) == KEPT


# AC2.5.3 (changed 2026-11-06, commit 046e4aa): orphan adapter folders


def test_AC2_5_3_orphan_adapter_folder_without_a_row_is_deleted(tmp_project_dirs):
    results, finalists = _setup(tmp_project_dirs)
    _make_adapter(tmp_project_dirs.checkpoints, "q06-sft-dev-8")  # no row in the run log
    log_before = results.read_bytes()

    code = _prune_cli(results, finalists, "--yes")

    assert code == 0
    assert _present(tmp_project_dirs.checkpoints) == KEPT
    assert results.read_bytes() == log_before


def test_AC2_5_3_orphan_folder_of_the_run_holding_the_gpu_lock_is_kept(tmp_project_dirs):
    from gsm8k.run_records.lock import GpuLock

    results, finalists = _setup(tmp_project_dirs)
    _make_adapter(tmp_project_dirs.checkpoints, "q17-sft-dev-9")  # the run in progress, no row yet
    _make_adapter(tmp_project_dirs.checkpoints, "q06-sft-dev-8")  # an orphan of no active run
    log_before = results.read_bytes()

    gpu_lock = GpuLock()
    gpu_lock.acquire("q17-sft-dev-9")
    try:
        code = _prune_cli(results, finalists, "--yes")
        present = _present(tmp_project_dirs.checkpoints)
    finally:
        gpu_lock.release()

    assert code == 0  # prune needs no GPU lock
    assert present == KEPT | {"q17-sft-dev-9"}
    assert (tmp_project_dirs.checkpoints / "q17-sft-dev-9" / "adapter_model.safetensors").exists()
    assert results.read_bytes() == log_before
