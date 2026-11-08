"""The NVIDIA GPU's live figures for the training page (contract C6 ``GET /gpu``, schema ``Gpu``, US4.5).

``read_gpu`` asks ``nvidia-smi`` for one CSV line (the first GPU) and turns it into the C6 ``Gpu``
object. It never raises: a missing, slow or failing ``nvidia-smi``, or output that does not parse,
gives ``available`` false with a ``reason`` and every figure null, so the route can always answer 200.
A figure ``nvidia-smi`` prints as ``[N/A]``, ``N/A`` or ``[Not Supported]`` is null.

The service never imports training code and never calls CUDA (ADR-006): only the ``nvidia-smi``
program is run, through ``subprocess`` (the ``run`` argument is the seam a test replaces).
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from typing import Any

QUERY_FIELDS = (
    "name",
    "utilization.gpu",
    "memory.used",
    "memory.total",
    "temperature.gpu",
    "power.draw",
    "power.limit",
    "clocks.sm",
    "clocks.max.sm",
)
COMMAND = [
    "nvidia-smi",
    "--query-gpu=" + ",".join(QUERY_FIELDS),
    "--format=csv,noheader,nounits",
]
# The C6 Gpu keys after "available" and "reason", in the order of QUERY_FIELDS.
FIGURE_KEYS = (
    "name",
    "utilization_pct",
    "memory_used_mb",
    "memory_total_mb",
    "temperature_c",
    "power_w",
    "power_limit_w",
    "sm_clock_mhz",
    "sm_clock_max_mhz",
)
NOT_REPORTED = frozenset({"[N/A]", "N/A", "[Not Supported]"})
NOT_FOUND = "nvidia-smi was not found"
UNREADABLE = "nvidia-smi printed output that could not be read"
_NUMBER = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)")


def _unavailable(reason: str) -> dict:
    """A C6 Gpu object for a GPU that could not be read: every figure null."""
    return {"available": False, "reason": reason, **dict.fromkeys(FIGURE_KEYS)}


def _first_line(text: Any) -> str | None:
    """The first line of ``text`` that is not blank, stripped; None when there is none."""
    if not isinstance(text, str):
        return None
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return None


def _parse(stdout: Any) -> dict:
    """The Gpu object for the first non-empty line of nvidia-smi's output, or an unavailable one."""
    line = _first_line(stdout)
    if line is None:
        return _unavailable(UNREADABLE)
    cells = [cell.strip() for cell in line.split(",")]
    if len(cells) != len(FIGURE_KEYS):
        return _unavailable(UNREADABLE)
    figures: dict[str, Any] = {"name": None if cells[0] in NOT_REPORTED or not cells[0] else cells[0]}
    for key, cell in zip(FIGURE_KEYS[1:], cells[1:], strict=True):
        if cell in NOT_REPORTED:
            figures[key] = None
        elif _NUMBER.fullmatch(cell):
            figures[key] = float(cell)
        else:
            return _unavailable(UNREADABLE)
    return {"available": True, "reason": None, **figures}


def read_gpu(run: Callable[..., Any] = subprocess.run, timeout: float = 3.0) -> dict:
    """The C6 ``Gpu`` object read from ``nvidia-smi``; never raises."""
    try:
        result = run(COMMAND, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return _unavailable(NOT_FOUND)
    except subprocess.TimeoutExpired:
        return _unavailable(f"nvidia-smi did not answer within {timeout:g} seconds")
    except Exception as exc:  # PermissionError, OSError, anything else the launch can raise
        detail = str(exc).strip() or type(exc).__name__
        return _unavailable(f"nvidia-smi could not be run: {detail}")
    try:
        code = result.returncode
        if code != 0:
            text = _first_line(result.stderr) or _first_line(result.stdout)
            return _unavailable(text or f"nvidia-smi failed (exit {code})")
        return _parse(result.stdout)
    except Exception:  # a run result of an unexpected shape
        return _unavailable(UNREADABLE)
