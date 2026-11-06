"""US2.1 (u3-sft): every run configuration is checked against the Training Dials table (stories.md)
before anything starts. AC2.1.1-AC2.1.5; FR2.1, FR2.2, NFR8.

``validate(cfg)`` checks a RunConfig; ``check_dials(d)`` parses user-given dials strictly (unknown name
or wrong type is a ConfigError naming the field) and returns a checked RunConfig (batch-2 plan, Part E).
No model, no GPU, no files.
"""

import re

import pytest

from gsm8k import run_config
from gsm8k.datasets_prompts.hub import MODEL_REVISIONS
from gsm8k.run_config import ConfigError, RunConfig, validate

RUN_ID = "q06-sft-dev-1"
MODEL_06 = "Qwen/Qwen3-0.6B-Base"
MODEL_17 = "Qwen/Qwen3-1.7B-Base"
TEST_SPLIT_MESSAGE = "The test split is never used for training or tuning"

# The Training Dials table (stories.md): C2 field -> default.
DIAL_DEFAULTS = {
    "model": MODEL_06,
    "learning_rate": 2e-4,
    "epochs": 1,
    "lora_rank": 16,
    "lora_alpha": 32,
    "max_seq_len": 512,
    "train_examples": "all",
    "batch_size": 4,
    "warmup_ratio": 0.03,
    "seed": 42,
    "answer_format": "step-by-step",
}

# Numeric dials: (C2 field, names the message may use, minimum, maximum, just below, just above).
NUMERIC_DIALS = [
    ("learning_rate", ("learning rate",), 1e-5, 5e-4, 9e-6, 5.1e-4),
    ("epochs", ("epochs",), 1, 3, 0, 4),
    ("lora_alpha", ("lora alpha",), 1, 128, 0, 129),
    ("max_seq_len", ("max seq len", "max sequence length"), 256, 1024, 255, 1025),
    ("train_examples", ("train examples", "training examples"), 50, 6973, 49, 6974),
    ("batch_size", ("batch size",), 1, 16, 0, 17),
    ("warmup_ratio", ("warmup ratio",), 0.0, 0.2, -0.01, 0.21),
    ("seed", ("seed",), 0, 2**31 - 1, -1, 2**31),
]
NUMERIC_IDS = [d[0] for d in NUMERIC_DIALS]

# Set dials: (C2 field, names the message may use, a value outside the set, the allowed values).
SET_DIALS = [
    ("model", ("model",), "gpt2", (MODEL_06, MODEL_17)),
    ("lora_rank", ("lora rank",), 7, (4, 8, 16, 32, 64)),
    ("lora_rank", ("lora rank",), 128, (4, 8, 16, 32, 64)),
    ("answer_format", ("answer format",), "verbose", ("step-by-step", "terse")),
]
SET_IDS = ["model", "lora_rank_7", "lora_rank_128", "answer_format"]

# Wrong types for user-given dials (AC2.1.4).
WRONG_TYPES = [
    ("learning_rate", "abc"),
    ("epochs", "two"),
    ("lora_rank", [16]),
    ("lora_alpha", 32.5),
    ("max_seq_len", None),
    ("train_examples", "some"),
    ("batch_size", True),
    ("warmup_ratio", {"value": 0.1}),
    ("seed", 4.5),
    ("model", 3),
    ("answer_format", 1),
]

# Methods that train or tune (sft, grpo, optuna, and the terse ablation, which fine-tunes); NFR8.
TRAINING_METHODS = ("sft", "grpo", "optuna", "terse")


def _normalised(message: str) -> str:
    return message.lower().replace("_", " ").replace("-", " ")


def _names_dial(message: str, names: tuple) -> bool:
    text = _normalised(message)
    return any(name.replace("-", " ") in text for name in names)


