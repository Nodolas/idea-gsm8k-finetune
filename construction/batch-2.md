# batch-2: u2-baselines, u3-sft

Branch `wip/batch-2`. Spec at approved commit 37fb5a4 plus the `spec(` commits since (`inception/changes.md`). `test_command`: `scripts/check.sh` (Ruff, then pytest with coverage on `src/gsm8k`, failing under 80%, on the CPU through `scripts/in-env.sh`). Every project tool runs through `scripts/in-env.sh`.

## Spec to read

`S` = `aidlc/spaces/default/intents/261030-gsm8k-finetune`.
- Criteria: `S/inception/user-stories/stories.md` US1.5 (u2) and US2.1–US2.5 (u3), the Conventions (quick tests, tiny model fixture, results file) and the Training Dials table.
- Requirements: `S/inception/requirements-analysis/requirements.md` FR1.8, FR1.9, FR2.1–FR2.6, FR1.7, NFR1–NFR3, NFR5, NFR7, NFR8.
- Design: `S/inception/domain-design/components.md` (Evaluation, RunConfiguration, Training, RunRecords, DatasetsAndPrompts, RunCommands), `S/inception/domain-design/decisions.md` (ADR-005 one Training block with two methods, ADR-006 commands, ADR-007 estimates live in RunConfiguration).
- Contracts: `S/inception/contract-design/contract-summary.md` C1, C2 (metrics.jsonl, timings.json, config fields), C3 (lock), C4 (finalists, read by prune), C5 (`train` arguments and exit codes).
- Built in batch-1 (read, reuse, do not break): `src/gsm8k/` and `construction/batch-1.md` (its Interfaces section). u1's design notes under `S/construction/u1-eval-skeleton/` still hold for the shared pieces (W4 steps, BR4.x, BR5.x).

## Criteria

