"""u7-grpo, gap-1: the closing dev score in the GRPO step plan (AC7.1.4, changed 2026-11-17) and the
Python headers kept in the project folder for Triton (AC7.1.6, added 2026-11-17).

Hooks assumed in the code (the builder provides them):
  * ``gsm8k._env.python_header_dirs()`` -> the two absolute include folders under ``.tools/python-headers/``;
    ``gsm8k._env.setup_env()`` puts them first on ``CPATH`` (no duplicates, existing entries kept), and
    looks the function up by its module-global name at call time.
  * ``gsm8k.training.grpo.python_headers_available()``: ``Python.h`` in ``sysconfig.get_paths()["include"]``
    or in ``gsm8k._env.python_header_dirs()[0]`` (both looked up at call time).
  * ``gsm8k.train_cmd._on_gpu()``; a GRPO run on the GPU without headers exits 2 before any model load.
  * ``gsm8k.training.grpo_plan``: ``DEV_SCORED_PROBLEMS``, ``FALLBACK_SECONDS_PER_PROBLEM``,
    ``closing_dev_reserve_s(model, outputs=None)``; ``grpo.steps_for`` takes the reserve off the cap.
Everything runs on the CPU with made-up timings files and no model download.
"""

import io
import json
import os
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROJECT_RESULTS = ROOT / "results" / "runs.csv"
MODEL = "Qwen/Qwen3-0.6B-Base"
CAP = 3 * 3600
RESERVE_AT_2S = 496 * 2.0  # 992 s
RESERVE_FALLBACK = 496 * 3.0  # 1488 s
FETCH_SCRIPT = "scripts/fetch-python-headers.sh"


def _make_run(
    outputs: Path, name: str, method: str | None, timings: dict, mtime: float | None = None
) -> None:
    folder = outputs / name
    folder.mkdir(parents=True)
    config = {"model": MODEL} if method is None else {"model": MODEL, "method": method}
    (folder / "config.json").write_text(json.dumps(config), encoding="utf-8")
    (folder / "timings.json").write_text(json.dumps(timings), encoding="utf-8")
    if mtime is not None:
        os.utime(folder / "timings.json", (mtime, mtime))


def _grpo_cfg(**fields):
    from gsm8k import run_config

    return run_config.RunConfig(run_id="q17-grpo-dev-1", method="grpo", split="dev", model=MODEL, **fields)


def _timed_outputs(outputs: Path, step_s: float = 30.0, problem_s: float = 2.0) -> None:
    _make_run(outputs, "g1", "grpo", {"seconds_per_step": step_s})
    _make_run(outputs, "e1", "eval", {"seconds_per_problem": problem_s})


# ---- AC7.1.4: the closing dev score is reserved in the step plan ----


def test_AC7_1_4_plan_constants_name_the_closing_dev_score():
    from gsm8k.training import grpo_plan

    assert grpo_plan.DEV_SCORED_PROBLEMS == 496
    assert grpo_plan.FALLBACK_SECONDS_PER_PROBLEM == 3.0


def test_AC7_1_4_reserve_is_496_problems_at_the_models_saved_seconds_per_problem(tmp_path):
    from gsm8k.training import grpo_plan

    _make_run(tmp_path, "e1", "eval", {"seconds_per_problem": 2.0})
    assert grpo_plan.closing_dev_reserve_s(MODEL, outputs=tmp_path) == pytest.approx(RESERVE_AT_2S)


def test_AC7_1_4_reserve_uses_the_stated_fallback_without_saved_timings(tmp_path):
    from gsm8k.training import grpo_plan

    assert grpo_plan.closing_dev_reserve_s(MODEL, outputs=tmp_path) == pytest.approx(RESERVE_FALLBACK)
    assert grpo_plan.closing_dev_reserve_s(MODEL, outputs=tmp_path / "nope") == pytest.approx(
        RESERVE_FALLBACK
    )


