# Units of Work

Nine units grouping the building blocks in `inception/domain-design/components.md` (decisions in `inception/domain-design/decisions.md`) along the learning path. Built from `inception/requirements-analysis/requirements.md` and `inception/user-stories/stories.md`; answers in `units-generation-questions.md` Q1–Q3, plan approved. Units whose dependencies are built go in one batch, built at the same time by parallel builder agents on `wip/batch-<n>` (`/build`; team-practices.md, Way of Working; inception/changes.md, 2026-10-31). Topology is in `unit-of-work-dependency.md`, story assignment in `unit-of-work-story-map.md`.

## Unit Table

| Unit ID | Directory | Kind | Complexity | Priority | Stories |
|---|---|---|---|---|---|
| U1 | u1-eval-skeleton | library | M | Must | US1.1, US1.2, US1.3, US1.4 |
| U2 | u2-baselines | library | S | Must | US1.5 |
| U3 | u3-sft | library | L | Must | US2.1, US2.2, US2.3, US2.4, US2.5 |
| U4 | u4-run-service | service | L | Must | US3.1, US3.2, US3.3, US3.4, US3.5, US3.6, US3.7 |
| U5 | u5-website | ui | L | Must | US4.1, US4.2, US4.3, US4.4, US4.5, US4.6 |
| U6 | u6-final-and-report | library | M | Must | US5.1, US6.1, US6.2, US6.3 |
| U7 | u7-grpo | library | M | Could | US7.1 |
| U8 | u8-tuning | library | M | Could | US8.1, US8.2 |
| U9 | u9-ablations | library | M | Could | US9.1 |

Kinds: `library` is code with commands but no long-running server; `service` is the long-running local service and worker; `ui` is the website.

## Packaging (Q3)

- One Python package `gsm8k` under `src/gsm8k/`, one subpackage per building block: `datasets_prompts`, `scoring`, `run_records`, `run_config`, `evaluation`, `training`, `commands`, `run_control`, `service`, `report`, `tuning`.
- Console commands: `gsm8k evaluate`, `train`, `tune`, `prune`, `report`, `serve`, `worker`. Every command sets the in-folder cache variables before any other import (NFR5).
- `make serve` starts the service and the worker as two local processes.
- The website is a Vite app in `web/`, with Node from `.tools/node/` (team-practices.md, Code Style).
- Tests live in `tests/` (Python with pytest, website with Vitest under `tests/web/`), named by criterion ID.

The deployment model of every unit is local only: nothing is deployed (team-practices.md, Deployment).

## U1 u1-eval-skeleton

- **Description:** The walking skeleton (team-practices.md). It evaluates `Qwen/Qwen3-0.6B-Base` end to end on 3 GSM8K dev problems on the CPU (NFR3) and writes one result row to a temporary file.
- **Building blocks:**
  - DatasetsAndPrompts: GSM8K only.
  - AnswerScoring: extraction and comparison.
  - RunConfiguration: the evaluation configuration, defaults and `config_hash`.
  - RunRecords: run log rows, attempt ids, run folders, an atomic lock.
  - Evaluation: greedy decoding.
  - RunCommands: `gsm8k evaluate` under the lock.
- **Owns and delivers:** the package skeleton, the cache-variable setup, the fixed split and prompt, scoring, `gsm8k evaluate` with `--run-id` and `--limit`, and the run-log format.
- **Deployment model:** embedded (library with a command).
- **Notes and constraints:**
  - The quick test runs on the CPU (NFR3): it downloads the 0.6B model and evaluates 3 dev problems, greedy, up to 256 new tokens. GPU use is first proven by the first detached long run, the 0.6B baseline evaluation (AC1.5.1, U2).
  - Rows go to a temporary path in tests.
  - The evaluation-only options that later units add (vote samples, calculator, limit) are recorded in the run folder's config. Settled (domain-design review finding R-01): by the C2 hash rule, every field whose value differs from its default enters `config_hash` (contract-summary.md C2; inception/changes.md, 2026-10-31).

## U2 u2-baselines

- **Description:** The lm-evaluation-harness cross-check wrapper, and the four baseline long runs plus the harness run on the main baseline.
- **Building blocks:** Evaluation (harness wrapper), RunCommands.
- **Owns and delivers:**
  - the harness wrapper with a quick test on 5 problems
  - five `[manual]` criteria, run as detached long runs by the `/build` lead (or from the website by Nico): `q06-base-dev`, `q06-base-test`, `q17-base-dev`, `q17-base-test`, `q17-base-harness`
- **Deployment model:** embedded.
- **Notes and constraints:** kept apart so the skeleton closes without waiting hours (Q2). The unit's code is done when its quick test passes; its `[manual]` criteria pass when the long runs' rows are in `results/runs.csv`, committed by the lead.

## U3 u3-sft

- **Description:** Supervised fine-tuning with LoRA, the full dial table, estimates and pruning.
- **Building blocks:**
  - RunConfiguration: all eleven dials and estimates.
  - Training: the shared loop and the `sft` method, adapters, pruning.
  - RunRecords: metrics lines, timings, peak memory.
  - DatasetsAndPrompts: training targets in step-by-step and terse formats.
  - RunCommands: `gsm8k train` and `gsm8k prune`.
