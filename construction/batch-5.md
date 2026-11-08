# batch-5: u10-self-taught-cot

Branch `wip/batch-5`. Spec: approved commit 37fb5a4 plus the `spec(` commits since, among them the 2026-11-08 `spec(inception)` commit that adds u10 (`inception/changes.md`, last lines). `test_command`: `scripts/check.sh` (Ruff, website lint, type check and Vitest, then pytest with coverage on `src/gsm8k` failing under 80%), on the CPU through `scripts/in-env.sh`. Every project tool runs through `scripts/in-env.sh`; website tools as `scripts/in-env.sh npm run web:<script>` (e.g. `scripts/in-env.sh npm run web:test -- tests/web/reasoning.test.tsx`).

Why now: Nico, 2026-11-08: "train a model with focus on chain of thought" (picked self-taught chain of thought) and "Make a page and explain how it affected the score". u3, u4 and u5 are built, so u10 is ready.

## Spec to read

`S` = `aidlc/spaces/default/intents/261030-gsm8k-finetune`.
- Criteria: `S/inception/user-stories/stories.md` group 10 (US10.1-US10.4, its intro, the chain-of-thought dials table and the reasoning-lines rule), Conventions (tests by ID, the tiny model fixture, quick tests), Training Dials.
- Requirements: `S/inception/requirements-analysis/requirements.md` FR10.1-FR10.4, FR4.1, FR1.3-FR1.6, FR2.1-FR2.4, NFR1-NFR3, NFR6, NFR8, NFR9.
- Design: `S/inception/domain-design/components.md` (SelfTaughtCoT, ReasoningReport, Training, Website), `decisions.md` (ADR-006: `run_control` and `service` never import training code; ADR-008: the website reads only the service), `S/inception/units-generation/unit-of-work.md` U10.
- Contracts: `S/inception/contract-design/contract-summary.md` C1 (new values), C2 (new fields, `cot_data.jsonl`, `cot_stats.json`, the reasoning-lines and split rules), C5 (`cot-generate`, `train --method selfcot`), C6 (`/reasoning`, schema `Reasoning`).
- Built (reuse, do not break): `src/gsm8k/`, the Interfaces of `construction/batch-1.md`-`batch-4.md`, `tests/conftest.py` (`tmp_project_dirs`, `tiny_model`), `web/src/test/utils.tsx`, `web/src/test/fake-api.ts`.

## Criteria

