"""The shared training loop pieces: metrics lines and the Trainer callback (FR2.3, ADR-005, contract C2).

``MetricsWriter`` appends one whole ``metrics.jsonl`` line per call with a single ``write`` of the
full line plus its newline, so a reader never sees a half line as data; ``read_metrics`` returns the
complete lines only (a last line without its newline is still being written). Both methods (``sft``
and, in u7, ``grpo``) stream through the same callback: its ``log_fields`` map C2 fields such as
``reward``, ``kl`` and ``answer_length`` to the Trainer's log keys, which is GRPO's hook. A step line
also carries the Trainer's ``grad_norm`` and fractional ``epoch`` (null when not logged; a line written
without them is still valid, so readers treat a missing field as null).

Heavy libraries (transformers) are imported inside the functions.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
METRICS_FILE = "metrics.jsonl"

# Every C2 metrics field after "v", in order; a field not given is written as null.
METRIC_FIELDS = (
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
    "grad_norm",
    "epoch",
)


def _json_number(value: Any) -> Any:
    """A float that JSON can hold (NaN and infinities become null); other values unchanged."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


class MetricsWriter:
    """Appends C2 metrics lines to ``<run_dir>/metrics.jsonl``."""

    def __init__(self, run_dir: Path):
        self.path = Path(run_dir) / METRICS_FILE

    def write(self, **fields: Any) -> dict:
        """Append one line; unknown field names raise ValueError. Returns the written object."""
        unknown = sorted(set(fields) - set(METRIC_FIELDS))
        if unknown:
            raise ValueError(f"Unknown metrics field: {', '.join(unknown)}")
        line = {"v": SCHEMA_VERSION}
        for name in METRIC_FIELDS:
            line[name] = _json_number(fields.get(name))
        data = (json.dumps(line, allow_nan=False) + "\n").encode("utf-8")
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            written = os.write(fd, data)
        finally:
            os.close(fd)
        if written != len(data):  # a short write on a regular file means the disk is full
            raise OSError(f"Metrics line was cut short in {self.path}")
        return line


def read_metrics(path: Path) -> list[dict]:
    """The complete lines of a metrics.jsonl as objects; a missing file is no lines (C2).

    The text after the last newline is a line still being written and is never data, even when it
    parses; a complete line that is not a JSON object is skipped.
    """
    try:
        text = Path(path).read_bytes().decode("utf-8", errors="replace")
    except FileNotFoundError:
        return []
    complete = text.split("\n")[:-1]
    lines: list[dict] = []
    for raw in complete:
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except ValueError:
            continue
        if isinstance(obj, dict):
            lines.append(obj)
    return lines


@dataclass
class LoopClock:
    """Wall time of the training loop and the part of it spent in dev evaluations."""

    started: float | None = None
    ended: float | None = None
    eval_seconds: float = 0.0
    steps: int = 0
    peak_gpu_memory_gb: float = 0.0
    dev_scores: list[tuple[int, float]] = field(default_factory=list)

    def elapsed(self) -> float:
        if self.started is None:
            return 0.0
        end = self.ended if self.ended is not None else time.monotonic()
        return max(0.0, end - self.started)

    def eta(self, step: int, total_steps: int) -> float | None:
        if step <= 0:
            return None
        return max(0.0, self.elapsed() / step * (total_steps - step))

    def seconds_per_step(self) -> float:
        """Training seconds per step, without the time spent in dev evaluations."""
        if self.steps <= 0:
            return 0.0
        return max(0.0, self.elapsed() - self.eval_seconds) / self.steps


def gpu_peak_gb() -> float:
    """Peak allocated CUDA memory in GiB since the last reset, or 0.0 without CUDA."""
    torch = sys.modules.get("torch")
    if torch is None or not torch.cuda.is_available():
        return 0.0
    return torch.cuda.max_memory_allocated() / 1024**3


def make_metrics_callback(
    writer: MetricsWriter,
    clock: LoopClock,
    total_steps: int,
    *,
    dev_eval: Callable[[Any], float] | None = None,
    eval_every: int | None = None,
    log_fields: dict[str, str] | None = None,
    progress_every: int | None = None,
) -> Any:
    """A transformers ``TrainerCallback`` that writes one metrics line per logging step.

    ``dev_eval(model) -> accuracy`` runs every ``eval_every`` steps (not at the last step: the
    closing dev score covers it) and adds a line with ``dev_accuracy``. ``log_fields`` maps extra C2
    fields to Trainer log keys (GRPO: ``{"reward": "reward", "kl": "kl", "answer_length": ...}``).
    """
    from transformers import TrainerCallback

    extra = dict(log_fields or {})
    every = progress_every or max(1, total_steps // 20)

    class MetricsCallback(TrainerCallback):
        def on_train_begin(self, args, state, control, **kwargs):
            clock.started = time.monotonic()

        def on_train_end(self, args, state, control, **kwargs):
            clock.ended = time.monotonic()
            clock.steps = state.global_step
            clock.peak_gpu_memory_gb = max(clock.peak_gpu_memory_gb, gpu_peak_gb())

        def on_log(self, args, state, control, logs=None, **kwargs):
            logs = logs or {}
            if "loss" not in logs:  # the closing summary (train_runtime, train_loss) is no step line
                return
            step = state.global_step
            fields = {
                "step": step,
                "total_steps": total_steps,
                "loss": float(logs["loss"]),
                "learning_rate": float(logs["learning_rate"]) if "learning_rate" in logs else None,
                "elapsed_s": round(clock.elapsed(), 3),
                "eta_s": _rounded(clock.eta(step, total_steps)),
            }
            for name in ("grad_norm", "epoch"):  # the trainer's own figures, null when not logged
                if name in logs and logs[name] is not None:
                    fields[name] = float(logs[name])
            for name, key in extra.items():
                if key in logs:
                    fields[name] = float(logs[key])
            writer.write(**fields)
            if step % every == 0 or step == total_steps:
                print(
                    f"step {step}/{total_steps} loss {fields['loss']:.4f} "
                    f"elapsed {fields['elapsed_s']:.0f}s eta {fields['eta_s'] or 0:.0f}s",
                    flush=True,
                )

        def on_step_end(self, args, state, control, model=None, **kwargs):
            step = state.global_step
            if dev_eval is None or not eval_every or step % eval_every or step >= total_steps:
                return
            clock.peak_gpu_memory_gb = max(clock.peak_gpu_memory_gb, gpu_peak_gb())
            target = model if model is not None else kwargs.get("model")
            t0 = time.monotonic()
            accuracy = dev_eval(target)
            clock.eval_seconds += time.monotonic() - t0
            clock.dev_scores.append((step, accuracy))
            writer.write(
                step=step,
                total_steps=total_steps,
                elapsed_s=round(clock.elapsed(), 3),
                eta_s=_rounded(clock.eta(step, total_steps)),
                dev_accuracy=accuracy,
            )
            print(f"step {step}/{total_steps} dev accuracy {accuracy:.4f}", flush=True)

    return MetricsCallback()


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(value, 3)
