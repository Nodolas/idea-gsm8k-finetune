"""Course run configurations, time estimates and attempt ids (US12.1; AC12.1.2, AC12.4.4; contract C9).

A course run is the run configuration defaults plus the changes of its Course Runs row, the first 100 scored
dev problems and seed 42. Building a configuration reads files and writes none. Importing this module stays
light: no torch, transformers, peft or bitsandbytes, and no environment change.
"""

from __future__ import annotations

import csv
import math
import re
from pathlib import Path

from gsm8k import estimates
from gsm8k.course.steps import COURSE_RUNS, CourseRunSpec, course_dir, model_revision
from gsm8k.run_config import RunConfig
from gsm8k.run_records.paths import checkpoints_root

LOAD_SECONDS = 30
COURSE_PROBLEMS = 100
GRPO_UPDATE_SECONDS = 6  # per step: the policy update and the reward pass (Course Timing)
QUANTIZED_STEP_FACTOR = 1.5
# Fallback seconds per scored problem and per training step (batch size 4), from the Course Timing table.
FALLBACK_SECONDS_PER_PROBLEM = {
    "EleutherAI/pythia-31m": 0.3,
    "HuggingFaceTB/SmolLM2-360M": 0.8,
    "Qwen/Qwen2.5-0.5B": 1.0,
    "Qwen/Qwen3-0.6B-Base": 1.2,
    "Qwen/Qwen3-1.7B-Base": 3.0,
}
FALLBACK_SECONDS_PER_STEP = {"Qwen/Qwen3-0.6B-Base": 0.5}

_COURSE_ID = re.compile(r"^course-(c[0-9]{2})-([a-z0-9-]+)-([1-9][0-9]*)$")
_C21_ID = re.compile(r"^course-c21-sft-([1-9][0-9]*)$")


class CourseRunRefused(Exception):
    """A course run cannot be built now; the message says what to do."""


def _spec(step: str, run: str) -> CourseRunSpec:
    for spec in COURSE_RUNS:
        if spec.step == step and spec.run == run:
            return spec
    raise ValueError(f"Unknown course run: {step} {run}")


def _course_rows(outputs: Path) -> list[str]:
    """The run ids of outputs/course/runs.csv (an unreadable or missing file reads as no rows)."""
    path = course_dir(Path(outputs)) / "runs.csv"
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            return [row.get("run_id", "") for row in csv.DictReader(handle)]
    except (OSError, csv.Error, UnicodeDecodeError):
        return []


def _latest_c21(outputs: Path) -> int | None:
    numbers = [int(m.group(1)) for run_id in _course_rows(outputs) if (m := _C21_ID.match(run_id))]
    return max(numbers) if numbers else None


def course_config(
    step: str,
    run: str,
    attempt_id: str,
    outputs: Path,
    *,
    cot_data_run: str | None = None,
    checkpoints: Path | None = None,
) -> RunConfig:
    """The C2 configuration of a course run (defaults plus the run's changes, dev split, limit 100, seed 42).

    c22 ``selfcot`` takes the ``cotgen`` attempt id queued with it as ``cot_data_run``; c23 ``grpo`` starts
    from the latest finished c21 adapter, or from the base model when there is none, and raises
    ``CourseRunRefused`` when that adapter's folder is missing.
    """
    spec = _spec(step, run)
    fields: dict = {"split": "dev", "limit": COURSE_PROBLEMS, "seed": 42}
    fields.update(spec.changes)
    fields["model_revision"] = model_revision(spec.model)
    if (step, run) == ("c22", "selfcot"):
        if not cot_data_run:
            raise ValueError("The selfcot run needs the attempt id of the cotgen run queued with it")
        fields["cot_data_run"] = cot_data_run
    if (step, run) == ("c23", "grpo"):
        number = _latest_c21(Path(outputs))
        if number is not None:
            root = Path(checkpoints) if checkpoints is not None else checkpoints_root()
            folder = root / f"course-c21-sft-{number}"
            if not folder.is_dir():
                raise CourseRunRefused("Run step c21 again: its adapter is missing")
            fields["adapter_path"] = str(folder)
    return RunConfig(run_id=attempt_id, **fields)


