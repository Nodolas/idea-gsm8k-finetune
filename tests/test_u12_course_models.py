"""u12-learning-course, part M: course models and QLoRA in the commands (US12.4; contracts C1, C2, C5, C9).

Covers AC12.4.1 (command side: a course attempt id is accepted as a run id, the run folder and adapter
folder follow it, the row goes to the `--results` file), AC12.4.2 (the three course-only models, pinned
revisions, refused outside base runs with a course id) and AC12.4.3 (`quantize`, its place in the hash,
the quantized-load seam `train_cmd.load_quantized_model(model_id, revision) -> (model, tokenizer)`).

Every run uses the tiny random-weight model from conftest (deep-copied for training), patched loaders, a
temp outputs/checkpoints folder and a temp results file standing in for `outputs/course/runs.csv`. No
real weights are loaded, the GPU is never used and results/runs.csv is never written.
"""

import copy
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROJECT_RESULTS = ROOT / "results" / "runs.csv"

QWEN_SMALL = "Qwen/Qwen3-0.6B-Base"
PYTHIA = "EleutherAI/pythia-31m"
SMOL = "HuggingFaceTB/SmolLM2-360M"
QWEN25 = "Qwen/Qwen2.5-0.5B"
COURSE_REVISIONS = {
    PYTHIA: "e556ace21b489575e94e9d50b6dad2fcc7419679",
    SMOL: "f8027fd0eaeea54caa13c31d31b9fdc459c38b49",
    QWEN25: "060db6499f32faf8b98477b0a26969ef7d8b9987",
}
QWEN_SMALL_REVISION = "da87bfb608c14b7cf20ba1ce41287e8de496c0cd"

EVAL_ARGS = ["--split", "dev", "--limit", "1", "--max-new-tokens", "4"]
TRAIN_ARGS = [
    "--train-examples",
    "50",
    "--max-steps",
    "2",
    "--limit",
    "1",
    "--max-seq-len",
    "256",
    "--batch-size",
    "2",
    "--lora-rank",
    "4",
    "--max-new-tokens",
    "4",
]
BAD_COURSE_IDS = [
    "course-x1-a-1",  # the step part must be c<two digits>
    "course-c1-base-1",  # one digit
    "course-c001-base-1",  # three digits
    "course-c01-base-06",  # no attempt number after the run name
    "course-c01-base-06-x",  # the attempt number is digits
    "course-c01-Base-1",  # upper case
    "course-c01-base/06-1",  # not a safe folder name
    "course-c01--1",  # no run name
]


def _run_cli(argv: list[str]) -> int:
    """Call the command in-process; an argparse exit counts as its exit code."""
    from gsm8k.cli import main

    try:
        return main(argv)
    except SystemExit as exc:  # argparse rejects bad options with SystemExit(2)
        return exc.code if isinstance(exc.code, int) else 1


