"""US2.3 (u3-sft): a run's duration is estimated from measured times before it starts (stories.md).
AC2.3.1-AC2.3.4; FR2.6, FR1.7, NFR2; ADR-007 (estimates live in RunConfiguration).

Measurements are the ``timings.json`` files (contract C2) of earlier run folders under outputs/, matched
to a model through the folder's ``config.json``; the newest file (by modification time) that holds the
value wins. Every test builds fake run folders under the temp outputs of ``tmp_project_dirs``.
"""

import json
import os
from pathlib import Path

import pytest


@pytest.fixture
def estimates():
    """The module under test, imported per test so a missing module fails each test, not collection."""
    import gsm8k.estimates

    return gsm8k.estimates


MODEL_06 = "Qwen/Qwen3-0.6B-Base"
MODEL_17 = "Qwen/Qwen3-1.7B-Base"
BASE_TIME = 1_800_000_000  # a fixed epoch second; later folders get later modification times


def _fake_run(
    outputs: Path,
    run_id: str,
    model: str,
    *,
    seconds_per_step: float | None = None,
    seconds_per_problem: float | None = None,
    age_rank: int = 0,
) -> Path:
    """A run folder with config.json and timings.json (C2); higher age_rank = newer timings."""
    folder = outputs / run_id
    folder.mkdir(parents=True)
    method = "sft" if seconds_per_step is not None else "base"
    (folder / "config.json").write_text(
        json.dumps({"v": 1, "run_id": run_id, "model": model, "method": method, "split": "dev"}),
        encoding="utf-8",
    )
    timings = folder / "timings.json"
    timings.write_text(
        json.dumps(
            {
                "v": 1,
                "seconds_per_step": seconds_per_step,
                "seconds_per_problem": seconds_per_problem,
                "peak_gpu_memory_gb": 5.5,
            }
        ),
        encoding="utf-8",
    )
    stamp = BASE_TIME + 60 * age_rank
    os.utime(timings, (stamp, stamp))
    os.utime(folder / "config.json", (stamp, stamp))
    return folder


# --- AC2.3.1 ---


def test_AC2_3_1_training_estimate_is_total_steps_times_seconds_per_step(estimates, tmp_project_dirs):
    _fake_run(tmp_project_dirs.outputs, "q06-sft-dev-1", MODEL_06, seconds_per_step=1.5)
    assert estimates.measured_seconds_per_step(MODEL_06) == pytest.approx(1.5)
    est = estimates.estimate_training(MODEL_06, 400)
    assert isinstance(est, estimates.Estimate)
    assert est.seconds == pytest.approx(600.0)
    assert est.over_cap is False
    assert est.text != estimates.NO_ESTIMATE
    assert estimates.OVER_CAP not in est.text


def test_AC2_3_1_explicit_outputs_folder_is_read(estimates, tmp_path):
    outputs = tmp_path / "elsewhere"
    _fake_run(outputs, "q17-sft-dev-1", MODEL_17, seconds_per_step=2.0)
    assert estimates.measured_seconds_per_step(MODEL_17, outputs) == pytest.approx(2.0)
    assert estimates.estimate_training(MODEL_17, 250, outputs).seconds == pytest.approx(500.0)


def test_AC2_3_1_newest_measurement_for_the_model_wins(estimates, tmp_project_dirs):
    out = tmp_project_dirs.outputs
    # Folder names sort the other way round from their age, so only the time decides.
    _fake_run(out, "q06-sft-dev-9", MODEL_06, seconds_per_step=3.0, age_rank=1)
    _fake_run(out, "q06-sft-dev-2", MODEL_06, seconds_per_step=0.8, age_rank=5)
    assert estimates.measured_seconds_per_step(MODEL_06) == pytest.approx(0.8)
    assert estimates.estimate_training(MODEL_06, 100).seconds == pytest.approx(80.0)


def test_AC2_3_1_other_models_timings_are_ignored(estimates, tmp_project_dirs):
    out = tmp_project_dirs.outputs
    _fake_run(out, "q06-sft-dev-1", MODEL_06, seconds_per_step=1.0, age_rank=1)
    _fake_run(out, "q17-sft-dev-1", MODEL_17, seconds_per_step=4.0, age_rank=9)
    assert estimates.measured_seconds_per_step(MODEL_06) == pytest.approx(1.0)
    assert estimates.measured_seconds_per_step(MODEL_17) == pytest.approx(4.0)
    assert estimates.estimate_training(MODEL_06, 10).seconds == pytest.approx(10.0)
    assert estimates.estimate_training(MODEL_17, 10).seconds == pytest.approx(40.0)


def test_AC2_3_1_newer_file_without_step_time_does_not_hide_older_one(estimates, tmp_project_dirs):
    out = tmp_project_dirs.outputs
    _fake_run(out, "q06-sft-dev-1", MODEL_06, seconds_per_step=1.2, age_rank=1)
    _fake_run(out, "q06-base-dev-1", MODEL_06, seconds_per_problem=0.5, age_rank=5)
    assert estimates.measured_seconds_per_step(MODEL_06) == pytest.approx(1.2)
    assert estimates.measured_seconds_per_problem(MODEL_06) == pytest.approx(0.5)


