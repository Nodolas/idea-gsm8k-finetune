"""u11-finetune-lab, US11.2: `gsm8k lab run` on the CPU (contract C8).

The lab model is replaced by deep copies of the session `tiny_model` fixture (never the shared object:
peft injects its layers in place) through the `gsm8k.lab.trainer.load_lab_model` seam, the problems by
a handful of fixture problems through `load_lab_problems`, and every configuration is made tiny by
wrapping `config_for` (16 training examples, batch 4, 8 dev problems, 16 new tokens, 1 sample problem,
64 tokens). Outputs go to temp folders only; `os.nice` and `torch.set_num_threads` are recorded instead
of changing the test process.
"""

import copy
import dataclasses
import fcntl
import importlib
import json
import math
import os
import resource
import signal
import subprocess
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
import torch.nn.functional as F

from gsm8k import cli, evaluation
from gsm8k.datasets_prompts import guard, hub, prompt, split
from gsm8k.datasets_prompts.hub import Problem
from gsm8k.lab import config as lab_config
from gsm8k.lab import lessons as lab_lessons
from gsm8k.lab import trainer as lab_trainer
from gsm8k.run_records import paths
from gsm8k.training.sft import tokenize_examples
from gsm8k.training.targets import training_prompt

ROOT = Path(__file__).resolve().parents[1]

TINY = {
    "train_examples": 16,
    "batch_size": 4,
    "dev_problems": 8,
    "max_new_tokens": 16,
    "sample_problems": 1,
    "max_seq_len": 64,
}

SUMMARY_FIELDS = {
    "v",
    "lesson",
    "variant",
    "label",
    "config",
    "trainable_params",
    "total_params",
    "steps",
    "seconds",
    "seconds_per_step",
    "tokenize_seconds",
    "retokenize_seconds_per_step",
    "padding_fraction",
    "peak_memory_mb",
    "train_loss_first",
    "train_loss_last",
    "dev_loss_before",
    "dev_loss_after",
    "dev_loss_best",
    "dev_loss_best_step",
    "accuracy_before",
    "accuracy_after",
    "format_rate_before",
    "format_rate_after",
    "samples",
}
LINE_FIELDS = {"v", "step", "total_steps", "loss", "learning_rate", "grad_norm", "elapsed_s", "dev_loss"}


# ---------------------------------------------------------------- fixture problems


def _problem(index: int, a: int, b: int, filler: int = 0) -> Problem:
    extra = " The shop on the corner is open all day long." * filler
    question = f"Tom has {a} apples.{extra} He buys {b} more. How many apples does he have?"
    answer = f"Tom has {a} + {b} = <<{a}+{b}={a + b}>>{a + b} apples.\n#### {a + b}"
    return Problem(id=f"gsm8k-train-{index}", question=question, answer=answer, gold=str(a + b))


TRAIN = [_problem(i, i + 2, 3) for i in range(16)]
DEV = [_problem(100 + i, i + 5, 4) for i in range(8)]
# Same text under 16 ids: every batch has the same loss, whatever the shuffle, and no padding.
SAME = [dataclasses.replace(_problem(0, 6, 7), id=f"gsm8k-train-{i}") for i in range(16)]
# Lengths differ a lot (0 to 3 filler sentences): length-grouped batches need less padding.
VARIED = [_problem(i, i + 2, 3, filler=i % 4) for i in range(16)]
# A question longer than 64 tokens leaves no answer token after the cut.
LONG = [
    Problem(
        id=f"gsm8k-train-{200 + i}",
        question="Count the words. " + "word " * 90 + "How many?",
        answer="There are 90.\n#### 90",
        gold="90",
    )
    for i in range(16)
]


def _fake_output(index: int, gold: str) -> str:
    """Right with a #### line (0, 1), wrong with a #### line (2), no #### line and no number (3)."""
    kind = index % 4
    if kind in (0, 1):
        return f"{gold} apples.\n#### {gold}"
    if kind == 2:
        return "\n#### 999"
    return " I am not sure."


# ---------------------------------------------------------------- helpers


def _flock_held(path: Path) -> bool:
    try:
        fd = os.open(path, os.O_RDONLY)
    except FileNotFoundError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def _read_json(path: Path):
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    return json.loads(text) if text.strip() else None


def _lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _step_lines(path: Path) -> list[dict]:
    return [line for line in _lines(path) if line["dev_loss"] is None]


def _dev_lines(path: Path) -> list[dict]:
    return [line for line in _lines(path) if line["dev_loss"] is not None]


def _label(lesson_id: str, variant: str) -> str:
    lesson = next(lesson for lesson in lab_lessons.LESSONS if lesson.id == lesson_id)
    return next(v.label for v in lesson.variants if v.name == variant)


def _tiny_cfg(**extra):
    return dataclasses.replace(lab_config.LabConfig(), **{**TINY, **extra})