def _file_state(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _read_csv(path: Path) -> list[dict[str, str]]:
    import csv

    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture
def project_results_untouched():
    """The real results/runs.csv must be byte-for-byte the same after the test."""
    before = _file_state(PROJECT_RESULTS)
    yield
    assert _file_state(PROJECT_RESULTS) == before, "results/runs.csv was changed by a test"


@pytest.fixture
def course_results(tmp_project_dirs) -> Path:
    """A temporary stand-in for outputs/course/runs.csv (not created)."""
    return tmp_project_dirs.outputs / "course" / "runs.csv"


@pytest.fixture
def eval_loads(monkeypatch, tiny_model) -> list[tuple]:
    """Every evaluation model load returns the tiny model and records (model, revision, adapter)."""
    import gsm8k.evaluation

    calls: list[tuple] = []

    def fake_load_model(model_id, revision, adapter_path=None):
        calls.append((model_id, revision, adapter_path))
        return tiny_model

    monkeypatch.setattr(gsm8k.evaluation, "load_model", fake_load_model)
    return calls


@pytest.fixture
def train_loads(monkeypatch, tiny_model) -> dict[str, list[tuple]]:
    """Training loads: the plain load and the quantized-load seam each return a fresh copy of the tiny
    model and record their arguments; evaluation loads (the closing dev score) do the same."""
    import gsm8k.datasets_prompts.hub
    import gsm8k.evaluation
    import gsm8k.train_cmd

    calls: dict[str, list[tuple]] = {"base": [], "quantized": [], "eval": []}

    def fresh():
        model, tokenizer = tiny_model
        return copy.deepcopy(model), copy.deepcopy(tokenizer)

    def fake_base(model_id, revision):
        calls["base"].append((model_id, revision))
        return fresh()

    def fake_quantized(model_id, revision):
        calls["quantized"].append((model_id, revision))
        return fresh()

    def fake_eval(model_id, revision, adapter_path=None):
        calls["eval"].append((model_id, revision, adapter_path))
        return fresh()

    def no_real_weights(*args, **kwargs):
        raise AssertionError("a test tried to load real model weights")

    monkeypatch.setattr(gsm8k.train_cmd, "load_base_model", fake_base)
    # raising=False: the tests that do not use the seam fail on their own criterion until it exists; the
    # quantize tests then fail because the seam is never asked.
    monkeypatch.setattr(gsm8k.train_cmd, "load_quantized_model", fake_quantized, raising=False)
    monkeypatch.setattr(gsm8k.evaluation, "load_model", fake_eval)
    monkeypatch.setattr(gsm8k.datasets_prompts.hub, "load_causal_lm", no_real_weights)
    return calls


def _nothing_written(dirs, results: Path, run_id: str) -> None:
    assert not (dirs.outputs / run_id).exists(), "a run folder was written"
    assert not (dirs.checkpoints / run_id).exists(), "an adapter folder was written"
    assert not results.exists(), "the results file was written"


# --- AC12.4.1: course attempt ids -----------------------------------------------------------------


def test_AC12_4_1_course_attempt_id_passes_the_run_id_checks():
    from gsm8k import cli
    from gsm8k.run_records import paths

    for run_id in ("course-c01-base-06-1", "course-c21-sft-1", "course-c22-selfcot-12", "course-c23-grpo-1"):
        paths.check_run_id(run_id)  # raises ValueError when invalid
        assert paths.RUN_ID_PATTERN.fullmatch(run_id), run_id
        assert cli.ATTEMPT_ID_PATTERN.fullmatch(run_id), run_id
    # The existing ids still pass, and an ad-hoc id is still not an attempt id.
    paths.check_run_id("q06-base-dev-1")
    assert cli.ATTEMPT_ID_PATTERN.fullmatch("q17-sft-dev-2")
    assert not cli.ATTEMPT_ID_PATTERN.fullmatch("adhoc-20261101-201530")


def test_AC12_4_1_invalid_course_ids_are_refused_by_the_run_id_checks():
    from gsm8k import cli
    from gsm8k.run_records import paths

    for run_id in BAD_COURSE_IDS:
        with pytest.raises(ValueError):
            paths.check_run_id(run_id)
        assert not cli.ATTEMPT_ID_PATTERN.fullmatch(run_id), run_id


def test_AC12_4_1_course_run_folder_is_outputs_attempt_id(tmp_project_dirs):
    from gsm8k.run_records import paths

    assert paths.run_dir("course-c05-pythia-1") == tmp_project_dirs.outputs / "course-c05-pythia-1"


def test_AC12_4_1_evaluate_takes_a_course_attempt_id_and_appends_to_the_results_file(
    tmp_project_dirs, course_results, eval_loads, capsys, project_results_untouched
):
    run_id = "course-c01-base-06-1"
    rc = _run_cli(["evaluate", *EVAL_ARGS, "--run-id", run_id, "--results", str(course_results)])
    text = "".join(capsys.readouterr())
    assert rc == 0, text

    run_dir = tmp_project_dirs.outputs / run_id
    assert run_dir.is_dir()
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    assert config["run_id"] == run_id
    status = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
    assert (status["status"], status["exit_code"], status["run_id"]) == ("finished", 0, run_id)

    rows = _read_csv(course_results)
    assert [r["run_id"] for r in rows] == [run_id]
    assert rows[0]["model"] == QWEN_SMALL
    assert rows[0]["method"] == "base"
    assert eval_loads == [(QWEN_SMALL, QWEN_SMALL_REVISION, None)]
    # Nothing but the run folder and the course results file was written under outputs/.
    assert sorted(p.name for p in tmp_project_dirs.outputs.iterdir()) == ["course", run_id]
    assert sorted(p.name for p in course_results.parent.iterdir()) == ["runs.csv"]


def test_AC12_4_1_evaluate_refuses_invalid_course_ids_and_writes_nothing(
    tmp_project_dirs, course_results, eval_loads, capsys, project_results_untouched
):
    for run_id in BAD_COURSE_IDS:
        rc = _run_cli(["evaluate", *EVAL_ARGS, "--run-id", run_id, "--results", str(course_results)])
        text = "".join(capsys.readouterr())
        assert rc == 2, f"{run_id}: exit {rc}\n{text}"
        assert not course_results.exists(), run_id
        assert [p.name for p in tmp_project_dirs.outputs.iterdir()] == [], run_id
    assert eval_loads == []


def test_AC12_4_1_train_takes_a_course_attempt_id_and_writes_run_and_adapter_folders(
    tmp_project_dirs, course_results, train_loads, capsys, project_results_untouched
):
    run_id = "course-c21-sft-1"
    rc = _run_cli(["train", *TRAIN_ARGS, "--run-id", run_id, "--results", str(course_results)])
    text = "".join(capsys.readouterr())
    assert rc == 0, text

    run_dir = tmp_project_dirs.outputs / run_id
    adapter = tmp_project_dirs.checkpoints / run_id
    assert (run_dir / "config.json").is_file()
    assert (run_dir / "metrics.jsonl").is_file()
    assert (adapter / "adapter_config.json").is_file()
    status = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
    assert (status["status"], status["exit_code"], status["run_id"]) == ("finished", 0, run_id)

    rows = _read_csv(course_results)
    assert [r["run_id"] for r in rows] == [run_id]
    assert rows[0]["method"] == "sft"
    assert [p.name for p in tmp_project_dirs.checkpoints.iterdir()] == [run_id]


def test_AC12_4_1_train_refuses_invalid_course_ids_and_writes_nothing(
    tmp_project_dirs, course_results, train_loads, capsys, project_results_untouched
):
    for run_id in BAD_COURSE_IDS:
        rc = _run_cli(["train", *TRAIN_ARGS, "--run-id", run_id, "--results", str(course_results)])
        text = "".join(capsys.readouterr())
        assert rc == 2, f"{run_id}: exit {rc}\n{text}"
        assert not course_results.exists(), run_id
        assert [p.name for p in tmp_project_dirs.outputs.iterdir()] == [], run_id
        assert [p.name for p in tmp_project_dirs.checkpoints.iterdir()] == [], run_id
    assert train_loads["base"] == [] and train_loads["quantized"] == []


# --- AC12.4.2: the three course-only models --------------------------------------------------------


def test_AC12_4_2_course_model_revisions_are_the_table_pins():
    from gsm8k.datasets_prompts import hub

    assert dict(hub.COURSE_MODEL_REVISIONS) == COURSE_REVISIONS
    # The project models keep their own pins and gain nothing.
    assert set(hub.MODEL_REVISIONS) == {QWEN_SMALL, "Qwen/Qwen3-1.7B-Base"}
    assert hub.MODEL_REVISIONS[QWEN_SMALL] == QWEN_SMALL_REVISION


def test_AC12_4_2_models_stay_the_two_project_models_and_course_only_models_are_the_three():
    from gsm8k import run_config

    assert run_config.MODELS == (QWEN_SMALL, "Qwen/Qwen3-1.7B-Base")
    assert set(run_config.COURSE_ONLY_MODELS) == set(COURSE_REVISIONS)
    assert len(run_config.COURSE_ONLY_MODELS) == 3


def test_AC12_4_2_hub_loads_a_course_model_at_its_pinned_revision(monkeypatch, tiny_model):
    import torch
    import transformers

    from gsm8k.datasets_prompts import hub

    seen: list[tuple[str, str, str | None]] = []

    def fake_tokenizer(model_id, revision=None, **kwargs):
        seen.append(("tokenizer", model_id, revision))
        return tiny_model[1]

    def fake_causal_lm(model_id, revision=None, **kwargs):
        seen.append(("model", model_id, revision))
        assert kwargs.get("trust_remote_code") is False
        assert kwargs.get("use_safetensors") is True
        return tiny_model[0]

    monkeypatch.setattr(transformers.AutoTokenizer, "from_pretrained", fake_tokenizer)
    monkeypatch.setattr(transformers.AutoModelForCausalLM, "from_pretrained", fake_causal_lm)

    for model_id, revision in COURSE_REVISIONS.items():
        hub.load_tokenizer(model_id, revision)
        hub.load_causal_lm(model_id, revision, torch.float32)
    expected = []
    for model_id, revision in COURSE_REVISIONS.items():
        expected += [("tokenizer", model_id, revision), ("model", model_id, revision)]
    assert seen == expected
    with pytest.raises(ValueError):  # an unknown model is still refused
        hub.load_tokenizer("someone/else-7b", "a" * 40)


def test_AC12_4_2_run_config_resolves_the_course_revision_and_validates_a_course_run():
    from gsm8k import run_config

    for model_id, revision in COURSE_REVISIONS.items():
        cfg = run_config.RunConfig(run_id="course-c05-pythia-1", model=model_id)
        assert cfg.model_revision == revision
        run_config.validate(cfg)  # a base run with a course attempt id is accepted
        checked = run_config.check_dials({"model": model_id}, run_id="course-c04-base-1")
        assert checked.model == model_id and checked.model_revision == revision


def test_AC12_4_2_run_config_refuses_a_course_model_for_a_project_run_id():
    from gsm8k import run_config

    cfg = run_config.RunConfig(run_id="q06-base-dev-1", model=PYTHIA)
    with pytest.raises(run_config.ConfigError) as exc:
        run_config.validate(cfg)
    assert PYTHIA in str(exc.value)
    with pytest.raises(run_config.ConfigError) as exc:
        run_config.check_dials({"model": SMOL}, run_id="q06-base-dev-1")
    assert SMOL in str(exc.value)
    with pytest.raises(run_config.ConfigError):  # no run id given: not a course attempt id either
        run_config.check_dials({"model": QWEN25})


def test_AC12_4_2_run_config_refuses_a_course_model_for_any_method_but_base():
    from gsm8k import run_config

    for method in ("sft", "grpo", "best", "terse", "vote", "calc", "optuna", "selfcot"):
        cfg = run_config.RunConfig(run_id="course-c21-sft-1", model=PYTHIA, method=method)
        with pytest.raises(run_config.ConfigError) as exc:
            run_config.validate(cfg)
        assert PYTHIA in str(exc.value), (method, str(exc.value))
    with pytest.raises(run_config.ConfigError) as exc:  # cotgen (split train) is not base either
        run_config.validate(run_config.RunConfig(run_id="course-c22-cotgen-1", model=QWEN25, method="cotgen"))
    assert QWEN25 in str(exc.value)
    with pytest.raises(run_config.ConfigError):  # an unknown model is refused as before
        run_config.validate(run_config.RunConfig(run_id="course-c05-x-1", model="someone/else-7b"))


@pytest.mark.parametrize("model_id", sorted(COURSE_REVISIONS))
def test_AC12_4_2_evaluate_loads_a_course_model_at_the_pinned_revision(
    model_id, tmp_project_dirs, course_results, eval_loads, capsys, project_results_untouched
):
    run_id = "course-c05-base-1"
    rc = _run_cli(
        ["evaluate", "--model", model_id, *EVAL_ARGS, "--run-id", run_id, "--results", str(course_results)]
    )
    text = "".join(capsys.readouterr())
    assert rc == 0, text
    assert eval_loads == [(model_id, COURSE_REVISIONS[model_id], None)]
    config = json.loads((tmp_project_dirs.outputs / run_id / "config.json").read_text(encoding="utf-8"))
    assert config["model"] == model_id
    assert config["model_revision"] == COURSE_REVISIONS[model_id]
    assert config["method"] == "base"
    rows = _read_csv(course_results)
    assert [(r["run_id"], r["model"], r["method"]) for r in rows] == [(run_id, model_id, "base")]


def test_AC12_4_2_a_course_model_row_is_read_back_by_the_run_log_reader(
    tmp_project_dirs, course_results, eval_loads, capsys
):
    """C1 lets course rows carry the course-only models; the reader must not skip them as malformed."""
    from gsm8k.run_records import log

    run_id = "course-c05-pythia-1"
    rc = _run_cli(
        ["evaluate", "--model", PYTHIA, *EVAL_ARGS, "--run-id", run_id, "--results", str(course_results)]
    )
    assert rc == 0, "".join(capsys.readouterr())
    rows, skipped = log.read_rows(course_results)
    assert skipped == 0
    assert [(r.run_id, r.model, r.method) for r in rows] == [(run_id, PYTHIA, "base")]
    assert log.has_run_id(course_results, run_id)


def test_AC12_4_2_evaluate_refuses_a_course_model_for_a_project_run_id(
    tmp_project_dirs, course_results, eval_loads, capsys, project_results_untouched
):
    run_id = "q06-base-dev-1"
    rc = _run_cli(
        ["evaluate", "--model", PYTHIA, *EVAL_ARGS, "--run-id", run_id, "--results", str(course_results)]
    )
    text = "".join(capsys.readouterr())
    assert rc == 2, text
    assert PYTHIA in text
    assert eval_loads == []
    _nothing_written(tmp_project_dirs, course_results, run_id)


def test_AC12_4_2_evaluate_refuses_a_course_model_without_a_run_id(tmp_project_dirs, eval_loads, capsys):
    rc = _run_cli(["evaluate", "--model", SMOL, *EVAL_ARGS])
    text = "".join(capsys.readouterr())
    assert rc == 2, text
    assert SMOL in text
    assert eval_loads == []
    assert [p.name for p in tmp_project_dirs.outputs.iterdir()] == []


def test_AC12_4_2_evaluate_refuses_a_course_model_for_method_best(
    tmp_project_dirs, course_results, eval_loads, capsys
):
    run_id = "course-c05-best-1"
    rc = _run_cli(
        ["evaluate", "--model", PYTHIA, "--method", "best", *EVAL_ARGS, "--run-id", run_id]
        + ["--results", str(course_results)]
    )
    text = "".join(capsys.readouterr())
    assert rc == 2, text
    assert PYTHIA in text
    _nothing_written(tmp_project_dirs, course_results, run_id)


def test_AC12_4_2_train_refuses_a_course_model_for_method_sft(
    tmp_project_dirs, course_results, train_loads, capsys, project_results_untouched
):
    for run_id in ("course-c21-sft-1", "q06-sft-dev-1"):
        rc = _run_cli(
            ["train", "--model", PYTHIA, *TRAIN_ARGS, "--run-id", run_id, "--results", str(course_results)]
        )
        text = "".join(capsys.readouterr())
        assert rc == 2, f"{run_id}: {text}"
        assert PYTHIA in text, f"{run_id}: {text}"
        _nothing_written(tmp_project_dirs, course_results, run_id)
    assert train_loads["base"] == [] and train_loads["quantized"] == []


# --- AC12.4.3: quantize ---------------------------------------------------------------------------


def _known_hash(data: dict) -> str:
    """The C2 hash rule written out: sha256 of the compact, key-sorted JSON of the hashed fields."""
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def test_AC12_4_3_quantize_defaults_to_none_and_is_a_config_field():
    from gsm8k import run_config

    cfg = run_config.RunConfig(run_id="q06-base-dev-1")
    assert cfg.quantize == "none"
    assert run_config.to_dict(cfg)["quantize"] == "none"
    assert run_config.from_dict({"run_id": "q06-sft-dev-1", "quantize": "4bit"}).quantize == "4bit"
    assert run_config.from_dict({"run_id": "q06-sft-dev-1"}).quantize == "none"  # older config.json files


def test_AC12_4_3_the_default_quantize_leaves_every_earlier_hash_unchanged():
    from gsm8k import run_config

    base = run_config.RunConfig(run_id="q06-base-dev-1")
    assert run_config.config_hash(base) == _known_hash({"model": QWEN_SMALL, "method": "base"})
    sft = run_config.RunConfig(run_id="q06-sft-dev-1", method="sft", limit=5, learning_rate=1e-4, lora_rank=8)
    assert run_config.config_hash(sft) == _known_hash(
        {"model": QWEN_SMALL, "method": "sft", "limit": 5, "learning_rate": 1e-4, "lora_rank": 8}
    )
    # Written out as "none" it is still the default, so still out of the hash.
    explicit = run_config.RunConfig(run_id="q06-base-dev-1", quantize="none")
    assert run_config.config_hash(explicit) == run_config.config_hash(base)


def test_AC12_4_3_4bit_changes_the_hash():
    from gsm8k import run_config

    plain = run_config.RunConfig(run_id="q06-sft-dev-1", method="sft")
    quantized = run_config.RunConfig(run_id="q06-sft-dev-1", method="sft", quantize="4bit")
    assert run_config.config_hash(quantized) != run_config.config_hash(plain)
    assert run_config.config_hash(quantized) == _known_hash(
        {"model": QWEN_SMALL, "method": "sft", "quantize": "4bit"}
    )


def test_AC12_4_3_quantize_is_checked_and_names_the_field():
    from gsm8k import run_config

    for method in ("sft", "selfcot", "grpo"):
        cfg = run_config.RunConfig(run_id="q06-sft-dev-1", method=method, quantize="4bit")
        run_config.validate(cfg)  # sft, selfcot and grpo may be quantized
    for method in ("base", "best", "terse", "vote", "calc", "optuna"):
        cfg = run_config.RunConfig(run_id="q06-base-dev-1", method=method, quantize="4bit")
        with pytest.raises(run_config.ConfigError) as exc:
            run_config.validate(cfg)
        assert "quantize" in str(exc.value), (method, str(exc.value))
    cot = run_config.RunConfig(run_id="q06-cotgen-train-1", method="cotgen", split="train", quantize="4bit")
    with pytest.raises(run_config.ConfigError) as exc:
        run_config.validate(cot)
    assert "quantize" in str(exc.value)
    with pytest.raises(run_config.ConfigError) as exc:
        run_config.validate(run_config.RunConfig(run_id="q06-sft-dev-1", method="sft", quantize="8bit"))
    assert "quantize" in str(exc.value)


def test_AC12_4_3_check_dials_takes_quantize_and_checks_its_type():
    from gsm8k import run_config

    cfg = run_config.check_dials({"method": "sft", "quantize": "4bit"}, run_id="q06-sft-dev-1")
    assert cfg.quantize == "4bit"
    with pytest.raises(run_config.ConfigError) as exc:
        run_config.check_dials({"method": "base", "quantize": "4bit"}, run_id="q06-base-dev-1")
    assert "quantize" in str(exc.value)
    with pytest.raises(run_config.ConfigError) as exc:
        run_config.check_dials({"method": "sft", "quantize": 4}, run_id="q06-sft-dev-1")
    assert "quantize" in str(exc.value)


def test_AC12_4_3_evaluate_refuses_a_quantized_config_naming_the_field(
    tmp_project_dirs, tmp_path, eval_loads, capsys, project_results_untouched
):
    from gsm8k import run_config

    run_id = "q06-base-dev-1"
    cfg = run_config.RunConfig(run_id=run_id, quantize="4bit")
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(run_config.to_dict(cfg)), encoding="utf-8")
    rc = _run_cli(
        [
            "evaluate",
            "--config",
            str(config_file),
            "--run-id",
            run_id,
            "--results",
            str(tmp_project_dirs.results),
        ]
    )
    text = "".join(capsys.readouterr())
    assert rc == 2, text
    assert "quantize" in text
    assert eval_loads == []
    _nothing_written(tmp_project_dirs, tmp_project_dirs.results, run_id)