def test_AC7_1_4_reserve_ignores_another_models_seconds_per_problem(tmp_path):
    from gsm8k.training import grpo_plan

    folder = tmp_path / "other"
    folder.mkdir()
    (folder / "config.json").write_text(json.dumps({"model": "Qwen/Qwen3-1.7B-Base"}), encoding="utf-8")
    (folder / "timings.json").write_text(json.dumps({"seconds_per_problem": 9.0}), encoding="utf-8")
    assert grpo_plan.closing_dev_reserve_s(MODEL, outputs=tmp_path) == pytest.approx(RESERVE_FALLBACK)


def test_AC7_1_4_reserve_reads_the_project_outputs_folder_by_default(tmp_project_dirs):
    from gsm8k.training import grpo_plan

    _make_run(tmp_project_dirs.outputs, "e1", "eval", {"seconds_per_problem": 1.5})
    assert grpo_plan.closing_dev_reserve_s(MODEL) == pytest.approx(496 * 1.5)


def test_AC7_1_4_default_steps_leave_room_for_the_closing_dev_score(tmp_project_dirs):
    from gsm8k.training import grpo

    _timed_outputs(tmp_project_dirs.outputs, step_s=30.0, problem_s=2.0)
    steps = grpo.steps_for(_grpo_cfg())
    assert steps == 326  # floor((10800 - 992) / 30), not the 360 of the whole cap
    assert steps * 30.0 + RESERVE_AT_2S <= CAP


def test_AC7_1_4_default_steps_use_the_fallback_reserve_without_dev_timings(tmp_project_dirs):
    from gsm8k.training import grpo

    _make_run(tmp_project_dirs.outputs, "g1", "grpo", {"seconds_per_step": 30.0})
    assert grpo.steps_for(_grpo_cfg()) == 310  # floor((10800 - 1488) / 30)


def test_AC7_1_4_default_steps_with_no_timings_at_all_fit_cap_minus_fallback_reserve(tmp_project_dirs):
    from gsm8k.training import grpo

    # 60 s per step fallback, 3 s per problem fallback: floor((10800 - 1488) / 60)
    assert grpo.steps_for(_grpo_cfg()) == 155


def test_AC7_1_4_default_steps_stay_at_least_one_when_the_reserve_eats_the_cap(tmp_project_dirs):
    from gsm8k.training import grpo

    _timed_outputs(tmp_project_dirs.outputs, step_s=30.0, problem_s=30.0)  # reserve 14880 s > cap
    assert grpo.steps_for(_grpo_cfg()) == 1


def test_AC7_1_4_an_explicit_step_count_is_used_as_is(tmp_project_dirs):
    from gsm8k.training import grpo

    _timed_outputs(tmp_project_dirs.outputs)
    assert grpo.steps_for(_grpo_cfg(grpo_steps=500)) == 500
    assert grpo.steps_for(_grpo_cfg(grpo_steps=7)) == 7


def test_AC7_1_4_max_steps_still_caps_the_planned_and_the_explicit_count(tmp_project_dirs):
    from gsm8k.training import grpo

    _timed_outputs(tmp_project_dirs.outputs)
    assert grpo.steps_for(_grpo_cfg(), max_steps=5) == 5
    assert grpo.steps_for(_grpo_cfg(grpo_steps=50), max_steps=5) == 5
    assert grpo.steps_for(_grpo_cfg(grpo_steps=3), max_steps=5) == 3
    assert grpo.steps_for(_grpo_cfg(), max_steps=100_000) == 326


# ---- AC7.1.4: the printed estimate is the GRPO estimate plus the closing dev score ----


def _prepared(tmp_path: Path, cfg, max_steps: int | None = None):
    from gsm8k import run_config, train_cmd

    return train_cmd.TrainPrepared(
        cfg=cfg,
        run_id=cfg.run_id,
        run_dir=tmp_path / "run",
        adapter_dir=tmp_path / "adapter",
        results=tmp_path / "runs.csv",
        config_hash=run_config.config_hash(cfg),
        config_given=None,
        eval_every=None,
        max_steps=max_steps,
    )


def _estimate_lines(capsys, tmp_path: Path, cfg, max_steps: int | None = None) -> tuple[list[str], str]:
    from gsm8k import train_cmd

    train_cmd._print_estimate(_prepared(tmp_path, cfg, max_steps))
    captured = capsys.readouterr()
    lines = [line for line in captured.out.splitlines() if line.startswith("estimate:")]
    return lines, captured.err


