"""u7-grpo, part G: the GRPO trainer and `gsm8k train --method grpo` (US7.1; AC7.1.2, AC7.1.3; contract C2).

Runs go through the command in-process on the CPU with the tiny random-weight model from conftest
(a fresh deep copy per load), a handful of made-up problems, 2 steps, 2 generations and 8-token
completions, temp outputs/ and checkpoints/ folders and a temp results file (never results/runs.csv).
AC7.1.5 is a `[manual]` long run and has no test here.

Hooks assumed in the code (the builder provides them):
  * ``gsm8k.train_cmd.load_base_model(model_id, revision)`` loads the base model for method grpo too,
    looked up at call time (as for sft); ``gsm8k.evaluation.load_model`` is the other loader patched.
  * ``gsm8k.training.grpo`` reads its training data through the module attribute
    ``sft.load_training_data(cfg, ...)`` (``gsm8k.training.sft``), not a from-import.
  * ``gsm8k train --method grpo`` takes ``--grpo-steps``, ``--grpo-generations`` and ``--adapter``
    (the supervised adapter folder to start from; stored as the config's ``adapter_path``).
  * A missing ``--adapter`` path exits non-zero (2) before any model load, naming the path on stderr.
"""

import copy
import csv
import hashlib
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROJECT_RESULTS = ROOT / "results" / "runs.csv"
RUN_ID = "q06-grpo-dev-1"
STEPS = 2
START_RANK = 8  # the supervised adapter's rank; differs from the run's --lora-rank
RUN_RANK = 4
GRPO_ARGS = [
    "train",
    "--method",
    "grpo",
    "--grpo-steps",
    str(STEPS),
    "--grpo-generations",
    "2",
    "--max-new-tokens",
    "8",
    "--limit",
    "2",
    "--max-seq-len",
    "256",
    "--batch-size",
    "2",
    "--lora-rank",
    str(RUN_RANK),
    "--learning-rate",
    "0.0005",
    "--train-examples",
    "50",
]
STEP_FIELDS = {"v", "step", "total_steps", "loss", "learning_rate", "elapsed_s", "eta_s"}


def _problem(i: int, split: str):
    from gsm8k.datasets_prompts.hub import Problem

    a, b = i + 2, i + 3
    return Problem(
        id=f"gsm8k-{split}-{i}",
        question=f"Tom has {a} apples and buys {b} more. How many apples does he have?",
        answer=f"{a} + {b} = <<{a}+{b}={a + b}>>{a + b}\n#### {a + b}",
        gold=str(a + b),
    )


def _fake_data():
    from gsm8k.training.sft import TrainingData

    return TrainingData(
        train=[_problem(i, "train") for i in range(4)],
        dev=[_problem(i, "dev") for i in range(10, 12)],
        exemplars=[_problem(i, "dev") for i in range(20, 24)],
    )