def test_AC12_4_3_train_quantize_4bit_asks_the_quantized_load_seam(
    tmp_project_dirs, course_results, train_loads, capsys, project_results_untouched
):
    from gsm8k import run_config

    run_id = "course-c20-qlora-1"
    rc = _run_cli(
        ["train", "--quantize", "4bit", *TRAIN_ARGS, "--run-id", run_id, "--results", str(course_results)]
    )
    text = "".join(capsys.readouterr())
    assert rc == 0, text
    assert train_loads["quantized"] == [(QWEN_SMALL, QWEN_SMALL_REVISION)]
    assert train_loads["base"] == []  # the plain load is not also made

    run_dir = tmp_project_dirs.outputs / run_id
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    assert config["quantize"] == "4bit"
    assert config["method"] == "sft"
    # The row's hash covers it: the hash of the written configuration, which differs from "none".
    dials = {
        "model": QWEN_SMALL,
        "method": "sft",
        "train_examples": 50,
        "lora_rank": 4,
        "max_seq_len": 256,
        "batch_size": 2,
        "limit": 1,
        "max_new_tokens": 4,
    }
    row = _read_csv(course_results)[0]
    assert row["run_id"] == run_id
    assert row["config_hash"] == run_config.config_hash(run_config.from_dict(config))
    assert row["config_hash"] == _known_hash({**dials, "quantize": "4bit"})
    assert row["config_hash"] != _known_hash(dials)
    assert (tmp_project_dirs.checkpoints / run_id / "adapter_config.json").is_file()


