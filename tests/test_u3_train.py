"""u3-sft, part F: training (US2.2, US2.4; FR2.1, FR2.3, FR2.4, FR1.7; contracts C2, C3, C5).

Every run uses the tiny random-weight model from conftest (deep-copied, since LoRA training changes
the model it is given), temp outputs/ and checkpoints/ folders and a temp results file. The fine-tune
runs once per module (`sft_run`) with 50 training examples, 3 steps and a 2-problem dev score.
AC2.4.2 and AC2.4.3 are `[manual]` long runs and have no test here.
"""

import copy
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROJECT_RESULTS = ROOT / "results" / "runs.csv"

RUN_ID = "q06-sft-dev-1"
MAX_STEPS = 3
LORA_RANK = 4
METRIC_KEYS = {"v", "step", "total_steps", "loss", "learning_rate", "elapsed_s", "eta_s"}
ALL_LINEAR = {"q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"}
TRAIN_ARGS = [
    "train",
    "--train-examples",
    "50",
    "--max-steps",
    str(MAX_STEPS),
    "--limit",
    "2",
    "--max-seq-len",
    "256",
    "--batch-size",
    "2",
    "--lora-rank",
    str(LORA_RANK),
]


def _run_cli(argv: list[str]) -> int:
    """Call the command in-process; an argparse exit counts as its exit code."""
    from gsm8k.cli import main

    try:
        return main(argv)
    except SystemExit as exc:  # argparse rejects bad options with SystemExit(2)
        return exc.code if isinstance(exc.code, int) else 1


