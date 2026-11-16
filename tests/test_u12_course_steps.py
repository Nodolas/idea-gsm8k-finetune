"""u12-learning-course, part D, US12.1 and AC12.4.4 (config side): the course's steps, run
configurations and time estimates.

Pure data and validation (stories.md Course Steps, Course Runs, Course Timing and Course Models tables;
contract C9); no model is loaded, nothing is downloaded, the CPU only. The modules under test are
imported inside each test, so a missing module fails that test alone.
"""

import dataclasses
import importlib
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

Q06 = "Qwen/Qwen3-0.6B-Base"
Q17 = "Qwen/Qwen3-1.7B-Base"
PYTHIA = "EleutherAI/pythia-31m"
SMOL = "HuggingFaceTB/SmolLM2-360M"
QWEN25 = "Qwen/Qwen2.5-0.5B"

# stories.md, Course Steps: (id, part, title, kind) in the table's order.
STEP_TABLE = [
    ("c01", 1, "How a base model is scored", "gpu"),
    ("c02", 2, "Tokens and the prompt", "inspect"),
    ("c03", 2, "Inside a decoder-only transformer", "inspect"),
    ("c04", 2, "Five designs side by side", "inspect"),
    ("c05", 2, "Same test, five designs", "gpu"),
    ("c06", 2, "Why Qwen3-1.7B, and why not the others", "read"),
    ("c07", 3, "What a fine-tune does", "lab"),
    ("c08", 3, "Learning rate", "lab"),
    ("c09", 3, "Epochs and overfitting", "lab"),
    ("c10", 3, "How much data", "lab"),
    ("c11", 3, "LoRA rank", "lab"),
    ("c12", 3, "LoRA or every weight", "lab"),
    ("c13", 3, "Batch size", "lab"),
    ("c14", 3, "What the loss counts", "lab"),
    ("c15", 3, "Answer format", "lab"),
    ("c16", 3, "Warm-up and schedule", "lab"),
    ("c17", 3, "Seed noise", "lab"),
    ("c18", 3, "Where the time goes", "lab"),
    ("c19", 4, "Memory budget: prompting, full, LoRA, QLoRA", "read"),
    ("c20", 4, "LoRA or QLoRA on the GPU", "gpu"),
    ("c21", 5, "Supervised fine-tune", "gpu"),
    ("c22", 5, "Self-taught reasoning", "gpu"),
    ("c23", 5, "Reinforcement learning with GRPO", "gpu"),
    ("c24", 5, "What moved the score, and noise", "read"),
]
PART_TITLES = {
    1: "Scoring a base model",
    2: "Model designs",
    3: "How fine-tuning works",
    4: "Fine-tuning approaches",
    5: "The training pipeline",
}
LESSON_OF = {f"c{n + 6:02d}": f"l{n:02d}" for n in range(1, 13)}  # c07..c18 -> l01..l12

# stories.md, Course Runs: (step, run, command, changes beyond the defaults) in the table's order.
RUN_TABLE = [
    ("c01", "base-06", "evaluate", {"model": Q06, "method": "base"}),
    ("c05", "pythia", "evaluate", {"model": PYTHIA, "method": "base"}),
    ("c05", "smollm2", "evaluate", {"model": SMOL, "method": "base"}),
    ("c05", "qwen25", "evaluate", {"model": QWEN25, "method": "base"}),
    ("c05", "qwen3-17", "evaluate", {"model": Q17, "method": "base"}),
    ("c20", "lora", "train", {"model": Q06, "method": "sft", "train_examples": 300}),
    ("c20", "qlora", "train", {"model": Q06, "method": "sft", "train_examples": 300, "quantize": "4bit"}),
    ("c21", "sft", "train", {"model": Q06, "method": "sft", "train_examples": 400}),
    (
        "c22",
        "cotgen",
        "cot-generate",
        {"model": Q06, "method": "cotgen", "split": "train", "cot_problems": 100, "cot_samples": 4},
    ),
    ("c22", "selfcot", "train", {"model": Q06, "method": "selfcot", "train_examples": 100}),
    ("c23", "grpo", "train", {"model": Q06, "method": "grpo", "grpo_steps": 20, "grpo_generations": 4}),
]

