"""u3-sft, batch-6 part P2: gradient norm and epoch on the metrics lines (US2.2; contract C2).

AC2.2.6: a fine-tune step line also carries `grad_norm` and `epoch`, both null when the trainer reports
neither, and a line written before this change (without the two fields) is still a valid line.

The fine-tune runs once per module (`grad_run`) on the tiny random-weight model from conftest with
temp outputs/ and checkpoints/ folders and a temp results file, the same way `tests/test_u3_train.py`
runs its `sft_run`: 50 training examples, batch size 2, 3 steps, a 2-problem dev score every 2 steps.
Everything runs on the CPU; nothing touches the project's outputs/, checkpoints/ or results/runs.csv.
"""

import copy
import hashlib
import io
import json
import math
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROJECT_RESULTS = ROOT / "results" / "runs.csv"

RUN_ID = "q06-sft-dev-2"
MAX_STEPS = 3
EPOCHS = 1  # the default dial; the run below does not change it
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
    "4",
]
OLD_FIELDS = (
    "step",
    "total_steps",
    "loss",
    "learning_rate",
    "elapsed_s",
    "eta_s",
    "dev_accuracy",
    "reward",
    "kl",
    "answer_length",
)


def _is_number(value) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _file_state(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


# --- a short fine-tune, shared by the module's run tests ---------------------------------------------


@dataclass
class GradRun:
    rc: int
    text: str
    run_dir: Path

    def lines(self) -> list[dict]:
        assert self.rc == 0, self.text
        raw = (self.run_dir / "metrics.jsonl").read_text(encoding="utf-8")
        assert raw.endswith("\n"), "the last metrics line of a finished run is incomplete"
        return [json.loads(line) for line in raw.splitlines() if line.strip()]


@pytest.fixture(scope="module")
def grad_run(tmp_path_factory, tiny_model) -> GradRun:
    """One quick fine-tune on the tiny model with a dev evaluation at step 2 (so both line kinds exist)."""
    base = tmp_path_factory.mktemp("grad_run")
    outputs, checkpoints = base / "outputs", base / "checkpoints"
    results = base / "results" / "runs.csv"
    outputs.mkdir()
    checkpoints.mkdir()
    results.parent.mkdir()
    before = _file_state(PROJECT_RESULTS)

    def fresh(*args, **kwargs):
        model, tokenizer = tiny_model
        return copy.deepcopy(model), copy.deepcopy(tokenizer)

    def no_real_weights(*args, **kwargs):
        raise AssertionError("a test tried to load real model weights")

    with pytest.MonkeyPatch.context() as mp:
        import gsm8k.datasets_prompts.hub
        import gsm8k.evaluation
        import gsm8k.train_cmd
        from gsm8k.cli import main

        mp.setenv("GSM8K_OUTPUTS_DIR", str(outputs))
        mp.setenv("GSM8K_CHECKPOINTS_DIR", str(checkpoints))
        mp.setattr(gsm8k.train_cmd, "load_base_model", fresh)
        mp.setattr(gsm8k.evaluation, "load_model", fresh)
        mp.setattr(gsm8k.datasets_prompts.hub, "load_causal_lm", no_real_weights)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                rc = main([*TRAIN_ARGS, "--eval-every", "2", "--run-id", RUN_ID, "--results", str(results)])
            except SystemExit as exc:  # argparse rejects bad options with SystemExit(2)
                rc = exc.code if isinstance(exc.code, int) else 1
    assert _file_state(PROJECT_RESULTS) == before, "results/runs.csv was changed by a test"
    return GradRun(rc, out.getvalue() + err.getvalue(), outputs / RUN_ID)


# --- AC2.2.6: a fine-tune's step lines carry the gradient norm and the epoch -------------------------


def test_AC2_2_6_step_lines_carry_grad_norm_and_epoch(grad_run):
    lines = grad_run.lines()
    steps = [line for line in lines if line.get("dev_accuracy") is None]
    assert [line["step"] for line in steps] == list(range(1, MAX_STEPS + 1)), steps
    config = json.loads((grad_run.run_dir / "config.json").read_text("utf-8"))
    epochs = config["epochs"]
    assert epochs == EPOCHS
    for line in steps:
        assert "grad_norm" in line and "epoch" in line, line
        assert _is_number(line["grad_norm"]) and math.isfinite(line["grad_norm"]), line
        assert line["grad_norm"] >= 0, line
        assert _is_number(line["epoch"]), line
        assert 0 < line["epoch"] <= epochs, line
    # The fractional epoch only moves forward as the run goes.
    run_epochs = [line["epoch"] for line in steps]
    assert run_epochs == sorted(run_epochs), run_epochs
    assert run_epochs[-1] > run_epochs[0], run_epochs


def test_AC2_2_6_dev_accuracy_lines_leave_grad_norm_and_epoch_null(grad_run):
    lines = grad_run.lines()
    dev = [line for line in lines if line.get("dev_accuracy") is not None]
    assert dev, f"no dev-accuracy line in {lines}"
    for line in dev:
        assert "grad_norm" in line and "epoch" in line, line
        assert line["grad_norm"] is None and line["epoch"] is None, line


def test_AC2_2_6_the_existing_fields_of_a_fine_tune_line_are_still_written(grad_run):
    steps = [line for line in grad_run.lines() if line.get("dev_accuracy") is None]
    assert steps
    for line in steps:
        assert line["v"] == 1
        assert set(OLD_FIELDS) <= set(line), line
        assert _is_number(line["loss"]) and _is_number(line["learning_rate"]), line
        assert line["total_steps"] == MAX_STEPS, line


def test_AC2_2_6_metric_fields_end_with_grad_norm_and_epoch():
    from gsm8k.training.loop import METRIC_FIELDS

    assert tuple(METRIC_FIELDS) == (*OLD_FIELDS, "grad_norm", "epoch")


# --- AC2.2.6: the writer ------------------------------------------------------------------------------


def _writer(tmp_path):
    from gsm8k.training.loop import MetricsWriter

    run_dir = tmp_path / RUN_ID
    run_dir.mkdir()
    return MetricsWriter(run_dir), run_dir / "metrics.jsonl"


def test_AC2_2_6_writer_without_them_writes_both_as_null(tmp_path):
    writer, path = _writer(tmp_path)
    returned = writer.write(step=1, total_steps=3, loss=2.0, learning_rate=1e-4, elapsed_s=0.5, eta_s=1.0)
    assert "grad_norm" in returned and "epoch" in returned
    assert returned["grad_norm"] is None and returned["epoch"] is None
    raw = path.read_text(encoding="utf-8")
    assert raw.endswith("\n") and raw.count("\n") == 1
    on_disk = json.loads(raw)
    assert on_disk["grad_norm"] is None and on_disk["epoch"] is None
    assert on_disk["step"] == 1 and on_disk["loss"] == 2.0


def test_AC2_2_6_writer_writes_the_given_grad_norm_and_epoch(tmp_path):
    writer, path = _writer(tmp_path)
    writer.write(
        step=2,
        total_steps=3,
        loss=1.5,
        learning_rate=1e-4,
        elapsed_s=1.0,
        eta_s=0.5,
        grad_norm=0.42,
        epoch=0.08,
    )
    line = json.loads(path.read_text(encoding="utf-8"))
    assert line["grad_norm"] == pytest.approx(0.42)
    assert line["epoch"] == pytest.approx(0.08)
    assert line["step"] == 2


def test_AC2_2_6_writer_writes_a_non_finite_grad_norm_as_null(tmp_path):
    writer, path = _writer(tmp_path)
    writer.write(step=1, total_steps=3, loss=2.0, elapsed_s=0.5, grad_norm=float("nan"), epoch=0.04)
    writer.write(step=2, total_steps=3, loss=2.0, elapsed_s=1.0, grad_norm=float("inf"), epoch=0.08)
    first, second = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert first["grad_norm"] is None and first["epoch"] == pytest.approx(0.04)
    assert second["grad_norm"] is None and second["epoch"] == pytest.approx(0.08)


def test_AC2_2_6_writer_still_refuses_an_unknown_field(tmp_path):
    writer, path = _writer(tmp_path)
    with pytest.raises(ValueError, match="gradient"):
        writer.write(step=1, total_steps=3, gradient=1.0)
    assert not path.exists()


# --- AC2.2.6: the Trainer callback --------------------------------------------------------------------


def _callback(tmp_path, total_steps: int = 3):
    from gsm8k.training.loop import LoopClock, make_metrics_callback

    writer, path = _writer(tmp_path)
    clock = LoopClock()
    callback = make_metrics_callback(writer, clock, total_steps)
    state = SimpleNamespace(global_step=0)
    callback.on_train_begin(None, state, None)
    return callback, state, path


def _logged(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_AC2_2_6_callback_writes_grad_norm_and_epoch_from_the_trainer_logs(tmp_path):
    callback, state, path = _callback(tmp_path)
    state.global_step = 1
    callback.on_log(
        None, state, None, logs={"loss": 2.5, "learning_rate": 2e-4, "grad_norm": 0.87, "epoch": 0.04}
    )
    state.global_step = 2
    callback.on_log(None, state, None, logs={"loss": 2.1, "learning_rate": 1e-4, "grad_norm": 1, "epoch": 1})
    first, second = _logged(path)
    assert first["step"] == 1
    assert first["grad_norm"] == pytest.approx(0.87) and isinstance(first["grad_norm"], float)
    assert first["epoch"] == pytest.approx(0.04) and isinstance(first["epoch"], float)
    # A whole number from the trainer is still written as a float.
    assert second["step"] == 2
    assert second["grad_norm"] == 1.0 and isinstance(second["grad_norm"], float)
    assert second["epoch"] == 1.0 and isinstance(second["epoch"], float)


def test_AC2_2_6_callback_writes_null_when_the_trainer_reports_neither(tmp_path):
    callback, state, path = _callback(tmp_path)
    state.global_step = 1
    callback.on_log(None, state, None, logs={"loss": 2.5, "learning_rate": 2e-4})
    (line,) = _logged(path)
    assert "grad_norm" in line and "epoch" in line
    assert line["grad_norm"] is None and line["epoch"] is None
    assert line["loss"] == 2.5 and line["step"] == 1


def test_AC2_2_6_callback_reports_one_of_the_two_when_only_one_is_given(tmp_path):
    callback, state, path = _callback(tmp_path)
    state.global_step = 1
    callback.on_log(None, state, None, logs={"loss": 2.5, "grad_norm": 0.5})
    state.global_step = 2
    callback.on_log(None, state, None, logs={"loss": 2.4, "epoch": 0.08})
    first, second = _logged(path)
    assert first["grad_norm"] == pytest.approx(0.5) and first["epoch"] is None
    assert second["grad_norm"] is None and second["epoch"] == pytest.approx(0.08)


def test_AC2_2_6_callback_writes_a_nan_grad_norm_as_null(tmp_path):
    callback, state, path = _callback(tmp_path)
    state.global_step = 1
    callback.on_log(None, state, None, logs={"loss": 2.5, "grad_norm": float("nan"), "epoch": 0.04})
    (line,) = _logged(path)
    assert line["grad_norm"] is None
    assert line["epoch"] == pytest.approx(0.04)


def test_AC2_2_6_callback_writes_no_line_for_the_closing_summary(tmp_path):
    callback, state, path = _callback(tmp_path)
    state.global_step = 3
    callback.on_log(None, state, None, logs={"train_runtime": 6.8, "train_loss": 11.9, "epoch": 0.12})
    assert not path.exists() or _logged(path) == []


# --- AC2.2.6: a line written before this change is still valid ----------------------------------------


def test_AC2_2_6_read_metrics_reads_a_line_without_the_two_fields(tmp_path):
    from gsm8k.training.loop import read_metrics

    old = {
        "v": 1,
        "step": 1,
        "total_steps": 3,
        "loss": 2.5,
        "learning_rate": 1e-4,
        "elapsed_s": 1.0,
        "eta_s": 2.0,
        "dev_accuracy": None,
        "reward": None,
        "kl": None,
        "answer_length": None,
    }
    new = {**old, "step": 2, "loss": 2.1, "grad_norm": 0.7, "epoch": 0.08}
    path = tmp_path / "metrics.jsonl"
    path.write_text(json.dumps(old) + "\n" + json.dumps(new) + "\n", encoding="utf-8")
    lines = read_metrics(path)
    assert lines == [old, new]
    # Readers leave a line as written: nothing is added to the old line.
    assert "grad_norm" not in lines[0] and "epoch" not in lines[0]
    assert lines[1]["grad_norm"] == 0.7 and lines[1]["epoch"] == 0.08


def test_AC2_2_6_old_and_new_lines_can_share_one_file(tmp_path):
    from gsm8k.training.loop import MetricsWriter, read_metrics

    run_dir = tmp_path / RUN_ID
    run_dir.mkdir()
    old = {
        "v": 1,
        "step": 1,
        "total_steps": 3,
        "loss": 2.5,
        "learning_rate": 1e-4,
        "elapsed_s": 1.0,
        "eta_s": 2.0,
    }
    (run_dir / "metrics.jsonl").write_text(json.dumps(old) + "\n", encoding="utf-8")
    MetricsWriter(run_dir).write(
        step=2,
        total_steps=3,
        loss=2.1,
        learning_rate=1e-4,
        elapsed_s=2.0,
        eta_s=1.0,
        grad_norm=0.9,
        epoch=0.08,
    )
    lines = read_metrics(run_dir / "metrics.jsonl")
    assert [line["step"] for line in lines] == [1, 2]
    assert lines[0] == old
    assert lines[1]["grad_norm"] == pytest.approx(0.9) and lines[1]["epoch"] == pytest.approx(0.08)