- u2-baselines: AC1.5.5 (harness wrapper on 5 problems, tiny model in tests); `[manual]` AC1.5.1, AC1.5.2, AC1.5.3, AC1.5.4 (served by u1's `gsm8k evaluate`, already built), AC1.5.6 (the harness long run).
- u3-sft: AC2.1.1–AC2.1.5, AC2.2.1–AC2.2.5, AC2.3.1–AC2.3.4, AC2.4.1, AC2.5.1–AC2.5.4; `[manual]` AC2.4.2, AC2.4.3 (the default fine-tunes).

## Rules for every part

- Tests run on the CPU. No test loads real model weights: use the `tiny_model` fixture (`tests/conftest.py`), saved to a temp folder if a library needs a path (`model.save_pretrained(tmp)`, `tokenizer.save_pretrained(tmp)`), or monkeypatch `gsm8k.evaluation.load_model` / your own loader.
- No test touches the project's `outputs/`, `checkpoints/`, `results/runs.csv` or `results/finalists.json`: use `tmp_project_dirs` (temp outputs and checkpoints) and pass explicit temp results and finalists paths.
- Every test is named by its criterion ID (`test_AC2_1_2_...`); helper tests take the closest criterion of the part.
- Ruff-clean (`scripts/in-env.sh .venv/bin/ruff check src tests`, `ruff format`), snake_case, English only. Heavy imports (torch, transformers, peft, trl, lm_eval, datasets) inside functions, so `import gsm8k.cli` and `gsm8k --help` stay light.
- Full module-path imports; the subpackage `__init__.py` files stay empty.
- A command module exposes `register(subparsers) -> None`: it adds its subcommand and calls `set_defaults(func=<callable(args) -> int>)`. `gsm8k/cli.py` (lead-owned) imports each module named in `COMMAND_MODULES` (`gsm8k.harness`, `gsm8k.train_cmd`, `gsm8k.prune`) and calls `register`. Exit codes follow C5: 0 finished, 1 failed, 2 invalid configuration (nothing written), 3 lock held (nothing written), 130 stopped. Reuse `gsm8k.cli` constants (`EXIT_*`, `ATTEMPT_ID_PATTERN`) and the run-records modules; a run takes the GPU lock (`gsm8k.run_records.lock.GpuLock`) for its whole life and writes `status.json` at the end, like `gsm8k evaluate`.
- Long runs never run here. A part that serves a `[manual]` criterion reports the exact command (it takes `--run-id <base id>-<n>` and writes that id as the row's `run_id`).

## Interfaces (the contract between the parts)

Part E, configuration and estimates (RunConfiguration block, ADR-007):
- `run_config.py` (extended, keep every batch-1 interface): `validate(cfg)` checks every dial against the Training Dials table (inclusive bounds; sets for model, LoRA rank, answer format), with messages naming the dial and its allowed range or values (AC2.1.2, AC2.1.3); a training method (`sft`, `grpo`, `optuna` and the ablation methods) with `split == "test"` raises `ConfigError("The test split is never used for training or tuning")` (AC2.1.5); new `check_dials(d: dict) -> RunConfig`: strict parsing of user-given dials (unknown name or wrong type raises `ConfigError` naming the field, AC2.1.4), while `from_dict` keeps ignoring unknown keys when reading files (C2 Common Rules).
- `estimates.py` (new): `CAP_SECONDS = 3 * 3600`; `NO_ESTIMATE = "No estimate yet"`; `OVER_CAP = "Estimated time is above the 3-hour cap"`; `@dataclass(frozen=True) Estimate(seconds: float | None, text: str, over_cap: bool)`; `measured_seconds_per_step(model: str, outputs: Path | None = None) -> float | None` and `measured_seconds_per_problem(model: str, outputs: Path | None = None) -> float | None` (the newest `timings.json` under `outputs_root()/*/` whose `config.json` names that model and holds the value); `estimate_training(model: str, total_steps: int, outputs: Path | None = None) -> Estimate` (AC2.3.1); `estimate_evaluation(model: str, n_problems: int, outputs: Path | None = None) -> Estimate` (AC2.3.2); over the cap flags `OVER_CAP` (AC2.3.3); no measurement gives `seconds=None` and `NO_ESTIMATE` (AC2.3.4).

Part F, training (Training block, ADR-005):
- `training/targets.py`: `training_text(problem: Problem, answer_format: str) -> tuple[str, str]` (prompt, target): the prompt is the zero-shot `Question: <q>\nAnswer:` frame of BR2.3; the target is the worked answer with `<<...>>` notes stripped, ending `#### <gold>` (`step-by-step`), or just `#### <gold>` (`terse`).
- `training/loop.py`: the shared loop (a TRL `SFTTrainer` or a transformers `Trainer` with a callback): `MetricsWriter(run_dir)` appends one whole C2 metrics line per logging step (`v`, `step`, `total_steps`, `loss`, `learning_rate`, `elapsed_s`, `eta_s`, other fields null; dev-evaluation lines add `dev_accuracy`), each line written with a single `write` of a full line plus `\n` (AC2.2.2); `read_metrics(path: Path) -> list[dict]` returns the complete lines only, never a half-written last line (AC2.2.2; u4 will reuse it); the loop leaves a hook for GRPO's `reward`, `kl`, `answer_length` (u7).
- `training/sft.py`: `train_sft(cfg: RunConfig, run_dir: Path, adapter_dir: Path, *, model=None, tokenizer=None, eval_every: int | None = None, max_steps: int | None = None) -> TrainResult` (LoRA on all linear layers via peft with the config's rank, alpha, learning rate, epochs, batch size, warmup ratio, max sequence length, seed, training examples from the train split only; saves the adapter to `adapter_dir`; `model`/`tokenizer` injectable for tests; `max_steps` caps steps for tests); `@dataclass TrainResult(steps: int, seconds_per_step: float, peak_gpu_memory_gb: float, model, tokenizer)`.
- `train_cmd.py`: `gsm8k train` with `--config`, `--run-id`, `--results`, `--started-by`, every dial as a flag (`--model`, `--learning-rate`, `--epochs`, `--lora-rank`, `--lora-alpha`, `--max-seq-len`, `--train-examples`, `--batch-size`, `--warmup-ratio`, `--seed`, `--answer-format`), `--limit` (closing dev score limit), `--eval-every N` (dev evaluation during training, AC2.2.3) and `--max-steps N` (tests). Steps: check (exit 2), print the estimate (`estimates.estimate_training`), take the lock (exit 3), write `config.json`, train, save the adapter to `checkpoints_root()/<run_id>/` (AC2.2.1), score it on dev in-process with `gsm8k.evaluation.evaluate` (limited by `--limit`), write `timings.json` with `seconds_per_step` and `peak_gpu_memory_gb` (AC2.2.5, AC2.4.1), append one row with method `sft`, data `gsm8k-dev`, its `config_hash` (AC2.2.4), then `status.json`. Without `--run-id`: `adhoc-<UTC timestamp>` and a temp run log inside the run folder, as `gsm8k evaluate` does. Its model loader is a module attribute (`train_cmd.load_base_model`, defaulting to `gsm8k.evaluation.load_model`) so tests can return the tiny model.

Part G, prune (Training block):
- `prune.py`: `FINALISTS_DEFAULT = ROOT / "results" / "finalists.json"`; `read_finalists(path: Path) -> set[str]` (no file: empty set; unreadable: `ValueError` naming the file, C4); `best_runs(rows: list[RunRow]) -> dict[str, RunRow]` (per model, the highest dev accuracy among rows with data `gsm8k-dev`, metric `accuracy` and an adapter-producing method; a tie goes to the earlier row, AC2.5.1); `plan_prune(rows, finalists, checkpoints: Path) -> PrunePlan(delete: list[Path], keep: list[str], already_gone: list[str])`; `gsm8k prune [--yes] [--results PATH] [--finalists PATH]`: without `--yes` it lists and deletes nothing (AC2.5.2); with it, deletes every adapter folder except each model's best run and every finalist, never touching the run log (AC2.5.3); a row whose adapter folder is gone is reported as already pruned (AC2.5.4). It deletes only folders directly under `checkpoints_root()` and needs no GPU lock.

Part D, harness (u2, Evaluation block):
- `harness.py`: `run_harness(model, tokenizer, *, limit: int | None, batch_size: int = 8) -> float` (lm-evaluation-harness `gsm8k` task, 5-shot, flexible-extract filter, test split, with the model object passed in); `gsm8k harness` with `--model` (default `Qwen/Qwen3-1.7B-Base`), `--run-id`, `--results`, `--limit`, `--started-by`: checks (exit 2), takes the lock (exit 3), writes `config.json` (method `base`, split `test`), runs the harness, appends one row with method `base`, data `gsm8k-test-harness`, metric `harness_flexible_accuracy` and the harness accuracy (AC1.5.5), writes `timings.json` and `status.json`. Its model loader is a module attribute (`harness.load_model`, defaulting to `gsm8k.evaluation.load_model`). Harness caches stay in the project folder (`.cache/`).

## Parts

| Part | Unit | Criteria | Owned files | Test files |
|---|---|---|---|---|
| D harness | u2-baselines | AC1.5.5; long run AC1.5.6 | `src/gsm8k/harness.py` | `tests/test_u2_harness.py` |
| E config | u3-sft | AC2.1.1–AC2.1.5, AC2.3.1–AC2.3.4 | `src/gsm8k/run_config.py`, `src/gsm8k/estimates.py` | `tests/test_u3_run_config.py`, `tests/test_u3_estimates.py` |
| F training | u3-sft | AC2.2.1–AC2.2.5, AC2.4.1; long runs AC2.4.2, AC2.4.3 | `src/gsm8k/training/targets.py`, `src/gsm8k/training/loop.py`, `src/gsm8k/training/sft.py`, `src/gsm8k/train_cmd.py` | `tests/test_u3_train.py` |
| G prune | u3-sft | AC2.5.1–AC2.5.4 | `src/gsm8k/prune.py` | `tests/test_u3_prune.py` |

## Lead's shared files and dependencies

- `src/gsm8k/cli.py` (now lead-owned: the `COMMAND_MODULES` registration hook), `src/gsm8k/training/__init__.py`, `requirements.txt`, `tests/conftest.py`.
- Dependencies added: peft 0.21.2, trl 1.17.1, lm_eval 0.4.13 (torch and transformers unchanged).

## Long runs (started detached by the lead after this batch merges, one GPU run at a time, 3.4)

- AC1.5.1 `q06-base-dev`: `.venv/bin/python -m gsm8k evaluate --model Qwen/Qwen3-0.6B-Base --split dev --run-id q06-base-dev-<n>`
- AC1.5.2 `q06-base-test`: `... evaluate --model Qwen/Qwen3-0.6B-Base --split test --run-id q06-base-test-<n>`
- AC1.5.3 `q17-base-dev`, AC1.5.4 `q17-base-test`: the same with `Qwen/Qwen3-1.7B-Base`.
- AC1.5.6 `q17-base-harness`: `.venv/bin/python -m gsm8k harness --model Qwen/Qwen3-1.7B-Base --run-id q17-base-harness-<n>` (the exact command comes from part D's report).
- AC2.4.2 `q06-sft-dev`, AC2.4.3 `q17-sft-dev`: `.venv/bin/python -m gsm8k train --model <model> --run-id q06-sft-dev-<n>` (exact command from part F's report).