# stories.md, Course Models: the three course-only models and their pinned revisions.
COURSE_ONLY_REVISIONS = {
    PYTHIA: "e556ace21b489575e94e9d50b6dad2fcc7419679",
    SMOL: "f8027fd0eaeea54caa13c31d31b9fdc459c38b49",
    QWEN25: "060db6499f32faf8b98477b0a26969ef7d8b9987",
}
COURSE_MODEL_ORDER = [PYTHIA, SMOL, QWEN25, Q06, Q17]

COTGEN_ID = "course-c22-cotgen-1"

# Course Timing, with the fallback timings alone: minutes = ceil((30 + work seconds) / 60).
FALLBACK_MINUTES = {
    ("c01", "base-06"): 3,
    ("c05", "smollm2"): 2,
    ("c05", "qwen25"): 3,
    ("c05", "qwen3-17"): 6,
    ("c20", "lora"): 4,
    ("c20", "qlora"): 4,
    ("c21", "sft"): 4,
    ("c22", "cotgen"): 9,
    ("c22", "selfcot"): 3,
    ("c23", "grpo"): 7,
}
# With saved Qwen3-0.6B timings of 3.0 s per problem and 2.2 s per training step (batch size 4).
MEASURED_MINUTES = {
    ("c01", "base-06"): 6,
    ("c20", "lora"): 9,
    ("c20", "qlora"): 10,
    ("c21", "sft"): 10,
    ("c22", "cotgen"): 21,
    ("c22", "selfcot"): 7,
    ("c23", "grpo"): 12,
}

HTML_TAG = re.compile(r"</?(?:div|p|span|br|ul|ol|li|a|b|i|strong|em|h[1-6]|table|tr|td|img|script)\b", re.I)


# --- helpers ---


def _steps():
    return importlib.import_module("gsm8k.course.steps")


def _configs():
    return importlib.import_module("gsm8k.course.configs")


def _run_config():
    return importlib.import_module("gsm8k.run_config")


def _attempt_id(step: str, run: str, n: int = 1) -> str:
    return f"course-{step}-{run}-{n}"


def _step(step_id: str):
    step = _steps().get_step(step_id)
    assert step is not None, step_id
    return step


def _step_text(step) -> str:
    """Everything a learner reads in the step, lower-cased."""
    parts = [step.why, step.body, step.model_answer, step.own_words_prompt]
    for question in step.questions:
        parts += [question.prompt, *question.options, question.explanation]
    return "\n".join(parts).lower()


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", text.lower()) if s.strip()]


def _has_sentence(text: str, *groups: tuple[str, ...]) -> bool:
    """A sentence of ``text`` holding, for every group, at least one of the group's words."""
    return any(all(any(w in s for w in group) for group in groups) for s in _sentences(text))


def _write_course_rows(outputs: Path, rows: list[tuple[str, str]]) -> None:
    """Finished rows (run id, method) of Qwen3-0.6B in outputs/course/runs.csv (C1 format)."""
    from gsm8k.run_records import log

    path = outputs / "course" / "runs.csv"
    for run_id, method in rows:
        log.append_row(
            path,
            log.RunRow(
                date="2026-11-08T10:00:00Z",
                run_id=run_id,
                model=Q06,
                method=method,
                data="gsm8k-dev",
                metric="accuracy",
                value=0.31,
                minutes=2.0,
                config_hash="0" * 64,
            ),
        )


def _write_timing_folder(outputs: Path, name: str, method: str, **timings) -> None:
    """A run folder with the config.json and timings.json that gsm8k.estimates reads."""
    folder = outputs / name
    folder.mkdir()
    (folder / "config.json").write_text(
        json.dumps({"run_id": name, "model": Q06, "method": method, "batch_size": 4}), encoding="utf-8"
    )
    body = {"v": 1, "seconds_per_step": None, "seconds_per_problem": None, "peak_gpu_memory_gb": 4.0}
    body.update(timings)
    (folder / "timings.json").write_text(json.dumps(body), encoding="utf-8")


