# Bolt Plan

A **Bolt** is one build pass over a piece of the work that ends in something that runs. Here each Bolt is exactly one unit of work from `inception/units-generation/unit-of-work.md`, built on its own `wip/<unit>` branch, one at a time (`inception/practices-discovery/team-practices.md`, Way of Working). The order follows the unit graph in `inception/units-generation/unit-of-work-dependency.md`, and the stories per unit come from `inception/units-generation/unit-of-work-story-map.md`. The criteria are in `inception/user-stories/stories.md`, the shared formats in `inception/contract-design/contract-summary.md` and the blocks in `inception/domain-design/components.md`. Requirements: `inception/requirements-analysis/requirements.md`. Screens: `inception/refined-mockups/mockups.md`. Answers: `delivery-planning-questions.md` Q1–Q2.

## Rules for Every Bolt

- **Tests first.** The unit's tests are written in `tests/` and named by criterion ID. They are run to see them fail, then the code follows (team-practices.md, Testing Posture).
- **Done** means:
  - the unit's tests, the full suite (the approved verification command) and `scripts/trace-check.sh` all pass in the session
  - the result is recorded in `STATE.md` `last_check`
  - Nico approves the unit's checkpoint
  - Nico answers one or two learning check questions (US6.3)
- **Long runs** (over about 10 minutes) are `[manual]` criteria. They do not hold the Bolt open (Q1): the lead lists each one in `STATE.md` `pending_runs` with its exact command and attempt id (`--run-id <base id>-1`). Nico runs them when the GPU is free, and the lead commits the row. A pending run blocks only the Bolt that needs its result.
- **Merging.** `main` moves only by fast-forward from a green `wip/<unit>` (team-practices.md, Way of Working).

## Sequence

| # | Bolt | Unit | Kind | Priority | Walking skeleton |
|---|---|---|---|---|---|
| 1 | B1 | u1-eval-skeleton | library | Must | Yes |
| 2 | B2 | u2-baselines | library | Must | — |
| 3 | B3 | u3-sft | library | Must | — |
| 4 | B4 | u4-run-service | service | Must | — |
| 5 | B5 | u5-website | ui | Must | — |
| 6 | B6 | u6-final-and-report | library | Must | — |
| 7 | B7 | u7-grpo | library | Could | — |
| 8 | B8 | u8-tuning | library | Could | — |
| 9 | B9 | u9-ablations | library | Could | — |

## B1 u1-eval-skeleton (walking skeleton)

The **walking skeleton** is the smallest slice that runs end to end through every layer before anything is built on top (team-practices.md, Walking Skeleton).

- **Stories:** US1.1, US1.2, US1.3, US1.4.
- **What it proves end to end:**
  - the Python environment in `.venv/` and the in-folder caches
  - downloading GSM8K and `Qwen/Qwen3-0.6B-Base`
  - GPU generation
  - the fixed split and 4-shot prompt
  - final-number scoring
  - the run-log row (C1)
  - the run folder (C2)
  - the atomic lock (C3)
  - the `gsm8k evaluate` command and its exit codes (C5)
- **Definition of done:** AC1.1.1–AC1.4.6 pass in the quick suite. Peak GPU memory and seconds per problem are recorded. The verification command passes in the session, and Nico approves the skeleton checkpoint.
- **Confidence hypothesis:** the whole chain runs on this PC inside the project folder. A 10-problem evaluation of the 0.6B model fits easily in 8 GB, and measured seconds per problem make the full dev and test baselines plausible within 3 hours.
- **Expected demo:** `gsm8k evaluate --limit 10 --split dev` prints accuracy, problems scored and minutes, then writes one row to a temporary run log and the per-problem predictions to `outputs/<run_id>/`.
- **Pending long runs:** none.

## B2 u2-baselines

- **Stories:** US1.5.
- **Definition of done:** AC1.5.5 (the harness wrapper on 5 problems) passes. The five baseline runs are listed in `STATE.md` `pending_runs`: `q06-base-dev`, `q06-base-test`, `q17-base-dev`, `q17-base-test` and `q17-base-harness`.
- **Confidence hypothesis:** the project's own 4-shot score and the lm-evaluation-harness score for the same model are close enough that the protocol can be trusted.
- **Expected demo:** the harness wrapper on 5 problems writes a `gsm8k-test-harness` row. Nico starts `q06-base-dev-1` and watches it run.
- **Pending long runs:** five baseline runs, about 6 hours of GPU in total. B6 needs their rows.

## B3 u3-sft

- **Stories:** US2.1, US2.2, US2.3, US2.4, US2.5.
- **Definition of done:**
  - AC2.1.1–AC2.5.4 pass in the quick suite.
  - A short default fine-tune of the 0.6B model, 50 examples and a few steps, records peak GPU memory and seconds per step (GPU risk first, Q2).
  - The estimate for the default full fine-tune is shown with its 3-hour flag.
  - `q06-sft-dev` and `q17-sft-dev` are listed as pending runs.
