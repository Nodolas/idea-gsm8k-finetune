"""Duration estimates for planned runs, from measured times (US2.3, FR2.6, FR1.7; ADR-007).

A measurement is the ``timings.json`` (contract C2) of an earlier run folder ``outputs/<run_id>/``
whose ``config.json`` names the model. The newest such file (by modification time) that holds the
needed value wins; a newer file without the value does not hide an older one. Entries of outputs/
that are not run folders (``run.lock``, ``queue/``, folders without both files) are skipped.
Importing this module stays light.
"""

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gsm8k.run_records.paths import outputs_root

CAP_SECONDS = 3 * 3600
NO_ESTIMATE = "No estimate yet"
OVER_CAP = "Estimated time is above the 3-hour cap"


@dataclass(frozen=True)
class Estimate:
    """A planned run's estimated duration; ``seconds`` is None when nothing was measured yet."""

    seconds: float | None
    text: str
    over_cap: bool


def _positive_number(value: Any) -> bool:
    return (
        isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value) and value > 0
    )


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _newest_measurement(model: str, key: str, outputs: Path | None) -> float | None:
    """The value ``key`` from the newest timings.json of a run folder for ``model``, or None."""
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
        timings = _read_json(timings_path)
        if not isinstance(timings, dict) or not _positive_number(timings.get(key)):
            continue
        try:
            mtime = timings_path.stat().st_mtime
        except OSError:
            continue
        candidate = (mtime, folder.name, float(timings[key]))
        if best is None or candidate[:2] > best[:2]:
            best = candidate
    return None if best is None else best[2]


def measured_seconds_per_step(model: str, outputs: Path | None = None) -> float | None:
    """Seconds per training step from the newest measurement for ``model``, or None."""
    return _newest_measurement(model, "seconds_per_step", outputs)


def measured_seconds_per_problem(model: str, outputs: Path | None = None) -> float | None:
    """Seconds per evaluated problem from the newest measurement for ``model``, or None."""
    return _newest_measurement(model, "seconds_per_problem", outputs)


def format_duration(seconds: float) -> str:
    """A short human duration: ``45 s``, ``12 min``, ``2 h 05 min``."""
    total = int(round(seconds))
    if total < 60:
        return f"{total} s"
    minutes = int(round(seconds / 60))
    if minutes < 60:
        return f"{minutes} min"
    hours, rest = divmod(minutes, 60)
    return f"{hours} h {rest:02d} min"


def _estimate(count: int, per_unit: float | None, what: str) -> Estimate:
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError(f"{what} must be a whole number of at least 0, got {count!r}")
    if per_unit is None:
        return Estimate(seconds=None, text=NO_ESTIMATE, over_cap=False)
    seconds = count * per_unit
    if seconds > CAP_SECONDS:
        return Estimate(seconds=seconds, text=f"{OVER_CAP} (about {format_duration(seconds)})", over_cap=True)
    return Estimate(seconds=seconds, text=f"Estimated time: about {format_duration(seconds)}", over_cap=False)


def estimate_training(model: str, total_steps: int, outputs: Path | None = None) -> Estimate:
    """Total steps times the measured seconds per step for ``model`` (AC2.3.1, AC2.3.3, AC2.3.4)."""
    return _estimate(total_steps, measured_seconds_per_step(model, outputs), "total_steps")


def estimate_evaluation(model: str, n_problems: int, outputs: Path | None = None) -> Estimate:
    """Problems times the measured seconds per problem for ``model`` (AC2.3.2, AC2.3.3, AC2.3.4)."""
    return _estimate(n_problems, measured_seconds_per_problem(model, outputs), "n_problems")