def test_AC7_1_4_printed_estimate_is_steps_times_grpo_step_time_plus_the_closing_dev_score(
    tmp_project_dirs, tmp_path, capsys
):
    from gsm8k import estimates

    _timed_outputs(tmp_project_dirs.outputs, step_s=30.0, problem_s=2.0)
    lines, err = _estimate_lines(capsys, tmp_path, _grpo_cfg(grpo_steps=100))
    assert len(lines) == 1, lines
    expected = estimates.format_duration(100 * 30.0 + RESERVE_AT_2S)  # 3992 s: 1 h 07 min
    assert expected in lines[0], (expected, lines[0])
    assert estimates.format_duration(100 * 30.0) not in lines[0]  # the steps alone: 50 min
    assert estimates.OVER_CAP not in err


def test_AC7_1_4_printed_estimate_for_the_planned_count_ends_inside_the_cap_and_is_not_flagged(
    tmp_project_dirs, tmp_path, capsys
):
    from gsm8k import estimates
    from gsm8k.training import grpo

    # 60 s per step, 5 s per dev problem: reserve 2480 s, floor((10800 - 2480) / 60) = 138 steps,
    # 138 * 60 + 2480 = 10760 s (2 h 59 min); the old plan (180 steps) printed 3 h 00 min.
    _timed_outputs(tmp_project_dirs.outputs, step_s=60.0, problem_s=5.0)
    assert grpo.steps_for(_grpo_cfg()) == 138
    lines, err = _estimate_lines(capsys, tmp_path, _grpo_cfg())
    assert len(lines) == 1, lines
    assert estimates.format_duration(138 * 60.0 + 496 * 5.0) in lines[0], lines[0]
    assert "3 h 00 min" not in lines[0], lines[0]
    assert estimates.OVER_CAP not in err


def test_AC7_1_4_printed_estimate_ignores_supervised_step_times(tmp_project_dirs, tmp_path, capsys):
    from gsm8k import estimates

    # Only an SFT run's step time and an evaluation run's problem time exist: a GRPO step is then
    # sized from the evaluation time (4 generations x 2 s x 2 + 10 s update = 26 s), never 0.45 s.
    _make_run(tmp_project_dirs.outputs, "sft1", "sft", {"seconds_per_step": 0.45})
    _make_run(tmp_project_dirs.outputs, "e1", "eval", {"seconds_per_problem": 2.0})
    lines, err = _estimate_lines(capsys, tmp_path, _grpo_cfg(grpo_steps=100))
    assert len(lines) == 1, lines
    assert estimates.format_duration(100 * 26.0 + RESERVE_AT_2S) in lines[0], lines[0]  # 3592 s
    assert estimates.format_duration(100 * 0.45 + RESERVE_AT_2S) not in lines[0], lines[0]  # 1037 s
    assert "45 s" not in lines[0]  # the old line: 100 steps x 0.45 s
    assert estimates.OVER_CAP not in err


def test_AC7_1_4_a_count_over_the_budget_prints_the_over_cap_message(tmp_project_dirs, tmp_path, capsys):
    from gsm8k import estimates

    _timed_outputs(tmp_project_dirs.outputs, step_s=30.0, problem_s=2.0)
    lines, err = _estimate_lines(capsys, tmp_path, _grpo_cfg(grpo_steps=400))  # 12000 s alone
    assert len(lines) == 1, lines
    assert estimates.OVER_CAP in err


def test_AC7_1_4_a_count_that_fits_only_without_the_closing_dev_score_is_flagged(
    tmp_project_dirs, tmp_path, capsys
):
    from gsm8k import estimates

    _timed_outputs(tmp_project_dirs.outputs, step_s=30.0, problem_s=2.0)
    # 355 steps = 10650 s <= 10800 s, but with the 992 s dev score it is 11642 s.
    lines, err = _estimate_lines(capsys, tmp_path, _grpo_cfg(grpo_steps=355))
    assert len(lines) == 1, lines
    assert estimates.OVER_CAP in err

    # 326 steps + the dev score = 10772 s fits.
    lines, err = _estimate_lines(capsys, tmp_path, _grpo_cfg(grpo_steps=326))
    assert estimates.OVER_CAP not in err


