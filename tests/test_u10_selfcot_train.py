"""u10-self-taught-cot, part C2: self-taught training (US10.2; FR10.2, FR2.1, FR2.4, NFR8; C2, C4, C5).

`gsm8k train --method selfcot --cot-data-run <generation run id>` fine-tunes on the kept solutions of a
generation run (`outputs/<run id>/cot_data.jsonl`, C2 line fields) through the supervised loop. Every
test builds its own `cot_data.jsonl` in temp folders from real training-part GSM8K problems (never dev or
test), uses the tiny random-weight model from conftest (deep-copied, as LoRA changes the model it is
given), and a temp results file. The CLI fine-tunes run a few steps with a 2-problem dev score.
AC10.2.5 is a `[manual]` long run and has no test here.

The training problems are observed by wrapping `gsm8k.training.sft.tokenize_examples` (the supervised
loop's tokenizer step), so the tests see exactly which problems, and which targets, are trained on.
"""

import copy
import csv
import hashlib
import inspect
import io
import json
import re
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROJECT_RESULTS = ROOT / "results" / "runs.csv"
Q06 = "Qwen/Qwen3-0.6B-Base"

GEN_RUN = "q06-cotgen-train-1"
RUN_ID = "q06-selfcot-dev-1"
MAX_STEPS = 2
FAST_ARGS = [
    "--max-steps",
    str(MAX_STEPS),
    "--limit",
    "2",
    "--max-new-tokens",
    "8",
    "--max-seq-len",
    "256",
    "--batch-size",
    "2",
    "--lora-rank",
    "4",
]


# --- helpers -------------------------------------------------------------------------------------


def _run_cli(argv: list[str]) -> int:
    """Call the command in-process; an argparse exit counts as its exit code."""
    from gsm8k.cli import main

    try:
        return main(argv)
    except SystemExit as exc:  # argparse rejects bad options with SystemExit(2)
        return exc.code if isinstance(exc.code, int) else 1