def test_AC12_4_3_train_quantize_none_and_the_default_never_ask_the_seam(
    tmp_project_dirs, course_results, train_loads, capsys, project_results_untouched
):
    results = tmp_project_dirs.results
    rc = _run_cli(["train", *TRAIN_ARGS, "--run-id", "q06-sft-dev-1", "--results", str(results)])
    text = "".join(capsys.readouterr())
    assert rc == 0, text
    rc = _run_cli(
        ["train", "--quantize", "none", *TRAIN_ARGS, "--run-id", "q06-sft-dev-2", "--results", str(results)]
    )
    text = "".join(capsys.readouterr())
    assert rc == 0, text
    assert train_loads["quantized"] == []
    assert train_loads["base"] == [(QWEN_SMALL, QWEN_SMALL_REVISION)] * 2
    config = json.loads((tmp_project_dirs.outputs / "q06-sft-dev-2" / "config.json").read_text("utf-8"))
    assert config["quantize"] == "none"
    # At its default it stays out of the hash: both rows hash the same configuration.
    rows = _read_csv(results)
    assert rows[0]["config_hash"] == rows[1]["config_hash"]
    assert rows[0]["config_hash"] == _known_hash(
        {
            "model": QWEN_SMALL,
            "method": "sft",
            "train_examples": 50,
            "lora_rank": 4,
            "max_seq_len": 256,
            "batch_size": 2,
            "limit": 1,
            "max_new_tokens": 4,
        }
    )