def test_AC7_1_4_a_huge_count_is_flagged_even_with_only_supervised_step_times(
    tmp_project_dirs, tmp_path, capsys
):
    from gsm8k import estimates

    _make_run(tmp_project_dirs.outputs, "sft1", "sft", {"seconds_per_step": 0.45})
    _make_run(tmp_project_dirs.outputs, "e1", "eval", {"seconds_per_problem": 2.0})
    _, err = _estimate_lines(capsys, tmp_path, _grpo_cfg(grpo_steps=20000))
    assert estimates.OVER_CAP in err


def test_AC7_1_4_max_steps_caps_the_steps_in_the_printed_estimate(tmp_project_dirs, tmp_path, capsys):
    from gsm8k import estimates

    _timed_outputs(tmp_project_dirs.outputs, step_s=30.0, problem_s=2.0)
    lines, err = _estimate_lines(capsys, tmp_path, _grpo_cfg(grpo_steps=400), max_steps=10)
    assert estimates.format_duration(10 * 30.0 + RESERVE_AT_2S) in lines[0], lines  # 1292 s
    assert estimates.OVER_CAP not in err


# ---- AC7.1.6: CPATH in every gsm8k process ----


def _dirs() -> list[str]:
    from gsm8k import _env

    return [str(p) for p in _env.python_header_dirs()]


def test_AC7_1_6_header_dirs_are_the_two_include_folders_under_the_project():
    from gsm8k import _env

    dirs = _env.python_header_dirs()
    assert dirs == [
        _env.ROOT / ".tools/python-headers/usr/include/python3.12",
        _env.ROOT / ".tools/python-headers/usr/include",
    ]
    assert all(p.is_absolute() for p in dirs)
    assert _env.ROOT == ROOT


def test_AC7_1_6_setup_env_puts_the_header_dirs_first_on_an_empty_cpath(monkeypatch):
    from gsm8k import _env

    for start in ("", None):
        if start is None:
            monkeypatch.delenv("CPATH", raising=False)
        else:
            monkeypatch.setenv("CPATH", start)
        _env.setup_env()
        assert os.environ["CPATH"].split(os.pathsep) == _dirs(), start  # no empty entry (it means "here")


def test_AC7_1_6_setup_env_keeps_the_entries_already_on_cpath_after_the_header_dirs(monkeypatch):
    from gsm8k import _env

    monkeypatch.setenv("CPATH", "/x/y:/z")
    _env.setup_env()
    assert os.environ["CPATH"].split(os.pathsep) == [*_dirs(), "/x/y", "/z"]


def test_AC7_1_6_setup_env_twice_adds_no_duplicate_entries(monkeypatch):
    from gsm8k import _env

    monkeypatch.setenv("CPATH", "/x/y")
    _env.setup_env()
    first = os.environ["CPATH"]
    _env.setup_env()
    assert os.environ["CPATH"] == first
    entries = os.environ["CPATH"].split(os.pathsep)
    assert len(entries) == len(set(entries)) == 3


def test_AC7_1_6_setup_env_with_the_dirs_already_on_cpath_moves_them_to_the_front_once(monkeypatch):
    from gsm8k import _env

    first, second = _dirs()
    monkeypatch.setenv("CPATH", os.pathsep.join([first, second, "/x/y"]))
    _env.setup_env()
    assert os.environ["CPATH"].split(os.pathsep) == [first, second, "/x/y"]

    monkeypatch.setenv("CPATH", os.pathsep.join(["/x/y", second, "/z", first]))
    _env.setup_env()
    assert os.environ["CPATH"].split(os.pathsep) == [first, second, "/x/y", "/z"]


def test_AC7_1_6_setup_env_sets_the_dirs_whether_or_not_they_exist(monkeypatch, tmp_path):
    from gsm8k import _env

    missing = [tmp_path / "no" / "python3.12", tmp_path / "no"]
    assert not any(p.exists() for p in missing)
    monkeypatch.setattr(_env, "python_header_dirs", lambda: missing)
    monkeypatch.setenv("CPATH", "/x/y")
    _env.setup_env()
    assert os.environ["CPATH"].split(os.pathsep) == [str(missing[0]), str(missing[1]), "/x/y"]