def _expected_config(step: str, run: str, changes: dict, attempt_id: str):
    """The run configuration defaults with exactly the run's changes (stories.md, Course Runs)."""
    rc = _run_config()
    fields = {"split": "dev", "limit": 100, "seed": 42}
    if step == "c22" and run == "cotgen":
        fields["limit"] = None
    if step == "c22" and run == "selfcot":
        fields["cot_data_run"] = COTGEN_ID
    fields.update(changes)
    fields["model_revision"] = (
        COURSE_ONLY_REVISIONS.get(fields["model"]) or rc.MODEL_REVISIONS[fields["model"]]
    )
    return rc.RunConfig(run_id=attempt_id, **fields)


def _build_config(step: str, run: str, dirs, attempt_id: str | None = None):
    attempt_id = attempt_id or _attempt_id(step, run)
    kwargs = {"checkpoints": dirs.checkpoints}
    if step == "c22" and run == "selfcot":
        kwargs["cot_data_run"] = COTGEN_ID
    return _configs().course_config(step, run, attempt_id, dirs.outputs, **kwargs)


# --- AC12.1.1: the 24 steps ---


def test_AC12_1_1_has_24_steps_in_table_order():
    steps = _steps()
    assert len(steps.STEPS) == 24
    assert [s.id for s in steps.STEPS] == [row[0] for row in STEP_TABLE]
    assert tuple(steps.STEP_IDS) == tuple(row[0] for row in STEP_TABLE)
    for step, (step_id, part, title, kind) in zip(steps.STEPS, STEP_TABLE, strict=True):
        assert step.number == int(step_id[1:])
        assert step.part == part
        assert PART_TITLES[part].lower() in step.part_title.lower()
        assert step.title == title
        assert step.kind == kind


def test_AC12_1_1_parts_and_lookup():
    steps = _steps()
    assert [number for number, _ in steps.PARTS] == [1, 2, 3, 4, 5]
    for number, title in steps.PARTS:
        assert PART_TITLES[number].lower() in title.lower()
    assert steps.get_step("c05").id == "c05"
    assert steps.get_step("c25") is None
    assert steps.get_step("nonsense") is None


def test_AC12_1_1_gpu_steps_list_exactly_their_runs():
    steps = _steps()
    expected: dict[str, list[str]] = {}
    for step, run, _, _ in RUN_TABLE:
        expected.setdefault(step, []).append(run)
    for step in steps.STEPS:
        assert list(step.runs) == expected.get(step.id, []), step.id
        if step.kind == "gpu":
            assert step.runs, step.id
    assert [(r.step, r.run) for r in steps.COURSE_RUNS] == [(s, r) for s, r, _, _ in RUN_TABLE]
    for spec, (step, run, command, changes) in zip(steps.COURSE_RUNS, RUN_TABLE, strict=True):
        assert spec.command == command, (step, run)
        assert spec.model == changes["model"], (step, run)
        assert changes.items() <= spec.changes.items(), (step, run)
        assert spec.changes_text.strip(), (step, run)
    assert [r.run for r in steps.runs_of("c05")] == ["pythia", "smollm2", "qwen25", "qwen3-17"]
    assert [r.run for r in steps.runs_of("c22")] == ["cotgen", "selfcot"]
    assert list(steps.runs_of("c06")) == []


def test_AC12_1_1_lab_steps_name_an_existing_lesson():
    from gsm8k.lab import lessons as lab_lessons

    lesson_ids = {lesson.id for lesson in lab_lessons.LESSONS}
    for step in _steps().STEPS:
        if step.kind == "lab":
            assert step.lesson == LESSON_OF[step.id], step.id
            assert step.lesson in lesson_ids, step.id
        else:
            assert not step.lesson, step.id