- **Confidence hypothesis:** the default dials fit in 8 GB for both models, and measured step times put a full default fine-tune under 3 hours. If not, the dial table changes through `inception/changes.md` before any long run.
- **Expected demo:** `gsm8k train` on 50 examples streams `metrics.jsonl` lines, saves an adapter under `checkpoints/`, scores it on a few dev problems and writes an `sft` row.
- **Pending long runs:** two default fine-tunes. B6 needs a fine-tuned finalist.

## B4 u4-run-service

- **Stories:** US3.1–US3.7.
- **Definition of done:** AC3.1.1–AC3.7.6 pass, using stub run processes and a temporary run folder. `make serve` starts the service and the worker on 127.0.0.1. The C6 endpoints and the C7 stream answer as specified.
- **Confidence hypothesis:** runs started from the website queue, start, stop and fail as the stories say, without ever putting two jobs on the GPU. Runs started from the terminal are refused while any run holds the lock.
- **Expected demo:** with `make serve` running, two runs are queued through the API. The first starts, the second waits, and stopping the first starts the second. The stream shows metrics lines as they are written.
- **Pending long runs:** none.

## B5 u5-website

- **Stories:** US4.1–US4.6.
- **Definition of done:** AC4.1.1–AC4.6.7 pass as Vitest tests. The `[manual]` checks AC4.1.3 (look against Nico's screenshots) and AC4.5.6 (a live run shows within 5 seconds) are approved by Nico at the checkpoint.
- **Confidence hypothesis:** Nico can start, watch, stop, queue and compare runs from the browser alone, and the pages match his inputs.
- **Expected demo:** with `make serve` and the Vite dev server running:
  - the landing page shows the `gsm8k` headline and the best result
  - the scores page ranks the baselines and SFT runs
  - the training page shows the hourglass band draining during a short run
- **Pending long runs:** none.

## B6 u6-final-and-report

- **Stories:** US5.1, US6.1, US6.2, US6.3.
- **Definition of done:**
  - AC5.1.1, AC5.1.2, AC6.1.1 and AC6.2.1–AC6.2.3 pass.
  - The six final long runs are listed as pending runs: `q17-base-gsmplus`, `q17-base-gsmsym`, `q17-best-gsmplus`, `q17-best-gsmsym`, `q17-best-test` and `q17-best-harness`.
  - When their rows are in, `gsm8k report` writes `results.md`, and Nico approves it (AC6.2.4).
- **Prerequisite:** the baseline rows from B2 and a finalist marked through B4 or B5, trained in B3.
- **Confidence hypothesis:** the best tuned checkpoint beats its own baseline on the full GSM8K test split (FR6.2), and the write-up says whether the gain lies within noise.
- **Expected demo:** `gsm8k report` builds `results.md` from the run log, with the gain labelled "within noise" or "outside noise".
- **Pending long runs:** six runs. This is the Bolt that closes the project.

## B7 u7-grpo (Could)

- **Stories:** US7.1.
- **Definition of done:** AC7.1.1–AC7.1.4 pass. The GRPO run (`q06-grpo-dev`, or `q17-grpo-dev`) is listed as pending.
- **Confidence hypothesis:** reinforcement learning with a correctness reward moves the dev score within 3 hours on this GPU.
- **Expected demo:** a few GRPO steps on the 0.6B model show reward, KL and answer-length curves.

## B8 u8-tuning (Could)

- **Stories:** US8.1, US8.2.
- **Definition of done:** AC8.1.1–AC8.2.2 pass. AC8.2.3 is checked by Nico. The study run `q06-optuna-dev` is listed as pending.
- **Confidence hypothesis:** short proxy trials on the 0.6B model point to dials that also help the full run.
- **Expected demo:** two tiny trials stored in SQLite under `outputs/`, and the rule checker rejecting a proposal that changes two dials at once.

## B9 u9-ablations (Could)

- **Stories:** US9.1.
- **Definition of done:** AC9.1.1–AC9.1.3 pass. The runs `q17-terse-dev`, `q17-vote-dev` and `q17-calc-dev` are listed as pending.
- **Confidence hypothesis:** at least one of answer format, majority vote or the calculator tool changes the dev score by more than noise.
- **Expected demo:** a terse training target, a majority vote over five samples, and a calculator call each computed on one problem.

## Construction Settings

- **Order (changed 2026-10-31):** `/build` builds every unit whose dependencies are built at the same time, in batches of up to four (unit-of-work-dependency.md), with parallel builder agents; AI-DLC's per-unit Construction stages are not run. The text below this line is the original plan. There are no parallel builds and no automatic continuation.
- **Verification command:** proposed at this stage's close for Nico to approve. It is run at every unit checkpoint.
