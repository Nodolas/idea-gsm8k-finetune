"""GRPO step plan (AC7.1.4): size the step count so the estimated time fits a budget.

Seconds per step come from saved timings of earlier runs of the model (``gsm8k.estimates``): a GRPO
run's own ``seconds_per_step``, else evaluation ``seconds_per_problem`` times the generations per step
plus an update time, else a stated fallback (``measured`` False). No torch import.
"""

import json
import math
from pathlib import Path
from typing import NamedTuple

from gsm8k.estimates import CAP_SECONDS, measured_seconds_per_problem
from gsm8k.run_records.paths import outputs_root

UPDATE_SECONDS = 10.0
FALLBACK_SECONDS_PER_STEP = 60.0
# The closing dev score every GRPO run ends with (AC7.1.4): 496 dev problems, at the model's saved
# seconds per problem, else this stated fallback.
DEV_SCORED_PROBLEMS = 496
FALLBACK_SECONDS_PER_PROBLEM = 3.0


class GrpoPlan(NamedTuple):
    steps: int
    estimate_s: float
    flagged: bool
    measured: bool


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _grpo_seconds_per_step(model: str, outputs: Path | None) -> float | None:
    """Newest ``seconds_per_step`` (by timings.json mtime) of a GRPO or method-less run of ``model``."""
    root = Path(outputs) if outputs is not None else outputs_root()
    if not root.is_dir():
        return None
    best: tuple[float, str, float] | None = None
    for folder in root.iterdir():
        timings_path = folder / "timings.json"
        config_path = folder / "config.json"
        if not folder.is_dir() or not timings_path.is_file() or not config_path.is_file():
            continue
        config = _read_json(config_path)
        if not isinstance(config, dict) or config.get("model") != model:
            continue
        if config.get("method") not in (None, "grpo"):
            continue
        timings = _read_json(timings_path)
        value = timings.get("seconds_per_step") if isinstance(timings, dict) else None
        if isinstance(value, bool) or not isinstance(value, int | float) or not 0 < value < math.inf:
            continue
        try:
            candidate = (timings_path.stat().st_mtime, folder.name, float(value))
        except OSError:
            continue
        if best is None or candidate[:2] > best[:2]:
            best = candidate
    return None if best is None else best[2]


def _seconds_per_step(model: str, generations: int, outputs: Path | None) -> tuple[float, bool]:
    per_step = _grpo_seconds_per_step(model, outputs)
    if per_step is not None:
        return per_step, True
    per_problem = measured_seconds_per_problem(model, outputs)
    if per_problem is not None:
        return per_problem * max(generations, 1) * 2 + UPDATE_SECONDS, True
    return FALLBACK_SECONDS_PER_STEP, False


def closing_dev_reserve_s(model: str, outputs: Path | None = None) -> float:
    """Seconds to keep free inside the cap for scoring the dev split after training."""
    per_problem = measured_seconds_per_problem(model, outputs)
    return DEV_SCORED_PROBLEMS * (per_problem if per_problem is not None else FALLBACK_SECONDS_PER_PROBLEM)


def plan_grpo_steps(
    model: str, generations: int, outputs: Path | None = None, budget_s: float = CAP_SECONDS
) -> GrpoPlan:
    """The most steps (at least 1) whose estimated time stays within ``budget_s``."""
    per_step, measured = _seconds_per_step(model, generations, outputs)
    steps = max(1, math.floor(budget_s / per_step))
    return GrpoPlan(steps, steps * per_step, steps * per_step > budget_s, measured)


def check_grpo_steps(
    requested: int, model: str, generations: int, outputs: Path | None = None, budget_s: float = CAP_SECONDS
) -> GrpoPlan:
    """The estimate for ``requested`` steps, flagged when it is over ``budget_s``."""
    per_step, measured = _seconds_per_step(model, generations, outputs)
    estimate = requested * per_step
    return GrpoPlan(requested, estimate, estimate > budget_s, measured)