def test_AC12_1_1_every_step_has_why_body_questions_and_own_words():
    for step in _steps().STEPS:
        assert step.why.strip(), step.id
        assert step.body.strip(), step.id
        assert not HTML_TAG.search(step.body), step.id
        assert 2 <= len(step.questions) <= 3, step.id
        for question in step.questions:
            assert question.prompt.strip(), step.id
            assert 3 <= len(question.options) <= 4, step.id
            assert all(isinstance(o, str) and o.strip() for o in question.options), step.id
            assert len(set(question.options)) == len(question.options), step.id
            assert isinstance(question.right, int) and not isinstance(question.right, bool), step.id
            assert 0 <= question.right < len(question.options), step.id
            assert question.explanation.strip(), step.id
        assert step.own_words_prompt.strip(), step.id
        assert step.model_answer.strip(), step.id


def test_AC12_1_1_course_models_table():
    steps = _steps()
    assert [m.id for m in steps.COURSE_MODELS] == COURSE_MODEL_ORDER
    by_id = {m.id: m for m in steps.COURSE_MODELS}
    for model, revision in COURSE_ONLY_REVISIONS.items():
        assert by_id[model].revision == revision
    assert by_id[Q06].revision == _run_config().MODEL_REVISIONS[Q06]
    assert by_id[Q17].revision == _run_config().MODEL_REVISIONS[Q17]
    assert [m.weights_label.replace(" ", "") for m in steps.COURSE_MODELS] == [
        "30.5M",
        "362M",
        "494M",
        "0.6B",
        "1.7B",
    ]
    for model in steps.COURSE_MODELS:
        assert model.licence == "Apache-2.0"
        assert model.why.strip()
    for spec in steps.COURSE_RUNS:
        assert spec.model in by_id


def test_AC12_1_1_results_file_course_dir_and_attempt_id_pattern(tmp_path):
    steps = _steps()
    assert steps.COURSE_RESULTS == "outputs/course/runs.csv"
    assert Path(steps.course_dir(tmp_path)) == tmp_path / "course"
    pattern = (
        re.compile(steps.ATTEMPT_ID_PATTERN)
        if isinstance(steps.ATTEMPT_ID_PATTERN, str)
        else steps.ATTEMPT_ID_PATTERN
    )
    for good in ("course-c05-pythia-1", "course-c01-base-06-12", "course-c22-selfcot-3"):
        assert pattern.fullmatch(good), good
    for bad in (
        "q06-base-dev-1",
        "course-c5-pythia-1",
        "course-c05-pythia",
        "course-c05-Pythia-1",
        "xcourse-c05-a-1",
    ):
        assert not pattern.fullmatch(bad), bad


# --- AC12.1.2: run configurations and estimates ---


@pytest.mark.parametrize(
    ("step", "run", "command", "changes"), RUN_TABLE, ids=[f"{r[0]}-{r[1]}" for r in RUN_TABLE]
)
def test_AC12_1_2_run_config_is_defaults_plus_its_changes(tmp_project_dirs, step, run, command, changes):
    rc = _run_config()
    cfg = _build_config(step, run, tmp_project_dirs)
    rc.validate(cfg)
    expected = _expected_config(step, run, changes, _attempt_id(step, run))
    assert rc.to_dict(cfg) == rc.to_dict(expected)
    assert cfg.run_id == _attempt_id(step, run)
    assert cfg.seed == 42
    if (step, run) == ("c22", "cotgen"):
        assert cfg.split == "train"
        assert cfg.limit is None
    else:
        assert cfg.split == "dev"
        assert cfg.limit == 100


def test_AC12_1_2_selfcot_takes_the_cotgen_attempt_it_is_queued_with(tmp_project_dirs):
    cfg = _configs().course_config(
        "c22",
        "selfcot",
        "course-c22-selfcot-2",
        tmp_project_dirs.outputs,
        cot_data_run="course-c22-cotgen-2",
        checkpoints=tmp_project_dirs.checkpoints,
    )
    _run_config().validate(cfg)
    assert cfg.method == "selfcot"
    assert cfg.cot_data_run == "course-c22-cotgen-2"
    assert cfg.train_examples == 100


