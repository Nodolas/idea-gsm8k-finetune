"""u10-self-taught-cot, part C1: generating the model's own reasoning (US10.1; FR10.1, NFR1, NFR2, NFR8;
contracts C1, C2, C5).

The keep rule runs on fixed strings. ``gsm8k cot-generate`` runs in-process on the tiny random-weight
model from conftest (``gsm8k.evaluation.load_model`` monkeypatched), temp outputs/ and checkpoints/
folders and a temp results file:

- ``random_run`` samples for real (50 problems, 3 samples, 8 new tokens). Nothing a random model writes
  is kept, so it also covers the kept = 0 case (means null, kept fraction 0).
- ``scripted_run`` replaces ``gsm8k.cot.generate.sample`` with a scripted sampler that knows each
  problem's gold answer, so the keep rule, ``cot_data.jsonl``, ``cot_stats.json`` and the row are checked
  against known outcomes.

AC10.1.5 is a ``[manual]`` long run (q17-cotgen-train) and has no test here.
"""

import copy
import csv
import hashlib
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROJECT_RESULTS = ROOT / "results" / "runs.csv"

MODEL = "Qwen/Qwen3-0.6B-Base"
RANDOM_RUN_ID = "q06-cotgen-train-1"
SCRIPTED_RUN_ID = "q06-cotgen-train-2"
RUN_ID = "q06-cotgen-train-3"
N_PROBLEMS = 50  # the smallest cot_problems allowed
N_SAMPLES = 3
MAX_NEW_TOKENS = 8
SCRIPTED_SEED = 7
SCRIPTED_TEMPERATURE = 0.9
TRAIN_SPLIT_SIZE = 6973

METRIC_KEYS = {"v", "step", "total_steps", "loss", "learning_rate", "elapsed_s", "eta_s"}
STATS_KEYS = {
    "v",
    "run_id",
    "problems",
    "samples_per_problem",
    "solved",
    "kept",
    "kept_fraction",
    "mean_lines_kept",
    "mean_words_kept",
    "mean_lines_reference",
    "mean_words_reference",
}
COT_LINE_KEYS = {"v", "problem_id", "question", "gold", "solution", "correct_samples", "samples"}


def kept_solution(gold: str) -> str:
    """The scripted sample that the keep rule keeps: two reasoning lines (8 words), then the gold."""
    return f"First, add the numbers.\nThen check the sum.\n#### {gold}"


def wrong(gold: str) -> str:
    return gold + "1"  # numerically different from the gold answer


def scripted_samples(k: int, gold: str) -> list[str]:
    """Three scripted samples for the k-th problem (0-based, index order):

    k % 3 == 0: correct without reasoning, then correct with reasoning (kept), then another correct one
                with reasoning (not kept: only the first such sample in sample order is kept);
    k % 3 == 1: all wrong (not solved, not kept);
    k % 3 == 2: two correct samples without any reasoning line and one wrong (solved, not kept).
    """
    if k % 3 == 0:
        return [f"#### {gold}", kept_solution(gold), f"Another way to see it.\n#### {gold}"]
    if k % 3 == 1:
        return [f"Wrong.\n#### {wrong(gold)}", f"Also wrong.\n#### {wrong(gold)}", f"No.\n#### {wrong(gold)}"]
    return [f"#### {gold}", f"#### {gold}", f"Wrong.\n#### {wrong(gold)}"]


# --- helpers ----------------------------------------------------------------------------------