def test_AC7_1_6_importing_gsm8k_puts_the_header_dirs_first_on_cpath_and_keeps_the_old_entries():
    code = "import gsm8k, os; print(os.environ['CPATH'])"
    done = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env={**os.environ, "CPATH": "/x/y"},
        cwd=ROOT,
    )
    assert done.returncode == 0, done.stderr
    entries = done.stdout.strip().split(os.pathsep)
    assert entries == [
        str(ROOT / ".tools/python-headers/usr/include/python3.12"),
        str(ROOT / ".tools/python-headers/usr/include"),
        "/x/y",
    ]


def test_AC7_1_6_importing_gsm8k_sets_cpath_when_there_was_none():
    code = "import gsm8k, os; print(os.environ['CPATH'])"
    env = {k: v for k, v in os.environ.items() if k != "CPATH"}
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=ROOT)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip().split(os.pathsep) == [
        str(ROOT / ".tools/python-headers/usr/include/python3.12"),
        str(ROOT / ".tools/python-headers/usr/include"),
    ]


# ---- AC7.1.6: python_headers_available ----


@pytest.fixture
def header_places(monkeypatch, tmp_path):
    """Three empty folders: the system include, the kept python3.12 include and the kept parent include."""
    import sysconfig

    from gsm8k import _env

    system = tmp_path / "system-include"
    kept = tmp_path / "kept" / "python3.12"
    kept_parent = tmp_path / "kept"
    for folder in (system, kept):
        folder.mkdir(parents=True)
    monkeypatch.setattr(_env, "python_header_dirs", lambda: [kept, kept_parent])
    monkeypatch.setattr(sysconfig, "get_paths", lambda *a, **k: {"include": str(system)})
    return {"system": system, "kept": kept, "kept_parent": kept_parent}


def test_AC7_1_6_headers_available_when_the_system_has_python_h(header_places):
    from gsm8k.training import grpo

    (header_places["system"] / "Python.h").write_text("", encoding="utf-8")
    assert grpo.python_headers_available() is True


def test_AC7_1_6_headers_available_when_only_the_project_folder_has_python_h(header_places):
    from gsm8k.training import grpo

    (header_places["kept"] / "Python.h").write_text("", encoding="utf-8")
    assert grpo.python_headers_available() is True


def test_AC7_1_6_headers_available_when_both_have_python_h(header_places):
    from gsm8k.training import grpo

    (header_places["system"] / "Python.h").write_text("", encoding="utf-8")
    (header_places["kept"] / "Python.h").write_text("", encoding="utf-8")
    assert grpo.python_headers_available() is True


def test_AC7_1_6_headers_missing_when_neither_place_has_python_h(header_places):
    from gsm8k.training import grpo

    assert grpo.python_headers_available() is False


def test_AC7_1_6_headers_missing_when_the_folders_do_not_exist(monkeypatch, tmp_path):
    import sysconfig

    from gsm8k import _env
    from gsm8k.training import grpo

    monkeypatch.setattr(_env, "python_header_dirs", lambda: [tmp_path / "a" / "b", tmp_path / "a"])
    monkeypatch.setattr(sysconfig, "get_paths", lambda *a, **k: {"include": str(tmp_path / "gone")})
    assert grpo.python_headers_available() is False


def test_AC7_1_6_a_python_h_folder_instead_of_a_file_does_not_count(header_places):
    from gsm8k.training import grpo

    (header_places["system"] / "Python.h").mkdir()
    assert grpo.python_headers_available() is False


# ---- AC7.1.6: a GPU GRPO run without headers exits 2 before the model loads ----

RUN_ID = "q17-grpo-dev-1"
GRPO_ARGS = [
    "train",
    "--method",
    "grpo",
    "--grpo-steps",
    "2",
    "--grpo-generations",
    "2",
    "--max-new-tokens",
    "8",
    "--limit",
    "2",
    "--max-seq-len",
    "256",
    "--batch-size",
    "2",
    "--lora-rank",
    "4",
    "--train-examples",
    "50",
]
SFT_ARGS = ["train", "--max-new-tokens", "8", "--limit", "2", "--train-examples", "50"]


