# batch-1: u1-eval-skeleton

Branch `wip/batch-1`. Spec at approved commit 37fb5a4 (`STATE.md` `approved_spec_commit`). `test_command`: `scripts/check.sh` (Ruff, then pytest with coverage on `src/gsm8k`, failing under 80%, all on the CPU through `scripts/in-env.sh`). Every project tool runs through `scripts/in-env.sh` (e.g. `scripts/in-env.sh .venv/bin/python -m pytest tests/test_u1_data.py -q`).

## Spec to read

`S` = `aidlc/spaces/default/intents/261030-gsm8k-finetune`.
- Criteria: `S/inception/user-stories/stories.md` US1.1–US1.4 (AC1.1.1–AC1.4.6), and its Conventions (quick tests, tiny model fixture, results file).
- Requirements: `S/inception/requirements-analysis/requirements.md` FR1.1–FR1.7, NFR3, NFR5–NFR8.
- Design: `S/inception/domain-design/components.md` (DatasetsAndPrompts, AnswerScoring, RunConfiguration, RunRecords, Evaluation, RunCommands), `S/inception/domain-design/decisions.md`.
- Contracts: `S/inception/contract-design/contract-summary.md` C1 (run log), C2 (run folder, `config.json` fields and the hash rule), C3 (lock part only), C5 (`gsm8k evaluate` arguments and exit codes).
- u1 design (Nico's answers there are decided): `S/construction/u1-eval-skeleton/functional-design/{functional-spec.md,rules.md,entities.md,functional-design-questions.md}`, `S/construction/u1-eval-skeleton/nfr-requirements/{security-requirements.md,tech-stack-decisions.md,nfr-requirements-questions.md}`, `S/construction/u1-eval-skeleton/nfr-design/{security-design.md,logical-components.md,nfr-design-questions.md}`. Rules BR1.1–BR5.4 are in `rules.md`.
- Dial defaults and ranges for `RunConfig`: stories.md "Training Dials".

## Criteria

- AC1.1.1, AC1.1.2, AC1.1.3, AC1.1.4, AC1.1.5 (US1.1)
- AC1.2.1, AC1.2.2, AC1.2.3 (US1.2)
- AC1.3.1, AC1.3.2, AC1.3.3, AC1.3.4 (US1.3)
- AC1.4.1 (walking skeleton: the real `Qwen/Qwen3-0.6B-Base` on the CPU, 3 dev problems, 256 new tokens), AC1.4.2, AC1.4.3, AC1.4.4, AC1.4.5, AC1.4.6 (US1.4)
- No `[manual]` criterion in u1. The 0.6B baseline long runs are u2's.

## Rules for every part

- Tests run on the CPU (`scripts/in-env.sh` hides the GPU). Only the AC1.4.1 test loads real model weights; every other test that runs a model uses the `tiny_model` fixture from `tests/conftest.py` and monkeypatches `gsm8k.evaluation.load_model`.
- No test touches the project's `outputs/`, `checkpoints/` or `results/runs.csv`: use the `tmp_project_dirs` fixture (sets `GSM8K_OUTPUTS_DIR` and `GSM8K_CHECKPOINTS_DIR` to temp folders) and pass `--results <tmp path>`. A detached long run may hold the real `outputs/run.lock` while tests run.
- Tests are named by criterion ID: `test_AC1_3_1_strips_commas`. A few helper tests for code paths no criterion names are fine, named after the closest criterion of this unit.
- Python 3.12, Ruff-clean (`scripts/in-env.sh .venv/bin/ruff check src tests` and `ruff format`), snake_case. English only.
- Imports between parts use full module paths (`from gsm8k.run_records.paths import outputs_root`); the subpackage `__init__.py` files stay empty.

## Interfaces (the contract between the parts)

Owned by the lead (written in shared setup):
- `gsm8k/_env.py`: `ROOT: Path` (project root); `setup_env() -> None` sets the six cache variables to absolute paths under `ROOT` (BR1.1), `HF_HUB_DISABLE_TELEMETRY=1`, and removes `HF_TOKEN` and `HUGGING_FACE_HUB_TOKEN` from the environment (NFR6.2). `gsm8k/__init__.py` calls it first, so importing any `gsm8k` module sets the caches before torch, transformers or datasets load.

Part A, data (`gsm8k.datasets_prompts`):
- `hub.py`: `DATASET_ID = "openai/gsm8k"`, `DATASET_CONFIG = "main"`, `DATASET_REVISION: str`, `MODEL_REVISIONS: dict[str, str]` for `Qwen/Qwen3-0.6B-Base` and `Qwen/Qwen3-1.7B-Base` (commit hashes resolved from the Hub once and written in the code); `@dataclass(frozen=True) Problem(id: str, question: str, answer: str, gold: str)` (`gold` = the number after `####`, as written); `load_gsm8k(revision: str = DATASET_REVISION) -> dict[str, list[Problem]]` with keys `"train"` and `"test"`, ids `gsm8k-train-<i>` / `gsm8k-test-<i>` by row order; `load_tokenizer(model_id: str, revision: str)`; `load_causal_lm(model_id: str, revision: str, dtype)`: safetensors only, `trust_remote_code=False`. This module is the only Hub access.
- `split.py`: `SPLIT_SEED = 42`, `DEV_SIZE = 500`; `@dataclass Split(dev_ids: list[str], train_ids: list[str], split_seed: int)`; `class SplitFileError(Exception)` with message `Split file could not be read: <path>`; `build_split(train_ids: list[str], split_seed: int = SPLIT_SEED) -> Split` (BR1.3); `validate_split(split: Split, all_train_ids: list[str]) -> None` (BR1.4, BR1.5; raises `ValueError`); `split_path(split_seed: int = SPLIT_SEED) -> Path` = `outputs_root() / "splits" / f"gsm8k-split{split_seed}.json"`; `load_or_build_split(train_ids: list[str], path: Path | None = None, split_seed: int = SPLIT_SEED) -> Split` (BR1.6; atomic save).
- `prompt.py`: `choose_exemplars(dev_ids: list[str], split_seed: int = SPLIT_SEED) -> list[str]` (BR2.1); `strip_calculator_notes(text: str) -> str`; `build_prompt(exemplars: list[Problem], question: str) -> str` (BR2.3); `problems_to_score(split_name: str, split: Split, problems: dict[str, list[Problem]], exemplar_ids: list[str], limit: int | None = None) -> list[Problem]` (BR2.2; `split_name` is `"dev"` or `"test"`).

Part B, scoring, configuration and run records:
- `scoring.py`: `cut_output(text: str) -> str` (BR3.5 cut: end of the first line with `#### <number>`, or before a new `Question:`); `extract_answer(text: str) -> str | None` (BR3.1–BR3.3); `is_correct(predicted: str | None, gold: str) -> bool` (BR3.4); `score(output: str, gold: str) -> tuple[str | None, bool]` (cut, extract, compare).
- `run_config.py`: `@dataclass RunConfig` with every C2 `config.json` field (including `v`, `run_id`, `split_seed`, `model_revision`, `dataset_revision`, `max_new_tokens`) and documented defaults (model `Qwen/Qwen3-0.6B-Base`, method `base`, split `dev`, revisions = the pins in `hub.py`, dials from stories.md "Training Dials"); `class ConfigError(Exception)` naming the dial and its allowed range; `validate(cfg: RunConfig) -> None`; `config_hash(cfg: RunConfig) -> str` (BR4.5); `to_dict(cfg) -> dict`; `from_dict(d: dict) -> RunConfig` (unknown keys ignored); `read_config(path: Path) -> RunConfig`.
- `run_records/paths.py`: `outputs_root() -> Path` (`$GSM8K_OUTPUTS_DIR` or `ROOT/outputs`); `checkpoints_root() -> Path` (`$GSM8K_CHECKPOINTS_DIR` or `ROOT/checkpoints`); `DEFAULT_RESULTS: Path` = `ROOT/results/runs.csv`; `run_dir(run_id: str) -> Path`; `RUN_ID_PATTERN` (C1, plus `adhoc-<UTC timestamp>` for runs without `--run-id`); `check_run_id(run_id: str) -> None` (raises `ValueError`); `resolve_adapter(path: str) -> Path` (must exist and lie under `checkpoints_root()`; raises `FileNotFoundError("Adapter not found: <path>")` or `ValueError`).
- `run_records/log.py`: `COLUMNS` (C1 order); `@dataclass RunRow` (C1 fields; `adapter_run` default `""`); `append_row(path: Path, row: RunRow) -> None` (creates the file with a header, one whole line per append); `read_rows(path: Path) -> tuple[list[RunRow], int]` (rows, skipped count; missing file -> `([], 0)`; unreadable -> `OSError` naming the file); `has_run_id(path: Path, run_id: str) -> bool`.
- `run_records/folder.py`: `atomic_write_text(path: Path, text: str) -> None`; `write_config(run_dir: Path, cfg: RunConfig) -> None`; `append_prediction(run_dir: Path, record: dict) -> None` (`predictions.jsonl`: problem_id, output, predicted, gold, correct); `write_timings(run_dir: Path, *, seconds_per_problem: float | None, seconds_per_step: float | None = None, peak_gpu_memory_gb: float) -> None`; `write_status(run_dir: Path, *, run_id: str, status: str, exit_code: int, reason: str | None) -> None`; `run_already_happened(run_dir: Path) -> bool` (BR5.3).
- `run_records/lock.py`: `lock_path() -> Path` = `outputs_root() / "run.lock"`; `class LockHeld(Exception)` with `.run_id`; `class GpuLock` with `acquire(run_id: str, started_by: str = "terminal") -> None` (raises `LockHeld`), `release() -> None`, context-manager use; `read_lock(path: Path | None = None) -> dict | None`; `is_free(path: Path | None = None) -> bool` (C3, BR5.1).

Part C, evaluation and the command:
- `evaluation.py`: `load_model(model_id: str, revision: str, adapter_path: Path | None = None) -> tuple[model, tokenizer]` (bfloat16 on CUDA, float32 on the CPU; through `hub.py`); `generate(model, tokenizer, prompts: list[str], max_new_tokens: int = 512) -> list[str]` (greedy, BR3.5 stop rule); `@dataclass EvalResult(accuracy: float, scored: int, correct: int, seconds_per_problem: float, peak_gpu_memory_gb: float)`; `evaluate(model, tokenizer, problems: list[Problem], prompt_for: Callable[[Problem], str], *, batch_size: int = 8, max_new_tokens: int = 512, on_prediction: Callable[[dict], None] | None = None) -> EvalResult`.
- `cli.py`: `main(argv: list[str] | None = None) -> int`, subcommand `evaluate` with the W4 arguments (`--config`, `--run-id`, `--results`, `--started-by`, `--split`, `--limit`, `--model`, `--adapter`, `--seed`, `--max-new-tokens`), the exit codes of C5 and BR5.2, and the W4 steps; prints accuracy, problems scored, minutes and the results path.
- `__main__.py`: `python -m gsm8k` calls `cli.main` and exits with its code.

## Parts

| Part | Criteria | Owned files | Test files |
|---|---|---|---|
| A data | AC1.1.1, AC1.1.2, AC1.1.3, AC1.1.5, AC1.2.1, AC1.2.2, AC1.2.3 | `src/gsm8k/datasets_prompts/hub.py`, `src/gsm8k/datasets_prompts/split.py`, `src/gsm8k/datasets_prompts/prompt.py` | `tests/test_u1_data.py` |
| B records | AC1.3.1, AC1.3.2, AC1.3.3, AC1.3.4, AC1.4.5 | `src/gsm8k/scoring.py`, `src/gsm8k/run_config.py`, `src/gsm8k/run_records/paths.py`, `src/gsm8k/run_records/log.py`, `src/gsm8k/run_records/folder.py`, `src/gsm8k/run_records/lock.py` | `tests/test_u1_scoring.py`, `tests/test_u1_run_config.py`, `tests/test_u1_run_records.py` |
| C command | AC1.1.4, AC1.4.1, AC1.4.2, AC1.4.3, AC1.4.4, AC1.4.6 | `src/gsm8k/evaluation.py`, `src/gsm8k/cli.py`, `src/gsm8k/__main__.py` | `tests/test_u1_evaluate.py`, `tests/test_u1_env.py` |

## Lead's shared files and dependencies

- `pyproject.toml` (package `gsm8k` under `src/`, console script `gsm8k = gsm8k.cli:main`, pytest and Ruff config), `requirements.txt` (exact pins), `scripts/check.sh`, `src/gsm8k/__init__.py`, `src/gsm8k/_env.py`, `src/gsm8k/datasets_prompts/__init__.py`, `src/gsm8k/run_records/__init__.py`, `tests/conftest.py` (`tmp_project_dirs`, `tiny_model`), `results/.gitkeep`.
- Dependencies: torch 2.14.1 (CUDA 13.0 wheel), transformers 5.22.2, accelerate 1.15.0, datasets 5.1.0, pytest 9.2.0, pytest-cov 7.1.0, ruff 0.17.4; the package installed editable into `.venv/`.
- Spec change before tests: C2 gains `max_new_tokens` (default 512), so the skeleton test's 256-token cap is a recorded config field, not a hidden option.

## Long runs

None in u1. After the merge, u2's batch builds the baseline long runs.