def test_AC12_4_3_train_refuses_an_unknown_quantize_value(
    tmp_project_dirs, course_results, train_loads, capsys, project_results_untouched
):
    run_id = "course-c20-qlora-1"
    rc = _run_cli(
        ["train", "--quantize", "8bit", *TRAIN_ARGS, "--run-id", run_id, "--results", str(course_results)]
    )
    capsys.readouterr()
    assert rc == 2
    _nothing_written(tmp_project_dirs, course_results, run_id)
    assert train_loads["quantized"] == [] and train_loads["base"] == []


# --- AC12.4.1: course rows in the run log (C1) -------------------------------------------------------


def _row(run_id: str, model: str, method: str = "base"):
    from gsm8k.run_records import log

    return log.RunRow(
        date="2026-11-16T10:00:00Z",
        run_id=run_id,
        model=model,
        method=method,
        data="gsm8k-dev",
        metric="accuracy",
        value=0.25,
        minutes=1.5,
        config_hash="0" * 64,
    )


def test_AC12_4_1_course_rows_with_course_models_are_read(tmp_path):
    from gsm8k.run_records import log

    course = tmp_path / "outputs" / "course" / "runs.csv"
    rows = [
        _row("course-c05-pythia-1", PYTHIA),
        _row("course-c05-smollm2-1", SMOL),
        _row("course-c05-qwen25-1", QWEN25),
        _row("course-c05-qwen3-1", QWEN_SMALL),
        _row("course-c21-sft-1", QWEN_SMALL, method="sft"),
    ]
    for row in rows:
        log.append_row(course, row)
    read, skipped = log.read_rows(course)
    assert skipped == 0
    assert [(r.run_id, r.model, r.method) for r in read] == [(r.run_id, r.model, r.method) for r in rows]
    assert log.has_run_id(course, "course-c05-pythia-1")


def test_AC12_4_1_a_course_only_model_row_with_a_project_run_id_is_still_skipped(tmp_path):
    from gsm8k.run_records import log

    path = tmp_path / "runs.csv"
    log.append_row(path, _row("q06-base-dev-1", QWEN_SMALL))  # a normal row stays
    log.append_row(path, _row("q06-base-dev-2", PYTHIA))  # course-only model, project run id
    log.append_row(path, _row("q17-base-dev-3", SMOL))
    log.append_row(path, _row("course-c21-sft-2", PYTHIA, method="sft"))  # course-only models are base only
    log.append_row(path, _row("course-c05-pythia-2", PYTHIA))  # a valid course row stays
    read, skipped = log.read_rows(path)
    assert [r.run_id for r in read] == ["q06-base-dev-1", "course-c05-pythia-2"]
    assert skipped == 3