def test_AC12_1_2_course_only_models_keep_their_pinned_revision(tmp_project_dirs):
    for run, model in (("pythia", PYTHIA), ("smollm2", SMOL), ("qwen25", QWEN25)):
        cfg = _build_config("c05", run, tmp_project_dirs)
        assert cfg.model == model
        assert cfg.method == "base"
        assert cfg.model_revision == COURSE_ONLY_REVISIONS[model]


def test_AC12_1_2_qlora_changes_only_quantize_against_lora(tmp_project_dirs):
    rc = _run_config()
    lora = rc.to_dict(_build_config("c20", "lora", tmp_project_dirs))
    qlora = rc.to_dict(_build_config("c20", "qlora", tmp_project_dirs))
    differing = {k for k in lora if lora[k] != qlora[k]} - {"run_id"}
    assert differing == {"quantize"}
    assert qlora["quantize"] == "4bit"
    assert lora["quantize"] == "none"


def test_AC12_1_2_fallback_estimates_are_ten_minutes_or_less_and_unmeasured(tmp_project_dirs):
    configs = _configs()
    for spec in _steps().COURSE_RUNS:
        minutes, measured = configs.estimate_minutes(spec.step, spec.run, tmp_project_dirs.outputs)
        assert isinstance(minutes, int) and not isinstance(minutes, bool)
        assert 1 <= minutes <= 10, (spec.step, spec.run, minutes)
        assert measured is False, (spec.step, spec.run)


def test_AC12_1_2_fallback_estimates_follow_the_course_timing_rule(tmp_project_dirs):
    configs = _configs()
    for (step, run), minutes in FALLBACK_MINUTES.items():
        got = configs.estimate_minutes(step, run, tmp_project_dirs.outputs)
        assert got == (minutes, False), (step, run, got)
    # pythia is exactly one minute (30 s load + 30 s of work); rounding may not push it past two.
    minutes, measured = configs.estimate_minutes("c05", "pythia", tmp_project_dirs.outputs)
    assert minutes in (1, 2)
    assert measured is False


def test_AC12_1_2_saved_timings_are_used_and_the_estimate_is_measured(tmp_project_dirs):
    configs = _configs()
    outputs = tmp_project_dirs.outputs
    _write_timing_folder(outputs, "q06-base-dev-1", "base", seconds_per_problem=3.0)
    _write_timing_folder(outputs, "q06-sft-dev-1", "sft", seconds_per_step=2.2)
    for (step, run), minutes in MEASURED_MINUTES.items():
        got = configs.estimate_minutes(step, run, outputs)
        assert got == (minutes, True), (step, run, got)


def test_AC12_1_2_saved_timings_are_per_model(tmp_project_dirs):
    configs = _configs()
    outputs = tmp_project_dirs.outputs
    _write_timing_folder(outputs, "q06-base-dev-1", "base", seconds_per_problem=3.0)
    # Qwen3-0.6B timings say nothing about the other models: they stay on the fallback.
    assert configs.estimate_minutes("c05", "qwen3-17", outputs) == (6, False)
    assert configs.estimate_minutes("c05", "smollm2", outputs) == (2, False)
    # Only the evaluation timing was saved, and the evaluation run needs only that one.
    assert configs.estimate_minutes("c01", "base-06", outputs) == (6, True)


def test_AC12_1_2_a_run_over_ten_minutes_is_estimated_never_refused(tmp_project_dirs):
    configs = _configs()
    outputs = tmp_project_dirs.outputs
    _write_timing_folder(outputs, "q06-base-dev-1", "base", seconds_per_problem=3.0)
    minutes, measured = configs.estimate_minutes("c22", "cotgen", outputs)
    assert minutes > 10
    assert measured is True
    assert minutes == math.ceil((30 + 100 * 4 * 3.0) / 60)


