"""RunConfiguration: every field of a run's config.json (contract C2), its checks and its hash (BR4.5).

Defaults are the documented ones: the dials from stories.md "Training Dials", the model and dataset
revisions pinned in ``gsm8k.datasets_prompts.hub`` and a generation cap of 512 new tokens (BR3.5).
Importing this module stays light: ``hub`` imports its heavy libraries inside its functions.
"""

import dataclasses
import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gsm8k.datasets_prompts.hub import DATASET_REVISION, MODEL_REVISIONS

SCHEMA_VERSION = 1
DEFAULT_MODEL = "Qwen/Qwen3-0.6B-Base"
MODELS = ("Qwen/Qwen3-0.6B-Base", "Qwen/Qwen3-1.7B-Base")
METHODS = ("base", "sft", "grpo", "best", "terse", "vote", "calc", "optuna", "cotgen", "selfcot")
SPLITS = ("dev", "test", "gsmplus-testmini", "gsmsym-p1", "train")
ANSWER_FORMATS = ("step-by-step", "terse")
LORA_RANKS = (4, 8, 16, 32, 64)
EVALUATORS = ("project", "lm-eval-harness")
TRAIN_SPLIT_SIZE = 6973  # 7,473 training problems minus the 500 dev problems
MAX_SEED = 2**31 - 1
MAX_NEW_TOKENS_CAP = 4096
# Methods that train or tune, so never read the test split (NFR8, AC2.1.5). The terse ablation fine-tunes;
# vote and calc are evaluation-only ablations, base and best only evaluate. selfcot fine-tunes on the
# model's own reasoning (US10.2); cotgen only samples the training part (split train, US10.1).
TRAINING_METHODS = ("sft", "grpo", "optuna", "terse", "selfcot")
# The chain-of-thought generation samples the training part of the split; split train is its own (C2).
COT_METHOD = "cotgen"
COT_SPLIT = "train"
COT_SAMPLES_RANGE = (1, 8)
COT_TEMPERATURE_RANGE = (0.1, 1.5)
TEST_SPLIT_MESSAGE = "The test split is never used for training or tuning"
# The run id check_dials puts in its config when the caller gives none (the caller sets the real one).
UNSET_RUN_ID = "unset"

# Fields that never enter the hash (C2).
_NOT_HASHED = ("run_id", "v")
# Fields always in the hash input, even at their default (C2).
_ALWAYS_HASHED = ("model", "method")


class ConfigError(Exception):
    """A configuration field is invalid; the message names the field and what it allows."""


@dataclass
class RunConfig:
    """One run's configuration, as written to ``outputs/<run_id>/config.json`` (C2)."""

    run_id: str
    v: int = SCHEMA_VERSION
    model: str = DEFAULT_MODEL
    method: str = "base"
    split: str = "dev"
    adapter_path: str | None = None
    learning_rate: float = 2e-4
    epochs: int = 1
    lora_rank: int = 16
    lora_alpha: int = 32
    max_seq_len: int = 512
    train_examples: int | str = "all"
    batch_size: int = 4
    warmup_ratio: float = 0.03
    seed: int = 42
    split_seed: int = 42
    # None means "the pin in the code for this model"; resolved at construction.
    model_revision: str | None = field(default=None)
    dataset_revision: str = DATASET_REVISION
    answer_format: str = "step-by-step"
    limit: int | None = None
    vote_samples: int = 1
    calculator: bool = False
    max_new_tokens: int = 512
    grpo_steps: int | None = None
    grpo_generations: int | None = None
    evaluator: str = "project"
    # Self-taught chain of thought (US10.1, US10.2; C2, added 2026-11-08). At their defaults they stay
    # out of the hash, so earlier hashes are unchanged.
    cot_problems: int | str = 1500
    cot_samples: int = 4
    cot_temperature: float = 0.7
    cot_data_run: str | None = None

    def __post_init__(self) -> None:
        if self.model_revision is None:
            self.model_revision = MODEL_REVISIONS.get(self.model)


_FIELD_NAMES = tuple(f.name for f in dataclasses.fields(RunConfig))


def _default_of(cfg: RunConfig, name: str) -> Any:
    """The documented default of a field; the model revision's default is the pin for cfg.model."""
    if name == "model_revision":
        return MODEL_REVISIONS.get(cfg.model)
    f = next(f for f in dataclasses.fields(RunConfig) if f.name == name)
    if f.default is dataclasses.MISSING:
        return dataclasses.MISSING
    return f.default


def to_dict(cfg: RunConfig) -> dict:
    """Every C2 field, JSON-serialisable, in declaration order."""
    return {name: getattr(cfg, name) for name in _FIELD_NAMES}


def from_dict(d: dict) -> RunConfig:
    """Build a RunConfig from a config.json object; unknown keys are ignored (C2 common rules)."""
    if not isinstance(d, dict):
        raise ConfigError("Configuration must be a JSON object")
    if "run_id" not in d:
        raise ConfigError("Configuration field run_id is missing")
    known = {k: v for k, v in d.items() if k in _FIELD_NAMES}
    return RunConfig(**known)