def _run_cli(argv: list[str]) -> tuple[int, str]:
    from gsm8k.cli import main

    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = main(argv)
        except SystemExit as exc:
            rc = exc.code if isinstance(exc.code, int) else 1
    return rc, err.getvalue()


def _train(tmp_project_dirs, monkeypatch, args: list[str], *, on_gpu: bool, headers: bool):
    """Run ``gsm8k train`` in-process; every model load is recorded and then fails, so a run that goes
    on stops right after the load (exit 1) instead of training."""
    import gsm8k.evaluation
    import gsm8k.train_cmd
    from gsm8k.training import grpo, sft

    loads: list = []

    def failing_load(*a, **k):
        loads.append(a)
        raise RuntimeError("stop after the model load")

    monkeypatch.chdir(tmp_project_dirs.results.parent.parent)
    monkeypatch.setattr(gsm8k.train_cmd, "load_base_model", failing_load)
    monkeypatch.setattr(gsm8k.evaluation, "load_model", failing_load)
    monkeypatch.setattr(sft, "load_training_data", lambda cfg, train=None: None)
    monkeypatch.setattr(gsm8k.train_cmd, "_on_gpu", lambda: on_gpu)
    monkeypatch.setattr(grpo, "python_headers_available", lambda: headers)
    before = PROJECT_RESULTS.read_bytes() if PROJECT_RESULTS.exists() else None
    rc, err = _run_cli([*args, "--run-id", RUN_ID, "--results", str(tmp_project_dirs.results)])
    after = PROJECT_RESULTS.read_bytes() if PROJECT_RESULTS.exists() else None
    assert after == before, "results/runs.csv was changed by a test"
    return rc, err, loads


def test_AC7_1_6_grpo_on_the_gpu_without_headers_exits_2_before_the_model_loads(
    tmp_project_dirs, monkeypatch
):
    rc, err, loads = _train(tmp_project_dirs, monkeypatch, GRPO_ARGS, on_gpu=True, headers=False)
    assert rc == 2, err
    assert FETCH_SCRIPT in err, err
    assert loads == [], "the model was loaded before the missing headers were caught"
    assert not tmp_project_dirs.results.exists(), "a results row was written"
    assert not (tmp_project_dirs.checkpoints / RUN_ID).exists()


def test_AC7_1_6_grpo_on_the_gpu_with_headers_goes_on_to_load_the_model(tmp_project_dirs, monkeypatch):
    rc, err, loads = _train(tmp_project_dirs, monkeypatch, GRPO_ARGS, on_gpu=True, headers=True)
    assert rc != 2, err
    assert FETCH_SCRIPT not in err
    assert loads, "the run never reached the model load"


def test_AC7_1_6_grpo_off_the_gpu_without_headers_goes_on_to_load_the_model(tmp_project_dirs, monkeypatch):
    rc, err, loads = _train(tmp_project_dirs, monkeypatch, GRPO_ARGS, on_gpu=False, headers=False)
    assert rc != 2, err
    assert FETCH_SCRIPT not in err
    assert loads, "a CPU run was stopped for missing headers"


def test_AC7_1_6_a_supervised_run_on_the_gpu_without_headers_is_not_stopped(tmp_project_dirs, monkeypatch):
    rc, err, loads = _train(tmp_project_dirs, monkeypatch, SFT_ARGS, on_gpu=True, headers=False)
    assert rc != 2, err
    assert FETCH_SCRIPT not in err
    assert loads, "a supervised run was stopped for missing headers"


def test_AC7_1_6_the_exit_2_check_writes_no_run_folder_status(tmp_project_dirs, monkeypatch):
    rc, _, _ = _train(tmp_project_dirs, monkeypatch, GRPO_ARGS, on_gpu=True, headers=False)
    assert rc == 2
    assert not (tmp_project_dirs.outputs / RUN_ID / "status.json").exists()