def test_AC12_1_2_next_attempt_id_counts_up_per_step_and_run(tmp_project_dirs):
    configs = _configs()
    outputs = tmp_project_dirs.outputs
    assert configs.next_attempt_id("c05", "pythia", outputs) == "course-c05-pythia-1"
    assert configs.next_attempt_id("c20", "lora", outputs) == "course-c20-lora-1"
    _write_course_rows(outputs, [("course-c20-lora-1", "sft"), ("course-c20-lora-2", "sft")])
    (outputs / "course-c20-lora-4").mkdir()  # a run folder that has no row (failed or stopped)
    (outputs / "course-c05-pythia-2").mkdir()
    assert configs.next_attempt_id("c20", "lora", outputs) == "course-c20-lora-5"
    assert configs.next_attempt_id("c05", "pythia", outputs) == "course-c05-pythia-3"
    assert configs.next_attempt_id("c20", "qlora", outputs) == "course-c20-qlora-1"
    assert configs.next_attempt_id("c05", "smollm2", outputs) == "course-c05-smollm2-1"


# --- AC12.1.3: what the model-design and approach steps say ---


def test_AC12_1_3_c03_names_the_parts_of_a_transformer():
    text = _step_text(_step("c03"))
    assert "embedding" in text
    assert "grouped-query attention" in text or "grouped query attention" in text
    assert "mlp" in text
    assert "norm" in text
    assert "residual stream" in text
    assert "output head" in text


def test_AC12_1_3_c03_says_qwen3_ties_its_head_to_its_embeddings():
    text = _step_text(_step("c03"))
    assert _has_sentence(
        text, ("qwen3-0.6b", "qwen3"), ("tie", "tied", "ties", "shares", "shared"), ("embedding",)
    )


def test_AC12_1_3_c04_explains_each_compared_column():
    text = _step_text(_step("c04"))
    for words in (
        ("layers",),
        ("width",),
        ("attention heads", "heads"),
        ("key-value", "kv"),
        ("grouped-query",),
        ("head size",),
        ("mlp",),
        ("vocabulary", "vocab"),
        ("context",),
        ("tied",),
        ("rotary",),
        ("activation",),
        ("bf16",),
        ("4-bit",),
    ):
        assert any(w in text for w in words), words


def test_AC12_1_3_c06_gives_why_qwen3_17b_was_chosen():
    text = (_step("c06").why + "\n" + _step("c06").body).lower()
    assert _has_sentence(text, ("qwen3-1.7b",), ("room", "improve", "headroom"))
    assert _has_sentence(text, ("8 gb",), ("lora",))
    assert _has_sentence(text, ("apache",))


def test_AC12_1_3_c06_gives_why_not_the_alternatives():
    text = (_step("c06").why + "\n" + _step("c06").body).lower()
    assert _has_sentence(text, ("dense",), ("8 gb",))
    assert _has_sentence(text, ("expert",), ("memory",))
    assert _has_sentence(text, ("encoder-decoder", "encoder decoder"))
    assert _has_sentence(text, ("gated",), ("account",))
    assert _has_sentence(text, ("contaminat",))
    assert "llama" in text
    assert "gemma" in text


def test_AC12_1_3_c19_compares_the_four_approaches():
    text = _step_text(_step("c19"))
    assert "prompting" in text
    assert "full fine-tuning" in text or "full fine tuning" in text
    assert "lora" in text
    assert "qlora" in text
    # what each one trains and what it stores
    for words in (("gradient",), ("optimizer", "adam"), ("adapter",), ("4-bit",)):
        assert any(w in text for w in words), words
    assert "8 gb" in text


# --- AC12.1.4: light imports ---

LIGHT_MODULES = [
    "gsm8k.course",
    "gsm8k.course.steps",
    "gsm8k.course.configs",
    "gsm8k.course.progress",
    "gsm8k.course_cmd",
]

_IMPORT_PROBE = """
import importlib, os, sys
import gsm8k  # sets the in-folder caches; the probe starts after it
before = dict(os.environ)
importlib.import_module({module!r})
heavy = [m for m in ("torch", "transformers", "peft", "bitsandbytes") if m in sys.modules]
changed = sorted(k for k in set(before) | set(os.environ) if before.get(k) != os.environ.get(k))
assert not heavy, f"imported {{heavy}}"
assert not changed, f"changed environment variables {{changed}}"
"""


