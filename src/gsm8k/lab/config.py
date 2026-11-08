"""Lab configuration: the Lab Defaults, their allowed values, variants' configurations, time estimates.

Pure data and validation (US11.1, contract C8); no model is loaded and nothing here imports torch.
"""

from __future__ import annotations

import dataclasses
import math
import re
from typing import Any

LAB_MODEL = "EleutherAI/pythia-31m"
LAB_MODEL_REVISION = "e556ace21b489575e94e9d50b6dad2fcc7419679"

MAX_SEED = 2**31 - 1


@dataclasses.dataclass(frozen=True)
class LabConfig:
    """The Lab Defaults of stories.md plus the pinned lab model."""

    method: str = "lora"
    lora_rank: int = 8
    lora_alpha: int = 16
    learning_rate: float = 1e-3
    batch_size: int = 8
    train_examples: int = 800
    epochs: int = 1
    max_seq_len: int = 256
    warmup_ratio: float = 0.1
    schedule: str = "linear"
    loss_on: str = "answer"
    answer_format: str = "step-by-step"
    batching: str = "random"
    retokenize: bool = False
    seed: int = 42
    dev_problems: int = 64
    sample_problems: int = 3
    max_new_tokens: int = 128
    threads: int = 4
    model: str = LAB_MODEL
    model_revision: str = LAB_MODEL_REVISION

    def validate(self) -> None:
        """Raise ``ValueError`` (message starting with the field name) for a value outside Allowed."""
        _choice("method", self.method, ("lora", "full"))
        _int_in("lora_rank", self.lora_rank, 1, 64)
        _int_in("lora_alpha", self.lora_alpha, 1, 128)
        _float_in("learning_rate", self.learning_rate, 1e-6, 1e-1)
        _int_in("batch_size", self.batch_size, 1, 64)
        _int_in("train_examples", self.train_examples, 16, 6973)
        _int_in("epochs", self.epochs, 1, 20)
        _int_in("max_seq_len", self.max_seq_len, 64, 512)
        _float_in("warmup_ratio", self.warmup_ratio, 0.0, 0.5)
        _choice("schedule", self.schedule, ("linear", "constant"))
        _choice("loss_on", self.loss_on, ("answer", "all"))
        _choice("answer_format", self.answer_format, ("step-by-step", "terse"))
        _choice("batching", self.batching, ("random", "by-length"))
        if not isinstance(self.retokenize, bool):
            raise ValueError(f"retokenize must be true or false, got {self.retokenize!r}")
        _int_in("seed", self.seed, 0, MAX_SEED)
        _int_in("dev_problems", self.dev_problems, 8, 496)
        _int_in("sample_problems", self.sample_problems, 0, 8)
        _int_in("max_new_tokens", self.max_new_tokens, 16, 256)
        _int_in("threads", self.threads, 1, 8)
        if not isinstance(self.model, str) or not self.model:
            raise ValueError(f"model must be a model name, got {self.model!r}")
        if not isinstance(self.model_revision, str) or not re.fullmatch(r"[0-9a-f]{40}", self.model_revision):
            raise ValueError(f"model_revision must be a 40-character commit id, got {self.model_revision!r}")


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _int_in(name: str, value: Any, low: int, high: int) -> None:
    if not _is_int(value) or not low <= value <= high:
        raise ValueError(f"{name} must be a whole number from {low:,} to {high:,}, got {value!r}")


def _float_in(name: str, value: Any, low: float, high: float) -> None:
    ok = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    if not ok or not low <= value <= high:
        raise ValueError(f"{name} must be a number from {low:g} to {high:g}, got {value!r}")


def _choice(name: str, value: Any, allowed: tuple[str, ...]) -> None:
    if value not in allowed:
        raise ValueError(f"{name} must be one of {', '.join(allowed)}, got {value!r}")


def config_for(lesson_id: str, variant_name: str) -> LabConfig:
    """The Lab Defaults with exactly the variant's changes, validated."""
    from gsm8k.lab.lessons import LESSONS

    lesson = next((item for item in LESSONS if item.id == lesson_id), None)
    if lesson is None:
        raise ValueError(f"Unknown lesson: {lesson_id}")
    variant = next((item for item in lesson.variants if item.name == variant_name), None)
    if variant is None:
        raise ValueError(f"Unknown variant of {lesson_id}: {variant_name}")
    cfg = dataclasses.replace(LabConfig(), **variant.changes)
    cfg.validate()
    return cfg


def estimate_minutes(lesson: Any) -> int:
    """Whole minutes: per variant train_examples x epochs x 0.2 s (doubled for ``full``) plus 60 s.

    Computed in whole tenths of a second so no float rounding enters; the sum is rounded up.
    """
    tenths = 0
    for variant in lesson.variants:
        cfg = dataclasses.replace(LabConfig(), **variant.changes)
        per_example = 4 if cfg.method == "full" else 2
        tenths += cfg.train_examples * cfg.epochs * per_example + 600
    return -(-tenths // 600)


def _number_text(value: float) -> str:
    """1e-05 -> '1e-5', 0.003 -> '3e-3', 0.1 -> '0.1', 12 -> '12'."""
    if isinstance(value, float):
        if value != 0 and abs(value) <= 0.01:
            mantissa, exponent = f"{value:e}".split("e")
            mantissa = mantissa.rstrip("0").rstrip(".")
            return f"{mantissa}e{int(exponent)}"
        return f"{value:g}"
    return str(value)


def changes_text(variant: Any) -> str:
    """The variant's changes in plain words, for example 'learning rate 1e-5'."""
    if not variant.changes:
        return "no change (the starting point)"
    parts = []
    for name, value in variant.changes.items():
        if isinstance(value, bool):
            text = "true" if value else "false"
        else:
            text = _number_text(value) if isinstance(value, (int, float)) else str(value)
        parts.append(f"{name.replace('_', ' ')} {text}")
    return ", ".join(parts)