def _file_state(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _fresh_tiny(tiny_model):
    model, tokenizer = tiny_model
    return copy.deepcopy(model), copy.deepcopy(tokenizer)


def _patch_models(mp, tiny_model, *, train: bool = True) -> None:
    """Every model load returns a fresh copy of the tiny model; real weights are never loaded."""
    import gsm8k.datasets_prompts.hub
    import gsm8k.evaluation

    def fake_load(*args, **kwargs):
        return _fresh_tiny(tiny_model)

    def no_real_weights(*args, **kwargs):
        raise AssertionError("a test tried to load real model weights")

    if train:
        import gsm8k.train_cmd

        mp.setattr(gsm8k.train_cmd, "load_base_model", fake_load)
    mp.setattr(gsm8k.evaluation, "load_model", fake_load)
    mp.setattr(gsm8k.datasets_prompts.hub, "load_causal_lm", no_real_weights)


@dataclass
class SftRun:
    rc: int
    text: str
    outputs: Path
    checkpoints: Path
    results: Path

    @property
    def run_dir(self) -> Path:
        return self.outputs / RUN_ID

    def assert_finished(self) -> None:
        assert self.rc == 0, self.text


@pytest.fixture(scope="module")
def sft_run(tmp_path_factory, tiny_model) -> SftRun:
    """One quick fine-tune with a dev evaluation every 2 steps, shared by the module's tests."""
    base = tmp_path_factory.mktemp("sft_run")
    outputs, checkpoints = base / "outputs", base / "checkpoints"
    results = base / "results" / "runs.csv"
    outputs.mkdir()
    checkpoints.mkdir()
    results.parent.mkdir()
    before = _file_state(PROJECT_RESULTS)
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("GSM8K_OUTPUTS_DIR", str(outputs))
        mp.setenv("GSM8K_CHECKPOINTS_DIR", str(checkpoints))
        _patch_models(mp, tiny_model)
        import io
        from contextlib import redirect_stderr, redirect_stdout

        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = _run_cli([*TRAIN_ARGS, "--eval-every", "2", "--run-id", RUN_ID, "--results", str(results)])
    assert _file_state(PROJECT_RESULTS) == before, "results/runs.csv was changed by a test"
    return SftRun(rc, out.getvalue() + err.getvalue(), outputs, checkpoints, results)


@pytest.fixture
def patched_models(monkeypatch, tiny_model) -> None:
    _patch_models(monkeypatch, tiny_model)


@pytest.fixture
def patched_eval_model(monkeypatch, tiny_model) -> None:
    _patch_models(monkeypatch, tiny_model, train=False)


def _nothing_written(dirs, run_id: str = RUN_ID) -> None:
    assert not (dirs.outputs / run_id).exists(), "a run folder was written"
    assert not (dirs.checkpoints / run_id).exists(), "an adapter folder was written"
    assert not dirs.results.exists(), "the results file was written"


# --- AC2.2.1: the adapter is saved under checkpoints/<run_id>/ ---------------------------------


def test_AC2_2_1_saves_adapter_under_checkpoints_run_id(sft_run):
    sft_run.assert_finished()
    adapter = sft_run.checkpoints / RUN_ID
    assert adapter.is_dir(), f"no adapter folder at {adapter}"
    assert (adapter / "adapter_config.json").is_file()
    weights = [adapter / "adapter_model.safetensors", adapter / "adapter_model.bin"]
    assert any(p.is_file() for p in weights), sorted(p.name for p in adapter.iterdir())
    # Nothing but the adapter goes to checkpoints/ (the run files stay in outputs/<run_id>/).
    assert [p.name for p in sft_run.checkpoints.iterdir()] == [RUN_ID]


def test_AC2_2_1_adapter_is_lora_on_all_linear_layers_with_the_given_rank(sft_run):
    sft_run.assert_finished()
    adapter_config = json.loads((sft_run.checkpoints / RUN_ID / "adapter_config.json").read_text("utf-8"))
    assert adapter_config["peft_type"] == "LORA"
    assert adapter_config["r"] == LORA_RANK
    assert adapter_config["lora_alpha"] == 32  # the default dial
    targets = adapter_config["target_modules"]
    targets = set(targets) if isinstance(targets, list | tuple | set) else {targets}
    assert targets == {"all-linear"} or ALL_LINEAR <= targets, targets


def test_AC2_2_1_writes_config_with_method_sft_and_the_given_dials(sft_run):
    sft_run.assert_finished()
    config = json.loads((sft_run.run_dir / "config.json").read_text("utf-8"))
    assert config["run_id"] == RUN_ID
    assert config["method"] == "sft"
    assert config["model"] == "Qwen/Qwen3-0.6B-Base"
    assert config["train_examples"] == 50
    assert config["lora_rank"] == LORA_RANK
    assert config["max_seq_len"] == 256
    assert config["batch_size"] == 2
    assert config["limit"] == 2
    assert config["split"] != "test"
    status = json.loads((sft_run.run_dir / "status.json").read_text("utf-8"))
    assert status["status"] == "finished"
    assert status["exit_code"] == 0
    assert status["run_id"] == RUN_ID


def test_AC2_2_1_invalid_dial_exits_2_and_writes_nothing(tmp_project_dirs, patched_models, capsys):
    results = str(tmp_project_dirs.results)
    for bad in (["--learning-rate", "1"], ["--learning-rate", "abc"], ["--lora-rank", "5"]):
        rc = _run_cli([*TRAIN_ARGS, *bad, "--run-id", RUN_ID, "--results", results])
        text = "".join(capsys.readouterr())
        assert rc == 2, f"{bad}: exit {rc}\n{text}"
        if bad == ["--learning-rate", "1"]:
            assert "learning" in text.lower(), text  # the message names the dial
        _nothing_written(tmp_project_dirs)


def test_AC2_2_1_lock_held_exits_3_and_writes_nothing(tmp_project_dirs, patched_models, capsys):
    from gsm8k.run_records.lock import GpuLock

    holder = GpuLock()
    holder.acquire("q06-base-dev-9")
    try:
        rc = _run_cli([*TRAIN_ARGS, "--run-id", RUN_ID, "--results", str(tmp_project_dirs.results)])
    finally:
        holder.release()
    text = "".join(capsys.readouterr())
    assert rc == 3, text
    assert "A run is already active" in text
    assert "q06-base-dev-9" in text
    _nothing_written(tmp_project_dirs)


def test_AC2_2_1_sft_on_the_test_split_is_refused(tmp_project_dirs, tmp_path, patched_models, capsys):
    from gsm8k import run_config

    cfg = run_config.RunConfig(run_id=RUN_ID, method="sft", split="test", train_examples=50, limit=2)
    given = tmp_path / "given-config.json"
    given.write_text(json.dumps(run_config.to_dict(cfg)), encoding="utf-8")
    rc = _run_cli(
        [
            "train",
            "--config",
            str(given),
            "--run-id",
            RUN_ID,
            "--results",
            str(tmp_project_dirs.results),
        ]
    )
    text = "".join(capsys.readouterr())
    assert rc == 2, text
    assert "The test split is never used for training or tuning" in text
    _nothing_written(tmp_project_dirs)


# --- AC2.2.1 (helper): training targets ----------------------------------------------------------

NATALIA = (
    "Natalia sold 48/2 = <<48/2=24>>24 clips in May.\n"
    "Natalia sold 48+24 = <<48+24=72>>72 clips altogether in April and May.\n"
    "#### 72"
)
NATALIA_QUESTION = (
    "Natalia sold clips to 48 of her friends in April, and then she sold half as many clips in May."
)


def _problem():
    from gsm8k.datasets_prompts.hub import Problem

    return Problem(id="train-0", question=NATALIA_QUESTION, answer=NATALIA, gold="72")


def test_AC2_2_1_step_by_step_target_strips_notes_and_ends_with_gold():
    from gsm8k.training.targets import training_text

    prompt, target = training_text(_problem(), "step-by-step")
    assert prompt.rstrip() == f"Question: {NATALIA_QUESTION}\nAnswer:"
    assert "<<" not in target and ">>" not in target
    assert target.strip() == (
        "Natalia sold 48/2 = 24 clips in May.\n"
        "Natalia sold 48+24 = 72 clips altogether in April and May.\n"
        "#### 72"
    )
    assert target.rstrip().endswith("#### 72")


def test_AC2_2_1_terse_target_is_only_the_gold_line():
    from gsm8k.training.targets import training_text

    prompt, target = training_text(_problem(), "terse")
    assert prompt.rstrip() == f"Question: {NATALIA_QUESTION}\nAnswer:"
    assert target.strip() == "#### 72"


# --- AC2.2.2: metrics.jsonl lines, and a half-written last line is never data -------------------


def _metric_lines(run_dir: Path) -> list[dict]:
    text = (run_dir / "metrics.jsonl").read_text(encoding="utf-8")
    assert text.endswith("\n"), "the last metrics line of a finished run is incomplete"
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def test_AC2_2_2_every_metrics_line_is_a_full_json_object(sft_run):
    sft_run.assert_finished()
    lines = _metric_lines(sft_run.run_dir)
    assert lines, "metrics.jsonl has no lines"
    for line in lines:
        assert isinstance(line, dict), line
        assert METRIC_KEYS <= set(line), line
        assert line["v"] == 1
        assert isinstance(line["step"], int) and not isinstance(line["step"], bool)
        assert line["total_steps"] == MAX_STEPS, line
        assert 0 <= line["step"] <= line["total_steps"], line
        assert isinstance(line["elapsed_s"], int | float) and line["elapsed_s"] >= 0, line
        assert line["eta_s"] is None or (isinstance(line["eta_s"], int | float) and line["eta_s"] >= 0), line
    training = [line for line in lines if line.get("dev_accuracy") is None]
    assert training, "no training-step metrics line"
    for line in training:
        assert isinstance(line["loss"], int | float), line
        assert isinstance(line["learning_rate"], int | float), line
    steps = [line["step"] for line in training]
    assert steps == sorted(steps)
    assert steps[-1] == MAX_STEPS


def test_AC2_2_2_read_metrics_skips_a_half_written_last_line(tmp_path):
    from gsm8k.training.loop import read_metrics

    first = {
        "v": 1,
        "step": 1,
        "total_steps": 3,
        "loss": 2.5,
        "learning_rate": 1e-4,
        "elapsed_s": 1.0,
        "eta_s": 2.0,
    }
    second = {**first, "step": 2, "loss": 2.1, "elapsed_s": 2.0, "eta_s": 1.0}
    path = tmp_path / "metrics.jsonl"
    full = json.dumps(first) + "\n" + json.dumps(second) + "\n"
    path.write_text(full + '{"v": 1, "step": 3, "total_st', encoding="utf-8")
    assert read_metrics(path) == [first, second]

    # A last line whose newline has not been written yet is not finished either.
    path.write_text(full + json.dumps({**first, "step": 3}), encoding="utf-8")
    assert read_metrics(path) == [first, second]

    path.write_text(full, encoding="utf-8")
    assert read_metrics(path) == [first, second]


def test_AC2_2_2_read_metrics_of_a_missing_file_is_no_lines(tmp_path):
    from gsm8k.training.loop import read_metrics

    assert read_metrics(tmp_path / "missing" / "metrics.jsonl") == []


def test_AC2_2_2_metrics_writer_appends_whole_lines(tmp_path):
    from gsm8k.training.loop import MetricsWriter, read_metrics

    run_dir = tmp_path / "q06-sft-dev-1"
    run_dir.mkdir()
    writer = MetricsWriter(run_dir)
    assert read_metrics(run_dir / "metrics.jsonl") == []
    for name in ("write", "append", "log"):
        method = getattr(writer, name, None)
        if callable(method):
            break
    else:
        pytest.fail("MetricsWriter has no write/append/log method")
    method(step=1, total_steps=3, loss=2.0, learning_rate=1e-4, elapsed_s=0.5, eta_s=1.0)
    method(step=2, total_steps=3, loss=1.5, learning_rate=1e-4, elapsed_s=1.0, eta_s=0.5)
    text = (run_dir / "metrics.jsonl").read_text(encoding="utf-8")
    assert text.endswith("\n") and text.count("\n") == 2
    lines = read_metrics(run_dir / "metrics.jsonl")
    assert [line["step"] for line in lines] == [1, 2]
    for line in lines:
        assert METRIC_KEYS <= set(line)
        assert line["v"] == 1
        for key in ("reward", "kl", "answer_length", "dev_accuracy"):
            assert line.get(key) is None


# --- AC2.2.3: a dev evaluation during training adds a dev_accuracy line --------------------------


def test_AC2_2_3_eval_during_training_adds_dev_accuracy_line(sft_run):
    sft_run.assert_finished()
    lines = _metric_lines(sft_run.run_dir)
    dev = [line for line in lines if line.get("dev_accuracy") is not None]
    assert dev, f"no metrics line with dev_accuracy in {lines}"
    for line in dev:
        assert METRIC_KEYS <= set(line), line
        assert 0.0 <= line["dev_accuracy"] <= 1.0, line
    assert any(line["step"] == 2 for line in dev), dev


# --- AC2.2.4: one row with method sft, data gsm8k-dev and the run's config_hash ------------------


def test_AC2_2_4_appends_one_sft_row_with_config_hash(sft_run):
    sft_run.assert_finished()
    from gsm8k import run_config

    rows = _read_rows(sft_run.results)
    assert len(rows) == 1, rows
    row = rows[0]
    assert row["run_id"] == RUN_ID
    assert row["model"] == "Qwen/Qwen3-0.6B-Base"
    assert row["method"] == "sft"
    assert row["data"] == "gsm8k-dev"
    assert row["metric"] == "accuracy"
    assert 0.0 <= float(row["value"]) <= 1.0
    assert float(row["minutes"]) >= 0.0
    expected = run_config.config_hash(run_config.read_config(sft_run.run_dir / "config.json"))
    assert row["config_hash"] == expected


# --- AC2.2.5 and AC2.4.1: timings.json holds seconds per step and peak GPU memory ----------------


def test_AC2_2_5_saves_seconds_per_step(sft_run):
    sft_run.assert_finished()
    timings = json.loads((sft_run.run_dir / "timings.json").read_text("utf-8"))
    assert timings["v"] == 1
    assert isinstance(timings["seconds_per_step"], int | float)
    assert timings["seconds_per_step"] > 0


def test_AC2_4_1_training_run_saves_peak_gpu_memory(sft_run):
    sft_run.assert_finished()
    timings = json.loads((sft_run.run_dir / "timings.json").read_text("utf-8"))
    assert isinstance(timings["peak_gpu_memory_gb"], int | float)
    assert timings["peak_gpu_memory_gb"] >= 0


def test_AC2_4_1_evaluation_run_saves_peak_gpu_memory(tmp_project_dirs, patched_eval_model, capsys):
    run_id = "q06-base-dev-1"
    rc = _run_cli(
        [
            "evaluate",
            "--split",
            "dev",
            "--limit",
            "2",
            "--max-new-tokens",
            "8",
            "--run-id",
            run_id,
            "--results",
            str(tmp_project_dirs.results),
        ]
    )
    assert rc == 0, "".join(capsys.readouterr())
    timings = json.loads((tmp_project_dirs.outputs / run_id / "timings.json").read_text("utf-8"))
    assert isinstance(timings["peak_gpu_memory_gb"], int | float)
    assert timings["peak_gpu_memory_gb"] >= 0
