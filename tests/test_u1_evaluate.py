"""u1-eval-skeleton, part C: `gsm8k evaluate` (US1.4, workflow W4, BR4.1-BR4.8, BR5.1-BR5.3, C1, C2, C5).

Only the AC1.4.1 walking-skeleton test loads real weights (Qwen/Qwen3-0.6B-Base on the CPU, 3 dev
problems). Every other test runs the tiny random-weight model from conftest by patching
`gsm8k.evaluation.load_model`. All runs use temp outputs/checkpoints and a temp results file.
"""

import csv
import hashlib
import json
import re
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROJECT_RESULTS = ROOT / "results" / "runs.csv"

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
PREDICTION_KEYS = {"problem_id", "output", "predicted", "gold", "correct"}
TINY_ARGS = ["--split", "dev", "--limit", "2", "--max-new-tokens", "8"]


def _run_cli(argv: list[str]) -> int:
    """Call the command in-process; an argparse exit counts as its exit code."""
    from gsm8k.cli import main

    try:
        return main(argv)
    except SystemExit as exc:  # argparse rejects bad options with SystemExit(2)
        return exc.code if isinstance(exc.code, int) else 1


def _file_state(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def _run_dirs(outputs: Path) -> list[Path]:
    return [p for p in outputs.iterdir() if p.is_dir() and p.name != "splits"]


@pytest.fixture
def use_tiny_model(monkeypatch, tiny_model):
    """Every model load inside the command returns the tiny random-weight model."""
    import gsm8k.evaluation

    calls: list[tuple] = []

    def fake_load_model(model_id, revision, adapter_path=None):
        calls.append((model_id, revision, adapter_path))
        return tiny_model

    monkeypatch.setattr(gsm8k.evaluation, "load_model", fake_load_model)
    return calls


@pytest.fixture
def project_results_untouched():
    """The real results/runs.csv must be byte-for-byte the same after the test."""
    before = _file_state(PROJECT_RESULTS)
    yield
    assert _file_state(PROJECT_RESULTS) == before, "results/runs.csv was changed by a test"


# --- AC1.4.1: walking skeleton (real model, CPU) -------------------------------------------------


def test_AC1_4_1_skeleton_real_model_three_dev_problems(tmp_project_dirs, capsys, project_results_untouched):
    run_id = "q06-base-dev-1"
    rc = _run_cli(
        [
            "evaluate",
            "--model",
            "Qwen/Qwen3-0.6B-Base",
            "--split",
            "dev",
            "--limit",
            "3",
            "--max-new-tokens",
            "256",
            "--run-id",
            run_id,
            "--results",
            str(tmp_project_dirs.results),
        ]
    )
    out = capsys.readouterr()
    text = out.out + out.err
    assert rc == 0, text

    # Reports accuracy, the number scored and minutes (BR4.1).
    assert re.search(r"accuracy\D{0,20}\d", text, re.I), text
    scored = re.search(r"scored\D{0,20}(\d+)|(\d+)\s+problems?\s+scored", text, re.I)
    assert scored, text
    assert int(scored.group(1) or scored.group(2)) == 3
    assert re.search(r"minutes\D{0,20}\d|\d\s*min", text, re.I), text

    # One prediction per problem in outputs/<run_id>/predictions.jsonl.
    run_dir = tmp_project_dirs.outputs / run_id
    lines = (run_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines if line.strip()]
    assert len(records) == 3
    for rec in records:
        assert PREDICTION_KEYS <= set(rec), rec
    assert len({rec["problem_id"] for rec in records}) == 3

    # The 256-token cap is a recorded config field (C2, changes 2026-11-06), with greedy defaults.
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    assert config["max_new_tokens"] == 256
    assert config["model"] == "Qwen/Qwen3-0.6B-Base"
    assert config["split"] == "dev"
    assert config["limit"] == 3


# --- AC1.4.2: no --run-id -> temporary results path ----------------------------------------------


def test_AC1_4_2_without_run_id_row_goes_to_printed_temp_path(
    tmp_project_dirs, tmp_path, monkeypatch, capsys, use_tiny_model, project_results_untouched
):
    import gsm8k.run_records.paths as paths

    sentinel = tmp_path / "sentinel-project-results.csv"
    sentinel.write_text("sentinel, do not touch\n", encoding="utf-8")
    monkeypatch.setattr(paths, "DEFAULT_RESULTS", sentinel)
    import gsm8k.cli

    if hasattr(gsm8k.cli, "DEFAULT_RESULTS"):
        monkeypatch.setattr(gsm8k.cli, "DEFAULT_RESULTS", sentinel)
    temp_root = tmp_path / "tmpdir"
    temp_root.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp_root))

    rc = _run_cli(["evaluate", *TINY_ARGS])
    out = capsys.readouterr()
    text = out.out + out.err
    assert rc == 0, text

    assert sentinel.read_text(encoding="utf-8") == "sentinel, do not touch\n"

    # The printed temporary path holds the run's single row.
    candidates = [Path(m.rstrip(".,;:)]")) for m in re.findall(r"(/[^\s'\"]+)", text)]
    printed = [p for p in candidates if p.is_file() and p.suffix == ".csv"]
    assert printed, f"no results path printed:\n{text}"
    temp_results = printed[-1]
    assert temp_results.resolve() != PROJECT_RESULTS.resolve()
    assert temp_results.resolve() != sentinel.resolve()
    header, rows = _read_csv(temp_results)
    assert header == C1_COLUMNS
    assert len(rows) == 1
    assert rows[0]["run_id"].startswith("adhoc-")

    # The run folder is named after the ad hoc run id.
    names = [p.name for p in _run_dirs(tmp_project_dirs.outputs)]
    assert names == [rows[0]["run_id"]]