def _file_state(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@dataclass
class Gsm8k:
    by_id: dict
    dev_ids: list[str]
    test_ids: list[str]
    train_part: list[str]  # training-part ids of the fixed split, in problem index order


@pytest.fixture(scope="module")
def gsm8k_data() -> Gsm8k:
    """GSM8K at its pinned revision and the fixed split (seed 42), computed as the project does."""
    from gsm8k.datasets_prompts import hub, split

    problems = hub.load_gsm8k()
    data_split = split.build_split([p.id for p in problems["train"]])
    by_id = {p.id: p for p in problems["train"] + problems["test"]}
    return Gsm8k(
        by_id=by_id,
        dev_ids=list(data_split.dev_ids),
        test_ids=[p.id for p in problems["test"]],
        train_part=split.sort_by_index(list(data_split.train_ids)),
    )


def _own_solution(problem) -> str:
    """A solution "in the model's own words": different from GSM8K's written answer, reasoning lines
    first and the "#### <gold>" line last (C2 `solution`)."""
    return (
        f"Let me work through problem {problem.id} step by step.\n"
        f"Putting the numbers together gives {problem.gold}.\n"
        f"#### {problem.gold}"
    )


def _cot_line(problem, solution: str | None = None) -> dict:
    return {
        "v": 1,
        "problem_id": problem.id,
        "question": problem.question,
        "gold": problem.gold,
        "solution": solution if solution is not None else _own_solution(problem),
        "correct_samples": 2,
        "samples": 4,
    }


def _write_cot(outputs: Path, problems, run_id: str = GEN_RUN, *, reverse: bool = True) -> Path:
    """outputs/<run_id>/cot_data.jsonl with one C2 line per problem; by default written in reverse
    problem index order, so index order has to come from the reader."""
    folder = outputs / run_id
    folder.mkdir(parents=True, exist_ok=True)
    lines = [_cot_line(p) for p in problems]
    if reverse:
        lines.reverse()
    path = folder / "cot_data.jsonl"
    path.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
    return path


def _train_problems(data: Gsm8k, n: int) -> list:
    return [data.by_id[i] for i in data.train_part[:n]]


def _fresh_tiny(tiny_model):
    model, tokenizer = tiny_model
    return copy.deepcopy(model), copy.deepcopy(tokenizer)


def _patch_models(mp, tiny_model) -> None:
    """Every model load returns a fresh copy of the tiny model; real weights are never loaded."""
    import gsm8k.datasets_prompts.hub
    import gsm8k.evaluation
    import gsm8k.train_cmd

    def fake_load(*args, **kwargs):
        return _fresh_tiny(tiny_model)

    def no_real_weights(*args, **kwargs):
        raise AssertionError("a test tried to load real model weights")

    mp.setattr(gsm8k.train_cmd, "load_base_model", fake_load)
    mp.setattr(gsm8k.evaluation, "load_model", fake_load)
    mp.setattr(gsm8k.datasets_prompts.hub, "load_causal_lm", no_real_weights)


@dataclass
class Spy:
    """What the supervised loop tokenized: one (problems, answer_format) entry per call."""

    calls: list = field(default_factory=list)

    @property
    def problems(self) -> list:
        assert self.calls, "the supervised loop never tokenized training examples"
        return [p for problems, _ in self.calls for p in problems]


def _spy_tokenize(mp) -> Spy:
    import gsm8k.training.sft as sft

    spy = Spy()
    original = sft.tokenize_examples
    signature = inspect.signature(original)

    def wrapper(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)
        spy.calls.append((list(bound.arguments["problems"]), bound.arguments["answer_format"]))
        return original(*args, **kwargs)

    mp.setattr(sft, "tokenize_examples", wrapper)
    return spy


@dataclass
class SelfcotRun:
    rc: int
    text: str
    outputs: Path
    checkpoints: Path
    results: Path
    spy: Spy
    kept: list  # the problems written to cot_data.jsonl, in index order

    @property
    def run_dir(self) -> Path:
        return self.outputs / RUN_ID

    def assert_finished(self) -> None:
        assert self.rc == 0, self.text


def _selfcot_run(base: Path, tiny_model, kept: list, train_examples: str) -> SelfcotRun:
    outputs, checkpoints = base / "outputs", base / "checkpoints"
    results = base / "results" / "runs.csv"
    outputs.mkdir()
    checkpoints.mkdir()
    results.parent.mkdir()
    _write_cot(outputs, kept)
    before = _file_state(PROJECT_RESULTS)
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("GSM8K_OUTPUTS_DIR", str(outputs))
        mp.setenv("GSM8K_CHECKPOINTS_DIR", str(checkpoints))
        _patch_models(mp, tiny_model)
        spy = _spy_tokenize(mp)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = _run_cli(
                [
                    "train",
                    "--method",
                    "selfcot",
                    "--cot-data-run",
                    GEN_RUN,
                    "--train-examples",
                    train_examples,
                    *FAST_ARGS,
                    "--run-id",
                    RUN_ID,
                    "--results",
                    str(results),
                ]
            )
    assert _file_state(PROJECT_RESULTS) == before, "results/runs.csv was changed by a test"
    return SelfcotRun(rc, out.getvalue() + err.getvalue(), outputs, checkpoints, results, spy, kept)


@pytest.fixture(scope="module")
def selfcot_run(tmp_path_factory, tiny_model, gsm8k_data) -> SelfcotRun:
    """60 kept solutions (file in reverse index order), --train-examples 50: trains on the first 50."""
    kept = _train_problems(gsm8k_data, 60)
    return _selfcot_run(tmp_path_factory.mktemp("selfcot_run"), tiny_model, kept, "50")


@pytest.fixture
def patched_models(monkeypatch, tiny_model) -> None:
    _patch_models(monkeypatch, tiny_model)


def _selfcot_argv(dirs, *extra: str) -> list[str]:
    return [
        "train",
        "--method",
        "selfcot",
        "--train-examples",
        "50",
        *FAST_ARGS,
        *extra,
        "--run-id",
        RUN_ID,
        "--results",
        str(dirs.results),
    ]


def _no_row_nothing_trained(dirs, run_id: str = RUN_ID) -> None:
    assert not dirs.results.exists(), "the results file was written"
    assert not (dirs.checkpoints / run_id).exists(), "an adapter folder was written"
    assert not (dirs.outputs / run_id / "metrics.jsonl").exists(), "training started (metrics.jsonl)"


def _names(text: str, problem_id: str) -> bool:
    """`problem_id` appears in `text` as a whole id (gsm8k-train-12 is not named by gsm8k-train-123)."""
    return re.search(rf"{re.escape(problem_id)}(?!\d)", text) is not None


def _refused_by_the_command(text: str) -> None:
    """The refusal comes from the command's own checks, not from argparse not knowing an option."""
    assert "unrecognized arguments" not in text, text
    assert "invalid choice" not in text, text


# --- AC10.2.1: train --method selfcot trains on the kept solutions, saves the adapter, scores dev --


def test_AC10_2_1_selfcot_train_saves_adapter_under_checkpoints_run_id(selfcot_run):
    selfcot_run.assert_finished()
    adapter = selfcot_run.checkpoints / RUN_ID
    assert adapter.is_dir(), f"no adapter folder at {adapter}"
    assert (adapter / "adapter_config.json").is_file()
    weights = [adapter / "adapter_model.safetensors", adapter / "adapter_model.bin"]
    assert any(p.is_file() for p in weights), sorted(p.name for p in adapter.iterdir())
    assert [p.name for p in selfcot_run.checkpoints.iterdir()] == [RUN_ID]


def test_AC10_2_1_selfcot_train_appends_one_selfcot_dev_row(selfcot_run):
    selfcot_run.assert_finished()
    from gsm8k import run_config

    rows = _read_rows(selfcot_run.results)
    assert len(rows) == 1, rows
    row = rows[0]
    assert row["run_id"] == RUN_ID
    assert row["model"] == Q06
    assert row["method"] == "selfcot"
    assert row["data"] == "gsm8k-dev"
    assert row["metric"] == "accuracy"
    assert row["adapter_run"] == ""
    assert 0.0 <= float(row["value"]) <= 1.0
    expected = run_config.config_hash(run_config.read_config(selfcot_run.run_dir / "config.json"))
    assert row["config_hash"] == expected


def test_AC10_2_1_selfcot_config_names_the_generation_run_and_dev_split(selfcot_run):
    selfcot_run.assert_finished()
    config = json.loads((selfcot_run.run_dir / "config.json").read_text("utf-8"))
    assert config["run_id"] == RUN_ID
    assert config["method"] == "selfcot"
    assert config["cot_data_run"] == GEN_RUN
    assert config["split"] == "dev"
    assert config["train_examples"] == 50
    status = json.loads((selfcot_run.run_dir / "status.json").read_text("utf-8"))
    assert status["status"] == "finished"
    assert status["exit_code"] == 0


def test_AC10_2_1_selfcot_scores_the_dev_split(selfcot_run, gsm8k_data):
    selfcot_run.assert_finished()
    lines = (selfcot_run.run_dir / "predictions.jsonl").read_text("utf-8").splitlines()
    records = [json.loads(line) for line in lines if line.strip()]
    assert len(records) == 2, records  # --limit 2
    dev = set(gsm8k_data.dev_ids)
    assert all(r["problem_id"] in dev for r in records), [r["problem_id"] for r in records]


def test_AC10_2_1_training_targets_are_kept_solutions_in_the_zero_shot_frame(selfcot_run):
    selfcot_run.assert_finished()
    from gsm8k.training.targets import training_text

    trained = selfcot_run.spy.problems
    by_id = {p.id: p for p in selfcot_run.kept}
    assert trained, "no training problem"
    for _problems, answer_format in selfcot_run.spy.calls:
        assert answer_format == "step-by-step", answer_format
    for problem in trained:
        source = by_id[problem.id]
        solution = _own_solution(source)
        assert problem.question == source.question
        assert problem.gold == source.gold
        assert problem.answer == solution  # the kept solution, not GSM8K's written answer
        prompt, target = training_text(problem, "step-by-step")
        assert prompt.rstrip() == f"Question: {source.question}\nAnswer:"
        assert target.strip() == solution  # the reasoning lines are kept
        assert target.rstrip().endswith(f"#### {source.gold}")


def test_AC10_2_1_load_cot_problems_makes_problems_from_c2_lines(tmp_project_dirs, gsm8k_data):
    from gsm8k.training.selfcot_data import cot_data_path, load_cot_problems

    kept = _train_problems(gsm8k_data, 3)
    path = _write_cot(tmp_project_dirs.outputs, kept, reverse=False)
    assert cot_data_path(GEN_RUN) == path
    problems = load_cot_problems(GEN_RUN, gsm8k_data.dev_ids, gsm8k_data.test_ids, "all")
    assert [(p.id, p.question, p.answer, p.gold) for p in problems] == [
        (p.id, p.question, _own_solution(p), p.gold) for p in kept
    ]


def test_AC10_2_1_selfcot_counts_as_an_adapter_method():
    from gsm8k import cli, prune

    assert "selfcot" in cli.ADAPTER_METHODS
    assert "selfcot" in prune.ADAPTER_METHODS
    for method in ("sft", "grpo", "terse", "optuna"):  # the existing adapter methods stay
        assert method in cli.ADAPTER_METHODS
        assert method in prune.ADAPTER_METHODS


def test_AC10_2_1_selfcot_adapter_is_kept_or_pruned_like_an_sft_adapter(tmp_project_dirs):
    from gsm8k import prune
    from gsm8k.run_records.log import RunRow, append_row, read_rows

    specs = (
        ("q06-sft-dev-1", "sft", 0.40),
        ("q06-selfcot-dev-1", "selfcot", 0.45),  # the best q06 adapter run
        ("q06-selfcot-dev-2", "selfcot", 0.30),
        ("q06-selfcot-dev-3", "selfcot", 0.20),  # its folder is already gone
    )
    for n, (run_id, method, value) in enumerate(specs):
        append_row(
            tmp_project_dirs.results,
            RunRow(
                date=f"2026-11-08T1{n}:00:00Z",
                run_id=run_id,
                model=Q06,
                method=method,
                data="gsm8k-dev",
                metric="accuracy",
                value=value,
                minutes=10.0,
                config_hash=f"{n:064x}",
                adapter_run="",
            ),
        )
    for run_id, _, _ in specs[:3]:
        folder = tmp_project_dirs.checkpoints / run_id
        folder.mkdir()
        (folder / "adapter_config.json").write_text("{}", encoding="utf-8")
    rows, skipped = read_rows(tmp_project_dirs.results)
    assert skipped == 0
    assert prune.best_runs(rows)[Q06].run_id == "q06-selfcot-dev-1"
    plan = prune.plan_prune(rows, set(), tmp_project_dirs.checkpoints)
    assert plan.keep == ["q06-selfcot-dev-1"]
    assert sorted(p.name for p in plan.delete) == ["q06-selfcot-dev-2", "q06-sft-dev-1"]
    assert plan.already_gone == ["q06-selfcot-dev-3"]


def test_AC10_2_1_finalist_selfcot_adapter_scores_as_method_best(
    tmp_project_dirs, tmp_path, monkeypatch, tiny_model
):
    import gsm8k.evaluation
    from gsm8k.run_config import RunConfig
    from gsm8k.run_records.folder import write_config

    monkeypatch.setattr(gsm8k.evaluation, "load_model", lambda *args, **kwargs: tiny_model)
    adapter_run = "q06-selfcot-dev-1"
    run_folder = tmp_project_dirs.outputs / adapter_run
    run_folder.mkdir()
    write_config(
        run_folder,
        RunConfig(run_id=adapter_run, method="selfcot", train_examples=50, cot_data_run=GEN_RUN),
    )
    adapter = tmp_project_dirs.checkpoints / adapter_run
    adapter.mkdir()
    (adapter / "adapter_config.json").write_text("{}", encoding="utf-8")
    finalists = tmp_path / "finalists.json"
    finalists.write_text(
        json.dumps({"v": 1, "finalists": [{"run_id": adapter_run, "marked_at": "2026-11-08T10:00:00Z"}]}),
        encoding="utf-8",
    )
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = _run_cli(
            [
                "evaluate",
                "--method",
                "best",
                "--adapter",
                str(adapter),
                "--split",
                "test",
                "--limit",
                "2",
                "--max-new-tokens",
                "8",
                "--finalists",
                str(finalists),
                "--run-id",
                "q06-best-test-1",
                "--results",
                str(tmp_project_dirs.results),
            ]
        )
    assert rc == 0, out.getvalue() + err.getvalue()
    rows = _read_rows(tmp_project_dirs.results)
    assert len(rows) == 1, rows
    assert rows[0]["method"] == "best"
    assert rows[0]["adapter_run"] == adapter_run
    assert rows[0]["data"] == "gsm8k-test"


# --- AC10.2.2: the first N kept solutions by problem index; all, or N above the kept count -------


def test_AC10_2_2_cli_trains_on_the_first_n_kept_solutions_by_index(selfcot_run):
    selfcot_run.assert_finished()
    trained = [p.id for p in selfcot_run.spy.problems]
    expected = [p.id for p in selfcot_run.kept[:50]]  # 60 kept, --train-examples 50
    assert trained == expected


def test_AC10_2_2_cli_n_larger_than_kept_trains_on_every_kept_solution(tmp_path, tiny_model, gsm8k_data):
    kept = _train_problems(gsm8k_data, 12)
    run = _selfcot_run(tmp_path, tiny_model, kept, "50")  # 50 asked, 12 kept
    run.assert_finished()
    assert [p.id for p in run.spy.problems] == [p.id for p in kept]
    rows = _read_rows(run.results)
    assert len(rows) == 1 and rows[0]["method"] == "selfcot", rows


def test_AC10_2_2_load_cot_problems_takes_first_n_in_index_order(tmp_project_dirs, gsm8k_data):
    from gsm8k.training.selfcot_data import load_cot_problems

    kept = _train_problems(gsm8k_data, 8)
    _write_cot(tmp_project_dirs.outputs, kept)  # reverse index order in the file
    problems = load_cot_problems(GEN_RUN, gsm8k_data.dev_ids, gsm8k_data.test_ids, 3)
    assert [p.id for p in problems] == [p.id for p in kept[:3]]


def test_AC10_2_2_load_cot_problems_all_takes_every_kept_solution(tmp_project_dirs, gsm8k_data):
    from gsm8k.training.selfcot_data import load_cot_problems

    kept = _train_problems(gsm8k_data, 8)
    _write_cot(tmp_project_dirs.outputs, kept)
    problems = load_cot_problems(GEN_RUN, gsm8k_data.dev_ids, gsm8k_data.test_ids, "all")
    assert [p.id for p in problems] == [p.id for p in kept]


def test_AC10_2_2_load_cot_problems_n_above_kept_takes_every_kept_solution(tmp_project_dirs, gsm8k_data):
    from gsm8k.training.selfcot_data import load_cot_problems

    kept = _train_problems(gsm8k_data, 8)
    _write_cot(tmp_project_dirs.outputs, kept)
    problems = load_cot_problems(GEN_RUN, gsm8k_data.dev_ids, gsm8k_data.test_ids, 50)
    assert [p.id for p in problems] == [p.id for p in kept]


def test_AC10_2_2_index_order_is_numeric_not_text(tmp_project_dirs, gsm8k_data):
    """gsm8k-train-9 comes before gsm8k-train-10: problem index order, not string order."""
    from gsm8k.datasets_prompts import split
    from gsm8k.training.selfcot_data import load_cot_problems

    picked = [i for i in gsm8k_data.train_part if split.index_of(i) in range(5, 200)]
    single = [i for i in picked if split.index_of(i) < 10][:1]
    multi = [i for i in picked if split.index_of(i) >= 100][:2]
    assert single and len(multi) == 2, "the split has no train ids in the expected index ranges"
    kept = [gsm8k_data.by_id[i] for i in multi + single]  # text order would put 1xx before 5..9
    _write_cot(tmp_project_dirs.outputs, kept, reverse=False)
    problems = load_cot_problems(GEN_RUN, gsm8k_data.dev_ids, gsm8k_data.test_ids, 2)
    assert [p.id for p in problems] == [single[0], multi[0]]


# --- AC10.2.3: no cot_data_run, or no readable cot_data.jsonl: exit 2 naming it, no row ----------


def test_AC10_2_3_selfcot_without_cot_data_run_exits_2_naming_the_field(
    tmp_project_dirs, patched_models, capsys
):
    rc = _run_cli(_selfcot_argv(tmp_project_dirs))
    text = "".join(capsys.readouterr())
    assert rc == 2, text
    _refused_by_the_command(text)
    assert "cot_data_run" in text or "cot-data-run" in text, text
    _no_row_nothing_trained(tmp_project_dirs)
    assert not (tmp_project_dirs.outputs / RUN_ID).exists(), "a run folder was written"


def test_AC10_2_3_launcher_config_selfcot_without_cot_data_run_exits_2(
    tmp_project_dirs, tmp_path, patched_models, capsys
):
    from gsm8k import run_config

    cfg = run_config.RunConfig(run_id=RUN_ID, method="selfcot", split="dev", train_examples=50, limit=2)
    given = tmp_path / "given-config.json"
    given.write_text(json.dumps(run_config.to_dict(cfg)), encoding="utf-8")
    rc = _run_cli(
        ["train", "--config", str(given), "--run-id", RUN_ID, "--results", str(tmp_project_dirs.results)]
    )
    text = "".join(capsys.readouterr())
    assert rc == 2, text
    _refused_by_the_command(text)
    assert "cot_data_run" in text or "cot-data-run" in text, text
    _no_row_nothing_trained(tmp_project_dirs)


def test_AC10_2_3_missing_cot_data_file_exits_2_naming_the_file(tmp_project_dirs, patched_models, capsys):
    missing_run = "q06-cotgen-train-9"
    rc = _run_cli(_selfcot_argv(tmp_project_dirs, "--cot-data-run", missing_run))
    text = "".join(capsys.readouterr())
    assert rc == 2, text
    _refused_by_the_command(text)
    assert missing_run in text and "cot_data.jsonl" in text, text
    _no_row_nothing_trained(tmp_project_dirs)


@pytest.mark.parametrize(
    "content",
    [
        b'{"v": 1, "problem_id": "gsm8k-train-0", "question": "Q?", "gold": "1", "sol\n',
        b"\xff\xfe\x00not text\n",
    ],
    ids=["broken-json", "not-utf8"],
)
def test_AC10_2_3_unreadable_cot_data_file_exits_2_naming_the_file(
    tmp_project_dirs, patched_models, capsys, content
):
    folder = tmp_project_dirs.outputs / GEN_RUN
    folder.mkdir()
    (folder / "cot_data.jsonl").write_bytes(content)
    rc = _run_cli(_selfcot_argv(tmp_project_dirs, "--cot-data-run", GEN_RUN))
    text = "".join(capsys.readouterr())
    assert rc == 2, text
    _refused_by_the_command(text)
    assert "cot_data.jsonl" in text and GEN_RUN in text, text
    _no_row_nothing_trained(tmp_project_dirs)


def test_AC10_2_3_line_without_c2_fields_is_unreadable(tmp_project_dirs, patched_models, capsys, gsm8k_data):
    """A line without its `solution` cannot become a training problem: the file is not readable."""
    kept = _train_problems(gsm8k_data, 3)
    path = _write_cot(tmp_project_dirs.outputs, kept, reverse=False)
    broken = _cot_line(kept[0])
    del broken["solution"]
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(broken) + "\n")
    rc = _run_cli(_selfcot_argv(tmp_project_dirs, "--cot-data-run", GEN_RUN))
    text = "".join(capsys.readouterr())
    assert rc == 2, text
    _refused_by_the_command(text)
    assert "cot_data.jsonl" in text, text
    _no_row_nothing_trained(tmp_project_dirs)


