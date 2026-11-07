"""u6-final-and-report, part F2: the final evaluation commands (US5.1, US6.1; BR4.6-BR4.8 as changed
2026-11-07; contracts C1, C2, C4, C5).

`gsm8k evaluate` gains the generalisation splits `gsmplus-testmini` and `gsmsym-p1` (AC5.1.1) and
`--method {base,best}` with `--finalists` (AC6.1.1); `gsm8k harness` gains `--adapter`, `--method` and
`--finalists` (it serves the q17-best-harness long run, AC6.1.3). The long runs AC5.1.3-AC5.1.6,
AC6.1.2 and AC6.1.3 are `[manual]` and have no tests here.

Every test runs on the CPU with the tiny random-weight model from conftest (`gsm8k.evaluation.load_model`
or `gsm8k.harness.load_model` patched; `gsm8k.harness.run_harness` patched), temp outputs/checkpoints
(`tmp_project_dirs`), a temp results file and a temp finalists file. The datasets load at their pinned
revisions from the project's `.cache/huggingface` (the first run downloads them once, no token).
"""

import csv
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROJECT_RESULTS = ROOT / "results" / "runs.csv"
PROJECT_FINALISTS = ROOT / "results" / "finalists.json"

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
FINALIST = "q06-sft-dev-1"
NOT_A_FINALIST = "Only finalists can be scored on the test split"
FAST = ["--max-new-tokens", "8"]


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


def _one_row(results: Path) -> dict[str, str]:
    assert results.exists(), "no results file was written"
    header, rows = _read_csv(results)
    assert header == C1_COLUMNS
    assert len(rows) == 1, rows
    return rows[0]


def _adapter_run(dirs, run_id: str = FINALIST, method: str = "sft") -> Path:
    """A finished adapter run: its config.json under outputs/<run_id>/ and its adapter folder under
    checkpoints/<run_id>/ (the patched loader never reads the weights)."""
    from gsm8k.run_config import RunConfig
    from gsm8k.run_records.folder import write_config

    run_folder = dirs.outputs / run_id
    run_folder.mkdir()
    write_config(run_folder, RunConfig(run_id=run_id, method=method, train_examples=50))
    adapter = dirs.checkpoints / run_id
    adapter.mkdir()
    (adapter / "adapter_config.json").write_text("{}", encoding="utf-8")
    return adapter


def _write_finalists(path: Path, run_ids: list[str]) -> Path:
    """A C4 finalists file."""
    content = {"v": 1, "finalists": [{"run_id": r, "marked_at": "2026-11-07T10:00:00Z"} for r in run_ids]}
    path.write_text(json.dumps(content), encoding="utf-8")
    return path


def _assert_nothing_written(dirs, run_id: str) -> None:
    assert not dirs.results.exists(), "a results file was written although the input was refused"
    assert not (dirs.outputs / run_id).exists(), "a run folder was written although the input was refused"


def _assert_refused_by_the_command(text: str) -> None:
    """The refusal comes from the command's own checks, not from argparse not knowing an option."""
    assert "unrecognized arguments" not in text, text
    assert "invalid choice" not in text, text


@pytest.fixture
def use_tiny_model(monkeypatch, tiny_model):
    """Every model load inside `gsm8k evaluate` returns the tiny random-weight model."""
    import gsm8k.evaluation

    calls: list[tuple] = []

    def fake_load_model(model_id, revision, adapter_path=None):
        calls.append((model_id, revision, adapter_path))
        return tiny_model

    monkeypatch.setattr(gsm8k.evaluation, "load_model", fake_load_model)
    return calls


@pytest.fixture
def captured_prompts(monkeypatch, tiny_model):
    """The prompt text of every problem the tiny model is asked to answer, decoded from its input."""
    model, tokenizer = tiny_model
    original = model.generate
    prompts: list[str] = []

    def generate(*args, **kwargs):
        input_ids = kwargs["input_ids"] if "input_ids" in kwargs else args[0]
        mask = kwargs.get("attention_mask")
        for i, row in enumerate(input_ids):
            tokens = row[mask[i].bool()] if mask is not None else row
            prompts.append(tokenizer.decode(tokens, skip_special_tokens=True))
        return original(*args, **kwargs)

    monkeypatch.setattr(model, "generate", generate)
    return prompts