# --- AC1.4.3: --run-id appends exactly one C1 row ------------------------------------------------


def test_AC1_4_3_run_id_appends_exactly_one_c1_row(
    tmp_project_dirs, capsys, use_tiny_model, project_results_untouched
):
    results = tmp_project_dirs.results
    rc = _run_cli(["evaluate", *TINY_ARGS, "--run-id", "q06-base-dev-1", "--results", str(results)])
    text = "".join(capsys.readouterr())
    assert rc == 0, text

    header, rows = _read_csv(results)
    assert header == C1_COLUMNS
    assert len(rows) == 1
    row = rows[0]
    assert row["run_id"] == "q06-base-dev-1"
    assert row["model"] == "Qwen/Qwen3-0.6B-Base"
    assert row["method"] == "base"
    assert row["data"] == "gsm8k-dev"
    assert row["metric"] == "accuracy"
    assert 0.0 <= float(row["value"]) <= 1.0
    assert float(row["minutes"]) >= 0.0
    assert re.fullmatch(r"[0-9a-f]{64}", row["config_hash"])
    assert row["adapter_run"] == ""
    assert re.match(r"\d{4}-\d{2}-\d{2}T", row["date"])


def test_AC1_4_3_appends_to_an_existing_log(tmp_project_dirs, capsys, use_tiny_model):
    results = tmp_project_dirs.results
    with results.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(C1_COLUMNS)
        writer.writerow(
            [
                "2026-11-01T10:00:00Z",
                "q06-base-dev-7",
                "Qwen/Qwen3-0.6B-Base",
                "base",
                "gsm8k-dev",
                "accuracy",
                "0.5000",
                "1.0",
                "a" * 64,
                "",
            ]
        )
    rc = _run_cli(["evaluate", *TINY_ARGS, "--run-id", "q06-base-dev-1", "--results", str(results)])
    assert rc == 0, "".join(capsys.readouterr())
    _, rows = _read_csv(results)
    assert [r["run_id"] for r in rows] == ["q06-base-dev-7", "q06-base-dev-1"]