def _expected_lora(model, rank: int) -> int:
    layers = model.get_decoder().layers
    return sum(
        rank * (m.in_features + m.out_features) for m in layers.modules() if isinstance(m, torch.nn.Linear)
    )


def _n_params(model) -> int:
    return sum(p.numel() for p in model.parameters())


def _reference_loss(model, tokenizer, problems, answer_format, max_seq_len, loss_on="answer") -> float:
    """Token-weighted mean next-token loss of the untrained model, one example at a time (no padding)."""
    total, count = 0.0, 0
    with torch.no_grad():
        for example in tokenize_examples(tokenizer, problems, answer_format, max_seq_len):
            ids = torch.tensor([example["input_ids"]])
            labels = torch.tensor([example["labels"] if loss_on == "answer" else example["input_ids"]])
            logits = model(input_ids=ids).logits[:, :-1]
            target = labels[:, 1:]
            total += F.cross_entropy(
                logits.reshape(-1, logits.size(-1)), target.reshape(-1), ignore_index=-100, reduction="sum"
            ).item()
            count += int((target != -100).sum())
    return total / count


def _unhandled_sigterm(signum, frame):
    raise RuntimeError("SIGTERM reached the test's own handler: the lab run installed none")


def run_lab(*args: str) -> int:
    previous = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, _unhandled_sigterm)
    try:
        return cli.main(["lab", "run", *args])
    finally:
        signal.signal(signal.SIGTERM, previous)


def install(
    mp,
    tiny_model,
    outputs: Path,
    *,
    train=TRAIN,
    dev=DEV,
    config=None,
    build_model=None,
    load_error=None,
    patch_problems=True,
    fake_generate=False,
):
    """Patch the lab's seams for one run and return what the run did through them."""
    record = {"loads": [], "models": [], "threads": [], "nice": [], "generate": [], "odd_prompts": []}
    overrides = {**TINY, **(config or {})}
    original = lab_config.config_for

    def tiny_config_for(*args, **kwargs):
        return dataclasses.replace(original(*args, **kwargs), **overrides)

    for name in ("gsm8k.lab.config", "gsm8k.lab.runner", "gsm8k.lab.trainer", "gsm8k.lab_cmd"):
        try:
            module = importlib.import_module(name)
        except ModuleNotFoundError:
            continue
        if hasattr(module, "config_for"):
            mp.setattr(module, "config_for", tiny_config_for)

    base_model, base_tokenizer = tiny_model
    tokenizer = copy.deepcopy(base_tokenizer)  # one copy per run; the shared one stays untouched

    def load(cfg):
        lock_file = outputs / "lab" / "lab.lock"
        record["loads"].append(
            {
                "cfg": cfg,
                "cuda": os.environ.get("CUDA_VISIBLE_DEVICES"),
                "lock_held": _flock_held(lock_file),
                "lock": _read_json(lock_file),
                "threads": list(record["threads"]),
                "nice": list(record["nice"]),
            }
        )
        if load_error:
            raise RuntimeError(load_error)
        model = build_model() if build_model else copy.deepcopy(base_model)
        record["models"].append(model)
        return model, tokenizer

    mp.setattr(lab_trainer, "load_lab_model", load)
    if patch_problems:
        mp.setattr(lab_trainer, "load_lab_problems", lambda cfg: (list(train), list(dev)))
    mp.setattr(os, "nice", lambda inc: record["nice"].append(inc) or 0)
    mp.setattr(torch, "set_num_threads", lambda n: record["threads"].append(n))
    mp.setenv("CUDA_VISIBLE_DEVICES", "-1")  # hides the GPU too, and must become "" in the handler
    mp.setattr(paths, "DEFAULT_RESULTS", outputs.parent / "never" / "runs.csv")

    if fake_generate:
        by_prompt = {training_prompt(p.question): (i, p.gold) for i, p in enumerate(dev)}

        def generate(model, tokenizer, prompts, max_new_tokens=128):
            record["generate"].append({"n": len(prompts), "max_new_tokens": max_new_tokens})
            outs = []
            for text in prompts:
                if text not in by_prompt:
                    record["odd_prompts"].append(text)
                    outs.append("")
                    continue
                index, gold = by_prompt[text]
                outs.append(_fake_output(index, gold))
            return outs

        mp.setattr(evaluation, "generate", generate)
    return record


# ---------------------------------------------------------------- shared runs (one per module)


