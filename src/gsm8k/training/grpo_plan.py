"""GRPO step plan (AC7.1.4): size the step count so the estimated time fits a budget.

Seconds per step come from saved timings of earlier runs of the model (``gsm8k.estimates``): a GRPO
run's own ``seconds_per_step``, else evaluation ``seconds_per_problem`` times the generations per step
plus an update time, else a stated fallback (``measured`` False). No torch import.
"""

import math
from pathlib import Path
from typing import NamedTuple

from gsm8k.estimates import CAP_SECONDS, measured_seconds_per_problem, measured_seconds_per_step

UPDATE_SECONDS = 5.0
FALLBACK_SECONDS_PER_STEP = 60.0


class GrpoPlan(NamedTuple):
    steps: int
    estimate_s: float
    flagged: bool
    measured: bool


def _seconds_per_step(model: str, generations: int, outputs: Path | None) -> tuple[float, bool]:
    per_step = measured_seconds_per_step(model, outputs)
    if per_step is not None:
        return per_step, True
    per_problem = measured_seconds_per_problem(model, outputs)
    if per_problem is not None:
        return per_problem * max(generations, 1) + UPDATE_SECONDS, True
    return FALLBACK_SECONDS_PER_STEP, False


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
