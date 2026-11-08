"""u11-finetune-lab, US11.1: the lab's lessons, their configurations and time estimates.

Pure data and validation (stories.md Lab Defaults and Lab Lessons, contract C8); no model is loaded.
"""

import dataclasses
import re

import pytest

from gsm8k import cli
from gsm8k.lab import config as lab_config
from gsm8k.lab import lessons as lab_lessons

# stories.md, Lab Defaults (plus the pinned lab model of contract C8).
DEFAULTS = {
    "method": "lora",
    "lora_rank": 8,
    "lora_alpha": 16,
    "learning_rate": 1e-3,
    "batch_size": 8,
    "train_examples": 800,
    "epochs": 1,
    "max_seq_len": 256,
    "warmup_ratio": 0.1,
    "schedule": "linear",
    "loss_on": "answer",
    "answer_format": "step-by-step",
    "batching": "random",
    "retokenize": False,
    "seed": 42,
    "dev_problems": 64,
    "sample_problems": 3,
    "max_new_tokens": 128,
    "threads": 4,
    "model": "EleutherAI/pythia-31m",
    "model_revision": "e556ace21b489575e94e9d50b6dad2fcc7419679",
}

# stories.md, Lab Lessons: (id, title, [(variant name, changes), ...]) in the table's order.
LESSON_TABLE = [
    ("l01", "What a fine-tune does", [("baseline", {})]),
    (
        "l02",
        "Learning rate",
        [
            ("lr-1e-5", {"learning_rate": 1e-5}),
            ("lr-1e-4", {"learning_rate": 1e-4}),
            ("lr-1e-3", {"learning_rate": 1e-3}),
            ("lr-1e-2", {"learning_rate": 1e-2}),
        ],
    ),
    (
        "l03",
        "Epochs and overfitting",
        [
            ("few-many", {"train_examples": 64, "epochs": 12}),
            ("many-once", {"train_examples": 768, "epochs": 1}),
        ],
    ),
    (
        "l04",
        "How much data",
        [
            ("data-200", {"train_examples": 200}),
            ("data-800", {"train_examples": 800}),
            ("data-1600", {"train_examples": 1600}),
        ],
    ),
    (
        "l05",
        "LoRA rank",
        [
            ("rank-1", {"lora_rank": 1, "lora_alpha": 2}),
            ("rank-8", {"lora_rank": 8, "lora_alpha": 16}),
            ("rank-64", {"lora_rank": 64, "lora_alpha": 128}),
        ],
    ),
    ("l06", "LoRA or every weight", [("lora", {}), ("full", {"method": "full", "learning_rate": 1e-4})]),
    (
        "l07",
        "Batch size",
        [("batch-1", {"batch_size": 1}), ("batch-8", {"batch_size": 8}), ("batch-32", {"batch_size": 32})],
    ),
    ("l08", "What the loss counts", [("answer-only", {}), ("whole-text", {"loss_on": "all"})]),
    ("l09", "Answer format", [("step-by-step", {}), ("terse", {"answer_format": "terse"})]),
    (
        "l10",
        "Warm-up and schedule",
        [
            ("warmup-decay", {}),
            ("constant", {"schedule": "constant", "warmup_ratio": 0}),
            ("hot-start", {"learning_rate": 3e-3, "warmup_ratio": 0}),
        ],
    ),
    ("l11", "Seed noise", [("seed-1", {"seed": 1}), ("seed-2", {"seed": 2}), ("seed-3", {"seed": 3})]),
    (
        "l12",
        "Where the time goes",
        [
            ("tokenize-once", {}),
            ("by-length", {"batching": "by-length"}),
            ("retokenize", {"retokenize": True}),
        ],
    ),
]

# A big_run text names a Training Dials dial (stories.md Training Dials) or a training method.
BIG_RUN_NAMES = re.compile(
    r"learning rate|\bepochs?\b|lora rank|lora alpha|max(imum)? sequence length|training examples"
    r"|batch size|warm-?up ratio|\bseed\b|answer format|\b(sft|grpo|optuna|terse|selfcot)\b",
    re.IGNORECASE,
)


