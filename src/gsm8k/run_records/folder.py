"""The run folder ``outputs/<run_id>/`` (contract C2): config, predictions, timings and status.

JSON files are written atomically (temp file in the same folder, then rename); predictions are
appended one whole line at a time (BR5.4).
"""

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from gsm8k.run_config import RunConfig, to_dict

SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def atomic_write_text(path: Path, text: str) -> None:
    """Write text to a temp file next to path and rename it into place; never a half-written file."""
    path = Path(path)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def _write_json(path: Path, data: dict) -> None:
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def write_config(run_dir: Path, cfg: RunConfig) -> None:
    _write_json(Path(run_dir) / "config.json", to_dict(cfg))


def append_prediction(run_dir: Path, record: dict) -> None:
    """Append one prediction (problem_id, output, predicted, gold, correct) as one JSON line."""
    line = json.dumps(record, ensure_ascii=False) + "\n"
    fd = os.open(Path(run_dir) / "predictions.jsonl", os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)


def write_timings(
    run_dir: Path,
    *,
    seconds_per_problem: float | None,
    seconds_per_step: float | None = None,
    peak_gpu_memory_gb: float,
) -> None:
    _write_json(
        Path(run_dir) / "timings.json",
        {
            "v": SCHEMA_VERSION,
            "seconds_per_step": seconds_per_step,
            "seconds_per_problem": seconds_per_problem,
            "peak_gpu_memory_gb": peak_gpu_memory_gb,
        },
    )


def write_status(run_dir: Path, *, run_id: str, status: str, exit_code: int, reason: str | None) -> None:
    _write_json(
        Path(run_dir) / "status.json",
        {
            "v": SCHEMA_VERSION,
            "run_id": run_id,
            "status": status,
            "exit_code": exit_code,
            "reason": reason,
            "ended_at": utc_now(),
        },
    )


def run_already_happened(run_dir: Path) -> bool:
    """True when the folder holds a status.json or predictions.jsonl (BR5.3); a launcher's
    config.json alone does not count (BR4.8)."""
    run_dir = Path(run_dir)
    return (run_dir / "status.json").exists() or (run_dir / "predictions.jsonl").exists()
