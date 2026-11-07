"""ResultsReport of u6-final-and-report (US6.2, FR6.1, contract C1): `gsm8k report` builds results.md.

`gsm8k.report.build_report(rows, skipped) -> str` returns the generated block; `gsm8k report --results
PATH --out PATH` writes it between `<!-- BEGIN GENERATED -->` and `<!-- END GENERATED -->`, keeping
the hand-written text outside the markers (construction/batch-4.md, Part F3; Settled details, Gain and
noise).

Every test uses temp paths only: run logs written with `gsm8k.run_records.log.append_row` under
`tmp_project_dirs`, and a temp results.md. Nothing touches the project's results/runs.csv or
results.md. `gsm8k.report` is imported inside each test, so a missing module fails each test on its
own.

Layout the tests rely on (and nothing more): the run table shows every C1 column of a row on one line
(so a row's config_hash appears on exactly that line); the gain is shown signed with one decimal
(`+3.0`), on the same line as its noise label; that line names only the label that applies.
"""

import re
from pathlib import Path

from gsm8k.run_records.log import RunRow, append_row, read_rows

Q06 = "Qwen/Qwen3-0.6B-Base"
Q17 = "Qwen/Qwen3-1.7B-Base"
BEGIN = "<!-- BEGIN GENERATED -->"
END = "<!-- END GENERATED -->"
NO_SCORE = "No final test score yet"


def _row(n, run_id, model, method, data, value, adapter_run="", metric="accuracy"):
    """Row number n gets a later date than every row before it and a config_hash whose first 12
    characters are unique to it."""
    return RunRow(
        date=f"2026-11-{1 + n // 20:02d}T{n % 20:02d}:30:00Z",
        run_id=run_id,
        model=model,
        method=method,
        data=data,
        metric=metric,
        value=value,
        minutes=10.0 + n,
        config_hash=f"{n + 1:04x}abcdef01" + "0" * 52,
        adapter_run=adapter_run,
    )


def _rows(*specs):
    return [_row(n, *spec) for n, spec in enumerate(specs)]


def _baseline_and_best(base_value, best_value):
    return _rows(
        ("q17-base-dev-1", Q17, "base", "gsm8k-dev", 0.7000),
        ("q17-sft-dev-1", Q17, "sft", "gsm8k-dev", 0.7500),
        ("q17-base-test-1", Q17, "base", "gsm8k-test", base_value),
        ("q17-best-test-1", Q17, "best", "gsm8k-test", best_value, "q17-sft-dev-1"),
    )


def _write_log(path: Path, rows) -> Path:
    for row in rows:
        append_row(path, row)
    return path


def _report_cli(results: Path, out: Path) -> int:
    from gsm8k import cli

    return cli.main(["report", "--results", str(results), "--out", str(out)])


def _generated(text: str) -> str:
    assert text.count(BEGIN) == 1, text
    assert text.count(END) == 1, text
    start = text.index(BEGIN) + len(BEGIN)
    end = text.index(END)
    assert start <= end, text
    return text[start:end]


def _outside(text: str) -> tuple[str, str]:
    return text[: text.index(BEGIN)], text[text.index(END) + len(END) :]


def _table_lines(block: str, rows) -> tuple[list[str], list[int]]:
    """The run table's line for each row, in the order the lines appear in the block."""
    lines = block.splitlines()
    found = []
    for row in rows:
        marker = row.config_hash[:12]
        hits = [i for i, line in enumerate(lines) if marker in line]
        assert len(hits) == 1, f"row {row.run_id}: config_hash on {len(hits)} lines\n{block}"
        found.append(hits[0])
    return [lines[i] for i in found], found


def _labelled_gains(block: str) -> list[str]:
    """Lines that show a signed gain with a noise label."""
    return [line for line in block.splitlines() if "noise" in line and re.search(r"[+\-\u2212]\d+\.\d", line)]


def _gain_line(block: str, signed: str) -> str:
    lines = [line for line in block.splitlines() if signed in line]
    assert lines, f"no line shows the gain {signed}\n{block}"
    return lines[0]


# AC6.2.1 run table, one line per row, written into results.md