def _file_state(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _run_cli(argv: list[str]) -> tuple[int, str, str]:
    from gsm8k.cli import main

    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = main(argv)
        except SystemExit as exc:
            rc = exc.code if isinstance(exc.code, int) else 1
    return rc, out.getvalue(), err.getvalue()


def _patch(mp, tiny_model, loads: list) -> None:
    import gsm8k.evaluation
    import gsm8k.train_cmd
    from gsm8k.training import sft

    def fake_load(*args, **kwargs):
        loads.append(args)
        model, tokenizer = tiny_model
        return copy.deepcopy(model), copy.deepcopy(tokenizer)

    mp.setattr(gsm8k.train_cmd, "load_base_model", fake_load)
    mp.setattr(gsm8k.evaluation, "load_model", fake_load)
    mp.setattr(sft, "load_training_data", lambda cfg, train=None: _fake_data())


def _supervised_adapter(tiny_model, folder: Path) -> Path:
    """A quickly made peft LoRA adapter (rank START_RANK, non-zero weights) of the tiny model."""
    import torch
    from peft import LoraConfig, get_peft_model

    model = copy.deepcopy(tiny_model[0])
    lora = LoraConfig(
        r=START_RANK,
        lora_alpha=16,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        task_type="CAUSAL_LM",
    )
    peft_model = get_peft_model(model, lora)
    with torch.no_grad():
        for name, param in peft_model.named_parameters():
            if "lora_B" in name:
                param.normal_(0.0, 0.02)
    peft_model.save_pretrained(str(folder))
    return folder


def _adapter_rank(folder: Path) -> int:
    return json.loads((folder / "adapter_config.json").read_text())["r"]


def _rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _grpo(tmp_project_dirs, tiny_model, extra: list[str], monkeypatch) -> tuple[int, str, list]:
    loads: list = []
    before = _file_state(PROJECT_RESULTS)
    monkeypatch.chdir(tmp_project_dirs.results.parent.parent)
    _patch(monkeypatch, tiny_model, loads)
    rc, out, err = _run_cli(
        [*GRPO_ARGS, *extra, "--run-id", RUN_ID, "--results", str(tmp_project_dirs.results)]
    )
    assert _file_state(PROJECT_RESULTS) == before, "results/runs.csv was changed by a test"
    return rc, out + err, loads


def test_AC7_1_2_metrics_lines_hold_reward_kl_and_answer_length(tmp_project_dirs, tiny_model, monkeypatch):
    from gsm8k.training import loop

    rc, text, _ = _grpo(tmp_project_dirs, tiny_model, [], monkeypatch)
    assert rc == 0, text
    run_dir = tmp_project_dir_run(tmp_project_dirs)
    lines = loop.read_metrics(run_dir / loop.METRICS_FILE)
    steps = [line for line in lines if line.get("loss") is not None]
    assert len(steps) == STEPS, lines
    assert [line["step"] for line in steps] == list(range(1, STEPS + 1))
    for line in steps:
        assert STEP_FIELDS <= set(line), line
        assert line["total_steps"] == STEPS
        for key in ("reward", "kl", "answer_length"):
            assert isinstance(line[key], int | float) and not isinstance(line[key], bool), (key, line)
        assert 0.0 <= line["answer_length"] <= 8.0
        assert line["kl"] >= 0.0


def tmp_project_dir_run(dirs) -> Path:
    return dirs.outputs / RUN_ID


def test_AC7_1_2_run_ends_with_one_grpo_row_and_saves_the_adapter(tmp_project_dirs, tiny_model, monkeypatch):
    rc, text, _ = _grpo(tmp_project_dirs, tiny_model, [], monkeypatch)
    assert rc == 0, text
    rows = _rows(tmp_project_dirs.results)
    assert len(rows) == 1, rows
    assert rows[0]["run_id"] == RUN_ID
    assert rows[0]["method"] == "grpo"
    assert rows[0]["metric"] == "accuracy"
    assert 0.0 <= float(rows[0]["value"]) <= 1.0
    adapter = tmp_project_dirs.checkpoints / RUN_ID
    assert (adapter / "adapter_config.json").is_file()
    assert any(adapter.glob("adapter_model.*"))
    assert _adapter_rank(adapter) == RUN_RANK
    status = json.loads((tmp_project_dir_run(tmp_project_dirs) / "status.json").read_text())
    assert status["status"] == "finished"


def test_AC7_1_3_starts_from_the_base_model_without_an_adapter(tmp_project_dirs, tiny_model, monkeypatch):
    rc, text, loads = _grpo(tmp_project_dirs, tiny_model, [], monkeypatch)
    assert rc == 0, text
    assert loads, "the base model was never loaded"
    # a fresh adapter of the run's rank
    assert _adapter_rank(tmp_project_dirs.checkpoints / RUN_ID) == RUN_RANK


def test_AC7_1_3_starts_from_a_given_supervised_adapter_trainable(
    tmp_project_dirs, tiny_model, tmp_path, monkeypatch
):
    import peft

    start = _supervised_adapter(tiny_model, tmp_path / "supervised")
    calls: list[dict] = []
    original = peft.PeftModel.from_pretrained.__func__

    def spy(cls, model, model_id, *args, **kwargs):
        calls.append({"path": str(model_id), "is_trainable": kwargs.get("is_trainable")})
        return original(cls, model, model_id, *args, **kwargs)

    monkeypatch.setattr(peft.PeftModel, "from_pretrained", classmethod(spy))
    rc, text, loads = _grpo(tmp_project_dirs, tiny_model, ["--adapter", str(start)], monkeypatch)
    assert rc == 0, text
    assert loads, "the base model was never loaded"
    # The run continued the supervised adapter (its rank), not a fresh one of the run's rank.
    assert _adapter_rank(tmp_project_dirs.checkpoints / RUN_ID) == START_RANK
    assert any(c["path"] == str(start) for c in calls), calls
    assert all(c["is_trainable"] is True for c in calls if c["path"] == str(start)), calls
    assert [r["method"] for r in _rows(tmp_project_dirs.results)] == ["grpo"]


def test_AC7_1_3_missing_adapter_path_stops_before_loading_any_model(
    tmp_project_dirs, tiny_model, tmp_path, monkeypatch
):
    missing = tmp_path / "no-such-adapter"
    rc, text, loads = _grpo(tmp_project_dirs, tiny_model, ["--adapter", str(missing)], monkeypatch)
    assert rc != 0
    assert str(missing) in text, text
    assert loads == [], "a model was loaded before the missing path was caught"
    assert not (tmp_project_dirs.outputs / RUN_ID).exists()
    assert not (tmp_project_dirs.checkpoints / RUN_ID).exists()
    assert not tmp_project_dirs.results.exists()


def test_AC7_1_3_train_grpo_stops_on_a_missing_start_path_before_loading(
    tmp_project_dirs, tiny_model, tmp_path, monkeypatch
):
    """The trainer itself refuses a missing starting path (not only the command line)."""
    from gsm8k import run_config
    from gsm8k.training import grpo

    missing = tmp_path / "gone"
    cfg = run_config.RunConfig(
        run_id=RUN_ID, method="grpo", split="dev", adapter_path=str(missing), grpo_steps=1,
        grpo_generations=2, max_new_tokens=8, limit=2,
    )  # fmt: skip
    loads: list = []
    _patch(monkeypatch, tiny_model, loads)
    with pytest.raises(Exception) as info:
        grpo.train_grpo(cfg, tmp_project_dirs.outputs / RUN_ID, tmp_project_dirs.checkpoints / RUN_ID)
    assert str(missing) in str(info.value)
    assert loads == []