def _lesson(lesson_id):
    return next(lesson for lesson in lab_lessons.LESSONS if lesson.id == lesson_id)


def _expected_minutes(variants):
    """AC11.1.3 in whole tenths of a second: 2 tenths per example-epoch (4 for full) + 600 per variant."""
    tenths = 0
    for _, changes in variants:
        cfg = {**DEFAULTS, **changes}
        per_example = 4 if cfg["method"] == "full" else 2
        tenths += cfg["train_examples"] * cfg["epochs"] * per_example + 600
    return -(-tenths // 600)


# ---------------------------------------------------------------- AC11.1.1


def test_AC11_1_1_twelve_lessons_with_table_ids_titles_and_variants_in_order():
    lessons = lab_lessons.LESSONS
    assert isinstance(lessons, tuple)
    assert [lesson.id for lesson in lessons] == [row[0] for row in LESSON_TABLE]
    assert [lesson.number for lesson in lessons] == list(range(1, 13))
    assert [lesson.title for lesson in lessons] == [row[1] for row in LESSON_TABLE]
    for lesson, (_, _, variants) in zip(lessons, LESSON_TABLE, strict=True):
        assert [v.name for v in lesson.variants] == [name for name, _ in variants], lesson.id


def test_AC11_1_1_every_lesson_has_its_teaching_texts_and_three_guess_options():
    for lesson in lab_lessons.LESSONS:
        for field in ("question", "watch", "guess_prompt", "why", "big_run", "check"):
            value = getattr(lesson, field)
            assert isinstance(value, str) and value.strip(), f"{lesson.id}.{field} is empty"
        options = lesson.guess_options
        assert len(options) == 3, lesson.id
        assert all(isinstance(o, str) and o.strip() for o in options), lesson.id
        assert len(set(options)) == 3, f"{lesson.id} repeats a guess option"
        labels = [v.label for v in lesson.variants]
        assert all(isinstance(label, str) and label.strip() for label in labels), lesson.id
        assert len(set(labels)) == len(labels), f"{lesson.id} repeats a variant label"


def test_AC11_1_1_big_run_names_a_training_dial_or_method():
    for lesson in lab_lessons.LESSONS:
        assert BIG_RUN_NAMES.search(lesson.big_run), f"{lesson.id} big_run names no dial or method"


def test_AC11_1_1_lab_list_prints_one_line_per_lesson(capsys):
    assert cli.main(["lab", "list"]) == 0
    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert len(lines) == 12
    for line, (lesson_id, title, variants) in zip(lines, LESSON_TABLE, strict=True):
        assert line.startswith(lesson_id), line
        assert title in line, line
        assert f"about {_expected_minutes(variants)} min" in line, line
    assert "(1 variant, about 4 min)" in lines[0]


# ---------------------------------------------------------------- AC11.1.2


def test_AC11_1_2_lab_config_is_a_frozen_dataclass_with_the_lab_defaults():
    cfg = lab_config.LabConfig()
    assert {f.name for f in dataclasses.fields(cfg)} == set(DEFAULTS)
    assert dataclasses.asdict(cfg) == DEFAULTS
    cfg.validate()
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.learning_rate = 0.1  # type: ignore[misc]


def test_AC11_1_2_variant_config_is_the_defaults_with_exactly_its_changes():
    for lesson_id, _, variants in LESSON_TABLE:
        lesson = _lesson(lesson_id)
        for variant, (name, changes) in zip(lesson.variants, variants, strict=True):
            assert variant.changes == changes, f"{lesson_id}/{name}"
            cfg = lab_config.config_for(lesson_id, name)
            assert isinstance(cfg, lab_config.LabConfig)
            assert dataclasses.asdict(cfg) == {**DEFAULTS, **changes}, f"{lesson_id}/{name}"
            cfg.validate()
    few_many = lab_config.config_for("l03", "few-many")
    assert (few_many.train_examples, few_many.epochs) == (64, 12)
    assert few_many.learning_rate == DEFAULTS["learning_rate"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("learning_rate", 0.5),
        ("learning_rate", 1e-7),
        ("schedule", "cosine"),
        ("batch_size", 0),
        ("batch_size", 65),
        ("method", "qlora"),
        ("lora_rank", 0),
        ("lora_rank", 65),
        ("lora_rank", 2.5),
        ("lora_alpha", 0),
        ("lora_alpha", 129),
        ("train_examples", 15),
        ("train_examples", 6974),
        ("epochs", 0),
        ("epochs", 21),
        ("max_seq_len", 63),
        ("max_seq_len", 513),
        ("warmup_ratio", -0.1),
        ("warmup_ratio", 0.6),
        ("loss_on", "question"),
        ("answer_format", "chatty"),
        ("batching", "sorted"),
        ("retokenize", "yes"),
        ("seed", -1),
        ("seed", 2**31),
        ("dev_problems", 7),
        ("dev_problems", 497),
        ("sample_problems", -1),
        ("sample_problems", 9),
        ("max_new_tokens", 15),
        ("max_new_tokens", 257),
        ("threads", 0),
        ("threads", 9),
    ],
)
def test_AC11_1_2_value_outside_allowed_is_refused_naming_the_field(field, value):
    with pytest.raises(ValueError) as excinfo:
        lab_config.LabConfig(**{field: value}).validate()
    assert str(excinfo.value).startswith(field), str(excinfo.value)