@pytest.mark.parametrize("module", LIGHT_MODULES)
def test_AC12_1_4_imports_no_heavy_library_and_changes_no_environment(module):
    env = dict(os.environ)
    src = str(ROOT / "src")
    env["PYTHONPATH"] = os.pathsep.join([src, env["PYTHONPATH"]]) if env.get("PYTHONPATH") else src
    env["CUDA_VISIBLE_DEVICES"] = ""
    result = subprocess.run(
        [sys.executable, "-c", _IMPORT_PROBE.format(module=module)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]


# --- AC12.4.4: c23 (grpo) from the latest finished c21 adapter ---


def test_AC12_4_4_c23_is_grpo_with_20_steps_and_4_generations_on_100_dev_problems(tmp_project_dirs):
    rc = _run_config()
    cfg = _build_config("c23", "grpo", tmp_project_dirs)
    rc.validate(cfg)
    assert cfg.model == Q06
    assert cfg.method == "grpo"
    assert cfg.grpo_steps == 20
    assert cfg.grpo_generations == 4
    assert cfg.split == "dev"
    assert cfg.limit == 100
    assert cfg.seed == 42


def test_AC12_4_4_c23_without_a_c21_row_starts_from_the_base_model(tmp_project_dirs):
    assert _build_config("c23", "grpo", tmp_project_dirs).adapter_path is None
    # a runs.csv with rows of other steps only does not give an adapter either
    _write_course_rows(tmp_project_dirs.outputs, [("course-c20-lora-1", "sft")])
    assert _build_config("c23", "grpo", tmp_project_dirs).adapter_path is None


def test_AC12_4_4_c23_starts_from_the_latest_finished_c21_adapter(tmp_project_dirs):
    _write_course_rows(
        tmp_project_dirs.outputs,
        [("course-c21-sft-1", "sft"), ("course-c20-lora-1", "sft"), ("course-c21-sft-2", "sft")],
    )
    for name in ("course-c21-sft-1", "course-c21-sft-2", "course-c20-lora-1"):
        (tmp_project_dirs.checkpoints / name).mkdir()
    cfg = _build_config("c23", "grpo", tmp_project_dirs)
    _run_config().validate(cfg)
    assert cfg.adapter_path is not None
    assert Path(cfg.adapter_path).resolve() == (tmp_project_dirs.checkpoints / "course-c21-sft-2").resolve()
    assert cfg.method == "grpo"
    assert cfg.grpo_steps == 20
    assert cfg.grpo_generations == 4


def test_AC12_4_4_c23_refuses_when_the_c21_adapter_folder_is_missing(tmp_project_dirs):
    configs = _configs()
    _write_course_rows(tmp_project_dirs.outputs, [("course-c21-sft-1", "sft")])
    assert issubclass(configs.CourseRunRefused, Exception)
    with pytest.raises(
        configs.CourseRunRefused, match=re.escape("Run step c21 again: its adapter is missing")
    ):
        _build_config("c23", "grpo", tmp_project_dirs)
    # once the adapter folder is back the run is built again
    (tmp_project_dirs.checkpoints / "course-c21-sft-1").mkdir()
    assert _build_config("c23", "grpo", tmp_project_dirs).adapter_path is not None


def test_AC12_4_4_building_the_c23_config_writes_no_file(tmp_project_dirs):
    """Building a course configuration reads files but writes none (the service queues the config)."""
    rc = _run_config()
    before = sorted(p.name for p in tmp_project_dirs.outputs.rglob("*"))
    cfg = _build_config("c23", "grpo", tmp_project_dirs)
    assert dataclasses.is_dataclass(cfg)
    assert isinstance(rc.to_dict(cfg), dict)
    assert sorted(p.name for p in tmp_project_dirs.outputs.rglob("*")) == before
