"""u2-baselines, part D: `gsm8k harness`, the lm-evaluation-harness cross-check (US1.5, AC1.5.5).

Contracts: C1 (row), C2 (run folder), C3 (lock), C5 (exit codes).

AC1.5.1-AC1.5.4 and AC1.5.6 are `[manual]` long runs and have no tests here. Every test runs on the
CPU with the tiny random-weight model from conftest (`gsm8k.harness.load_model` is patched), temp
outputs/checkpoints (`tmp_project_dirs`) and a temp results file; the real lm-evaluation-harness
`gsm8k` task runs on that tiny model on a handful of problems. Helper tests carry the part's only
criterion ID, AC1.5.5.
"""

import csv
import hashlib
import json
import re
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
RUN_ID = "q17-base-harness-1"
HEX64 = re.compile(r"[0-9a-f]{64}")


def _run_cli(argv: list[str]) -> int:
    """Call the command in-process; an argparse exit counts as its exit code."""
    from gsm8k.cli import main

    try:
        return main(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1


def _file_state(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def _harness_argv(results: Path, run_id: str = RUN_ID) -> list[str]:
    return ["harness", "--limit", "5", "--run-id", run_id, "--results", str(results)]


@pytest.fixture
def use_tiny_model(monkeypatch, tiny_model):
    """The harness command's model loader returns the tiny random-weight model."""
    import gsm8k.harness

    calls: list[tuple] = []

    def fake_load_model(*args, **kwargs):
        calls.append((args, kwargs))
        return tiny_model

    monkeypatch.setattr(gsm8k.harness, "load_model", fake_load_model)
    return calls


@pytest.fixture
def project_results_untouched():
    """The real results/runs.csv must be byte-for-byte the same after the test."""
    before = _file_state(PROJECT_RESULTS)
    yield
    assert _file_state(PROJECT_RESULTS) == before, "results/runs.csv was changed by a test"


def _assert_one_harness_row(results: Path) -> dict[str, str]:
    assert results.exists(), "no results file was written"
    header, rows = _read_csv(results)
    assert header[:2] == ["date", "run_id"]
    assert header == C1_COLUMNS
    assert len(rows) == 1, rows
    row = rows[0]
    assert row["run_id"] == RUN_ID
    assert row["method"] == "base"
    assert row["data"] == "gsm8k-test-harness"
    assert row["metric"] == "harness_flexible_accuracy"
    value = float(row["value"])
    assert 0.0 <= value <= 1.0
    assert HEX64.fullmatch(row["config_hash"]), row["config_hash"]
    assert float(row["minutes"]) >= 0
    assert row["adapter_run"] == ""
    return row


# --- AC1.5.5: the real harness on the tiny model, 5 problems --------------------------------------


def test_AC1_5_5_harness_writes_one_base_row(
    tmp_project_dirs, capsys, use_tiny_model, project_results_untouched
):
    from gsm8k import run_config

    results = tmp_project_dirs.results
    rc = _run_cli(_harness_argv(results))
    text = "".join(capsys.readouterr())
    assert rc == 0, text
    assert use_tiny_model, "gsm8k.harness.load_model was not used"

    row = _assert_one_harness_row(results)
    assert row["model"] == "Qwen/Qwen3-1.7B-Base"  # the command's default model

    run_dir = tmp_project_dirs.outputs / RUN_ID
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    assert config["method"] == "base"
    assert config["split"] == "test"
    assert config["run_id"] == RUN_ID
    cfg = run_config.read_config(run_dir / "config.json")
    assert row["config_hash"] == run_config.config_hash(cfg)

    status = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
    assert status["status"] == "finished"
    assert status["exit_code"] == 0
    assert status["run_id"] == RUN_ID
    assert (run_dir / "timings.json").exists()


def test_AC1_5_5_row_value_is_the_harness_accuracy(
    tmp_project_dirs, capsys, monkeypatch, use_tiny_model, project_results_untouched
):
    """Additional to the real-harness test: the row carries exactly what run_harness returned, and the
    command passes the --limit through."""
    import gsm8k.harness

    seen: list[dict] = []

    def fake_run_harness(model, tokenizer, *, limit, batch_size=8):
        seen.append({"model": model, "tokenizer": tokenizer, "limit": limit, "batch_size": batch_size})
        return 0.4

    monkeypatch.setattr(gsm8k.harness, "run_harness", fake_run_harness)
    results = tmp_project_dirs.results
    rc = _run_cli(_harness_argv(results))
    assert rc == 0, "".join(capsys.readouterr())
    assert len(seen) == 1
    assert seen[0]["limit"] == 5
    row = _assert_one_harness_row(results)
    assert float(row["value"]) == pytest.approx(0.4)


def test_AC1_5_5_run_harness_returns_accuracy_between_0_and_1(tiny_model):
    from gsm8k.harness import run_harness

    model, tokenizer = tiny_model
    accuracy = run_harness(model, tokenizer, limit=2, batch_size=2)
    assert isinstance(accuracy, float)
    assert 0.0 <= accuracy <= 1.0


def test_AC1_5_5_lock_held_exits_3_and_writes_nothing(
    tmp_project_dirs, capsys, use_tiny_model, project_results_untouched
):
    from gsm8k.run_records.lock import GpuLock

    results = tmp_project_dirs.results
    lock = GpuLock()
    lock.acquire("q06-sft-dev-1")
    try:
        rc = _run_cli(_harness_argv(results))
    finally:
        lock.release()
    text = "".join(capsys.readouterr())
    assert rc == 3, text
    assert "q06-sft-dev-1" in text
    assert not results.exists()
    assert not (tmp_project_dirs.outputs / RUN_ID).exists()
    assert not use_tiny_model, "the model was loaded although the lock was held"


@pytest.mark.parametrize(
    "bad_id", ["not a run id", "q17-base-harness", "adhoc-20261106-120000", "x99-base-harness-1"]
)
def test_AC1_5_5_invalid_run_id_exits_2_and_writes_nothing(
    tmp_project_dirs, capsys, use_tiny_model, project_results_untouched, bad_id
):
    results = tmp_project_dirs.results
    rc = _run_cli(_harness_argv(results, run_id=bad_id))
    capsys.readouterr()
    assert rc == 2
    assert not results.exists()
    assert [p for p in tmp_project_dirs.outputs.iterdir() if p.name != "run.lock"] == []
    assert not use_tiny_model


def test_AC1_5_5_help_lists_harness_command(capsys):
    rc = _run_cli(["--help"])
    out = capsys.readouterr().out
    assert rc == 0
    assert re.search(r"^\s+harness\b", out, re.M), out


def test_AC1_5_5_harness_help_lists_its_options(capsys):
    rc = _run_cli(["harness", "--help"])
    out = capsys.readouterr().out
    assert rc == 0
    for flag in ("--model", "--run-id", "--results", "--limit", "--started-by"):
        assert flag in out, f"{flag} missing from gsm8k harness --help"