def test_AC2_3_1_non_run_entries_in_outputs_are_skipped(estimates, tmp_project_dirs):
    out = tmp_project_dirs.outputs
    (out / "run.lock").write_text("", encoding="utf-8")
    (out / "queue").mkdir()
    (out / "adhoc-20261101-201530").mkdir()  # a run folder with no files yet
    _fake_run(out, "q06-sft-dev-1", MODEL_06, seconds_per_step=2.5)
    assert estimates.estimate_training(MODEL_06, 4).seconds == pytest.approx(10.0)


# --- AC2.3.2 ---


def test_AC2_3_2_evaluation_estimate_is_problems_times_seconds_per_problem(estimates, tmp_project_dirs):
    _fake_run(tmp_project_dirs.outputs, "q17-base-dev-1", MODEL_17, seconds_per_problem=2.0)
    assert estimates.measured_seconds_per_problem(MODEL_17) == pytest.approx(2.0)
    est = estimates.estimate_evaluation(MODEL_17, 1319)
    assert est.seconds == pytest.approx(2638.0)
    assert est.over_cap is False
    assert est.text != estimates.NO_ESTIMATE
    assert estimates.OVER_CAP not in est.text


def test_AC2_3_2_newest_per_problem_time_for_the_model_wins(estimates, tmp_project_dirs):
    out = tmp_project_dirs.outputs
    _fake_run(out, "q06-base-dev-1", MODEL_06, seconds_per_problem=1.0, age_rank=1)
    _fake_run(out, "q06-base-dev-2", MODEL_06, seconds_per_problem=0.25, age_rank=3)
    _fake_run(out, "q17-base-dev-1", MODEL_17, seconds_per_problem=9.0, age_rank=7)
    assert estimates.estimate_evaluation(MODEL_06, 500).seconds == pytest.approx(125.0)


# --- AC2.3.3 ---


def test_AC2_3_3_cap_constants(estimates):
    assert estimates.CAP_SECONDS == 3 * 3600
    assert estimates.OVER_CAP == "Estimated time is above the 3-hour cap"


def test_AC2_3_3_training_estimate_above_three_hours_is_flagged(estimates, tmp_project_dirs):
    _fake_run(tmp_project_dirs.outputs, "q17-sft-dev-1", MODEL_17, seconds_per_step=10.0)
    est = estimates.estimate_training(MODEL_17, 1081)  # 10,810 s > 10,800 s
    assert est.seconds == pytest.approx(10810.0)
    assert est.over_cap is True
    assert estimates.OVER_CAP in est.text


def test_AC2_3_3_evaluation_estimate_above_three_hours_is_flagged(estimates, tmp_project_dirs):
    _fake_run(tmp_project_dirs.outputs, "q17-base-dev-1", MODEL_17, seconds_per_problem=9.0)
    est = estimates.estimate_evaluation(MODEL_17, 1319)  # 11,871 s
    assert est.seconds == pytest.approx(11871.0)
    assert est.over_cap is True
    assert estimates.OVER_CAP in est.text


def test_AC2_3_3_exactly_three_hours_is_not_above_the_cap(estimates, tmp_project_dirs):
    _fake_run(tmp_project_dirs.outputs, "q06-sft-dev-1", MODEL_06, seconds_per_step=10.0)
    est = estimates.estimate_training(MODEL_06, 1080)  # exactly 10,800 s
    assert est.seconds == pytest.approx(10800.0)
    assert est.over_cap is False
    assert estimates.OVER_CAP not in est.text


# --- AC2.3.4 ---


def test_AC2_3_4_no_measurement_reads_no_estimate_yet_never_zero(estimates, tmp_project_dirs):
    assert estimates.NO_ESTIMATE == "No estimate yet"
    assert estimates.measured_seconds_per_step(MODEL_06) is None
    assert estimates.measured_seconds_per_problem(MODEL_06) is None
    for est in (estimates.estimate_training(MODEL_06, 400), estimates.estimate_evaluation(MODEL_06, 500)):
        assert est.seconds is None
        assert est.text == estimates.NO_ESTIMATE
        assert est.over_cap is False


def test_AC2_3_4_only_other_models_measured_gives_no_estimate(estimates, tmp_project_dirs):
    out = tmp_project_dirs.outputs
    _fake_run(out, "q17-sft-dev-1", MODEL_17, seconds_per_step=4.0, seconds_per_problem=2.0)
    for est in (estimates.estimate_training(MODEL_06, 400), estimates.estimate_evaluation(MODEL_06, 500)):
        assert est.seconds is None
        assert est.text == estimates.NO_ESTIMATE


def test_AC2_3_4_missing_outputs_folder_gives_no_estimate(estimates, tmp_path):
    missing = tmp_path / "no-outputs-here"
    assert estimates.measured_seconds_per_step(MODEL_06, missing) is None
    est = estimates.estimate_training(MODEL_06, 400, missing)
    assert est.seconds is None
    assert est.text == estimates.NO_ESTIMATE


def test_AC2_3_4_step_time_alone_gives_no_evaluation_estimate(estimates, tmp_project_dirs):
    _fake_run(tmp_project_dirs.outputs, "q06-sft-dev-1", MODEL_06, seconds_per_step=1.0)
    est = estimates.estimate_evaluation(MODEL_06, 500)
    assert est.seconds is None
    assert est.text == estimates.NO_ESTIMATE