@pytest.mark.parametrize(
    "changes",
    [
        {"lora_rank": 1, "lora_alpha": 1, "learning_rate": 1e-6, "batch_size": 1, "train_examples": 16},
        {"lora_rank": 64, "lora_alpha": 128, "learning_rate": 1e-1, "batch_size": 64, "train_examples": 6973},
        {
            "epochs": 1,
            "max_seq_len": 64,
            "warmup_ratio": 0,
            "seed": 0,
            "dev_problems": 8,
            "sample_problems": 0,
        },
        {"epochs": 20, "max_seq_len": 512, "warmup_ratio": 0.5, "seed": 2**31 - 1, "dev_problems": 496},
        {"sample_problems": 8, "max_new_tokens": 16, "threads": 1, "method": "full", "schedule": "constant"},
        {"max_new_tokens": 256, "threads": 8, "loss_on": "all", "answer_format": "terse"},
        {"batching": "by-length", "retokenize": True},
    ],
)
def test_AC11_1_2_bounds_of_the_allowed_column_pass(changes):
    lab_config.LabConfig(**changes).validate()


def test_AC11_1_2_changes_text_in_plain_words():
    assert lab_config.changes_text(_lesson("l01").variants[0]) == "no change (the starting point)"
    assert lab_config.changes_text(_lesson("l02").variants[0]) == "learning rate 1e-5"
    for lesson in lab_lessons.LESSONS:
        for variant in lesson.variants:
            text = lab_config.changes_text(variant)
            assert isinstance(text, str) and text.strip(), f"{lesson.id}/{variant.name}"


# ---------------------------------------------------------------- AC11.1.3


def test_AC11_1_3_estimate_of_l01_and_l02():
    assert lab_config.estimate_minutes(_lesson("l01")) == 4
    assert lab_config.estimate_minutes(_lesson("l02")) == 15


def test_AC11_1_3_estimate_of_every_lesson_in_whole_tenths():
    for lesson_id, _, variants in LESSON_TABLE:
        estimate = lab_config.estimate_minutes(_lesson(lesson_id))
        assert isinstance(estimate, int), lesson_id
        assert estimate == _expected_minutes(variants), lesson_id
    # l06 and l07 land exactly on whole minutes (6,000 and 6,600 tenths): no float rounding up.
    assert lab_config.estimate_minutes(_lesson("l06")) == 10
    assert lab_config.estimate_minutes(_lesson("l07")) == 11
