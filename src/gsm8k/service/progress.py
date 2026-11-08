"""Evaluation progress of a running run (u4-run-service, AC3.1.6, contract C6 ``Status.evaluation``).

A run scores its split one problem at a time and appends one line per scored problem to
``outputs/<run_id>/predictions.jsonl``. The progress is ``{split, scored, total}``: ``scored`` is the number
of complete lines (ending in a newline, so a line still being written does not count), ``total`` the split's
size or the run's ``limit`` when that is smaller. The file is only counted, never parsed, and read as bytes
in chunks, so a growing file costs one pass and no JSON work. Reading never raises: any problem gives None.
"""

from __future__ import annotations

import json
from pathlib import Path

from gsm8k.run_control.launch import SPLIT_SIZES

PREDICTIONS_FILE = "predictions.jsonl"
CONFIG_FILE = "config.json"
_CHUNK_BYTES = 1 << 20


def evaluation_progress(outputs: Path, run_id: str) -> dict | None:
    """``{"split", "scored", "total"}`` for ``run_id``, or None when it cannot be told.

    None when there is no predictions file, config.json is missing, unreadable or not an object, the split
    has no known size, or any read fails (OSError, ValueError, UnicodeError).
    """
    folder = Path(outputs) / run_id
    try:
        predictions = folder / PREDICTIONS_FILE
        if not predictions.exists():
            return None
        config = json.loads((folder / CONFIG_FILE).read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            return None
        split = config.get("split")
        if not isinstance(split, str) or split not in SPLIT_SIZES:
            return None
        total = SPLIT_SIZES[split]
        limit = config.get("limit")
        if isinstance(limit, int) and not isinstance(limit, bool) and 1 <= limit < total:
            total = limit
        scored = _complete_lines(predictions)
    except (OSError, ValueError, UnicodeError):
        return None
    return {"split": split, "scored": min(scored, total), "total": total}


def _complete_lines(path: Path) -> int:
    """The number of newline bytes in ``path``: its complete lines, without decoding or parsing them."""
    count = 0
    with path.open("rb") as f:
        while chunk := f.read(_CHUNK_BYTES):
            count += chunk.count(b"\n")
    return count