def _numbers_in(message: str) -> list[float]:
    """Every number written in the message (thousands commas allowed: 6,973)."""
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", message)
    return [float(m) for m in re.findall(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", text)]


def _mentions_number(message: str, value: float) -> bool:
    return any(n == pytest.approx(value, rel=1e-9, abs=1e-12) for n in _numbers_in(message))


def _check_range_message(message: str, names: tuple, low: float, high: float) -> None:
    assert _names_dial(message, names), f"message does not name the dial {names[0]}: {message!r}"
    assert _mentions_number(message, low), f"message lacks the minimum {low}: {message!r}"
    assert _mentions_number(message, high), f"message lacks the maximum {high}: {message!r}"


def _check_set_message(message: str, names: tuple, allowed: tuple) -> None:
    assert _names_dial(message, names), f"message does not name the dial {names[0]}: {message!r}"
    for value in allowed:
        if isinstance(value, int):
            assert _mentions_number(message, value), f"message lacks {value}: {message!r}"
        else:
            assert value in message, f"message lacks {value}: {message!r}"


# --- AC2.1.1 ---


def test_AC2_1_1_config_with_no_dials_set_passes_with_table_defaults():
    cfg = RunConfig(run_id=RUN_ID, method="sft")
    validate(cfg)
    for name, default in DIAL_DEFAULTS.items():
        value = getattr(cfg, name)
        if isinstance(default, float):
            assert value == pytest.approx(default), name
        else:
            assert value == default, name
    assert cfg.model_revision == MODEL_REVISIONS[MODEL_06]


def test_AC2_1_1_check_dials_with_no_dials_gives_table_defaults():
    cfg = run_config.check_dials({})
    assert isinstance(cfg, RunConfig)
    for name, default in DIAL_DEFAULTS.items():
        value = getattr(cfg, name)
        if isinstance(default, float):
            assert value == pytest.approx(default), name
        else:
            assert value == default, name


# --- AC2.1.2 ---


@pytest.mark.parametrize("dial,names,low,high,below,above", NUMERIC_DIALS, ids=NUMERIC_IDS)
def test_AC2_1_2_validate_accepts_bounds_and_rejects_just_outside(dial, names, low, high, below, above):
    validate(RunConfig(run_id=RUN_ID, method="sft", **{dial: low}))
    validate(RunConfig(run_id=RUN_ID, method="sft", **{dial: high}))
    for outside in (below, above):
        with pytest.raises(ConfigError) as excinfo:
            validate(RunConfig(run_id=RUN_ID, method="sft", **{dial: outside}))
        _check_range_message(str(excinfo.value), names, low, high)


@pytest.mark.parametrize("dial,names,low,high,below,above", NUMERIC_DIALS, ids=NUMERIC_IDS)
def test_AC2_1_2_check_dials_accepts_bounds_and_rejects_just_outside(dial, names, low, high, below, above):
    assert getattr(run_config.check_dials({dial: low}), dial) == low
    assert getattr(run_config.check_dials({dial: high}), dial) == high
    for outside in (below, above):
        with pytest.raises(ConfigError) as excinfo:
            run_config.check_dials({dial: outside})
        _check_range_message(str(excinfo.value), names, low, high)


def test_AC2_1_2_train_examples_all_passes():
    validate(RunConfig(run_id=RUN_ID, method="sft", train_examples="all"))
    assert run_config.check_dials({"train_examples": "all"}).train_examples == "all"


# --- AC2.1.3 ---


@pytest.mark.parametrize("dial,names,outside,allowed", SET_DIALS, ids=SET_IDS)
def test_AC2_1_3_validate_rejects_value_outside_set_listing_allowed(dial, names, outside, allowed):
    for value in allowed:
        validate(RunConfig(run_id=RUN_ID, method="sft", **{dial: value}))
    with pytest.raises(ConfigError) as excinfo:
        validate(RunConfig(run_id=RUN_ID, method="sft", **{dial: outside}))
    _check_set_message(str(excinfo.value), names, allowed)


@pytest.mark.parametrize("dial,names,outside,allowed", SET_DIALS, ids=SET_IDS)
def test_AC2_1_3_check_dials_rejects_value_outside_set_listing_allowed(dial, names, outside, allowed):
    for value in allowed:
        assert getattr(run_config.check_dials({dial: value}), dial) == value
    with pytest.raises(ConfigError) as excinfo:
        run_config.check_dials({dial: outside})
    _check_set_message(str(excinfo.value), names, allowed)


# --- AC2.1.4 ---


def test_AC2_1_4_unknown_dial_name_is_rejected_naming_the_field():
    with pytest.raises(ConfigError) as excinfo:
        run_config.check_dials({"learnig_rate": 1e-4})
    assert "learnig_rate" in str(excinfo.value)


def test_AC2_1_4_unknown_name_among_valid_dials_is_rejected():
    with pytest.raises(ConfigError) as excinfo:
        run_config.check_dials({"learning_rate": 1e-4, "lora_rank": 8, "dropout": 0.1})
    assert "dropout" in str(excinfo.value)


def test_AC2_1_4_learning_rate_abc_is_rejected_naming_the_field():
    with pytest.raises(ConfigError) as excinfo:
        run_config.check_dials({"learning_rate": "abc"})
    assert "learning rate" in _normalised(str(excinfo.value))


@pytest.mark.parametrize("dial,value", WRONG_TYPES, ids=[w[0] for w in WRONG_TYPES])
def test_AC2_1_4_wrong_type_is_rejected_naming_the_field(dial, value):
    with pytest.raises(ConfigError) as excinfo:
        run_config.check_dials({dial: value})
    assert dial.replace("_", " ") in _normalised(str(excinfo.value)) or dial in str(excinfo.value)


def test_AC2_1_4_valid_dials_are_parsed_into_the_config():
    cfg = run_config.check_dials(
        {
            "model": MODEL_17,
            "learning_rate": 1e-4,
            "epochs": 2,
            "lora_rank": 8,
            "lora_alpha": 16,
            "max_seq_len": 256,
            "train_examples": 100,
            "batch_size": 8,
            "warmup_ratio": 0.1,
            "seed": 7,
            "answer_format": "terse",
        }
    )
    assert cfg.model == MODEL_17
    assert cfg.model_revision == MODEL_REVISIONS[MODEL_17]
    assert cfg.learning_rate == pytest.approx(1e-4)
    assert (cfg.epochs, cfg.lora_rank, cfg.lora_alpha, cfg.max_seq_len) == (2, 8, 16, 256)
    assert (cfg.train_examples, cfg.batch_size, cfg.seed) == (100, 8, 7)
    assert cfg.warmup_ratio == pytest.approx(0.1)
    assert cfg.answer_format == "terse"


# --- AC2.1.5 ---


@pytest.mark.parametrize("method", TRAINING_METHODS)
def test_AC2_1_5_training_on_test_split_is_rejected(method):
    with pytest.raises(ConfigError) as excinfo:
        validate(RunConfig(run_id=RUN_ID, method=method, split="test"))
    assert str(excinfo.value) == TEST_SPLIT_MESSAGE


@pytest.mark.parametrize("method", TRAINING_METHODS)
def test_AC2_1_5_training_on_dev_split_passes(method):
    validate(RunConfig(run_id=RUN_ID, method=method, split="dev"))


@pytest.mark.parametrize("method", ("base", "best"))
def test_AC2_1_5_evaluation_on_test_split_still_passes(method):
    validate(RunConfig(run_id="q06-base-test-1", method=method, split="test"))