def _per_problem(model: str, outputs: Path) -> tuple[float, bool]:
    measured = estimates.measured_seconds_per_problem(model, outputs)
    if measured is not None:
        return measured, True
    return FALLBACK_SECONDS_PER_PROBLEM[model], False


def _per_step(model: str, outputs: Path) -> tuple[float, bool]:
    measured = estimates.measured_seconds_per_step(model, outputs)
    if measured is not None:
        return measured, True
    return FALLBACK_SECONDS_PER_STEP[model], False


def estimate_minutes(step: str, run: str, outputs: Path) -> tuple[int, bool]:
    """(minutes, measured) by the Course Timing rule: ceil((30 s load + work seconds) / 60).

    Saved timings of the same model are used when there are any; the estimate is ``measured`` only when
    every per-unit time it used was saved, otherwise the fallback timings were used and it is unmeasured.
    """
    spec = _spec(step, run)
    outputs = Path(outputs)
    model = spec.model
    method = spec.changes["method"]
    batch_size = RunConfig(run_id="x").batch_size
    measured = True

    def problem() -> float:
        nonlocal measured
        seconds, ok = _per_problem(model, outputs)
        measured = measured and ok
        return seconds

    def train_step() -> float:
        nonlocal measured
        seconds, ok = _per_step(model, outputs)
        measured = measured and ok
        return seconds

    if method == "base":
        work = COURSE_PROBLEMS * problem()
    elif method == "cotgen":
        work = spec.changes["cot_problems"] * spec.changes["cot_samples"] * problem()
    elif method == "sft":
        factor = QUANTIZED_STEP_FACTOR if spec.changes.get("quantize") == "4bit" else 1.0
        steps = math.ceil(spec.changes["train_examples"] / batch_size)
        work = steps * train_step() * factor + COURSE_PROBLEMS * problem()
    elif method == "selfcot":
        steps = math.ceil(spec.changes["train_examples"] / batch_size)
        work = steps * train_step() + COURSE_PROBLEMS * problem()
    elif method == "grpo":
        generations = spec.changes["grpo_generations"]
        work = spec.changes["grpo_steps"] * (generations * problem() + GRPO_UPDATE_SECONDS)
        work += COURSE_PROBLEMS * problem()
    else:  # pragma: no cover - every method of the table is handled
        raise ValueError(f"No estimate for method {method!r}")
    return math.ceil((LOAD_SECONDS + work) / 60 - 1e-9), measured


def _used_numbers(step: str, run: str, outputs: Path) -> list[int]:
    """Every attempt number already taken for the step and run: rows, run folders and queue entries."""
    outputs = Path(outputs)
    prefix = f"course-{step}-{run}-"
    names: list[str] = list(_course_rows(outputs))
    try:
        names += [p.name for p in outputs.iterdir() if p.is_dir()]
    except OSError:
        pass
    queue = outputs / "queue"
    try:
        for entry in queue.glob("*.json"):
            _, _, attempt_id = entry.stem.partition("-")  # <pos:03d>-<attempt id>
            names.append(attempt_id)
    except OSError:
        pass
    numbers = []
    for name in names:
        match = _COURSE_ID.match(name)
        if match and name.startswith(prefix) and name[len(prefix) :] == match.group(3):
            numbers.append(int(match.group(3)))
    return numbers


def next_attempt_id(step: str, run: str, outputs: Path) -> str:
    """``course-<step>-<run>-<n>``, one more than the highest n among rows, run folders and queue entries."""
    _spec(step, run)
    numbers = _used_numbers(step, run, outputs)
    return f"course-{step}-{run}-{max(numbers, default=0) + 1}"