def test_AC10_2_3_load_cot_problems_missing_file_raises_naming_it(tmp_project_dirs, gsm8k_data):
    from gsm8k.training.selfcot_data import cot_data_path, load_cot_problems

    with pytest.raises(Exception) as info:
        load_cot_problems("q06-cotgen-train-9", gsm8k_data.dev_ids, gsm8k_data.test_ids, "all")
    assert str(cot_data_path("q06-cotgen-train-9")) in str(info.value)


# --- AC10.2.4: a dev or test id in cot_data.jsonl: exit 2 naming the ids, nothing trained --------


def _leaky_cot(outputs: Path, data: Gsm8k, leaked_ids: list[str]) -> list[str]:
    kept = _train_problems(data, 5) + [data.by_id[i] for i in leaked_ids]
    _write_cot(outputs, kept)
    return leaked_ids


def test_AC10_2_4_dev_id_in_cot_data_exits_2_naming_it(tmp_project_dirs, patched_models, capsys, gsm8k_data):
    leaked = _leaky_cot(tmp_project_dirs.outputs, gsm8k_data, [gsm8k_data.dev_ids[0]])
    rc = _run_cli(_selfcot_argv(tmp_project_dirs, "--cot-data-run", GEN_RUN))
    text = "".join(capsys.readouterr())
    assert rc == 2, text
    _refused_by_the_command(text)
    assert _names(text, leaked[0]), text
    _no_row_nothing_trained(tmp_project_dirs)