def test_AC6_2_1_run_table_has_one_line_per_row_in_file_order():
    from gsm8k import report

    rows = _rows(
        ("q06-base-dev-1", Q06, "base", "gsm8k-dev", 0.4000),
        ("q17-base-dev-1", Q17, "base", "gsm8k-dev", 0.7000),
        ("q06-sft-dev-1", Q06, "sft", "gsm8k-dev", 0.4500),
        ("q17-base-test-1", Q17, "base", "gsm8k-test", 0.6800),
        ("q17-base-harness-1", Q17, "base", "gsm8k-test-harness", 0.6500, "", "harness_flexible_accuracy"),
    )
    # File order is not date order: the run table follows the file.
    rows.insert(1, _row(9, "q06-terse-dev-1", Q06, "terse", "gsm8k-dev", 0.4200))
    block = report.build_report(rows, 0)
    lines, positions = _table_lines(block, rows)
    assert positions == sorted(positions), block
    for row, line in zip(rows, lines, strict=True):
        assert row.run_id in line, line
        assert row.date in line, line
        assert row.data in line, line


def test_AC6_2_1_skipped_rows_are_noted():
    from gsm8k import report

    rows = _rows(("q17-base-dev-1", Q17, "base", "gsm8k-dev", 0.7000))
    block = report.build_report(rows, 2).lower()
    assert "skipped" in block, block
    assert re.search(r"2\D*skipped|skipped\D*2", block), block


def test_AC6_2_1_command_writes_generated_block_with_every_row(tmp_project_dirs, tmp_path):
    from gsm8k import report

    rows = _baseline_and_best(0.6800, 0.7100)
    results = _write_log(tmp_project_dirs.results, rows)
    with results.open("a", encoding="utf-8") as f:  # one malformed row: too few fields
        f.write("2026-11-02T10:00:00Z,q17-broken-dev-1,Qwen/Qwen3-1.7B-Base\n")
    out = tmp_path / "results.md"
    assert _report_cli(results, out) == 0
    text = out.read_text(encoding="utf-8")
    block = _generated(text)
    _table_lines(block, rows)
    assert "q17-broken-dev-1" not in text
    assert re.search(r"1\D*skipped|skipped\D*1", block.lower()), block
    parsed, skipped = read_rows(results)
    assert skipped == 1
    assert report.build_report(parsed, skipped).strip() in text


def test_AC6_2_1_missing_results_md_is_created_with_hand_written_sections(tmp_project_dirs, tmp_path):
    rows = _baseline_and_best(0.6800, 0.7100)
    results = _write_log(tmp_project_dirs.results, rows)
    out = tmp_path / "write-up" / "results.md"
    out.parent.mkdir()
    assert not out.exists()
    assert _report_cli(results, out) == 0
    text = out.read_text(encoding="utf-8")
    _table_lines(_generated(text), rows)
    before, after = _outside(text)
    hand = before + after
    assert "What moved the number and why" in hand, text
    assert "What to try next" in hand, text


def test_AC6_2_1_second_run_keeps_hand_written_text(tmp_project_dirs, tmp_path):
    rows = _baseline_and_best(0.6800, 0.7100)
    results = _write_log(tmp_project_dirs.results, rows)
    out = tmp_path / "results.md"
    head = "# GSM8K results\n\nNico's introduction, written by hand.\n\n"
    tail = (
        "\n\n## What moved the number and why\n\nThe step-by-step targets did it.\n\n"
        "## What to try next\n\nGRPO on the 1.7B model.\n"
    )
    out.write_text(head + BEGIN + "\nstale generated text\n" + END + tail, encoding="utf-8")

    assert _report_cli(results, out) == 0
    first = out.read_text(encoding="utf-8")
    assert "stale generated text" not in first
    assert _outside(first) == (head, tail)
    _table_lines(_generated(first), rows)

    assert _report_cli(results, out) == 0
    assert out.read_text(encoding="utf-8") == first  # same log, same file

    extra = _row(len(rows), "q17-sft-dev-2", Q17, "sft", "gsm8k-dev", 0.7600)
    append_row(results, extra)
    assert _report_cli(results, out) == 0
    third = out.read_text(encoding="utf-8")
    assert _outside(third) == (head, tail)
    _table_lines(_generated(third), [*rows, extra])


def test_AC6_2_1_empty_results_file_gives_empty_table(tmp_project_dirs, tmp_path):
    from gsm8k import report

    results = tmp_project_dirs.results
    results.write_text("", encoding="utf-8")
    out = tmp_path / "results.md"
    assert _report_cli(results, out) == 0
    text = out.read_text(encoding="utf-8")
    block = _generated(text)
    assert "q06-" not in block and "q17-" not in block
    assert NO_SCORE in block
    assert NO_SCORE in report.build_report([], 0)


