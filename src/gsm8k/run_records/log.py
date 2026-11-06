"""The run log ``results/runs.csv`` (contract C1).

One row per scored run, appended one whole line at a time.
"""

import csv
import fcntl
import io
import math
import os
from dataclasses import dataclass
from pathlib import Path

COLUMNS = (
    "date",
    "run_id",
    "model",
    "method",
    "data",
    "metric",
    "value",
    "minutes",
    "config_hash",
    "adapter_run",
)

MODELS = ("Qwen/Qwen3-0.6B-Base", "Qwen/Qwen3-1.7B-Base")
METHODS = ("base", "sft", "grpo", "best", "terse", "vote", "calc", "optuna")
DATA = ("gsm8k-dev", "gsm8k-test", "gsm8k-test-harness", "gsmplus-testmini", "gsmsym-p1")
METRICS = ("accuracy", "harness_flexible_accuracy")


@dataclass
class RunRow:
    date: str
    run_id: str
    model: str
    method: str
    data: str
    metric: str
    value: float
    minutes: float
    config_hash: str
    adapter_run: str = ""


def _csv_line(cells: list[str]) -> str:
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerow(cells)
    return buffer.getvalue()


def _cells(row: RunRow) -> list[str]:
    return [
        row.date,
        row.run_id,
        row.model,
        row.method,
        row.data,
        row.metric,
        f"{float(row.value):.4f}",
        f"{float(row.minutes):.1f}",
        row.config_hash,
        row.adapter_run or "",
    ]


def append_row(path: Path, row: RunRow) -> None:
    """Append one row; a new or empty file gets the header first. Each append is one write call."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = _csv_line(_cells(row))
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            text = line
            if os.fstat(fd).st_size == 0:
                text = _csv_line(list(COLUMNS)) + line
            os.write(fd, text.encode("utf-8"))
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _parse(record: dict[str, str]) -> RunRow | None:
    if record["model"] not in MODELS or record["method"] not in METHODS:
        return None
    if record["data"] not in DATA or record["metric"] not in METRICS:
        return None
    try:
        value = float(record["value"])
        minutes = float(record["minutes"])
    except ValueError:
        return None
    if not (math.isfinite(value) and math.isfinite(minutes)) or not record["run_id"]:
        return None
    return RunRow(
        date=record["date"],
        run_id=record["run_id"],
        model=record["model"],
        method=record["method"],
        data=record["data"],
        metric=record["metric"],
        value=value,
        minutes=minutes,
        config_hash=record["config_hash"],
        adapter_run=record["adapter_run"],
    )


def read_rows(path: Path) -> tuple[list[RunRow], int]:
    """All valid rows and the number of skipped malformed rows (C1 rules).

    A missing file is an empty log; an unreadable file raises OSError naming the file.
    """
    path = Path(path)
    try:
        with path.open(newline="", encoding="utf-8") as f:
            lines = list(csv.reader(f))
    except FileNotFoundError:
        return [], 0
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise OSError(f"Run log could not be read: {path} ({exc})") from exc
    lines = [line for line in lines if line]
    if not lines:
        return [], 0
    header, body = lines[0], lines[1:]
    rows: list[RunRow] = []
    skipped = 0
    for line in body:
        if len(line) != len(header):
            skipped += 1
            continue
        named = dict(zip(header, line, strict=True))
        record = {column: named.get(column, "") for column in COLUMNS}
        row = _parse(record)
        if row is None:
            skipped += 1
        else:
            rows.append(row)
    return rows, skipped


def has_run_id(path: Path, run_id: str) -> bool:
    rows, _ = read_rows(path)
    return any(row.run_id == run_id for row in rows)