def test_AC10_2_4_test_id_in_cot_data_exits_2_naming_it(tmp_project_dirs, patched_models, capsys, gsm8k_data):
    leaked = _leaky_cot(tmp_project_dirs.outputs, gsm8k_data, ["gsm8k-test-5"])
    rc = _run_cli(_selfcot_argv(tmp_project_dirs, "--cot-data-run", GEN_RUN))
    text = "".join(capsys.readouterr())
    assert rc == 2, text
    _refused_by_the_command(text)
    assert _names(text, leaked[0]), text
    _no_row_nothing_trained(tmp_project_dirs)


def test_AC10_2_4_dev_and_test_ids_are_both_named(tmp_project_dirs, patched_models, capsys, gsm8k_data):
    leaked = _leaky_cot(tmp_project_dirs.outputs, gsm8k_data, [gsm8k_data.dev_ids[1], "gsm8k-test-7"])
    rc = _run_cli(_selfcot_argv(tmp_project_dirs, "--cot-data-run", GEN_RUN))
    text = "".join(capsys.readouterr())
    assert rc == 2, text
    _refused_by_the_command(text)
    for problem_id in leaked:
        assert _names(text, problem_id), text
    _no_row_nothing_trained(tmp_project_dirs)


def test_AC10_2_4_leak_beyond_the_first_n_still_stops(tmp_project_dirs, gsm8k_data):
    """The whole file is checked, not only the first N solutions it would train on."""
    from gsm8k.datasets_prompts import split
    from gsm8k.training.selfcot_data import load_cot_problems

    kept = _train_problems(gsm8k_data, 4)
    last_kept = split.index_of(kept[-1].id)
    late_dev = next(i for i in split.sort_by_index(gsm8k_data.dev_ids) if split.index_of(i) > last_kept)
    _write_cot(tmp_project_dirs.outputs, kept + [gsm8k_data.by_id[late_dev]])
    with pytest.raises(Exception) as info:
        load_cot_problems(GEN_RUN, gsm8k_data.dev_ids, gsm8k_data.test_ids, 2)
    assert _names(str(info.value), late_dev)


def test_AC10_2_4_load_cot_problems_names_at_most_three_leaked_ids(tmp_project_dirs, gsm8k_data):
    from gsm8k.training.selfcot_data import load_cot_problems

    leaked = gsm8k_data.dev_ids[:5]
    _leaky_cot(tmp_project_dirs.outputs, gsm8k_data, leaked)
    with pytest.raises(Exception) as info:
        load_cot_problems(GEN_RUN, gsm8k_data.dev_ids, gsm8k_data.test_ids, "all")
    message = str(info.value)
    named = [i for i in leaked if _names(message, i)]
    assert 1 <= len(named) <= 3, message