def test_AC6_2_1_missing_results_file_is_an_empty_log(tmp_project_dirs, tmp_path):
    """C1: no file means an empty log (read_rows returns no rows)."""
    results = tmp_project_dirs.results
    assert not results.exists()
    out = tmp_path / "results.md"
    assert _report_cli(results, out) == 0
    block = _generated(out.read_text(encoding="utf-8"))
    assert "q06-" not in block and "q17-" not in block
    assert NO_SCORE in block
    assert not results.exists()


def test_AC6_2_1_unreadable_results_file_exits_nonzero_and_writes_nothing(tmp_project_dirs, tmp_path, capsys):
    """C1: an unreadable file is an error naming the file; results.md stays as it was."""
    results = tmp_project_dirs.results
    results.mkdir()  # a folder where the file should be: cannot be read as a run log
    out = tmp_path / "results.md"
    original = "# Results\n\n" + BEGIN + "\nold block\n" + END + "\n"
    out.write_text(original, encoding="utf-8")
    code = _report_cli(results, out)
    assert code != 0
    captured = capsys.readouterr()
    assert str(results) in captured.err + captured.out
    assert out.read_text(encoding="utf-8") == original


# AC6.2.2 gain and noise label


def test_AC6_2_2_gain_under_three_points_is_within_noise():
    from gsm8k import report

    block = report.build_report(_baseline_and_best(0.6800, 0.7090), 0)
    line = _gain_line(block, "+2.9")
    assert "within noise" in line, line
    assert "outside noise" not in line, line
    assert NO_SCORE not in block


def test_AC6_2_2_gain_of_three_points_or_more_is_outside_noise():
    """0.7100 - 0.6800 is 2.9999... in floating point; the gain shown is +3.0, and the label follows the
    gain in points to one decimal, so a shown +3.0 is never "within noise"."""
    from gsm8k import report

    block = report.build_report(_baseline_and_best(0.6800, 0.7100), 0)
    line = _gain_line(block, "+3.0")
    assert "outside noise" in line, line
    assert "within noise" not in line, line

    block = report.build_report(_baseline_and_best(0.6000, 0.7240), 0)
    line = _gain_line(block, "+12.4")
    assert "outside noise" in line, line


def test_AC6_2_2_negative_gain_is_signed_and_judged_by_its_size():
    from gsm8k import report

    block = report.build_report(_baseline_and_best(0.7000, 0.6650), 0)
    lines = [line for line in block.splitlines() if re.search(r"[-−]3\.5", line)]
    assert lines, block
    assert "outside noise" in lines[0], lines[0]

    block = report.build_report(_baseline_and_best(0.7000, 0.6900), 0)
    lines = [line for line in block.splitlines() if re.search(r"[-−]1\.0", line)]
    assert lines, block
    assert "within noise" in lines[0], lines[0]


def test_AC6_2_2_baseline_and_best_are_the_chosen_models_latest_test_rows():
    from gsm8k import report

    rows = _rows(
        ("q06-base-test-1", Q06, "base", "gsm8k-test", 0.3000),
        ("q17-base-test-1", Q17, "base", "gsm8k-test", 0.5000),  # older q17 baseline
        ("q17-base-test-2", Q17, "base", "gsm8k-test", 0.6800),  # the baseline
        ("q17-sft-dev-1", Q17, "sft", "gsm8k-dev", 0.7500),
        ("q17-best-test-1", Q17, "best", "gsm8k-test", 0.6900, "q17-sft-dev-1"),  # older best
        ("q06-best-test-1", Q06, "best", "gsm8k-test", 0.4000, "q06-sft-dev-1"),  # older, other model
        ("q17-best-test-2", Q17, "best", "gsm8k-test", 0.7300, "q17-sft-dev-1"),  # the best
        # Later rows that must not count:
        ("q17-base-test-3", Q17, "base", "gsm8k-test", 0.9000, "q17-sft-dev-1"),  # has an adapter_run
        ("q17-base-dev-1", Q17, "base", "gsm8k-dev", 0.7000),  # dev, not test
        ("q06-base-test-2", Q06, "base", "gsm8k-test", 0.3500),  # not the chosen model
        ("q17-best-gsmplus-1", Q17, "best", "gsmplus-testmini", 0.5000, "q17-sft-dev-1"),
        ("q17-best-gsmsym-1", Q17, "best", "gsmsym-p1", 0.4500, "q17-sft-dev-1"),
        ("q17-sft-test-1", Q17, "sft", "gsm8k-test", 0.9900, "q17-sft-dev-1"),  # not method best
    )
    block = report.build_report(rows, 0)
    line = _gain_line(block, "+5.0")
    assert "outside noise" in line, line
    assert NO_SCORE not in block