@pytest.fixture(scope="module")
def l01_run(tiny_model, tmp_path_factory):
    """`gsm8k lab run l01 --outputs <tmp>`, over an earlier l01 folder and a lock file left by an ended
    process; GSM8K_OUTPUTS_DIR points at a decoy folder that must stay empty."""
    base = tmp_path_factory.mktemp("lab-l01")
    outputs, decoy = base / "outputs", base / "decoy"
    decoy.mkdir()
    old = outputs / "lab" / "l01" / "old-variant"
    old.mkdir(parents=True)
    (old / "summary.json").write_text("{}", encoding="utf-8")
    stale = {"v": 1, "pid": 999999, "lesson": "l05", "started_at": "2026-11-08T10:00:00Z"}
    (outputs / "lab" / "lab.lock").write_text(json.dumps(stale), encoding="utf-8")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("GSM8K_OUTPUTS_DIR", str(decoy))
        record = install(mp, tiny_model, outputs, fake_generate=True)
        code = run_lab("l01", "--outputs", str(outputs))
        maxrss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    lab = outputs / "lab"
    return SimpleNamespace(
        code=code,
        outputs=outputs,
        decoy=decoy,
        lab=lab,
        variant_dir=lab / "l01" / "baseline",
        record=record,
        maxrss_mb=maxrss_mb,
    )


@pytest.fixture(scope="module")
def steps_run(tiny_model, tmp_path_factory):
    """l01 with 16 examples, batch 5 and 3 epochs: 4 steps per epoch (the last batch short), 12 steps."""
    outputs = tmp_path_factory.mktemp("lab-steps") / "outputs"
    outputs.mkdir()
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("GSM8K_OUTPUTS_DIR", str(outputs))
        record = install(mp, tiny_model, outputs, config={"batch_size": 5, "epochs": 3}, fake_generate=True)
        code = run_lab("l01")
    variant_dir = outputs / "lab" / "l01" / "baseline"
    return SimpleNamespace(code=code, variant_dir=variant_dir, record=record)


@pytest.fixture(scope="module")
def l08_run(tiny_model, tmp_path_factory):
    """l08 (answer-only, whole-text) on 16 copies of one problem, constant schedule without warm-up."""
    outputs = tmp_path_factory.mktemp("lab-l08") / "outputs"
    outputs.mkdir()
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("GSM8K_OUTPUTS_DIR", str(outputs))
        record = install(
            mp, tiny_model, outputs, train=SAME, config={"schedule": "constant", "warmup_ratio": 0}
        )
        code = run_lab("l08")
    return SimpleNamespace(code=code, lesson_dir=outputs / "lab" / "l08", record=record)


@pytest.fixture(scope="module")
def l12_run(tiny_model, tmp_path_factory):
    """l12 (tokenize-once, by-length, retokenize) on examples of very different lengths."""
    outputs = tmp_path_factory.mktemp("lab-l12") / "outputs"
    outputs.mkdir()
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("GSM8K_OUTPUTS_DIR", str(outputs))
        record = install(mp, tiny_model, outputs, train=VARIED, config={"max_seq_len": 128})
        code = run_lab("l12")
    return SimpleNamespace(code=code, lesson_dir=outputs / "lab" / "l12", record=record)


# ---------------------------------------------------------------- AC11.2.1


def test_AC11_2_1_run_writes_metrics_summary_and_finished_status(l01_run):
    assert l01_run.code == 0
    assert (l01_run.variant_dir / "metrics.jsonl").is_file()
    assert (l01_run.variant_dir / "summary.json").is_file()
    status = _read_json(l01_run.lab / "l01" / "status.json")
    assert status["v"] == 1
    assert status["lesson"] == "l01"
    assert status["state"] == "finished"
    assert status["variants"] == ["baseline"]
    assert status["done"] == ["baseline"]
    assert isinstance(status["pid"], int)
    assert status["started_at"] and status["ended_at"]
    assert status["message"] is None
    # --outputs wins over GSM8K_OUTPUTS_DIR; nothing lands in the decoy folder.
    assert list(l01_run.decoy.iterdir()) == []


def test_AC11_2_1_variant_option_is_repeatable_and_runs_only_those(tiny_model, tmp_project_dirs, monkeypatch):
    outputs = tmp_project_dirs.outputs
    install(monkeypatch, tiny_model, outputs, fake_generate=True)
    code = run_lab("l02", "--variant", "lr-1e-5", "--variant", "lr-1e-2")
    assert code == 0
    lesson_dir = outputs / "lab" / "l02"
    assert sorted(p.name for p in lesson_dir.iterdir() if p.is_dir()) == ["lr-1e-2", "lr-1e-5"]
    for variant in ("lr-1e-5", "lr-1e-2"):
        assert (lesson_dir / variant / "metrics.jsonl").is_file()
        assert (lesson_dir / variant / "summary.json").is_file()
    status = _read_json(lesson_dir / "status.json")
    assert status["state"] == "finished"
    assert status["variants"] == ["lr-1e-5", "lr-1e-2"]
    assert status["done"] == ["lr-1e-5", "lr-1e-2"]
    assert _read_json(lesson_dir / "lr-1e-2" / "summary.json")["config"]["learning_rate"] == 1e-2