def test_AC1_4_3_finished_run_writes_status_and_config(tmp_project_dirs, capsys, use_tiny_model):
    rc = _run_cli(
        ["evaluate", *TINY_ARGS, "--run-id", "q06-base-dev-1", "--results", str(tmp_project_dirs.results)]
    )
    assert rc == 0, "".join(capsys.readouterr())
    run_dir = tmp_project_dirs.outputs / "q06-base-dev-1"
    status = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
    assert status["status"] == "finished"
    assert status["exit_code"] == 0
    assert status["run_id"] == "q06-base-dev-1"
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    assert config["run_id"] == "q06-base-dev-1"
    assert config["max_new_tokens"] == 8
    assert config["method"] == "base"
    assert config["adapter_path"] is None
    lines = (run_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
    assert len([line for line in lines if line.strip()]) == 2


def test_AC1_4_3_refuses_a_used_run_id(tmp_project_dirs, capsys, use_tiny_model):
    results = tmp_project_dirs.results
    argv = ["evaluate", *TINY_ARGS, "--run-id", "q06-base-dev-1", "--results", str(results)]
    assert _run_cli(argv) == 0
    capsys.readouterr()
    before = _file_state(results)

    rc = _run_cli(argv)
    text = "".join(capsys.readouterr())
    assert rc == 2
    assert "Run id already used" in text
    assert "q06-base-dev-1" in text
    assert _file_state(results) == before


def test_AC1_4_3_lock_held_exits_3_and_writes_nothing(tmp_project_dirs, capsys, use_tiny_model):
    from gsm8k.run_records.lock import GpuLock

    results = tmp_project_dirs.results
    lock = GpuLock()
    lock.acquire("q06-sft-dev-1")
    try:
        rc = _run_cli(["evaluate", *TINY_ARGS, "--run-id", "q06-base-dev-1", "--results", str(results)])
    finally:
        lock.release()
    text = "".join(capsys.readouterr())
    assert rc == 3
    assert "A run is already active: q06-sft-dev-1" in text
    assert not results.exists()
    assert not (tmp_project_dirs.outputs / "q06-base-dev-1").exists()


# --- AC1.4.4: seconds per problem saved -----------------------------------------------------------


def test_AC1_4_4_saves_seconds_per_problem(tmp_project_dirs, capsys, use_tiny_model):
    rc = _run_cli(
        ["evaluate", *TINY_ARGS, "--run-id", "q06-base-dev-1", "--results", str(tmp_project_dirs.results)]
    )
    assert rc == 0, "".join(capsys.readouterr())
    timings = json.loads((tmp_project_dirs.outputs / "q06-base-dev-1" / "timings.json").read_text("utf-8"))
    assert isinstance(timings["seconds_per_problem"], int | float)
    assert timings["seconds_per_problem"] > 0
    assert isinstance(timings["peak_gpu_memory_gb"], int | float)
    assert timings["peak_gpu_memory_gb"] >= 0


# --- AC1.4.6: missing adapter -> exit 2, message names the path, no row ---------------------------


def test_AC1_4_6_missing_adapter_exits_2_and_writes_no_row(
    tmp_project_dirs, capsys, use_tiny_model, project_results_untouched
):
    missing = tmp_project_dirs.checkpoints / "q06-sft-dev-9"
    results = tmp_project_dirs.results
    rc = _run_cli(
        [
            "evaluate",
            *TINY_ARGS,
            "--adapter",
            str(missing),
            "--run-id",
            "q06-best-dev-1",
            "--results",
            str(results),
        ]
    )
    text = "".join(capsys.readouterr())
    assert rc == 2
    assert "Adapter not found" in text
    assert str(missing) in text
    assert not results.exists()
    assert _run_dirs(tmp_project_dirs.outputs) == []
    assert use_tiny_model == [], "the model was loaded although the adapter is missing"


def test_AC1_4_6_unknown_option_exits_2(tmp_project_dirs, capsys, use_tiny_model):
    rc = _run_cli(["evaluate", "--not-an-option", "--results", str(tmp_project_dirs.results)])
    assert rc == 2
    assert not tmp_project_dirs.results.exists()


def test_AC1_4_6_bad_value_exits_2(tmp_project_dirs, capsys, use_tiny_model):
    rc = _run_cli(
        ["evaluate", "--split", "nonsense", "--limit", "2", "--results", str(tmp_project_dirs.results)]
    )
    assert rc == 2
    assert not tmp_project_dirs.results.exists()
    assert _run_dirs(tmp_project_dirs.outputs) == []