@pytest.fixture
def project_files_untouched():
    """The real results/runs.csv and results/finalists.json must be byte-for-byte the same."""
    before = (_file_state(PROJECT_RESULTS), _file_state(PROJECT_FINALISTS))
    yield
    after = (_file_state(PROJECT_RESULTS), _file_state(PROJECT_FINALISTS))
    assert after == before, "results/runs.csv or results/finalists.json was changed by a test"


def _gsm8k_exemplars():
    """GSM8K's four fixed exemplars (BR2.1), computed the way the project's protocol does."""
    from gsm8k.datasets_prompts import hub, prompt, split

    problems = hub.load_gsm8k()
    data_split = split.build_split([p.id for p in problems["train"]])
    by_id = {p.id: p for p in problems["train"]}
    return [by_id[i] for i in prompt.choose_exemplars(data_split.dev_ids)]


# --- AC5.1.1: GSM-Plus testmini and GSM-Symbolic p1, 5 problems each, the GSM8K protocol -------------


@pytest.mark.parametrize(
    ("split_name", "run_id"),
    [("gsmplus-testmini", "q06-base-gsmplus-1"), ("gsmsym-p1", "q06-base-gsmsym-1")],
)
def test_AC5_1_1_generalisation_split_scored_with_gsm8k_protocol_writes_one_row(
    tmp_project_dirs, capsys, use_tiny_model, captured_prompts, project_files_untouched, split_name, run_id
):
    from gsm8k.datasets_prompts import hub, prompt

    results = tmp_project_dirs.results
    rc = _run_cli(
        [
            "evaluate",
            "--split",
            split_name,
            "--limit",
            "5",
            *FAST,
            "--run-id",
            run_id,
            "--results",
            str(results),
        ]
    )
    text = "".join(capsys.readouterr())
    assert rc == 0, text
    assert use_tiny_model, "gsm8k.evaluation.load_model was not used"

    # loaded: the first 5 problems of the pinned generalisation set, in row order
    problems, _left_out = hub.load_generalisation(split_name)
    first = problems[:5]
    assert len(first) == 5
    assert all(p.id.startswith(f"{split_name}-") for p in first), [p.id for p in first]

    # prompted: GSM8K's fixed 4-shot prompt with GSM8K's own four exemplars
    exemplars = _gsm8k_exemplars()
    expected = [prompt.build_prompt(exemplars, p.question) for p in first]
    assert sorted(captured_prompts) == sorted(expected)

    # scored: one prediction per problem, against the set's own gold answer
    lines = (tmp_project_dirs.outputs / run_id / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
    predictions = [json.loads(line) for line in lines if line.strip()]
    assert [r["problem_id"] for r in predictions] == [p.id for p in first]
    assert [r["gold"] for r in predictions] == [p.gold for p in first]

    # one C1 row with the C1 data value
    row = _one_row(results)
    assert row["run_id"] == run_id
    assert row["model"] == "Qwen/Qwen3-0.6B-Base"
    assert row["method"] == "base"
    assert row["data"] == split_name
    assert row["metric"] == "accuracy"
    assert 0.0 <= float(row["value"]) <= 1.0
    assert row["adapter_run"] == ""
    config = json.loads((tmp_project_dirs.outputs / run_id / "config.json").read_text(encoding="utf-8"))
    assert config["split"] == split_name
    assert config["limit"] == 5


def test_AC5_1_1_best_adapter_on_gsmplus_writes_a_best_row(
    tmp_project_dirs, tmp_path, capsys, use_tiny_model, project_files_untouched
):
    """The command behind AC5.1.5/AC5.1.6: the finalist's adapter on a generalisation set."""
    adapter = _adapter_run(tmp_project_dirs)
    finalists = _write_finalists(tmp_path / "finalists.json", [FINALIST])
    results = tmp_project_dirs.results
    rc = _run_cli(
        [
            "evaluate",
            "--method",
            "best",
            "--adapter",
            str(adapter),
            "--split",
            "gsmplus-testmini",
            "--limit",
            "5",
            *FAST,
            "--finalists",
            str(finalists),
            "--run-id",
            "q06-best-gsmplus-1",
            "--results",
            str(results),
        ]
    )
    text = "".join(capsys.readouterr())
    assert rc == 0, text
    row = _one_row(results)
    assert row["run_id"] == "q06-best-gsmplus-1"
    assert row["method"] == "best"
    assert row["data"] == "gsmplus-testmini"
    assert row["adapter_run"] == FINALIST
    assert [Path(c[2]).resolve() for c in use_tiny_model] == [adapter.resolve()]


# --- AC6.1.1: a finalist's adapter on 5 test problems writes one `best` row ------------------------


def test_AC6_1_1_finalist_adapter_on_test_writes_best_row_with_adapter_run(
    tmp_project_dirs, tmp_path, capsys, use_tiny_model, project_files_untouched
):
    adapter = _adapter_run(tmp_project_dirs)
    finalists = _write_finalists(tmp_path / "finalists.json", [FINALIST])
    results = tmp_project_dirs.results
    run_id = "q06-best-test-1"
    rc = _run_cli(
        [
            "evaluate",
            "--method",
            "best",
            "--adapter",
            str(adapter),
            "--split",
            "test",
            "--limit",
            "5",
            *FAST,
            "--finalists",
            str(finalists),
            "--run-id",
            run_id,
            "--results",
            str(results),
        ]
    )
    text = "".join(capsys.readouterr())
    assert rc == 0, text
    assert [Path(c[2]).resolve() for c in use_tiny_model] == [adapter.resolve()], "the adapter was not loaded"

    row = _one_row(results)
    assert row["run_id"] == run_id
    assert row["method"] == "best"
    assert row["data"] == "gsm8k-test"
    assert row["metric"] == "accuracy"
    assert row["adapter_run"] == FINALIST
    assert 0.0 <= float(row["value"]) <= 1.0

    config = json.loads((tmp_project_dirs.outputs / run_id / "config.json").read_text(encoding="utf-8"))
    assert config["method"] == "best"
    assert config["split"] == "test"
    assert config["adapter_path"]
    lines = (tmp_project_dirs.outputs / run_id / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
    assert len([line for line in lines if line.strip()]) == 5


def test_AC6_1_1_launcher_config_with_method_best_is_used_unchanged(
    tmp_project_dirs, tmp_path, capsys, use_tiny_model, project_files_untouched
):
    """The service's finalist flow writes config.json with method best and adapter_path (C2, C5); the
    worker passes it with --config, and the command keeps method best (BR4.8 as changed 2026-11-07)."""
    from gsm8k.run_config import RunConfig
    from gsm8k.run_records.folder import write_config

    adapter = _adapter_run(tmp_project_dirs)
    finalists = _write_finalists(tmp_path / "finalists.json", [FINALIST])
    run_id = "q06-best-test-1"
    run_folder = tmp_project_dirs.outputs / run_id
    run_folder.mkdir()
    cfg = RunConfig(
        run_id=run_id, method="best", split="test", adapter_path=str(adapter), limit=5, max_new_tokens=8
    )
    write_config(run_folder, cfg)
    config_path = run_folder / "config.json"
    written = json.loads(config_path.read_text(encoding="utf-8"))

    results = tmp_project_dirs.results
    rc = _run_cli(
        [
            "evaluate",
            "--config",
            str(config_path),
            "--run-id",
            run_id,
            "--results",
            str(results),
            "--finalists",
            str(finalists),
            "--started-by",
            "worker",
        ]
    )
    text = "".join(capsys.readouterr())
    assert rc == 0, text
    row = _one_row(results)
    assert row["run_id"] == run_id
    assert row["method"] == "best"
    assert row["data"] == "gsm8k-test"
    assert row["adapter_run"] == FINALIST
    assert json.loads(config_path.read_text(encoding="utf-8")) == written, "the launcher's config was changed"


def test_AC6_1_1_non_finalist_adapter_on_test_is_refused(
    tmp_project_dirs, tmp_path, capsys, use_tiny_model, project_files_untouched
):
    adapter = _adapter_run(tmp_project_dirs)
    finalists = _write_finalists(tmp_path / "finalists.json", ["q06-sft-dev-9"])
    run_id = "q06-best-test-1"
    rc = _run_cli(
        [
            "evaluate",
            "--method",
            "best",
            "--adapter",
            str(adapter),
            "--split",
            "test",
            "--limit",
            "5",
            *FAST,
            "--finalists",
            str(finalists),
            "--run-id",
            run_id,
            "--results",
            str(tmp_project_dirs.results),
        ]
    )
    text = "".join(capsys.readouterr())
    assert rc == 2, text
    assert NOT_A_FINALIST in text
    assert use_tiny_model == [], "the model was loaded although the input was refused"
    _assert_nothing_written(tmp_project_dirs, run_id)


def test_AC6_1_1_adapter_on_test_without_method_best_is_refused(
    tmp_project_dirs, tmp_path, capsys, use_tiny_model, project_files_untouched
):
    """An adapter's test-split evaluation must be method best, even for a finalist: without --method
    (the default, base) the command refuses instead of scoring the adapter as its own run's method."""
    adapter = _adapter_run(tmp_project_dirs)
    finalists = _write_finalists(tmp_path / "finalists.json", [FINALIST])
    run_id = "q06-sft-test-1"
    rc = _run_cli(
        [
            "evaluate",
            "--adapter",
            str(adapter),
            "--split",
            "test",
            "--limit",
            "5",
            *FAST,
            "--finalists",
            str(finalists),
            "--run-id",
            run_id,
            "--results",
            str(tmp_project_dirs.results),
        ]
    )
    text = "".join(capsys.readouterr())
    assert rc == 2, text
    _assert_refused_by_the_command(text)
    assert NOT_A_FINALIST in text
    assert use_tiny_model == [], "the model was loaded although the input was refused"
    _assert_nothing_written(tmp_project_dirs, run_id)


def test_AC6_1_1_adapter_on_test_with_method_base_is_refused(
    tmp_project_dirs, tmp_path, capsys, use_tiny_model, project_files_untouched
):
    adapter = _adapter_run(tmp_project_dirs)
    finalists = _write_finalists(tmp_path / "finalists.json", [FINALIST])
    run_id = "q06-base-test-1"
    rc = _run_cli(
        [
            "evaluate",
            "--method",
            "base",
            "--adapter",
            str(adapter),
            "--split",
            "test",
            "--limit",
            "5",
            *FAST,
            "--finalists",
            str(finalists),
            "--run-id",
            run_id,
            "--results",
            str(tmp_project_dirs.results),
        ]
    )
    text = "".join(capsys.readouterr())
    assert rc == 2, text
    _assert_refused_by_the_command(text)
    assert NOT_A_FINALIST in text
    assert use_tiny_model == []
    _assert_nothing_written(tmp_project_dirs, run_id)


def test_AC6_1_1_method_best_without_adapter_is_refused(
    tmp_project_dirs, tmp_path, capsys, use_tiny_model, project_files_untouched
):
    finalists = _write_finalists(tmp_path / "finalists.json", [FINALIST])
    run_id = "q06-best-test-1"
    rc = _run_cli(
        [
            "evaluate",
            "--method",
            "best",
            "--split",
            "test",
            "--limit",
            "5",
            *FAST,
            "--finalists",
            str(finalists),
            "--run-id",
            run_id,
            "--results",
            str(tmp_project_dirs.results),
        ]
    )
    text = "".join(capsys.readouterr())
    assert rc == 2, text
    _assert_refused_by_the_command(text)
    assert "adapter" in text.lower(), text
    assert use_tiny_model == []
    _assert_nothing_written(tmp_project_dirs, run_id)


def test_AC6_1_1_method_best_with_a_non_adapter_run_is_refused(
    tmp_project_dirs, tmp_path, capsys, use_tiny_model, project_files_untouched
):
    """Method best needs an adapter whose run's method makes an adapter (sft, grpo, terse, optuna)."""
    adapter = _adapter_run(tmp_project_dirs, run_id="q06-base-dev-3", method="base")
    finalists = _write_finalists(tmp_path / "finalists.json", ["q06-base-dev-3"])
    run_id = "q06-best-test-1"
    rc = _run_cli(
        [
            "evaluate",
            "--method",
            "best",
            "--adapter",
            str(adapter),
            "--split",
            "test",
            "--limit",
            "5",
            *FAST,
            "--finalists",
            str(finalists),
            "--run-id",
            run_id,
            "--results",
            str(tmp_project_dirs.results),
        ]
    )
    text = "".join(capsys.readouterr())
    assert rc == 2, text
    _assert_refused_by_the_command(text)
    assert use_tiny_model == []
    _assert_nothing_written(tmp_project_dirs, run_id)


# --- AC6.1.1 (serves AC6.1.3, q17-best-harness): `gsm8k harness --method best --adapter` -------------


@pytest.fixture
def harness_tiny_model(monkeypatch, tiny_model):
    """The harness command's model loader returns the tiny model; run_harness returns a fixed value."""
    import gsm8k.harness

    calls: list[tuple] = []

    def fake_load_model(model_id, revision, adapter_path=None):
        calls.append((model_id, revision, adapter_path))
        return tiny_model

    def fake_run_harness(model, tokenizer, *, limit, batch_size=8):
        return 0.25

    monkeypatch.setattr(gsm8k.harness, "load_model", fake_load_model)
    monkeypatch.setattr(gsm8k.harness, "run_harness", fake_run_harness)
    return calls


def _harness_argv(adapter: Path, finalists: Path, results: Path, run_id: str) -> list[str]:
    return [
        "harness",
        "--model",
        "Qwen/Qwen3-0.6B-Base",
        "--method",
        "best",
        "--adapter",
        str(adapter),
        "--finalists",
        str(finalists),
        "--limit",
        "5",
        "--run-id",
        run_id,
        "--results",
        str(results),
    ]


def test_AC6_1_1_harness_best_adapter_writes_row_with_adapter_run(
    tmp_project_dirs, tmp_path, capsys, harness_tiny_model, project_files_untouched
):
    adapter = _adapter_run(tmp_project_dirs)
    finalists = _write_finalists(tmp_path / "finalists.json", [FINALIST])
    results = tmp_project_dirs.results
    run_id = "q06-best-harness-1"
    rc = _run_cli(_harness_argv(adapter, finalists, results, run_id))
    text = "".join(capsys.readouterr())
    assert rc == 0, text
    assert [Path(c[2]).resolve() for c in harness_tiny_model] == [adapter.resolve()], (
        "the adapter was not loaded"
    )

    row = _one_row(results)
    assert row["run_id"] == run_id
    assert row["model"] == "Qwen/Qwen3-0.6B-Base"
    assert row["method"] == "best"
    assert row["data"] == "gsm8k-test-harness"
    assert row["metric"] == "harness_flexible_accuracy"
    assert float(row["value"]) == pytest.approx(0.25)
    assert row["adapter_run"] == FINALIST
    config = json.loads((tmp_project_dirs.outputs / run_id / "config.json").read_text(encoding="utf-8"))
    assert config["method"] == "best"
    assert config["evaluator"] == "lm-eval-harness"
    assert config["adapter_path"]


def test_AC6_1_1_harness_best_non_finalist_is_refused(
    tmp_project_dirs, tmp_path, capsys, harness_tiny_model, project_files_untouched
):
    adapter = _adapter_run(tmp_project_dirs)
    finalists = _write_finalists(tmp_path / "finalists.json", [])
    run_id = "q06-best-harness-1"
    rc = _run_cli(_harness_argv(adapter, finalists, tmp_project_dirs.results, run_id))
    text = "".join(capsys.readouterr())
    assert rc == 2, text
    assert NOT_A_FINALIST in text
    assert harness_tiny_model == []
    _assert_nothing_written(tmp_project_dirs, run_id)
