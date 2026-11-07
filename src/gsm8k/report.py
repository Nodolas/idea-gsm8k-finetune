"""ResultsReport: ``gsm8k report`` builds the generated part of results.md (US6.2, FR6.1, contract C1).

``build_report(rows, skipped)`` returns the generated block: the baseline and best test accuracy of
the chosen model with the gain and its noise label (AC6.2.2), the generalisation rows (reported only,
no pass or fail), the lm-evaluation-harness rows as a cross-check that never enters the gain
(AC6.2.3), and the run table with one line per run-log row in file order plus a skipped-rows note
(AC6.2.1).

``gsm8k report [--results PATH] [--out PATH]`` reads the run log (default ``results/runs.csv``) and
writes the block between ``<!-- BEGIN GENERATED -->`` and ``<!-- END GENERATED -->`` of results.md
(default ``ROOT/results.md``), keeping every hand-written line outside the markers. A missing
results.md is created with the block and the empty hand-written sections "What moved the number and
why" and "What to try next". The file is written atomically (a temp file in the same folder, then a
rename), so a failure leaves results.md as it was. No lock, no run id.

Gain and noise (construction/batch-4.md, Settled details): the chosen model is the model of the latest
``best`` ``gsm8k-test``/``accuracy`` row; its baseline is that model's latest ``base``
``gsm8k-test``/``accuracy`` row with an empty ``adapter_run``. The gain in points is
``round((best - baseline) * 100, 1)``, signed; the label follows that rounded gain: under 3.0 points
is "within noise", otherwise "outside noise". Missing either row: "No final test score yet".
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from gsm8k._env import ROOT
from gsm8k.cli import EXIT_FAILED, EXIT_FINISHED
from gsm8k.run_records import paths
from gsm8k.run_records.log import COLUMNS, RunRow, read_rows

RESULTS_MD_DEFAULT: Path = ROOT / "results.md"

BEGIN = "<!-- BEGIN GENERATED -->"
END = "<!-- END GENERATED -->"

TEST_DATA = "gsm8k-test"
TEST_METRIC = "accuracy"
HARNESS_DATA = "gsm8k-test-harness"
GENERALISATION_DATA = ("gsmplus-testmini", "gsmsym-p1")

NOISE_POINTS = 3.0
NO_SCORE = "No final test score yet"

HARNESS_HEADING = "Cross-check (lm-evaluation-harness), not used for the gain"
GENERALISATION_HEADING = "Generalisation (GSM-Plus testmini, GSM-Symbolic p1): reported only, no pass or fail"

TITLE = "# GSM8K fine-tuning results"
HAND_SECTIONS = ("What moved the number and why", "What to try next")


class ReportError(Exception):
    """results.md could not be read or written; the message names the file."""


@dataclass
class FinalScore:
    model: str
    baseline: RunRow
    best: RunRow
    points: float
    label: str


def _latest(rows: list[RunRow], keep) -> RunRow | None:
    """The row with the latest date among those ``keep`` accepts; equal dates go to the later row."""
    found: tuple[str, int, RunRow] | None = None
    for index, row in enumerate(rows):
        if not keep(row):
            continue
        key = (row.date, index)
        if found is None or key > found[:2]:
            found = (row.date, index, row)
    return found[2] if found else None


def gain_points(baseline: float, best: float) -> float:
    """The gain in points, rounded to one decimal (never -0.0)."""
    points = round((best - baseline) * 100, 1)
    return 0.0 if points == 0 else points


def noise_label(points: float) -> str:
    return "within noise" if abs(points) < NOISE_POINTS else "outside noise"


def final_score(rows: list[RunRow]) -> FinalScore | None:
    """The chosen model's baseline and best test rows, the gain and its label; None when either is
    missing. Harness and generalisation rows never count (other data)."""
    best = _latest(
        rows,
        lambda r: r.method == "best" and r.data == TEST_DATA and r.metric == TEST_METRIC,
    )
    if best is None:
        return None
    baseline = _latest(
        rows,
        lambda r: (
            r.model == best.model
            and r.method == "base"
            and r.data == TEST_DATA
            and r.metric == TEST_METRIC
            and not r.adapter_run
        ),
    )
    if baseline is None:
        return None
    points = gain_points(baseline.value, best.value)
    return FinalScore(
        model=best.model, baseline=baseline, best=best, points=points, label=noise_label(points)
    )


def _cell(text: str) -> str:
    text = str(text).replace("\r", " ").replace("\n", " ").replace("|", "\\|")
    return text if text else "—"


def _table(header: tuple[str, ...], lines: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(_cell(c) for c in line) + " |" for line in lines]
    return out


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _signed(points: float) -> str:
    return f"{points:+.1f}"


def _final_section(rows: list[RunRow]) -> list[str]:
    out = ["## Final test score", ""]
    score = final_score(rows)
    if score is None:
        out.append(
            f"{NO_SCORE}: it needs a `best` and a `base` `{TEST_DATA}` accuracy row of the same model "
            "(the base row without an adapter run)."
        )
        return out
    out += _table(
        ("Score", "Model", "Run", "Adapter run", "Test accuracy", "Value", "Date"),
        [
            [
                name,
                row.model,
                row.run_id,
                row.adapter_run,
                _pct(row.value),
                f"{row.value:.4f}",
                row.date,
            ]
            for name, row in (("Baseline", score.baseline), ("Best", score.best))
        ],
    )
    # The gain line carries the only signed number next to a noise label; the model name (which holds
    # "-1.7B" or "-0.6B") stays on its own line.
    out += [
        "",
        f"Chosen model: {score.model}, the model of the latest `best` test row.",
        "",
        f"**Gain: {_signed(score.points)} points, {score.label}.**",
        "",
        "Noise rule (FR6.1): on 1,319 test problems the 95% interval is about 2.5 points either way, "
        f"so a gain under {NOISE_POINTS:.1f} points (rounded to one decimal) counts as noise.",
    ]
    return out


def _side_table(rows: list[RunRow], heading: str, keep, empty: str) -> list[str]:
    out = [f"## {heading}", ""]
    chosen = [row for row in rows if keep(row)]
    if not chosen:
        out.append(empty)
        return out
    out += _table(
        ("Model", "Method", "Data", "Metric", "Run", "Adapter run", "Value", "Date"),
        [
            [
                row.model,
                row.method,
                row.data,
                row.metric,
                row.run_id,
                row.adapter_run,
                f"{row.value:.4f}",
                row.date,
            ]
            for row in chosen
        ],
    )
    return out


def _run_table(rows: list[RunRow], skipped: int) -> list[str]:
    out = ["## Run table", "", "Every row of the run log, in file order (contract C1 columns).", ""]
    if rows:
        out += _table(
            COLUMNS,
            [
                [
                    row.date,
                    row.run_id,
                    row.model,
                    row.method,
                    row.data,
                    row.metric,
                    f"{float(row.value):.4f}",
                    f"{float(row.minutes):.1f}",
                    row.config_hash,
                    row.adapter_run,
                ]
                for row in rows
            ],
        )
    else:
        out.append("The run log has no rows yet.")
    out += ["", f"Rows skipped as malformed: {skipped}."]
    return out


def build_report(rows: list[RunRow], skipped: int) -> str:
    """The generated block of results.md (without the markers). Same rows, same text."""
    lines = ["_Generated by `gsm8k report` from the run log; edits between the markers are replaced._", ""]
    lines += _final_section(rows)
    lines.append("")
    lines += _side_table(
        rows,
        GENERALISATION_HEADING,
        lambda r: r.data in GENERALISATION_DATA,
        "No generalisation rows yet.",
    )
    lines.append("")
    lines += _side_table(
        rows,
        HARNESS_HEADING,
        lambda r: r.data == HARNESS_DATA,
        "No harness rows yet.",
    )
    lines.append("")
    lines += _run_table(rows, skipped)
    return "\n".join(lines) + "\n"


def _generated_section(block: str) -> str:
    return f"{BEGIN}\n{block.strip()}\n{END}"


def new_results_md(block: str) -> str:
    """A fresh results.md: the title, the generated block and the empty hand-written sections."""
    parts = [TITLE, "", _generated_section(block), ""]
    for heading in HAND_SECTIONS:
        parts += [f"## {heading}", ""]
    return "\n".join(parts)


def merge_results_md(existing: str, block: str, path: Path) -> str:
    """Replace only the text between the markers; text without markers gets the block appended."""
    begins, ends = existing.count(BEGIN), existing.count(END)
    if begins == 0 and ends == 0:
        sep = (
            "" if existing.endswith("\n\n") or not existing else ("\n" if existing.endswith("\n") else "\n\n")
        )
        return existing + sep + _generated_section(block) + "\n"
    start, stop = existing.find(BEGIN), existing.find(END)
    if begins != 1 or ends != 1 or stop < start:
        raise ReportError(
            f"results.md has broken markers, nothing written: {path} "
            f"(needs one {BEGIN} before one {END}; found {begins} and {ends})"
        )
    return existing[:start] + _generated_section(block) + existing[stop + len(END) :]


def _read_existing(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as exc:
        raise ReportError(f"results.md could not be read: {path} ({exc})") from exc


def _write_atomic(path: Path, text: str) -> None:
    tmp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as f:
            tmp_name = f.name
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        if path.exists():
            os.chmod(tmp_name, path.stat().st_mode & 0o777)
        else:
            os.chmod(tmp_name, 0o644)
        os.replace(tmp_name, path)
        tmp_name = None
    except OSError as exc:
        raise ReportError(f"results.md could not be written: {path} ({exc})") from exc
    finally:
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def write_report(results: Path, out: Path) -> tuple[int, int]:
    """Read the run log and write results.md; returns (rows, skipped). Raises OSError (run log) or
    ReportError (results.md), in both cases before results.md changes."""
    rows, skipped = read_rows(results)
    block = build_report(rows, skipped)
    existing = _read_existing(out)
    text = new_results_md(block) if existing is None else merge_results_md(existing, block, out)
    if text != existing:
        _write_atomic(out, text)
    return len(rows), skipped


def run_report(args: argparse.Namespace) -> int:
    results = Path(args.results) if args.results is not None else paths.DEFAULT_RESULTS
    out = Path(args.out) if args.out is not None else RESULTS_MD_DEFAULT
    try:
        count, skipped = write_report(results, out)
    except (OSError, ReportError) as exc:
        print(f"Report stopped, {out} unchanged: {exc}", file=sys.stderr)
        return EXIT_FAILED
    if skipped:
        print(f"Skipped {skipped} malformed row(s) in {results}", file=sys.stderr)
    print(f"Wrote the generated part of {out} from {count} row(s) of {results}")
    return EXIT_FINISHED


def register(subparsers) -> None:
    parser = subparsers.add_parser(
        "report",
        help="build the generated part of results.md from the run log",
        description=(
            "Write the run table, the final test score with its gain and noise label, the generalisation "
            "rows and the lm-evaluation-harness cross-check between the GENERATED markers of results.md. "
            "Text outside the markers is kept."
        ),
    )
    parser.add_argument("--results", type=Path, help="run log to read (default results/runs.csv)")
    parser.add_argument("--out", type=Path, help="results file to write (default results.md)")
    parser.set_defaults(func=run_report)