@pytest.mark.parametrize("argv", [["l99"], ["l01", "--variant", "nope"], ["l02", "--variant", "baseline"]])
def test_AC11_2_1_unknown_lesson_or_variant_exits_2_and_writes_nothing(
    argv, tiny_model, tmp_project_dirs, monkeypatch
):
    outputs = tmp_project_dirs.outputs
    record = install(monkeypatch, tiny_model, outputs)
    assert run_lab(*argv) == 2
    assert not (outputs / "lab").exists()
    assert record["loads"] == []


# ---------------------------------------------------------------- AC11.2.2


def test_AC11_2_2_handler_keeps_the_run_on_the_cpu(tiny_model, tmp_project_dirs, monkeypatch):
    outputs = tmp_project_dirs.outputs
    record = install(monkeypatch, tiny_model, outputs, fake_generate=True)
    real_is_available = torch.cuda.is_available

    def is_available():
        # The lab's own code is told a GPU is there; torch's internals keep the real answer.
        caller = sys._getframe(1).f_globals.get("__name__", "")
        return True if caller.startswith("gsm8k.lab") else real_is_available()

    monkeypatch.setattr(torch.cuda, "is_available", is_available)
    code = run_lab("l01", "--threads", "2")
    assert code == 0, _read_json(outputs / "lab" / "l01" / "status.json")
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == ""
    load = record["loads"][0]
    assert load["cuda"] == "", "CUDA_VISIBLE_DEVICES must be empty before the model is loaded"
    assert load["threads"] == [2]
    assert load["nice"] == [10]
    assert record["nice"] == [10]
    model = record["models"][0]
    assert all(p.device.type == "cpu" for p in model.parameters())
    assert all(b.device.type == "cpu" for b in model.buffers())
    summary = _read_json(outputs / "lab" / "l01" / "baseline" / "summary.json")
    assert summary["config"]["threads"] == 2


def test_AC11_2_2_threads_default_from_the_configuration(l01_run):
    load = l01_run.record["loads"][0]
    assert load["threads"] == [lab_config.LabConfig().threads]
    assert load["nice"] == [10]
    assert load["cuda"] == ""


def test_AC11_2_2_never_touches_run_log_gpu_lock_or_queue(l01_run):
    assert sorted(p.name for p in l01_run.outputs.iterdir()) == ["lab"]
    assert not (l01_run.outputs / "run.lock").exists()
    assert not (l01_run.outputs / "queue").exists()
    assert not (l01_run.outputs.parent / "never" / "runs.csv").exists()