def read_config(path: Path) -> RunConfig:
    """Read a config.json; an unreadable or malformed file raises ConfigError naming the file."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ConfigError(f"Configuration file could not be read: {path}") from exc
    try:
        return from_dict(data)
    except ConfigError as exc:
        raise ConfigError(f"Configuration file could not be read: {path} ({exc})") from exc


def _hash_input(cfg: RunConfig) -> dict:
    data = {}
    for name in _FIELD_NAMES:
        if name in _NOT_HASHED:
            continue
        value = getattr(cfg, name)
        if name in _ALWAYS_HASHED or value != _default_of(cfg, name):
            data[name] = value
    return data


def config_hash(cfg: RunConfig) -> str:
    """sha256 hex of the canonical JSON of {model, method} plus every field that differs from its
    default, keys sorted, compact separators, without run_id and v (BR4.5, contract C2)."""
    text = json.dumps(_hash_input(cfg), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- checks ---


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return (_is_int(value) or isinstance(value, float)) and math.isfinite(value)


def _int_in(name: str, value: Any, low: int, high: int) -> None:
    if not _is_int(value) or not low <= value <= high:
        raise ConfigError(f"{name} must be a whole number from {low} to {high}, got {value!r}")


def _number_in(name: str, value: Any, low: float, high: float) -> None:
    if not _is_number(value) or not low <= value <= high:
        raise ConfigError(f"{name} must be a number from {low:g} to {high:g}, got {value!r}")


def _one_of(name: str, value: Any, allowed: tuple) -> None:
    if isinstance(value, bool) or value not in allowed:
        listed = ", ".join(str(a) for a in allowed)
        raise ConfigError(f"{name} must be one of {listed}, got {value!r}")


def _optional_int_from(name: str, value: Any, low: int) -> None:
    if value is not None and (not _is_int(value) or value < low):
        raise ConfigError(f"{name} must be empty or a whole number of at least {low}, got {value!r}")


def _revision(name: str, value: Any) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{name} must be a Hub commit hash, got {value!r}")


def validate(cfg: RunConfig) -> None:
    """Check every field against its allowed values; raise ConfigError naming the first bad field."""
    if not isinstance(cfg.run_id, str) or not cfg.run_id:
        raise ConfigError(f"run_id must be a non-empty string, got {cfg.run_id!r}")
    if cfg.v != SCHEMA_VERSION or not _is_int(cfg.v):
        raise ConfigError(f"v must be {SCHEMA_VERSION}, got {cfg.v!r}")
    _one_of("model", cfg.model, MODELS)
    _one_of("method", cfg.method, METHODS)
    _one_of("split", cfg.split, SPLITS)
    if cfg.method in TRAINING_METHODS and cfg.split == "test":
        raise ConfigError(TEST_SPLIT_MESSAGE)
    if cfg.adapter_path is not None and (not isinstance(cfg.adapter_path, str) or not cfg.adapter_path):
        raise ConfigError(f"adapter_path must be empty or a path, got {cfg.adapter_path!r}")
    _number_in("learning_rate", cfg.learning_rate, 1e-5, 5e-4)
    _int_in("epochs", cfg.epochs, 1, 3)
    _one_of("lora_rank", cfg.lora_rank, LORA_RANKS)
    _int_in("lora_alpha", cfg.lora_alpha, 1, 128)
    _int_in("max_seq_len", cfg.max_seq_len, 256, 1024)
    if cfg.train_examples != "all":
        if not _is_int(cfg.train_examples) or not 50 <= cfg.train_examples <= TRAIN_SPLIT_SIZE:
            raise ConfigError(
                f"train_examples must be 'all' or a whole number from 50 to {TRAIN_SPLIT_SIZE}, "
                f"got {cfg.train_examples!r}"
            )
    _int_in("batch_size", cfg.batch_size, 1, 16)
    _number_in("warmup_ratio", cfg.warmup_ratio, 0.0, 0.2)
    _int_in("seed", cfg.seed, 0, MAX_SEED)
    _int_in("split_seed", cfg.split_seed, 0, MAX_SEED)
    _revision("model_revision", cfg.model_revision)
    _revision("dataset_revision", cfg.dataset_revision)
    _one_of("answer_format", cfg.answer_format, ANSWER_FORMATS)
    _optional_int_from("limit", cfg.limit, 1)
    _int_in("vote_samples", cfg.vote_samples, 1, 64)
    if not isinstance(cfg.calculator, bool):
        raise ConfigError(f"calculator must be true or false, got {cfg.calculator!r}")
    _int_in("max_new_tokens", cfg.max_new_tokens, 1, MAX_NEW_TOKENS_CAP)
    _optional_int_from("grpo_steps", cfg.grpo_steps, 1)
    _optional_int_from("grpo_generations", cfg.grpo_generations, 1)
    _one_of("evaluator", cfg.evaluator, EVALUATORS)
    _validate_cot(cfg)


def _validate_cot(cfg: RunConfig) -> None:
    """The chain-of-thought dials (stories.md group 10) and the split train rule (C2)."""
    if cfg.cot_problems != "all":
        if not _is_int(cfg.cot_problems) or not 50 <= cfg.cot_problems <= TRAIN_SPLIT_SIZE:
            raise ConfigError(
                f"cot_problems must be 'all' or a whole number from 50 to {TRAIN_SPLIT_SIZE}, "
                f"got {cfg.cot_problems!r}"
            )
    _int_in("cot_samples", cfg.cot_samples, *COT_SAMPLES_RANGE)
    _number_in("cot_temperature", cfg.cot_temperature, *COT_TEMPERATURE_RANGE)
    if cfg.cot_data_run is not None and (not isinstance(cfg.cot_data_run, str) or not cfg.cot_data_run):
        raise ConfigError(f"cot_data_run must be empty or a run id, got {cfg.cot_data_run!r}")
    if (cfg.split == COT_SPLIT) != (cfg.method == COT_METHOD):
        raise ConfigError(
            f"split {COT_SPLIT} is only for method {COT_METHOD}, and method {COT_METHOD} only takes split "
            f"{COT_SPLIT}; got method {cfg.method!r} with split {cfg.split!r}"
        )


# --- strict parsing of user-given dials (AC2.1.4) ---

_FLOAT_FIELDS = ("learning_rate", "warmup_ratio", "cot_temperature")
_INT_FIELDS = (
    "v",
    "epochs",
    "lora_rank",
    "lora_alpha",
    "max_seq_len",
    "batch_size",
    "seed",
    "split_seed",
    "vote_samples",
    "max_new_tokens",
    "cot_samples",
)
_STR_FIELDS = (
    "run_id",
    "model",
    "method",
    "split",
    "model_revision",
    "dataset_revision",
    "answer_format",
    "evaluator",
)
_OPTIONAL_INT_FIELDS = ("limit", "grpo_steps", "grpo_generations")


def _check_type(name: str, value: Any) -> Any:
    """Return the value if its JSON type fits the field (ints widen to floats for float fields), else
    raise ConfigError naming the field. Nothing is coerced from strings or booleans."""
    if name in _FLOAT_FIELDS:
        if not _is_number(value):
            raise ConfigError(f"{name} must be a number, got {value!r}")
        return float(value)
    if name in _INT_FIELDS:
        if not _is_int(value):
            raise ConfigError(f"{name} must be a whole number, got {value!r}")
        return value
    if name in _STR_FIELDS:
        if not isinstance(value, str):
            raise ConfigError(f"{name} must be text, got {value!r}")
        return value
    if name in _OPTIONAL_INT_FIELDS:
        if value is not None and not _is_int(value):
            raise ConfigError(f"{name} must be empty or a whole number, got {value!r}")
        return value
    if name == "train_examples":
        if value != "all" and not _is_int(value):
            raise ConfigError(f"train_examples must be 'all' or a whole number, got {value!r}")
        return value
    if name == "cot_problems":
        if value != "all" and not _is_int(value):
            raise ConfigError(f"cot_problems must be 'all' or a whole number, got {value!r}")
        return value
    if name == "cot_data_run":
        if value is not None and not isinstance(value, str):
            raise ConfigError(f"cot_data_run must be empty or a run id, got {value!r}")
        return value
    if name == "adapter_path":
        if value is not None and not isinstance(value, str):
            raise ConfigError(f"adapter_path must be empty or a path, got {value!r}")
        return value
    if name == "calculator":
        if not isinstance(value, bool):
            raise ConfigError(f"calculator must be true or false, got {value!r}")
        return value
    raise ConfigError(f"Unknown configuration field: {name}")  # pragma: no cover - every field is listed


def check_dials(d: dict, run_id: str = UNSET_RUN_ID) -> RunConfig:
    """Parse user-given dials (C2 field names) strictly and return a fully checked RunConfig.

    An unknown name or a value of the wrong type raises ConfigError naming the field (AC2.1.4); then
    every field is checked as ``validate`` does (AC2.1.2, AC2.1.3, AC2.1.5). Fields not given take their
    defaults; the model revision follows the model unless given. ``run_id`` is the run id to put in the
    config (a ``run_id`` key in ``d`` takes precedence).
    """
    if not isinstance(d, dict):
        raise ConfigError("Dials must be given as a mapping of field names to values")
    unknown = [name for name in d if name not in _FIELD_NAMES]
    if unknown:
        listed = ", ".join(str(name) for name in unknown)
        raise ConfigError(f"Unknown configuration field: {listed}")
    fields = {name: _check_type(name, value) for name, value in d.items()}
    fields.setdefault("run_id", run_id)
    cfg = RunConfig(**fields)
    validate(cfg)
    return cfg