- AC10.1.1-AC10.1.4 (part C1), AC10.2.1-AC10.2.4 (part C2), AC10.3.1-AC10.3.4 (part C3), AC10.4.1-AC10.4.4 (part C4).
- Long runs, [manual], started detached by the lead after the merge, one at a time: AC10.1.5 `q17-cotgen-train` (under 3 h), then AC10.2.5 `q17-selfcot-dev` (about 30-45 min; needs the generation run's id).
- [manual] without a run: AC10.4.5 (Nico reads the Reasoning page and the `results.md` section after q17-selfcot-dev ends; the lead writes that section).

## Rules for every part

- Python as batch-4: CPU only; `tmp_project_dirs` with explicit temp `--results`; never the project's `outputs/`, `checkpoints/` or `results/runs.csv`. Tests named by criterion ID (`test_AC10_1_2_...`), Ruff-clean (lint and format), full module-path imports, heavy imports (torch, transformers, peft, trl) inside functions, ADR-006 holds. Models: `tiny_model`, with `gsm8k.evaluation.load_model` (and `gsm8k.train_cmd.load_base_model` where training loads) monkeypatched. GSM8K loads through the real `hub.load_gsm8k()` (cached under `.cache/huggingface`).
- Website as batch-4: `tests/web/reasoning.test.tsx`, titles starting `AC10.4.x`; Vitest globals; `renderPage(route, { api: fakeApi({...}) })`; TypeScript strict, no `any`; ESLint and Prettier clean; data only through `useApi()`; one `h1`, `h2` per panel; native elements; status and noise in words, never colour alone (NFR9); colours from the tokens.
- Builders install nothing: ask the lead.
- Never edit or delete an existing test; new tests go in the new files below.

## Interfaces (the contract between the parts)

Lead, shared setup (before the test writers start):
- `src/gsm8k/cot/__init__.py` (empty package).
- `src/gsm8k/reasoning_text.py`: `reasoning_lines(text: str) -> list[str]` (the stripped non-empty lines before the first line that starts with `####`, or all non-empty lines when there is none) and `reasoning_words(text: str) -> int` (whitespace-separated words of those lines). Used by C1 (stats) and C3 (comparison).
- `web/src/lib/api.ts`: types `ReasoningRole {role: "base"|"sft"|"selfcot"; run_id: string|null; accuracy: number|null; correct: number|null; scored: number|null; interval_low: number|null; interval_high: number|null; trained_on: number|null; gain_pts: number|null; noise: "within noise"|"outside noise"|null; mean_lines: number|null; mean_words: number|null; error: string|null}`, `ReasoningFlip {role: "sft"|"selfcot"; run_id; against; fixed; broken; both_right; both_wrong}`, `ReasoningGeneration` (C2 `cot_stats.json` fields), `ReasoningExample {problem_id; gold; base_output; selfcot_output}`, `Reasoning {v; model; available: boolean; roles: ReasoningRole[]; flips: ReasoningFlip[]; generation: ReasoningGeneration|null; generation_error: string|null; examples: ReasoningExample[]; summary: string[]}`; `Api.getReasoning(model?: string): Promise<Reasoning>` (GET `/reasoning?model=`).
- `web/src/test/fake-api.ts`: `getReasoning` default resolves an empty comparison (`available: false`, three roles with nulls, no flips, examples or summary); fixture helper `reasoning(partial)`.
- `web/src/lib/queries.ts`: `useReasoning(model?: string)` (a `useAsync` over `getReasoning`).

Part C1, generation (US10.1). Owns: `src/gsm8k/cot/generate.py` (new), `src/gsm8k/cot_cmd.py` (new), `src/gsm8k/run_config.py`, `src/gsm8k/run_records/log.py`, `src/gsm8k/cli.py`. Tests: `tests/test_u10_cot_generate.py`.
- `run_config.py`: `METHODS` gains `cotgen`, `selfcot`; `SPLITS` gains `train`; `TRAINING_METHODS` gains `selfcot`; `RunConfig` gains, at the end, `cot_problems: int | str = 1500`, `cot_samples: int = 4`, `cot_temperature: float = 0.7`, `cot_data_run: str | None = None` (C2; at their defaults they stay out of `config_hash`). `validate` checks the three cot dials' ranges (stories.md table; messages in the existing style naming the dial and range), that split `train` is used only by `cotgen` and `cotgen` only with split `train`.
- `run_records/log.py`: `METHODS` gains `cotgen`, `selfcot`; `DATA` gains `gsm8k-train`; `METRICS` gains `kept_fraction`.
- `cli.py`: `COMMAND_MODULES` gains `gsm8k.cot_cmd`; `ADAPTER_METHODS` gains `selfcot`.
- `cot/generate.py`: `keep_sample(output: str, gold: str) -> bool` (correct final number and at least one reasoning line); `choose_kept(outputs: list[str], gold: str) -> str | None` (first kept, sample order); `sample(model, tokenizer, prompts: list[str], *, samples: int, temperature: float, max_new_tokens: int) -> list[list[str]]` (sampling with `num_return_sequences=samples`, per-sequence BR3.5 stop via `gsm8k.evaluation._stop_criterion`, each cut with `scoring.cut_output`); `generate_cot(model, tokenizer, problems, prompt_for, cfg, *, on_progress) -> CotResult` with the kept records and the `cot_stats.json` figures. Problem batch: `max(1, SEQUENCES_PER_BATCH[model] // cot_samples)` with `SEQUENCES_PER_BATCH = {"Qwen/Qwen3-0.6B-Base": 16, "Qwen/Qwen3-1.7B-Base": 8}` (8 GB, NFR1). Seed: `transformers.set_seed(cfg.seed)` once before sampling.
- `cot_cmd.py`: `register(subparsers)` adds `gsm8k cot-generate` (C5 args and flags; `--cot-problems` takes a number or `all`). Problems: the first `cot_problems` of the training part by index (reuse `gsm8k.training.sft.load_training_data` with `train_examples=cot_problems`, which already runs the split guard); prompt: the fixed 4-shot prompt. Under `GpuLock` like `gsm8k train`; writes `config.json` first, metrics lines (`step` = problems done, `total_steps`, `elapsed_s`, `eta_s`, loss and learning_rate null), `cot_data.jsonl` and `cot_stats.json` (C2; the four means null when nothing is kept), `timings.json` with `seconds_per_problem` null (so evaluation estimates stay clean) plus `seconds_per_generated_problem`, the row (method `cotgen`, data `gsm8k-train`, metric `kept_fraction`, value 4 decimals), `status.json`; exit codes as C5 (0, 1, 2, 3, 130).

Part C2, self-taught training (US10.2). Owns: `src/gsm8k/training/selfcot_data.py` (new), `src/gsm8k/train_cmd.py`, `src/gsm8k/training/sft.py`, `src/gsm8k/prune.py`. Tests: `tests/test_u10_selfcot_train.py`.
- `selfcot_data.py`: `cot_data_path(run_id) -> Path` (`outputs/<run_id>/cot_data.jsonl`), `load_cot_problems(run_id, dev_ids, test_ids, train_examples) -> list[Problem]` (each line becomes `Problem(id, question, answer=solution, gold)`, sorted by problem index, first N or all; a missing or unreadable file raises naming it; dev or test ids raise naming up to 3 of them).
- `train_cmd.py`: `--method sft|selfcot` (default `sft`) and `--cot-data-run`; method `selfcot` needs `cot_data_run` (exit 2 naming the field), trains through the same `train_sft` loop with the self-taught problems as training data (targets via `training_text(..., "step-by-step")`, so the reasoning is kept and the last line is `#### <gold>`), scores dev, writes the row with method `selfcot`, data `gsm8k-dev`.
- `sft.py`: only what that needs (e.g. `load_training_data` takes an optional replacement training list); behaviour for `sft` unchanged.
- `prune.py`: `ADAPTER_METHODS` gains `selfcot`.

Part C3, comparison and endpoint (US10.3). Owns: `src/gsm8k/reasoning_report.py` (new), `src/gsm8k/service/app.py`, `src/gsm8k/run_control/launch.py` (only the refusal below). Tests: `tests/test_u10_reasoning_report.py`.
- `reasoning_report.py` (imports only `run_records`, `reasoning_text`, stdlib; ADR-006): `build_reasoning(model: str, results: Path, outputs: Path) -> dict` returning C6 `Reasoning` exactly (roles always base, sft, selfcot; `trained_on` from the run's config.json `train_examples`, `all` = 6973 for sft and the kept count of its generation run for selfcot, capped at what was available, null for base; interval normal approximation clipped; `gain_pts` 1 decimal; noise cut-off 4 points; flips; `generation` from the selfcot run's `config.json` `cot_data_run` and that run's `cot_stats.json`; up to 3 examples; `summary` sentences). Raises `ValueError` for a model outside the two allowed; an unreadable run log raises the existing run-log error.
- `POST /runs/check` (app.py or `launch.py`, wherever the method is checked) refuses methods `cotgen` and `selfcot` with 422 `invalid_dial`, field `method`. `app.py`: `GET /api/v1/reasoning?model=` (default `Qwen/Qwen3-1.7B-Base`) calls it with the service's results and outputs paths; 422 `invalid_dial` with `field: "model"`; 500 `run_log_unreadable` with `file`.

Part C4, Reasoning page (US10.4). Owns: `web/src/pages/reasoning.tsx` (new), `web/src/components/reasoning-panels.tsx` (new; more `web/src/components/reasoning-*.tsx` files if needed, named in the report), `web/src/router.tsx`, `web/src/components/top-bar.tsx`. Tests: `tests/web/reasoning.test.tsx`.
- Route `/reasoning` inside `AppLayout`; top bar link "Reasoning" after "Training" (`NavLink`, `aria-current="page"`); the existing tab order (skip link, wordmark, run tag, Scores, Training) stays a prefix.
- Page: `h1` "Reasoning"; a short explanation of self-taught chain of thought; the score table (base, reference fine-tune, self-taught: dev accuracy, interval, training problems learned from, gain via `formatGain`, noise label in words); flips; mean reasoning lines and words; the generation figures; `h2` "How it affected the score" with the summary sentences; examples (problem id, gold, base and self-taught outputs side by side, in `pre` blocks); empty state "No self-taught chain-of-thought run yet" with whatever base and reference figures exist; error and loading states as on the other pages.

Ruled wrong by Nico (2026-11-08, in session): `tests/test_u1_run_config.py` `test_AC1_4_5_defaults_match_documented_values` pins the batch-1 C2 field set; its writer (C1's test writer) adds the four cot fields and their defaults to the expected set and assertions, nothing else, committed as `test(u1-eval-skeleton): fix test ...` after the `spec(u1-eval-skeleton)` line. Only that file may lose lines.

## Long runs (lead, after the merge, detached)

1. `scripts/run-detached.sh q17-cotgen-train-1 .venv/bin/python -m gsm8k cot-generate --model Qwen/Qwen3-1.7B-Base --run-id q17-cotgen-train-1` (default dials: 1,500 problems, 4 samples, temperature 0.7; under 3 h even without a batching gain).
2. After it ends with a row: `scripts/run-detached.sh q17-selfcot-dev-1 .venv/bin/python -m gsm8k train --model Qwen/Qwen3-1.7B-Base --method selfcot --cot-data-run q17-cotgen-train-1 --batch-size 2 --run-id q17-selfcot-dev-1`.
3. After both: the lead writes the "Self-taught chain of thought" section of `results.md` from the Reasoning comparison (AC10.4.5).