def test_AC11_2_2_importing_the_lab_loads_no_torch_and_sets_no_env():
    code = textwrap.dedent(
        """
        import json, os, sys
        import gsm8k
        heavy = ("torch", "transformers", "peft")
        assert not [m for m in heavy if m in sys.modules], "torch was loaded before the lab"
        before = dict(os.environ)
        import gsm8k.lab, gsm8k.lab.config, gsm8k.lab.lessons, gsm8k.lab_cmd
        loaded = sorted(m for m in heavy if m in sys.modules)
        changed = sorted(k for k in set(before) | set(os.environ) if before.get(k) != os.environ.get(k))
        print(json.dumps({"loaded": loaded, "changed": changed}))
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=120, check=False
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout.strip().splitlines()[-1])
    assert report == {"loaded": [], "changed": []}


# ---------------------------------------------------------------- AC11.2.3


def test_AC11_2_3_lab_lock_is_held_during_the_run_and_released(l01_run):
    load = l01_run.record["loads"][0]
    assert load["lock_held"] is True
    assert load["lock"]["lesson"] == "l01"
    assert load["lock"]["pid"] == os.getpid()
    assert not _flock_held(l01_run.lab / "lab.lock")


def test_AC11_2_3_lock_file_of_an_ended_process_is_taken_over(l01_run):
    # The fixture left {"lesson": "l05"} in lab.lock with no flock held; the run went ahead.
    assert l01_run.code == 0
    assert _read_json(l01_run.lab / "l01" / "status.json")["state"] == "finished"


def test_AC11_2_3_second_run_exits_3_naming_the_running_lesson(
    tiny_model, tmp_project_dirs, monkeypatch, capsys
):
    outputs = tmp_project_dirs.outputs
    record = install(monkeypatch, tiny_model, outputs)
    lab = outputs / "lab"
    (lab / "l01").mkdir(parents=True)
    (lab / "l01" / "keep.txt").write_text("earlier run", encoding="utf-8")
    holder = {"v": 1, "pid": 4242, "lesson": "l02", "started_at": "2026-11-08T10:00:00Z"}
    fd = os.open(lab / "lab.lock", os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.write(fd, json.dumps(holder).encode("utf-8"))
        capsys.readouterr()
        assert run_lab("l01") == 3
        out = capsys.readouterr()
        assert "l02" in out.out + out.err
        assert (lab / "l01" / "keep.txt").read_text(encoding="utf-8") == "earlier run"
        assert sorted(p.name for p in (lab / "l01").iterdir()) == ["keep.txt"]
        assert record["loads"] == []
        assert _read_json(lab / "lab.lock") == holder
        # AC11.2.9 order: an unknown lesson is refused (2) before the lock is looked at (3).
        assert run_lab("l99") == 2
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


# ---------------------------------------------------------------- AC11.2.4


def _synthetic_gsm8k():
    train = [
        Problem(f"gsm8k-train-{i}", f"What is 1 + {i}?", f"1 + {i} = {1 + i}\n#### {1 + i}", str(1 + i))
        for i in range(600)
    ]
    test = [
        Problem(f"gsm8k-test-{i}", f"What is 2 + {i}?", f"2 + {i} = {2 + i}\n#### {2 + i}", str(2 + i))
        for i in range(5)
    ]
    return {"train": train, "test": test}


def test_AC11_2_4_problems_come_from_the_fixed_split_by_index(tmp_project_dirs, monkeypatch):
    problems = _synthetic_gsm8k()
    revisions = []

    def load_gsm8k(revision=hub.DATASET_REVISION):
        revisions.append(revision)
        return {name: list(rows) for name, rows in problems.items()}

    calls = []
    original_guard = guard.check_training_problems

    def spy(training, dev_ids=()):
        training, dev_ids = list(training), list(dev_ids)
        calls.append(([p.id for p in training], dev_ids))
        return original_guard(training, dev_ids)

    monkeypatch.setattr(hub, "load_gsm8k", load_gsm8k)
    monkeypatch.setattr(guard, "check_training_problems", spy)

    train, dev = lab_trainer.load_lab_problems(_tiny_cfg())

    assert revisions == [hub.DATASET_REVISION]
    data_split = split.build_split([p.id for p in problems["train"]])
    expected_train = split.sort_by_index(list(data_split.train_ids))[:16]
    exemplars = prompt.choose_exemplars(data_split.dev_ids)
    scored = prompt.problems_to_score("dev", data_split, problems, exemplars)
    assert len(scored) == 496
    assert [p.id for p in train][:16] == expected_train
    assert len(train) in (16, len(data_split.train_ids))
    assert [p.id for p in dev][:8] == [p.id for p in scored[:8]]
    assert len(dev) in (8, 496)
    assert not {p.id for p in train} & (set(data_split.dev_ids) | {p.id for p in problems["test"]})
    assert not {p.id for p in dev} & {p.id for p in problems["test"]}
    assert any(
        set(expected_train) <= set(ids) and set(dev_ids) == set(data_split.dev_ids) for ids, dev_ids in calls
    )
    assert all(len(dev_ids) == 500 for _, dev_ids in calls)


def test_AC11_2_4_a_problem_the_guard_refuses_fails_the_run_before_training(
    tiny_model, tmp_project_dirs, monkeypatch
):
    outputs = tmp_project_dirs.outputs
    problems = _synthetic_gsm8k()
    monkeypatch.setattr(hub, "load_gsm8k", lambda revision=hub.DATASET_REVISION: problems)

    def refuse(training, dev_ids=()):
        raise guard.TrainingDataError("Training data holds evaluation problems: gsm8k-train-7")

    monkeypatch.setattr(guard, "check_training_problems", refuse)
    install(monkeypatch, tiny_model, outputs, patch_problems=False, fake_generate=True)
    assert run_lab("l01") == 1
    status = _read_json(outputs / "lab" / "l01" / "status.json")
    assert status["state"] == "failed"
    assert "evaluation problems" in status["message"]
    variant_dir = outputs / "lab" / "l01" / "baseline"
    assert _step_lines(variant_dir / "metrics.jsonl") == []
    assert not (variant_dir / "summary.json").exists()
    assert not _flock_held(outputs / "lab" / "lab.lock")


def test_AC11_2_4_sample_problems_are_the_first_dev_problems(l01_run):
    summary = _read_json(l01_run.variant_dir / "summary.json")
    assert [(s["question"], s["gold"]) for s in summary["samples"]] == [(DEV[0].question, DEV[0].gold)]


# ---------------------------------------------------------------- AC11.2.5


def test_AC11_2_5_total_steps_keep_the_last_short_batch(steps_run):
    assert steps_run.code == 0
    steps = _step_lines(steps_run.variant_dir / "metrics.jsonl")
    assert [line["step"] for line in steps] == list(range(1, 13))
    assert {line["total_steps"] for line in steps} == {12}
    assert _read_json(steps_run.variant_dir / "summary.json")["steps"] == 12


def test_AC11_2_5_linear_schedule_warms_up_then_decays(steps_run):
    rates = [line["learning_rate"] for line in _step_lines(steps_run.variant_dir / "metrics.jsonl")]
    peak = max(rates)
    assert peak <= 1e-3 * (1 + 1e-9)
    assert rates[0] < peak  # ceil(0.1 x 12) = 2 warm-up steps
    assert rates[-1] < peak
    after_peak = rates[rates.index(peak) :]
    assert after_peak == sorted(after_peak, reverse=True)


def test_AC11_2_5_constant_schedule_keeps_the_learning_rate(l08_run):
    for variant in ("answer-only", "whole-text"):
        rates = [
            line["learning_rate"] for line in _step_lines(l08_run.lesson_dir / variant / "metrics.jsonl")
        ]
        assert rates and all(rate == pytest.approx(1e-3, rel=1e-9) for rate in rates), variant


def test_AC11_2_5_answer_loss_masks_the_question_and_all_counts_it(l08_run, tiny_model):
    assert l08_run.code == 0
    model, tokenizer = tiny_model
    expected = {
        "answer-only": _reference_loss(model, tokenizer, SAME[:1], "step-by-step", 64, "answer"),
        "whole-text": _reference_loss(model, tokenizer, SAME[:1], "step-by-step", 64, "all"),
    }
    # A random model gives about log(vocabulary) everywhere: the two differ by about 0.01.
    assert abs(expected["answer-only"] - expected["whole-text"]) > 2e-3
    for variant, loss in expected.items():
        first = _step_lines(l08_run.lesson_dir / variant / "metrics.jsonl")[0]
        assert first["step"] == 1
        assert first["loss"] == pytest.approx(loss, abs=2e-4), variant


def test_AC11_2_5_examples_with_no_answer_token_left_are_dropped(tiny_model, tmp_project_dirs, monkeypatch):
    outputs = tmp_project_dirs.outputs
    install(monkeypatch, tiny_model, outputs, train=LONG[:8] + TRAIN[:8], fake_generate=True)
    assert run_lab("l01") == 0
    steps = _step_lines(outputs / "lab" / "l01" / "baseline" / "metrics.jsonl")
    assert [line["total_steps"] for line in steps] == [2, 2]  # 8 kept examples / batch 4


def test_AC11_2_5_no_example_left_fails_with_a_message(tiny_model, tmp_project_dirs, monkeypatch):
    outputs = tmp_project_dirs.outputs
    install(monkeypatch, tiny_model, outputs, train=LONG, fake_generate=True)
    assert run_lab("l01") == 1
    status = _read_json(outputs / "lab" / "l01" / "status.json")
    assert status["state"] == "failed"
    assert status["message"] and status["message"].strip()
    variant_dir = outputs / "lab" / "l01" / "baseline"
    assert _step_lines(variant_dir / "metrics.jsonl") == []
    assert not (variant_dir / "summary.json").exists()
    assert not _flock_held(outputs / "lab" / "lab.lock")


def test_AC11_2_5_lora_trains_only_adapters_in_the_decoder_blocks_of_qwen3(l01_run, tiny_model):
    fresh, _ = tiny_model
    summary = _read_json(l01_run.variant_dir / "summary.json")
    expected = _expected_lora(fresh, rank=8)
    assert summary["trainable_params"] == expected
    assert _n_params(fresh) <= summary["total_params"] <= _n_params(fresh) + expected
    trained = l01_run.record["models"][0]
    assert torch.equal(trained.get_input_embeddings().weight, fresh.get_input_embeddings().weight)
    assert torch.equal(trained.get_output_embeddings().weight, fresh.get_output_embeddings().weight)


def test_AC11_2_5_lora_on_a_tiny_gptneox_model(tiny_model, tmp_project_dirs, monkeypatch):
    from transformers import GPTNeoXConfig, GPTNeoXForCausalLM

    _, tokenizer = tiny_model
    config = GPTNeoXConfig(
        vocab_size=len(tokenizer),
        hidden_size=64,
        num_hidden_layers=2,
        num_attention_heads=4,
        intermediate_size=128,
        max_position_embeddings=512,
        tie_word_embeddings=False,
    )
    torch.manual_seed(0)
    reference = GPTNeoXForCausalLM(config).eval()
    embed_in = reference.get_input_embeddings().weight.detach().clone()
    embed_out = reference.get_output_embeddings().weight.detach().clone()
    expected = _expected_lora(reference, rank=8)
    total = _n_params(reference)

    outputs = tmp_project_dirs.outputs
    record = install(
        monkeypatch, tiny_model, outputs, build_model=lambda: copy.deepcopy(reference), fake_generate=True
    )
    assert run_lab("l01") == 0, _read_json(outputs / "lab" / "l01" / "status.json")
    summary = _read_json(outputs / "lab" / "l01" / "baseline" / "summary.json")
    assert summary["trainable_params"] == expected
    assert total <= summary["total_params"] <= total + expected
    trained = record["models"][0]
    assert torch.equal(trained.get_input_embeddings().weight, embed_in)
    assert torch.equal(trained.get_output_embeddings().weight, embed_out)


def test_AC11_2_5_full_trains_every_weight(tiny_model, tmp_project_dirs, monkeypatch):
    fresh, _ = tiny_model
    outputs = tmp_project_dirs.outputs
    record = install(monkeypatch, tiny_model, outputs, fake_generate=True)
    assert run_lab("l06", "--variant", "full") == 0, _read_json(outputs / "lab" / "l06" / "status.json")
    summary = _read_json(outputs / "lab" / "l06" / "full" / "summary.json")
    assert summary["config"]["method"] == "full"
    assert summary["trainable_params"] == summary["total_params"] == _n_params(fresh)
    trained = record["models"][0]
    assert not torch.equal(trained.get_input_embeddings().weight, fresh.get_input_embeddings().weight)


# ---------------------------------------------------------------- AC11.2.6


def test_AC11_2_6_one_line_per_step_and_dev_lines_at_tenths(steps_run):
    lines = _lines(steps_run.variant_dir / "metrics.jsonl")
    assert lines
    for line in lines:
        assert set(line) == LINE_FIELDS
        assert line["v"] == 1
        assert line["total_steps"] == 12
        assert isinstance(line["elapsed_s"], (int, float)) and line["elapsed_s"] >= 0
    for line in _step_lines(steps_run.variant_dir / "metrics.jsonl"):
        assert line["step"] >= 1
        assert isinstance(line["loss"], float)
        assert isinstance(line["learning_rate"], float)
        assert isinstance(line["grad_norm"], float) and line["grad_norm"] > 0
    dev = _dev_lines(steps_run.variant_dir / "metrics.jsonl")
    for line in dev:
        assert line["loss"] is None and line["learning_rate"] is None and line["grad_norm"] is None
        assert isinstance(line["dev_loss"], float)
    expected = sorted({0} | {max(1, math.ceil(k * 12 / 10)) for k in range(1, 11)})
    assert expected == [0, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12]
    assert [line["step"] for line in dev] == expected


def test_AC11_2_6_small_run_has_a_dev_line_after_every_step(l01_run):
    dev = _dev_lines(l01_run.variant_dir / "metrics.jsonl")
    assert [line["step"] for line in dev] == [0, 1, 2, 3, 4]  # 16 examples / batch 4 = 4 steps


def test_AC11_2_6_dev_loss_counts_answer_tokens_whatever_loss_on_is(l08_run, l01_run, tiny_model):
    model, tokenizer = tiny_model
    expected = _reference_loss(model, tokenizer, DEV, "step-by-step", 64, "answer")
    for variant in ("answer-only", "whole-text"):
        first = _dev_lines(l08_run.lesson_dir / variant / "metrics.jsonl")[0]
        assert first["step"] == 0
        assert first["dev_loss"] == pytest.approx(expected, abs=2e-4), variant
    first = _dev_lines(l01_run.variant_dir / "metrics.jsonl")[0]
    assert first["dev_loss"] == pytest.approx(expected, abs=2e-4)


# ---------------------------------------------------------------- AC11.2.7


def test_AC11_2_7_summary_holds_the_c8_fields(l01_run):
    summary = _read_json(l01_run.variant_dir / "summary.json")
    assert set(summary) == SUMMARY_FIELDS
    assert summary["v"] == 1
    assert (summary["lesson"], summary["variant"]) == ("l01", "baseline")
    assert summary["label"] == _label("l01", "baseline")
    assert summary["config"] == dataclasses.asdict(_tiny_cfg())
    steps = _step_lines(l01_run.variant_dir / "metrics.jsonl")
    dev = _dev_lines(l01_run.variant_dir / "metrics.jsonl")
    assert summary["steps"] == len(steps) == 4
    assert summary["seconds"] > 0 and summary["seconds_per_step"] > 0
    assert isinstance(summary["tokenize_seconds"], float) and summary["tokenize_seconds"] >= 0
    assert summary["retokenize_seconds_per_step"] is None
    assert 0 <= summary["padding_fraction"] < 1
    assert 0 < summary["peak_memory_mb"] <= l01_run.maxrss_mb + 1
    assert summary["trainable_params"] < summary["total_params"]
    losses = [line["loss"] for line in steps]
    assert summary["train_loss_first"] == pytest.approx(losses[0], rel=1e-6)
    assert summary["train_loss_last"] == pytest.approx(sum(losses[-10:]) / len(losses[-10:]), rel=1e-6)
    assert summary["dev_loss_before"] == pytest.approx(dev[0]["dev_loss"], rel=1e-6)
    assert summary["dev_loss_after"] == pytest.approx(dev[-1]["dev_loss"], rel=1e-6)
    best = min(dev, key=lambda line: line["dev_loss"])
    assert summary["dev_loss_best"] == pytest.approx(best["dev_loss"], rel=1e-6)
    assert summary["dev_loss_best_step"] == best["step"]


def test_AC11_2_7_accuracy_and_format_rate_before_and_after(l01_run):
    summary = _read_json(l01_run.variant_dir / "summary.json")
    # Fake answers: 4 of 8 right, 6 of 8 with a "#### <number>" line, in the zero-shot frame.
    assert summary["accuracy_before"] == summary["accuracy_after"] == 0.5
    assert summary["format_rate_before"] == summary["format_rate_after"] == 0.75
    record = l01_run.record
    assert record["odd_prompts"] == []
    assert record["generate"] and all(call["max_new_tokens"] == 16 for call in record["generate"])
    sample = summary["samples"][0]
    assert sample["before"] == sample["after"] == _fake_output(0, DEV[0].gold)


def test_AC11_2_7_accuracy_and_format_rate_are_fractions_with_4_decimals(l12_run):
    assert l12_run.code == 0
    for variant in ("tokenize-once", "by-length", "retokenize"):
        summary = _read_json(l12_run.lesson_dir / variant / "summary.json")
        for field in ("accuracy_before", "accuracy_after", "format_rate_before", "format_rate_after"):
            value = summary[field]
            assert 0 <= value <= 1 and round(value, 4) == value, (variant, field)
        assert len(summary["samples"]) == 1
        assert all(isinstance(summary["samples"][0][k], str) for k in ("question", "gold", "before", "after"))


def test_AC11_2_7_retokenize_seconds_only_when_retokenizing(l12_run):
    for variant in ("tokenize-once", "by-length", "retokenize"):
        summary = _read_json(l12_run.lesson_dir / variant / "summary.json")
        assert isinstance(summary["tokenize_seconds"], float) and summary["tokenize_seconds"] > 0, variant
        if variant == "retokenize":
            assert isinstance(summary["retokenize_seconds_per_step"], float)
            assert summary["retokenize_seconds_per_step"] > 0
        else:
            assert summary["retokenize_seconds_per_step"] is None, variant


def test_AC11_2_7_padding_fraction_is_zero_for_equal_lengths(l08_run):
    for variant in ("answer-only", "whole-text"):
        assert _read_json(l08_run.lesson_dir / variant / "summary.json")["padding_fraction"] == 0


# ---------------------------------------------------------------- AC11.2.8


def test_AC11_2_8_length_grouped_batches_pad_less_than_random(l12_run):
    assert l12_run.code == 0
    random_padding = _read_json(l12_run.lesson_dir / "tokenize-once" / "summary.json")["padding_fraction"]
    grouped_padding = _read_json(l12_run.lesson_dir / "by-length" / "summary.json")["padding_fraction"]
    assert 0 < random_padding < 1
    assert grouped_padding <= random_padding
    assert grouped_padding < random_padding  # lengths differ and there are 4 batches
    steps = _step_lines(l12_run.lesson_dir / "by-length" / "metrics.jsonl")
    assert [line["step"] for line in steps] == [1, 2, 3, 4]


# ---------------------------------------------------------------- AC11.2.9


def test_AC11_2_9_sigterm_stops_after_the_current_step(tiny_model, tmp_project_dirs, monkeypatch):
    base_model, _ = tiny_model
    state = {"first": None, "sent": False}

    def hook(module, args, output):
        if not module.training or state["sent"]:
            return
        if state["first"] is None:
            state["first"] = id(module)
        elif id(module) != state["first"]:  # the second variant's model is training
            state["sent"] = True
            os.kill(os.getpid(), signal.SIGTERM)

    def build():
        model = copy.deepcopy(base_model)
        model.register_forward_hook(hook)
        return model

    outputs = tmp_project_dirs.outputs
    install(monkeypatch, tiny_model, outputs, build_model=build, fake_generate=True)
    code = run_lab("l02", "--variant", "lr-1e-5", "--variant", "lr-1e-4")
    assert state["sent"] is True
    assert code == 130
    lesson_dir = outputs / "lab" / "l02"
    status = _read_json(lesson_dir / "status.json")
    assert status["state"] == "stopped"
    assert status["done"] == ["lr-1e-5"]
    assert (lesson_dir / "lr-1e-5" / "summary.json").is_file()
    assert not (lesson_dir / "lr-1e-4" / "summary.json").exists()
    assert len(_step_lines(lesson_dir / "lr-1e-4" / "metrics.jsonl")) <= 1
    assert not _flock_held(outputs / "lab" / "lab.lock")


def test_AC11_2_9_error_in_a_variant_fails_the_run(tiny_model, tmp_project_dirs, monkeypatch):
    outputs = tmp_project_dirs.outputs
    install(monkeypatch, tiny_model, outputs, load_error="the model file went missing")
    assert run_lab("l01") == 1
    status = _read_json(outputs / "lab" / "l01" / "status.json")
    assert status["state"] == "failed"
    assert "the model file went missing" in status["message"]
    assert status["done"] == []
    assert not (outputs / "lab" / "l01" / "baseline" / "summary.json").exists()
    assert not _flock_held(outputs / "lab" / "lab.lock")


def test_AC11_2_9_earlier_folder_of_the_lesson_is_removed_before_the_start(l01_run):
    assert not (l01_run.lab / "l01" / "old-variant").exists()
    assert sorted(p.name for p in (l01_run.lab / "l01").iterdir()) == ["baseline", "status.json"]