def test_AC6_2_2_chosen_model_is_the_latest_best_rows_model():
    from gsm8k import report

    rows = _rows(
        ("q06-base-test-1", Q06, "base", "gsm8k-test", 0.3000),
        ("q17-base-test-1", Q17, "base", "gsm8k-test", 0.6800),
        ("q17-best-test-1", Q17, "best", "gsm8k-test", 0.7300, "q17-sft-dev-1"),
        ("q06-best-test-1", Q06, "best", "gsm8k-test", 0.3150, "q06-sft-dev-1"),  # latest best: q06
    )
    block = report.build_report(rows, 0)
    line = _gain_line(block, "+1.5")
    assert "within noise" in line, line


def test_AC6_2_2_missing_baseline_or_best_says_no_final_test_score_yet():
    from gsm8k import report

    only_baseline = _rows(("q17-base-test-1", Q17, "base", "gsm8k-test", 0.6800))
    only_best = _rows(("q17-best-test-1", Q17, "best", "gsm8k-test", 0.7300, "q17-sft-dev-1"))
    other_model_baseline = _rows(
        ("q06-base-test-1", Q06, "base", "gsm8k-test", 0.3000),
        ("q17-best-test-1", Q17, "best", "gsm8k-test", 0.7300, "q17-sft-dev-1"),
    )
    dev_only = _rows(
        ("q17-base-dev-1", Q17, "base", "gsm8k-dev", 0.7000),
        ("q17-sft-dev-1", Q17, "sft", "gsm8k-dev", 0.7500),
    )
    for rows in (only_baseline, only_best, other_model_baseline, dev_only, []):
        block = report.build_report(rows, 0)
        assert NO_SCORE in block, block
        assert _labelled_gains(block) == [], block


# AC6.2.3 harness rows: a labelled cross-check, never in the gain


def test_AC6_2_3_harness_rows_are_labelled_cross_check():
    from gsm8k import report

    rows = [
        *_baseline_and_best(0.6800, 0.7000),
        _row(
            10,
            "q17-best-harness-1",
            Q17,
            "best",
            "gsm8k-test-harness",
            0.7120,
            "q17-sft-dev-1",
            "harness_flexible_accuracy",
        ),
    ]
    block = report.build_report(rows, 0)
    assert "cross-check (lm-evaluation-harness), not used for the gain" in block.lower(), block
    _table_lines(block, rows)  # the harness row is still one run-table line


def test_AC6_2_3_harness_rows_do_not_change_the_gain():
    from gsm8k import report

    rows = _baseline_and_best(0.6800, 0.7000)
    without = report.build_report(rows, 0)
    line = _gain_line(without, "+2.0")
    assert "within noise" in line, line

    harness = [
        _row(
            10,
            "q17-base-harness-1",
            Q17,
            "base",
            "gsm8k-test-harness",
            0.1000,
            "",
            "harness_flexible_accuracy",
        ),
        _row(
            11,
            "q17-best-harness-1",
            Q17,
            "best",
            "gsm8k-test-harness",
            0.9900,
            "q17-sft-dev-1",
            "harness_flexible_accuracy",
        ),
    ]
    with_harness = report.build_report([*rows, *harness], 0)
    assert _gain_line(with_harness, "+2.0") == line
    assert "+89.0" not in with_harness and "+31.0" not in with_harness, with_harness
    assert _labelled_gains(with_harness) == [line], with_harness


def test_AC6_2_3_harness_row_never_stands_in_for_a_test_score():
    from gsm8k import report

    rows = _rows(
        ("q17-base-test-1", Q17, "base", "gsm8k-test", 0.6800),
        (
            "q17-best-harness-1",
            Q17,
            "best",
            "gsm8k-test-harness",
            0.9000,
            "q17-sft-dev-1",
            "harness_flexible_accuracy",
        ),
    )
    block = report.build_report(rows, 0)
    assert NO_SCORE in block, block
    assert _labelled_gains(block) == [], block