- **Owns and delivers:**
  - `gsm8k train` with live `metrics.jsonl`
  - the closing dev score
  - `checkpoints/<run_id>/`
  - the 3-hour estimate flag
  - `gsm8k prune`
  - two `[manual]` long runs, `q06-sft-dev` and `q17-sft-dev`
- **Deployment model:** embedded.
- **Notes and constraints:**
  - The first measurements here confirm that the default dials fit 8 GB and 3 hours (NFR1, NFR2).
  - The shared loop must allow GRPO's extra metrics later (ADR-005).

## U4 u4-run-service

- **Description:** The local run service and worker:
  - queue, worker, stop and status
  - reporting a run that ended without finishing (the C3 `flock` lock on `outputs/run.lock` is released by the kernel)
  - finalists and the finalist-only test-split rule
  - the HTTP API and the live metrics stream
- **Building blocks:** RunControl, RunService, plus the queue and finalist parts of RunRecords.
- **Owns and delivers:**
  - `gsm8k serve` and `gsm8k worker`, started together by `make serve`
  - every endpoint the website needs
  - Server-Sent Events of complete metrics lines
- **Deployment model:** standalone local processes on 127.0.0.1. The worker loop is its own process (`gsm8k worker`), so queued runs advance while the service is down.
- **Notes and constraints:**
  - The service never imports training code (ADR-006).
  - Settled (domain-design review R-02, R-03), by the C3 lock and queue rules in `contract-summary.md`:
    - the worker removes a queue entry only once the process it launched holds the lock
    - the lock is the C3 `flock` OS lock on `outputs/run.lock`, held by the run's process and released by the kernel when it ends, the same for command-line and worker runs; nothing renames or takes over a lock
  - Any detail still open is settled in the `/build` batch plan (`construction/batch-<n>.md`).

## U5 u5-website

- **Description:** The three pages and dialogs from `inception/refined-mockups/mockups.md`, styled with the dark "night" tokens.
- **Building blocks:** Website.
- **Owns and delivers:**
  - Landing with the `gsm8k` halftone headline
  - Scores with ranking, filters, compare and finalist marks
  - Training with the hourglass band, curves, dials, dialogs, queued runs and past runs
  - Vitest tests named `AC4.x.y …`
- **Deployment model:** local Vite app, never deployed.
- **Notes and constraints:**
  - Reads only from the run service (ADR-008).
  - Needs Nico's screenshots in `inputs/design/` before it is built (AC4.1.3).
  - Node lives in `.tools/node/` and npm's cache in `.cache/npm`.

## U6 u6-final-and-report

- **Description:** The generalisation sets, the final test score of the best checkpoint and its harness cross-check, `results.md`, and the learning check questions.
- **Building blocks:**
  - DatasetsAndPrompts: GSM-Plus and GSM-Symbolic loaders and the training-data guard.
  - Evaluation.
  - ResultsReport: `gsm8k report`.
  - RunCommands.
- **Owns and delivers:**
  - `gsm8k report`
  - six `[manual]` long runs: `q17-base-gsmplus`, `q17-base-gsmsym`, `q17-best-gsmplus`, `q17-best-gsmsym`, `q17-best-test`, `q17-best-harness`
  - the finished `results.md`
- **Deployment model:** embedded.
- **Notes and constraints:**
  - The final test run needs a finalist (U4) and an adapter (U3).
  - US6.3's check questions are a process step at every unit's end; they are traced here because this unit closes the project.

## U7 u7-grpo (Could)

- **Description:** GRPO training as the second method of the Training loop.
- **Building blocks:** Training (`grpo` method), AnswerScoring (rewards), RunConfiguration (GRPO steps and sampling).
- **Owns and delivers:** `gsm8k train --method grpo` and its `[manual]` run, `q06-grpo-dev` (or `q17-grpo-dev`).
- **Deployment model:** embedded.
- **Notes and constraints:** the model size is chosen from U3's measurements.

## U8 u8-tuning (Could)

- **Description:** The Optuna proxy study and the proposal rule checker.
- **Building blocks:** Tuning, RunCommands (`gsm8k tune`).
- **Owns and delivers:** `gsm8k tune` with SQLite under `outputs/`, the rule checker, and the `[manual]` study run `q06-optuna-dev`.
- **Deployment model:** embedded.
- **Notes and constraints:** the proposer and reviewer helpers never start a run (AC8.2.3).

## U9 u9-ablations (Could)

- **Description:** Terse answer format, majority vote and the calculator tool, each compared on dev.
- **Building blocks:** DatasetsAndPrompts (terse targets), AnswerScoring (majority vote), Evaluation (vote and calculator options).
- **Owns and delivers:** the three transforms and three `[manual]` runs: `q17-terse-dev`, `q17-vote-dev`, `q17-calc-dev`.
- **Deployment model:** embedded.
- **Notes and constraints:** the calculator evaluates arithmetic only (AC9.1.3).