def _run_cli(argv: list[str]) -> int:
    """Call the command in-process; an argparse exit counts as its exit code."""
    from gsm8k.cli import main

    try:
        return main(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1


def _file_state(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text("utf-8"))


def _patch_models(mp, tiny_model) -> None:
    """Every model load returns a fresh copy of the tiny model; real weights are never loaded."""
    import gsm8k.datasets_prompts.hub
    import gsm8k.evaluation

    def fake_load(*args, **kwargs):
        model, tokenizer = tiny_model
        return copy.deepcopy(model), copy.deepcopy(tokenizer)

    def no_real_weights(*args, **kwargs):
        raise AssertionError("a test tried to load real model weights")

    mp.setattr(gsm8k.evaluation, "load_model", fake_load)
    mp.setattr(gsm8k.datasets_prompts.hub, "load_causal_lm", no_real_weights)


def _cot_args(run_id: str, results: Path, *extra: str) -> list[str]:
    return ["cot-generate", "--model", MODEL, "--run-id", run_id, "--results", str(results), *extra]


@dataclass
class Gsm8kView:
    """The training part of the fixed split, its first problems by index and the fixed 4-shot prompt."""

    train_ids_by_index: list[str]
    dev_ids: set[str]
    test_ids: set[str]
    by_id: dict
    prompt_by_question: dict[str, str]
    id_by_question: dict[str, str]

    def first(self, n: int) -> list[str]:
        return self.train_ids_by_index[:n]


def _gsm8k_view() -> Gsm8kView:
    """Built with the same modules the command uses; needs GSM8K_OUTPUTS_DIR set (the split file)."""
    from gsm8k.datasets_prompts import hub, prompt, split

    problems = hub.load_gsm8k()
    train_ids = [p.id for p in problems["train"]]
    data_split = split.load_or_build_split(train_ids)
    by_id = {p.id: p for p in problems["train"]}
    exemplars = [by_id[i] for i in prompt.choose_exemplars(data_split.dev_ids)]
    ordered = split.sort_by_index(list(data_split.train_ids))
    prompt_by_question: dict[str, str] = {}
    id_by_question: dict[str, str] = {}
    for problem_id in ordered:
        question = by_id[problem_id].question
        prompt_by_question.setdefault(question, prompt.build_prompt(exemplars, question))
        id_by_question.setdefault(question, problem_id)
    return Gsm8kView(
        train_ids_by_index=ordered,
        dev_ids=set(data_split.dev_ids),
        test_ids={p.id for p in problems["test"]},
        by_id=by_id,
        prompt_by_question=prompt_by_question,
        id_by_question=id_by_question,
    )


def _question_of(prompt_text: str) -> str:
    """The target question of a fixed 4-shot prompt (its last 'Question: <q>' newline 'Answer:')."""
    tail = prompt_text.rsplit("Question: ", 1)[-1]
    assert tail.endswith("\nAnswer:"), f"prompt does not end with the target frame: {prompt_text[-80:]!r}"
    return tail[: -len("\nAnswer:")]


@dataclass
class SamplerCalls:
    prompts: list[str] = field(default_factory=list)
    kwargs: list[dict] = field(default_factory=list)
    outputs: list[list[str]] = field(default_factory=list)
    seeds: list[int] = field(default_factory=list)


@dataclass
class CotRun:
    rc: int
    text: str
    outputs: Path
    results: Path
    run_id: str
    calls: SamplerCalls
    view: Gsm8kView

    @property
    def run_dir(self) -> Path:
        return self.outputs / self.run_id

    def assert_finished(self) -> None:
        assert self.rc == 0, self.text

    def stats(self) -> dict:
        return _read_json(self.run_dir / "cot_stats.json")

    def cot_lines(self) -> list[dict]:
        return _read_jsonl(self.run_dir / "cot_data.jsonl")


def _record_seeds(mp, calls: SamplerCalls) -> None:
    import transformers

    original = transformers.set_seed

    def recording_set_seed(seed, *args, **kwargs):
        calls.seeds.append(seed)
        return original(seed, *args, **kwargs)

    mp.setattr(transformers, "set_seed", recording_set_seed)


def _start_run(base: Path, tiny_model, run_id: str, extra: list[str], install_sampler) -> CotRun:
    outputs = base / "outputs"
    results = base / "results" / "runs.csv"
    outputs.mkdir()
    (base / "checkpoints").mkdir()
    results.parent.mkdir()
    before = _file_state(PROJECT_RESULTS)
    calls = SamplerCalls()
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("GSM8K_OUTPUTS_DIR", str(outputs))
        mp.setenv("GSM8K_CHECKPOINTS_DIR", str(base / "checkpoints"))
        _patch_models(mp, tiny_model)
        _record_seeds(mp, calls)
        view = _gsm8k_view()
        install_sampler(mp, calls, view)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = _run_cli(_cot_args(run_id, results, *extra))
    assert _file_state(PROJECT_RESULTS) == before, "results/runs.csv was changed by a test"
    return CotRun(rc, out.getvalue() + err.getvalue(), outputs, results, run_id, calls, view)


def _install_recording_real_sampler(mp, calls: SamplerCalls, view: Gsm8kView) -> None:
    """Keep the real sampler, recording what it is given and what it returns."""
    import gsm8k.cot.generate as generate

    real = generate.sample

    def recording(model, tokenizer, prompts, **kwargs):
        result = real(model, tokenizer, prompts, **kwargs)
        calls.prompts.extend(prompts)
        calls.kwargs.append(dict(kwargs))
        calls.outputs.extend(result)
        return result

    mp.setattr(generate, "sample", recording)


def _scripted_sampler(script):
    """A sampler that answers each prompt with ``script(k, gold, samples)``; k is the problem's position
    among the training part's problems by index. An unknown prompt fails the run."""

    def install(mp, calls: SamplerCalls, view: Gsm8kView) -> None:
        import gsm8k.cot.generate as generate

        position = {problem_id: k for k, problem_id in enumerate(view.train_ids_by_index)}

        def fake_sample(model, tokenizer, prompts, *, samples, temperature, max_new_tokens, **extra):
            calls.kwargs.append(
                {"samples": samples, "temperature": temperature, "max_new_tokens": max_new_tokens}
            )
            result = []
            for prompt_text in prompts:
                question = _question_of(prompt_text)
                problem_id = view.id_by_question.get(question)
                assert problem_id is not None, (
                    f"prompted a problem outside the training part: {question[:60]!r}"
                )
                gold = view.by_id[problem_id].gold
                outputs = script(position[problem_id], gold, samples)
                calls.prompts.append(prompt_text)
                calls.outputs.append(outputs)
                result.append(outputs)
            return result

        mp.setattr(generate, "sample", fake_sample)

    return install


@pytest.fixture(scope="module")
def random_run(tmp_path_factory, tiny_model) -> CotRun:
    """Real sampling on the tiny random model: 50 problems, 3 samples, 8 new tokens, default temperature."""
    return _start_run(
        tmp_path_factory.mktemp("cot_random"),
        tiny_model,
        RANDOM_RUN_ID,
        [
            "--cot-problems",
            str(N_PROBLEMS),
            "--cot-samples",
            str(N_SAMPLES),
            "--max-new-tokens",
            str(MAX_NEW_TOKENS),
        ],
        _install_recording_real_sampler,
    )


@pytest.fixture(scope="module")
def scripted_run(tmp_path_factory, tiny_model) -> CotRun:
    """The scripted sampler on the first 50 training problems, 3 samples, temperature 0.9, seed 7."""
    return _start_run(
        tmp_path_factory.mktemp("cot_scripted"),
        tiny_model,
        SCRIPTED_RUN_ID,
        [
            "--cot-problems",
            str(N_PROBLEMS),
            "--cot-samples",
            str(N_SAMPLES),
            "--cot-temperature",
            str(SCRIPTED_TEMPERATURE),
            "--seed",
            str(SCRIPTED_SEED),
            "--max-new-tokens",
            str(MAX_NEW_TOKENS),
        ],
        _scripted_sampler(lambda k, gold, samples: scripted_samples(k, gold)[:samples]),
    )


@pytest.fixture
def patched_models(monkeypatch, tiny_model) -> None:
    _patch_models(monkeypatch, tiny_model)


def _nothing_written(dirs, run_id: str = RUN_ID) -> None:
    assert not (dirs.outputs / run_id).exists(), "a run folder was written"
    assert not dirs.results.exists(), "the results file was written"
    from gsm8k.run_records.lock import is_free, read_lock

    lock_file = dirs.outputs / "run.lock"
    assert is_free(lock_file) and read_lock(lock_file) is None, "the GPU lock was left behind"


def _expected_scripted() -> dict:
    kept_k = [k for k in range(N_PROBLEMS) if k % 3 == 0]
    solved_k = [k for k in range(N_PROBLEMS) if k % 3 in (0, 2)]
    return {"kept_k": kept_k, "kept": len(kept_k), "solved": len(solved_k)}


# --- AC10.1.1: sampling with the fixed prompt, the stop rule and the run folder ----------------


def test_AC10_1_1_random_run_finishes_and_writes_the_run_folder(random_run):
    random_run.assert_finished()
    for name in (
        "config.json",
        "cot_data.jsonl",
        "cot_stats.json",
        "timings.json",
        "status.json",
        "metrics.jsonl",
    ):
        assert (random_run.run_dir / name).is_file(), f"no {name} in {random_run.run_dir}"
    status = _read_json(random_run.run_dir / "status.json")
    assert status["status"] == "finished"
    assert status["exit_code"] == 0
    assert status["run_id"] == RANDOM_RUN_ID
    assert status["v"] == 1


def test_AC10_1_1_config_holds_method_cotgen_split_train_and_the_cot_dials(random_run):
    random_run.assert_finished()
    config = _read_json(random_run.run_dir / "config.json")
    assert config["v"] == 1
    assert config["run_id"] == RANDOM_RUN_ID
    assert config["model"] == MODEL
    assert config["method"] == "cotgen"
    assert config["split"] == "train"
    assert config["cot_problems"] == N_PROBLEMS
    assert config["cot_samples"] == N_SAMPLES
    assert config["cot_temperature"] == pytest.approx(0.7)  # the default dial
    assert config["max_new_tokens"] == MAX_NEW_TOKENS
    assert config["cot_data_run"] is None


def test_AC10_1_1_each_problem_is_prompted_once_with_the_fixed_4_shot_prompt(random_run):
    random_run.assert_finished()
    view = random_run.view
    expected = [view.prompt_by_question[view.by_id[i].question] for i in view.first(N_PROBLEMS)]
    assert sorted(random_run.calls.prompts) == sorted(expected)
    assert len(random_run.calls.prompts) == N_PROBLEMS  # each problem once (its samples come back together)


def test_AC10_1_1_samples_cot_samples_times_at_cot_temperature(random_run):
    random_run.assert_finished()
    assert random_run.calls.kwargs, "the sampler was never called"
    for kwargs in random_run.calls.kwargs:
        assert kwargs["samples"] == N_SAMPLES
        assert kwargs["temperature"] == pytest.approx(0.7)
        assert kwargs["max_new_tokens"] == MAX_NEW_TOKENS
    assert len(random_run.calls.outputs) == N_PROBLEMS
    assert all(len(outputs) == N_SAMPLES for outputs in random_run.calls.outputs)


def test_AC10_1_1_every_sample_is_cut_by_the_stop_rule(random_run):
    from gsm8k import scoring

    random_run.assert_finished()
    for outputs in random_run.calls.outputs:
        for text in outputs:
            assert isinstance(text, str)
            assert scoring.cut_output(text) == text, f"sample not cut at its stop point: {text!r}"


def test_AC10_1_1_metrics_lines_count_problems_done_and_eta(random_run):
    random_run.assert_finished()
    lines = _read_jsonl(random_run.run_dir / "metrics.jsonl")
    assert lines, "no metrics lines"
    steps = []
    for line in lines:
        assert METRIC_KEYS <= set(line), sorted(line)
        assert line["v"] == 1
        assert line["total_steps"] == N_PROBLEMS
        assert line["loss"] is None
        assert line["learning_rate"] is None
        assert line["elapsed_s"] >= 0
        if line["step"] >= 1:
            assert isinstance(line["eta_s"], int | float) and line["eta_s"] >= 0, line
        steps.append(line["step"])
    assert steps == sorted(steps), steps
    assert steps[-1] == N_PROBLEMS
    assert lines[-1]["eta_s"] == pytest.approx(0, abs=1e-6)


def test_AC10_1_1_timings_leave_seconds_per_problem_null(random_run):
    random_run.assert_finished()
    timings = _read_json(random_run.run_dir / "timings.json")
    assert timings["v"] == 1
    assert timings["seconds_per_problem"] is None
    assert isinstance(timings["seconds_per_generated_problem"], int | float)
    assert timings["seconds_per_generated_problem"] >= 0
    assert "peak_gpu_memory_gb" in timings


def test_AC10_1_1_sampling_uses_the_runs_seed(scripted_run):
    scripted_run.assert_finished()
    assert SCRIPTED_SEED in scripted_run.calls.seeds, scripted_run.calls.seeds
    for kwargs in scripted_run.calls.kwargs:
        assert kwargs["temperature"] == pytest.approx(SCRIPTED_TEMPERATURE)
        assert kwargs["samples"] == N_SAMPLES


def test_AC10_1_1_sample_is_seeded_sampling_not_greedy(tiny_model):
    import transformers

    from gsm8k import scoring
    from gsm8k.cot.generate import sample

    model, tokenizer = copy.deepcopy(tiny_model[0]), copy.deepcopy(tiny_model[1])
    prompts = [
        "Question: What is 2 plus 3?\nAnswer:",
        "Question: A pen costs $4. How much do 3 pens cost?\nAnswer:",
    ]

    def draw(seed: int, samples: int) -> list[list[str]]:
        transformers.set_seed(seed)
        return sample(
            model, tokenizer, prompts, samples=samples, temperature=0.7, max_new_tokens=MAX_NEW_TOKENS
        )

    first = draw(11, 3)
    assert len(first) == len(prompts)
    assert all(len(outputs) == 3 for outputs in first)
    assert all(scoring.cut_output(t) == t for outputs in first for t in outputs)
    assert draw(11, 3) == first, "the same seed must give the same samples"
    assert len(set(first[0])) > 1, "three samples at temperature 0.7 should not all be identical"
    single = draw(11, 1)
    assert len(single) == len(prompts) and all(len(outputs) == 1 for outputs in single)


def test_AC10_1_1_lock_held_exits_3_and_writes_nothing(tmp_project_dirs, patched_models, capsys):
    from gsm8k.run_records.lock import GpuLock

    holder = GpuLock()
    holder.acquire("q06-base-dev-9")
    try:
        rc = _run_cli(_cot_args(RUN_ID, tmp_project_dirs.results, "--cot-problems", "50"))
    finally:
        holder.release()
    text = "".join(capsys.readouterr())
    assert rc == 3, text
    assert "A run is already active" in text
    assert "q06-base-dev-9" in text
    _nothing_written(tmp_project_dirs)


# --- AC10.1.2: the keep rule --------------------------------------------------------------------


def test_AC10_1_2_keeps_a_correct_sample_with_reasoning():
    from gsm8k.cot.generate import keep_sample

    assert keep_sample("Natalia sold 48/2 = 24 clips in May.\n48 + 24 = 72\n#### 72", "72") is True
    assert keep_sample("One line of work: 1000 + 234 = 1234\n#### 1,234", "1234") is True  # numeric compare


def test_AC10_1_2_rejects_a_wrong_final_number():
    from gsm8k.cot.generate import keep_sample

    assert keep_sample("48 + 24 = 72\n#### 71", "72") is False
    assert keep_sample("I am not sure.\n#### ", "72") is False


def test_AC10_1_2_rejects_a_correct_sample_without_reasoning_lines():
    from gsm8k.cot.generate import keep_sample

    assert keep_sample("#### 72", "72") is False
    assert keep_sample("\n   \n\n#### 72", "72") is False  # blank lines are not reasoning


def test_AC10_1_2_rejects_a_sample_without_a_final_hash_line():
    from gsm8k.cot.generate import keep_sample

    # The kept solution must end with its "#### <number>" line (C2 cot_data.jsonl), so reasoning whose
    # last number happens to be right but that never writes the final line is not kept.
    assert keep_sample("48 + 24 = 72, so she sold 72", "72") is False


def test_AC10_1_2_choose_kept_takes_the_first_kept_sample_in_order():
    from gsm8k.cot.generate import choose_kept

    outputs = ["#### 72", "Wrong.\n#### 70", "48 + 24 = 72\n#### 72", "A longer way: 24 * 3 = 72\n#### 72"]
    assert choose_kept(outputs, "72") == "48 + 24 = 72\n#### 72"
    assert choose_kept(list(reversed(outputs)), "72") == "A longer way: 24 * 3 = 72\n#### 72"


def test_AC10_1_2_choose_kept_returns_none_when_no_sample_qualifies():
    from gsm8k.cot.generate import choose_kept

    assert choose_kept(["#### 72", "Wrong.\n#### 71", "No number here"], "72") is None
    assert choose_kept([], "72") is None


def test_AC10_1_2_at_most_one_kept_line_per_problem_first_in_sample_order(scripted_run):
    scripted_run.assert_finished()
    view = scripted_run.view
    lines = scripted_run.cot_lines()
    expected_ids = [view.first(N_PROBLEMS)[k] for k in _expected_scripted()["kept_k"]]
    assert [line["problem_id"] for line in lines] == expected_ids  # problem index order, one line each
    for line in lines:
        assert COT_LINE_KEYS <= set(line), sorted(line)
        problem = view.by_id[line["problem_id"]]
        assert line["v"] == 1
        assert line["question"] == problem.question
        assert line["gold"] == problem.gold
        assert line["solution"] == kept_solution(problem.gold)  # the first kept sample, not the third
        assert line["correct_samples"] == 3
        assert line["samples"] == N_SAMPLES


def test_AC10_1_2_problems_without_a_kept_sample_are_left_out_and_counted(scripted_run):
    scripted_run.assert_finished()
    expected = _expected_scripted()
    kept_ids = {line["problem_id"] for line in scripted_run.cot_lines()}
    left_out = [i for i in scripted_run.view.first(N_PROBLEMS) if i not in kept_ids]
    assert len(left_out) == N_PROBLEMS - expected["kept"]
    stats = scripted_run.stats()
    assert stats["problems"] == N_PROBLEMS
    assert stats["kept"] == expected["kept"]
    assert stats["problems"] - stats["kept"] == len(left_out)
    # Solved without reasoning (k % 3 == 2) counts as solved but is not kept.
    assert stats["solved"] == expected["solved"]


# --- AC10.1.3: the row and cot_stats.json --------------------------------------------------------


def test_AC10_1_3_row_has_method_cotgen_data_train_metric_kept_fraction(scripted_run):
    from gsm8k import run_config

    scripted_run.assert_finished()
    rows = _read_rows(scripted_run.results)
    assert len(rows) == 1, rows
    row = rows[0]
    assert row["run_id"] == SCRIPTED_RUN_ID
    assert row["model"] == MODEL
    assert row["method"] == "cotgen"
    assert row["data"] == "gsm8k-train"
    assert row["metric"] == "kept_fraction"
    expected = _expected_scripted()["kept"] / N_PROBLEMS
    assert row["value"] == f"{expected:.4f}"
    assert row["adapter_run"] == ""
    cfg = run_config.read_config(scripted_run.run_dir / "config.json")
    assert row["config_hash"] == run_config.config_hash(cfg)


def test_AC10_1_3_stats_hold_counts_and_means_of_kept_and_reference(scripted_run):
    from gsm8k.datasets_prompts.prompt import strip_calculator_notes
    from gsm8k.reasoning_text import reasoning_lines, reasoning_words

    scripted_run.assert_finished()
    stats = scripted_run.stats()
    assert STATS_KEYS <= set(stats), sorted(stats)
    expected = _expected_scripted()
    assert stats["v"] == 1
    assert stats["run_id"] == SCRIPTED_RUN_ID
    assert stats["problems"] == N_PROBLEMS
    assert stats["samples_per_problem"] == N_SAMPLES
    assert stats["solved"] == expected["solved"]
    assert stats["kept"] == expected["kept"]
    assert stats["kept_fraction"] == pytest.approx(expected["kept"] / N_PROBLEMS, abs=5e-5)
    assert stats["mean_lines_kept"] == pytest.approx(2.0)
    assert stats["mean_words_kept"] == pytest.approx(8.0)
    view = scripted_run.view
    references = [
        strip_calculator_notes(view.by_id[view.first(N_PROBLEMS)[k]].answer) for k in expected["kept_k"]
    ]
    lines_ref = sum(len(reasoning_lines(t)) for t in references) / len(references)
    words_ref = sum(reasoning_words(t) for t in references) / len(references)
    assert stats["mean_lines_reference"] == pytest.approx(lines_ref, abs=0.01)
    assert stats["mean_words_reference"] == pytest.approx(words_ref, abs=0.01)


def test_AC10_1_3_nothing_kept_gives_null_means_and_kept_fraction_0(random_run):
    random_run.assert_finished()
    stats = random_run.stats()
    assert STATS_KEYS <= set(stats), sorted(stats)
    assert stats["problems"] == N_PROBLEMS
    assert stats["samples_per_problem"] == N_SAMPLES
    assert stats["kept"] == 0
    assert 0 <= stats["solved"] <= N_PROBLEMS
    assert stats["kept_fraction"] == 0
    for name in ("mean_lines_kept", "mean_words_kept", "mean_lines_reference", "mean_words_reference"):
        assert stats[name] is None, f"{name} should be null when nothing is kept"
    assert random_run.cot_lines() == []  # cot_data.jsonl exists and is empty


def test_AC10_1_3_nothing_kept_still_writes_one_row_with_value_0(random_run):
    from gsm8k import run_config

    random_run.assert_finished()
    rows = _read_rows(random_run.results)
    assert len(rows) == 1, rows
    row = rows[0]
    assert row["run_id"] == RANDOM_RUN_ID
    assert (row["method"], row["data"], row["metric"]) == ("cotgen", "gsm8k-train", "kept_fraction")
    assert row["value"] == "0.0000"
    cfg = run_config.read_config(random_run.run_dir / "config.json")
    assert row["config_hash"] == run_config.config_hash(cfg)
    # The cot dials enter the hash once they differ from their defaults.
    import dataclasses

    other = dataclasses.replace(cfg, cot_samples=N_SAMPLES + 1)
    assert run_config.config_hash(other) != row["config_hash"]


def test_AC10_1_3_run_log_reads_back_cotgen_rows(tmp_path):
    from gsm8k.run_records import log

    path = tmp_path / "runs.csv"
    row = log.RunRow(
        date="2026-11-08T12:00:00Z",
        run_id="q17-cotgen-train-1",
        model="Qwen/Qwen3-1.7B-Base",
        method="cotgen",
        data="gsm8k-train",
        metric="kept_fraction",
        value=0.34,
        minutes=150.0,
        config_hash="0" * 64,
    )
    log.append_row(path, row)
    log.append_row(
        path,
        log.RunRow(
            date="2026-11-08T13:00:00Z",
            run_id="q17-selfcot-dev-1",
            model="Qwen/Qwen3-1.7B-Base",
            method="selfcot",
            data="gsm8k-dev",
            metric="accuracy",
            value=0.7,
            minutes=40.0,
            config_hash="1" * 64,
        ),
    )
    rows, skipped = log.read_rows(path)
    assert skipped == 0
    assert [(r.run_id, r.method, r.data, r.metric) for r in rows] == [
        ("q17-cotgen-train-1", "cotgen", "gsm8k-train", "kept_fraction"),
        ("q17-selfcot-dev-1", "selfcot", "gsm8k-dev", "accuracy"),
    ]
    assert rows[0].value == pytest.approx(0.34)


# --- AC10.1.4: which problems, and the dial and split checks ------------------------------------


def test_AC10_1_4_picks_the_first_cot_problems_training_problems_by_index(scripted_run):
    scripted_run.assert_finished()
    view = scripted_run.view
    asked = [view.id_by_question[_question_of(p)] for p in scripted_run.calls.prompts]
    assert sorted(asked, key=view.train_ids_by_index.index) == view.first(N_PROBLEMS)
    assert not set(asked) & view.dev_ids, "a dev problem was sampled"
    assert not set(asked) & view.test_ids, "a test problem was sampled"
    assert all(i.startswith("gsm8k-train-") for i in asked)
    for line in scripted_run.cot_lines():
        assert line["problem_id"] not in view.dev_ids
        assert line["problem_id"] not in view.test_ids


def test_AC10_1_4_cot_problems_all_takes_the_whole_training_part(tmp_path, tiny_model):
    run = _start_run(
        tmp_path,
        tiny_model,
        RUN_ID,
        ["--cot-problems", "all", "--cot-samples", "2"],
        _scripted_sampler(lambda k, gold, samples: [kept_solution(gold)] * samples),
    )
    run.assert_finished()
    view = run.view
    ids = [line["problem_id"] for line in run.cot_lines()]
    assert len(ids) == TRAIN_SPLIT_SIZE
    assert ids == view.train_ids_by_index
    assert not set(ids) & view.dev_ids
    assert not set(ids) & view.test_ids
    stats = run.stats()
    assert stats["problems"] == TRAIN_SPLIT_SIZE
    assert stats["kept"] == TRAIN_SPLIT_SIZE
    assert stats["kept_fraction"] == pytest.approx(1.0)
    assert _read_json(run.run_dir / "config.json")["cot_problems"] == "all"


@pytest.mark.parametrize(
    ("flag", "value", "dial", "bounds"),
    [
        ("--cot-problems", "49", "cot_problems", ("50", "6973")),
        ("--cot-problems", "6974", "cot_problems", ("50", "6973")),
        ("--cot-samples", "0", "cot_samples", ("1", "8")),
        ("--cot-samples", "9", "cot_samples", ("1", "8")),
        ("--cot-temperature", "0.05", "cot_temperature", ("0.1", "1.5")),
        ("--cot-temperature", "1.6", "cot_temperature", ("0.1", "1.5")),
    ],
)
def test_AC10_1_4_dial_out_of_range_exits_2_naming_dial_and_range(
    tmp_project_dirs, patched_models, capsys, flag, value, dial, bounds
):
    rc = _run_cli(_cot_args(RUN_ID, tmp_project_dirs.results, flag, value))
    text = "".join(capsys.readouterr())
    assert rc == 2, f"{flag} {value}: exit {rc}\n{text}"
    assert dial in text or dial.replace("_", "-") in text, text
    for bound in bounds:
        assert bound in text, f"the message should give the allowed range: {text}"
    _nothing_written(tmp_project_dirs)


@pytest.mark.parametrize(("flag", "value"), [("--cot-problems", "many"), ("--cot-samples", "two")])
def test_AC10_1_4_dial_of_the_wrong_type_exits_2(tmp_project_dirs, patched_models, capsys, flag, value):
    rc = _run_cli(_cot_args(RUN_ID, tmp_project_dirs.results, flag, value))
    text = "".join(capsys.readouterr())
    assert rc == 2, text
    dial = flag.removeprefix("--")
    assert dial in text or dial.replace("-", "_") in text, f"the message should name {flag}: {text}"
    _nothing_written(tmp_project_dirs)


def test_AC10_1_4_config_with_a_split_other_than_train_exits_2(
    tmp_project_dirs, tmp_path, patched_models, capsys
):
    from gsm8k import run_config

    for split_name in ("dev", "test"):
        cfg = run_config.RunConfig(run_id=RUN_ID, method="cotgen", split=split_name, cot_problems=50)
        given = tmp_path / f"given-{split_name}.json"
        given.write_text(json.dumps(run_config.to_dict(cfg)), encoding="utf-8")
        rc = _run_cli(
            [
                "cot-generate",
                "--config",
                str(given),
                "--run-id",
                RUN_ID,
                "--results",
                str(tmp_project_dirs.results),
            ]
        )
        text = "".join(capsys.readouterr())
        assert rc == 2, f"split {split_name}: exit {rc}\n{text}"
        assert "split" in text.lower(), text
        assert "train" in text, text
        _nothing_written(tmp_project_dirs)


def test_AC10_1_4_evaluate_on_the_train_split_exits_2(tmp_project_dirs, patched_models, capsys):
    rc = _run_cli(
        [
            "evaluate",
            "--split",
            "train",
            "--limit",
            "2",
            "--run-id",
            "q06-base-dev-1",
            "--results",
            str(tmp_project_dirs.results),
        ]
    )
    text = "".join(capsys.readouterr())
    assert rc == 2, text
    assert "split" in text.lower(), text
    _nothing_written(tmp_project_dirs, "q06-base-dev-1")


def test_AC10_1_4_validate_accepts_the_cot_dials_at_their_bounds():
    from gsm8k.run_config import RunConfig, validate

    validate(RunConfig(run_id=RUN_ID))  # defaults
    validate(RunConfig(run_id=RUN_ID, method="cotgen", split="train"))
    for value in (50, TRAIN_SPLIT_SIZE, "all"):
        validate(RunConfig(run_id=RUN_ID, method="cotgen", split="train", cot_problems=value))
    for value in (1, 8):
        validate(RunConfig(run_id=RUN_ID, method="cotgen", split="train", cot_samples=value))
    for value in (0.1, 1.5, 1):
        validate(RunConfig(run_id=RUN_ID, method="cotgen", split="train", cot_temperature=value))


@pytest.mark.parametrize(
    ("dial", "value"),
    [
        ("cot_problems", 49),
        ("cot_problems", TRAIN_SPLIT_SIZE + 1),
        ("cot_problems", "some"),
        ("cot_problems", 50.0),
        ("cot_problems", True),
        ("cot_samples", 0),
        ("cot_samples", 9),
        ("cot_samples", 2.5),
        ("cot_temperature", 0.09),
        ("cot_temperature", 1.51),
        ("cot_temperature", "hot"),
    ],
)
def test_AC10_1_4_validate_rejects_a_cot_dial_outside_its_range(dial, value):
    from gsm8k.run_config import ConfigError, RunConfig, validate

    cfg = RunConfig(run_id=RUN_ID, method="cotgen", split="train", **{dial: value})
    with pytest.raises(ConfigError) as error:
        validate(cfg)
    assert dial in str(error.value), str(error.value)


@pytest.mark.parametrize(
    ("method", "split_name"),
    [("cotgen", "dev"), ("cotgen", "test"), ("base", "train"), ("sft", "train"), ("selfcot", "train")],
)
def test_AC10_1_4_split_train_and_method_cotgen_only_go_together(method, split_name):
    from gsm8k.run_config import ConfigError, RunConfig, validate

    with pytest.raises(ConfigError) as error:
        validate(RunConfig(run_id=RUN_ID, method=method, split=split_name))
    assert "split" in str(error.value).lower(), str(error.value)


def test_AC10_1_4_check_dials_parses_the_cot_dials_strictly():
    from gsm8k.run_config import ConfigError, check_dials

    cfg = check_dials(
        {"method": "cotgen", "split": "train", "cot_problems": "all", "cot_samples": 2, "cot_temperature": 1}
    )
    assert (cfg.cot_problems, cfg.cot_samples, cfg.cot_temperature) == ("all", 2, 1.0)
    for bad in ({"cot_samples": "3"}, {"cot_temperature": "warm"}, {"cot_problems": 49.5}):
        dial = next(iter(bad))
        with pytest.raises(ConfigError) as error:
            check_dials({"method": "cotgen", "split": "train", **bad})
        assert dial in str(error.value), str(error.value)
