# User Stories: Fine tune model for grade math

Sources: `inception/requirements-analysis/requirements.md` (FR1–FR9, NFR1–NFR10), `inception/practices-discovery/team-practices.md` (tests first and named by criterion; long runs are `[manual]`), the wireframes in `ideation/rough-mockups/wireframes.md` (page states), and the answers in `user-stories-questions.md` (Q1–Q7). The single persona is Nico (`personas.md`).

## Conventions

- **Format:** "As Nico, I want …, so that …". Each story has a stable `US{group}.{seq}` ID, and each acceptance criterion an `AC{group}.{seq}.{k}` ID written on one line in Given/When/Then form.
- **Tests:** every criterion is checked by at least one test named by its ID (Python `test_AC1_4_1_...` with pytest; website `AC4.2.1 ...` with Vitest and React Testing Library), or carries `[manual]` on its own line with how to verify it (Q6).
- **Long runs:** a criterion whose run takes over about 10 minutes carries `[manual]` and `Verify: results/runs.csv row <base id>`. Base ids follow `<model>-<method>-<split>` (Q7): model `q06` (`Qwen/Qwen3-0.6B-Base`) or `q17` (`Qwen/Qwen3-1.7B-Base`); method `base`, `sft`, `grpo`, `best` (the best tuned checkpoint, whichever method made it), `cotgen` and `selfcot` (group 10, added 2026-11-08), or an ablation name; split `dev`, `test`, `harness` (lm-evaluation-harness on the test split), `gsmplus`, `gsmsym` or `train` (the chain-of-thought generation, which samples the training part only). Each attempt is started detached by the `/build` lead (`scripts/run-detached.sh`) or by Nico from the website, never typed by Nico in a terminal, with `--run-id <base id>-1`, `-2`, and so on (inception/changes.md, 2026-10-31); the row's `run_id` is the attempt id. The `q17` ids assume the 1.7B model is the final one (inception/brief.md); if the best checkpoint turns out to be 0.6B, the same criteria use `q06`.
- **Quick tests:** tests run on the CPU in under 10 minutes; only the walking-skeleton test loads a real model (3 dev problems), others use tiny fixtures, mocks or a few training steps. Wherever a test runs a model on a few problems or steps ("a limit of 5 problems", "a few steps"), the model is a tiny model fixture: a Qwen3-architecture model with random weights and a few small layers, built by the test (with the 0.6B tokenizer), never the real 0.6B or 1.7B weights. All tests point the results file at a temporary path, never `results/runs.csv` (NFR3, team-practices.md).
- **Run results file:** "the results file" below means `results/runs.csv` for long runs and a temporary file in tests (FR1.6).
- **Priority:** groups 1–6 are Must Have (scope-document.md IB-1 to IB-6); groups 7–9 are Could Have, built only after everything else works (IB-7 to IB-9, Q2), and are deferred: not built in this build (Nico, 2026-11-07; units u7-u9 deferred in unit-of-work.md). Group 10 is Could Have too and is built (Nico, 2026-11-08: self-taught chain of thought and a page on how it moved the score; unit u10-self-taught-cot). Group 11 is Could Have and is built (Nico, 2026-11-08: a small model that trains in minutes on the CPU and a step-by-step lab on what affects what; unit u11-finetune-lab). No story is Should Have or Won't Have; exclusions are listed in requirements.md Out of Scope.

## Training Dials

Q4 fixed the allowed range and default of every dial (FR2.1, FR2.2). The first unit's measured times and memory confirm that the defaults fit 8 GB and 3 hours (NFR1, NFR2); a change to this table goes through `inception/changes.md` first.

| Dial | Allowed | Default |
|---|---|---|
| model | `Qwen/Qwen3-0.6B-Base` or `Qwen/Qwen3-1.7B-Base` | `Qwen/Qwen3-0.6B-Base` |
| learning rate | 1e-5 to 5e-4 | 2e-4 |
| epochs | 1 to 3 (whole number) | 1 |
| LoRA rank | 4, 8, 16, 32 or 64 | 16 |
| LoRA alpha | 1 to 128 (whole number) | 32 |
| max sequence length | 256 to 1024 tokens (whole number) | 512 |
| training examples | 50 to the size of the training split (6,973), or `all` | `all` |
| batch size | 1 to 16 (whole number) | 4 (use 2 or less with `Qwen/Qwen3-1.7B-Base` on this 8 GB GPU) |
| warmup ratio | 0 to 0.2 | 0.03 |
| random seed | 0 to 2³¹−1 (whole number) | 42 |
| answer format | `step-by-step` or `terse` | `step-by-step` |

Bounds are inclusive.

## Story Map

| Learning-path step | Stories | Priority |
|---|---|---|
| 1. Data and evaluation (walking skeleton first) | US1.1–US1.5 | Must |
| 2. Supervised fine-tuning | US2.1–US2.5 | Must |
| 3. Run control service | US3.1–US3.7 | Must |
| 4. Results website | US4.1–US4.8 | Must |
| 5. Generalisation check | US5.1 | Must |
| 6. Final score, write-up and learning checks | US6.1–US6.3 | Must |
| 7. Reinforcement learning | US7.1 | Could |
| 8. Tuning loop | US8.1–US8.2 | Could |
| 9. Ablations | US9.1 | Could |
| 10. Self-taught chain of thought | US10.1–US10.4 | Could |
| 11. Fine-tuning lab | US11.1–US11.4 | Could |
| 12. Learning course | US12.1–US12.5 | Could |

---

## 1. Data and Evaluation

### US1.1 Load GSM8K and a fixed dev split

As Nico, I want GSM8K loaded inside the project folder and split once into a fixed dev set and a training set, so that every run trains and tunes on the same problems and the test split stays untouched.

- **Priority:** Must Have
- **Requirements:** FR1.1, FR1.2, NFR5, NFR7, NFR8
- **Depends on:** none
- **INVEST:** independent first story; small (loading and splitting); testable without a GPU.

- **AC1.1.1** Given an empty project cache, when the data command runs, then `openai/gsm8k` config `main` loads with no login or token and every downloaded file lies under the project folder's `.cache/`.
- **AC1.1.2** Given seed 42, when the split is built twice, then both builds save the same 500 dev problem ids and the same 6,973 training ids, the two lists do not overlap, and together they cover all 7,473 training problems.
- **AC1.1.3** Given the built dev and training lists, when they are checked against the 1,319 test problems, then no test problem appears in either list.
- **AC1.1.4** Given any project script, when it starts, then `HF_HOME`, `PIP_CACHE_DIR`, `XDG_CACHE_HOME`, `TRITON_CACHE_DIR`, `TORCHINDUCTOR_CACHE_DIR` and `TORCH_HOME` are set to absolute paths under the project root before any other import.
- **AC1.1.5** Given the saved split file is missing, when a run needs it, then it is rebuilt from the seed with the same ids; given the file is unreadable, then the run stops with a message naming the file.

### US1.2 Build the fixed 4-shot prompt

As Nico, I want one fixed 4-shot prompt built from the dev split, so that every model is scored with the same examples and never on its own examples.

- **Priority:** Must Have
- **Requirements:** FR1.3
- **Depends on:** US1.1
- **INVEST:** small; pure text building, testable without a model.

- **AC1.2.1** Given the dev split and the seed, when the prompt is built twice, then the same four dev problems are chosen as exemplars both times, picked deterministically from the seed.
- **AC1.2.2** Given the four exemplars, when the dev split is scored, then those four problems are left out and 496 problems are scored.
- **AC1.2.3** Given a target question, when the prompt is built, then it holds the four exemplar questions, each followed by its worked answer ending in `#### <number>`, then the target question, and the text is byte-identical for the same inputs.

### US1.3 Score a model's answer

As Nico, I want each answer scored by its final number, so that a score means "the model got the number right" and nothing else.

- **Priority:** Must Have
- **Requirements:** FR1.4
- **Depends on:** none
- **INVEST:** small; pure function, testable without a model.

- **AC1.3.1** Given an output ending `#### 1,234` and gold answer `1234`, when it is scored, then the comma is stripped and the answer counts as correct.
- **AC1.3.2** Given an output with no `####` line, when it is scored, then the last number in the output is taken as the answer.
- **AC1.3.3** Given an output with no number at all, when it is scored, then it counts as wrong and scoring carries on with the next problem.
- **AC1.3.4** Given the outputs `72.0`, `$18` and `-5` against gold answers `72`, `18` and `-5`, when they are scored, then all three count as correct because the comparison is numeric.

### US1.4 Evaluate a model on a split (walking skeleton)

As Nico, I want one command that evaluates a model, or a model plus a saved adapter, on a named split and logs the result, so that I can prove the whole chain works on a few problems before any training goes in.

- **Priority:** Must Have
- **Requirements:** FR1.5, FR1.6, FR1.7, NFR3, NFR7
- **Depends on:** US1.1, US1.2, US1.3
- **INVEST:** this is the walking skeleton (team-practices.md, Walking Skeleton); small enough for one unit; testable on the CPU on 3 dev problems in minutes. GPU use is first proven by the first detached long run, the 0.6B baseline evaluation (AC1.5.1).

- **AC1.4.1** Given `Qwen/Qwen3-0.6B-Base` on the CPU and a limit of 3 dev problems, when the evaluation runs with greedy decoding and up to 256 new tokens, then it reports accuracy, the number scored and minutes, and writes one prediction per problem to `outputs/<run_id>/`.
- **AC1.4.2** Given an evaluation started without `--run-id`, when it ends, then its row is written to a temporary path and `results/runs.csv` is unchanged.
- **AC1.4.3** Given an evaluation started with `--run-id q06-base-dev-1` and the results file pointed at a temporary path, when it ends, then exactly one row is appended with `date, run_id, model, method, data, metric, value, minutes, config_hash` and `run_id` equal to `q06-base-dev-1`.
- **AC1.4.4** Given an evaluation run, when it ends, then the measured seconds per problem are saved in `outputs/<run_id>/` for later estimates.
- **AC1.4.5** Given the same configuration and seed, when two evaluations are started, then both rows carry the same `config_hash`; given any dial changed, then the hash differs.
- **AC1.4.6** Given an adapter path that does not exist, when the evaluation starts, then it stops with a message naming the path and writes no row.

### US1.5 Score the baselines

As Nico, I want both base models scored on the dev and test splits, and the main baseline cross-checked once with lm-evaluation-harness, so that every later gain is measured against a trusted starting point.

- **Priority:** Must Have
- **Requirements:** FR1.8, FR1.9
- **Depends on:** US1.4
- **INVEST:** independent once the evaluation exists; the long runs are detached runs, the harness wrapper is testable on a few problems.

- **AC1.5.1** Given `Qwen/Qwen3-0.6B-Base`, when it is scored on the 496 scored dev problems, then its dev accuracy is recorded. [manual] Verify: results/runs.csv row q06-base-dev
- **AC1.5.2** Given `Qwen/Qwen3-0.6B-Base`, when it is scored on all 1,319 test problems, then its test accuracy is recorded. [manual] Verify: results/runs.csv row q06-base-test
- **AC1.5.3** Given `Qwen/Qwen3-1.7B-Base`, when it is scored on the 496 scored dev problems, then its dev accuracy is recorded. [manual] Verify: results/runs.csv row q17-base-dev
- **AC1.5.4** Given `Qwen/Qwen3-1.7B-Base`, when it is scored on all 1,319 test problems, then its test accuracy is recorded. [manual] Verify: results/runs.csv row q17-base-test
- **AC1.5.5** Given the lm-evaluation-harness `gsm8k` task (5-shot, flexible extract, test split) and a limit of 5 problems, when the harness wrapper runs, then it writes one row with method `base`, data `gsm8k-test-harness` and the harness accuracy to the results file.
- **AC1.5.6** Given `Qwen/Qwen3-1.7B-Base`, when the full harness cross-check runs, then the harness accuracy is recorded beside the project's own test number as a cross-check only. [manual] Verify: results/runs.csv row q17-base-harness

---

## 2. Supervised Fine-Tuning

### US2.1 Check a run configuration before training

As Nico, I want every run configuration checked against the dial table before anything starts, so that a typo never costs me a run.

- **Priority:** Must Have
- **Requirements:** FR2.1, FR2.2
- **Depends on:** none
- **INVEST:** small; pure validation, testable without a GPU.

- **AC2.1.1** Given a configuration with no dials set, when it is checked, then it passes and every dial takes the default in the Training Dials table.
- **AC2.1.2** Given each numeric dial set to its minimum and to its maximum, when the configuration is checked, then it passes; given a value just outside either bound, then it is rejected with a message naming the dial and its allowed range.
- **AC2.1.3** Given a model, LoRA rank or answer format outside its allowed set, when the configuration is checked, then it is rejected with a message naming the dial and listing the allowed values.
- **AC2.1.4** Given an unknown dial name or a value of the wrong type (for example learning rate `abc`), when the configuration is checked, then it is rejected with a message naming the field.
- **AC2.1.5** Given a configuration that names the test split as training or tuning data, when it is checked, then it is rejected with "The test split is never used for training or tuning".

### US2.2 Fine-tune with LoRA and stream metrics

As Nico, I want a LoRA fine-tuning command that streams its metrics as it trains, saves the adapter and scores it on dev, so that I can watch a run and get its result without extra steps.

- **Priority:** Must Have
- **Requirements:** FR2.1, FR2.3, FR2.4, FR1.7
- **Depends on:** US1.4, US2.1
- **INVEST:** one vertical slice of training; testable on a tiny model fixture with a few examples and steps.

- **AC2.2.1** Given a model (in tests the tiny model fixture), 50 training examples and a few steps, when the fine-tune runs, then it saves its adapter under `checkpoints/<run_id>/`.
- **AC2.2.2** Given a running fine-tune, when its `outputs/<run_id>/metrics.jsonl` is read at any moment, then every complete line is one JSON object with step, total steps, loss, learning rate, elapsed seconds and estimated seconds remaining, and a half-written last line is never read as data.
- **AC2.2.3** Given a fine-tune that evaluates during training, when it evaluates, then a metrics line with the dev accuracy is added.
- **AC2.2.4** Given a fine-tune that ends, when it finishes, then it scores the adapter on dev (limited in tests) and appends one row with method `sft` and its `config_hash` to the results file.
- **AC2.2.5** Given a fine-tune run, when it ends, then the measured seconds per training step are saved in `outputs/<run_id>/` for later estimates.
- **AC2.2.6** Given a running fine-tune, when a step is logged, then its metrics line also carries `grad_norm` (the gradient norm the trainer reports) and `epoch` (the fractional epoch the step is in); given a trainer that reports neither, then both are null; a line written before this change, without the two fields, is still a valid line.

### US2.3 Estimate how long a run will take

As Nico, I want each run's duration estimated from measured times before it starts, so that I never launch a run that blows past 3 hours.

- **Priority:** Must Have
- **Requirements:** FR2.6, FR1.7, NFR2
- **Depends on:** US1.4, US2.2
- **INVEST:** small; arithmetic on saved measurements, testable without a GPU.

- **AC2.3.1** Given saved seconds per training step for a model, when a training run is planned, then its estimate is its total steps times that per-step time.
- **AC2.3.2** Given saved seconds per problem for a model, when an evaluation is planned, then its estimate is the number of problems times that per-problem time.
- **AC2.3.3** Given an estimate above 3 hours, when the run is planned, then it is flagged "Estimated time is above the 3-hour cap".
- **AC2.3.4** Given no saved measurement for that model, when a run is planned, then the estimate reads "No estimate yet", never zero.

### US2.4 Run the first real fine-tunes

As Nico, I want to run the default fine-tune on both models and see their dev scores and memory use, so that I know the defaults fit my GPU and how much fine-tuning helps.

- **Priority:** Must Have
- **Requirements:** FR2.4, NFR1, NFR2
- **Depends on:** US2.2, US2.3
- **INVEST:** independent once training exists; the long runs are detached runs.

- **AC2.4.1** Given any training or evaluation run, when it ends, then its peak GPU memory in gigabytes is saved in `outputs/<run_id>/`.
- **AC2.4.2** Given the default dials on `Qwen/Qwen3-0.6B-Base`, when the fine-tune runs, then it finishes within 3 hours without running out of GPU memory and records its dev accuracy. [manual] Verify: results/runs.csv row q06-sft-dev
- **AC2.4.3** Given the default dials with `Qwen/Qwen3-1.7B-Base` and batch size 2 (changed 2026-11-07: batch size 4 ran out of memory on this 8 GB GPU), when the fine-tune runs, then it finishes within 3 hours without running out of GPU memory and records its dev accuracy. [manual] Verify: results/runs.csv row q17-sft-dev

### US2.5 Keep only the weights that matter

As Nico, I want old adapters pruned except the best run's and the finalists', so that my disk does not fill up while every result stays in the run log.

- **Priority:** Must Have
- **Requirements:** FR2.5
- **Depends on:** US2.2
- **INVEST:** small; file housekeeping, testable with fake checkpoint folders.

- **AC2.5.1** Given several runs of one model in the results file, when the best run is picked, then it is the run with the highest dev accuracy for that model, and a tie goes to the earlier run.
- **AC2.5.2** Given adapters under `checkpoints/`, when the prune command runs without `--yes`, then it only lists the adapters it would delete and deletes nothing.
- **AC2.5.3** Given adapters under `checkpoints/`, when the prune command runs with `--yes`, then it deletes every adapter except each model's best run and every finalist in `results/finalists.json`, and `results/runs.csv` is unchanged; an adapter folder with no row in the results file is deleted too, unless its run holds the GPU lock (a run still in progress).
- **AC2.5.4** Given a run row whose adapter folder is already gone, when the prune command runs, then it skips that run and reports it as already pruned.

---

## 3. Run Control Service

### US3.1 See the runs and the current status

As Nico, I want a local service that lists my runs and the current status, so that the website always shows what is true on disk.

- **Priority:** Must Have
- **Requirements:** FR3.1, FR3.7, NFR6
- **Depends on:** US1.4
- **INVEST:** small read-only slice; testable with a temporary results file and outputs folder.

- **AC3.1.1** Given rows in the results file and run folders in `outputs/`, when the run list is requested, then every run appears once with its run id, model, method, dev accuracy, test accuracy where scored, minutes and date.
- **AC3.1.2** Given the lock is free (no process holds the OS lock on `outputs/run.lock`, whether or not the file exists), when the status is requested, then it reads IDLE.
- **AC3.1.3** Given one malformed row among good rows in the results file, when the run list is requested, then the good rows are listed and the response says one row was skipped.
- **AC3.1.4** Given no results file yet, when the run list is requested, then the list is empty; given an unreadable results file, then the response is an error naming the file.
- **AC3.1.5** Given the service starts, when it binds, then it listens on 127.0.0.1 only.
- **AC3.1.6** Given a RUNNING run whose folder holds `predictions.jsonl`, when the status is requested (`GET /status`, and the stream's `status` event), then the status carries `evaluation: {split, scored, total}`: `split` from the run's `config.json`, `scored` the number of complete lines (ending in a newline) in `predictions.jsonl`, and `total` the split's size (dev 500, test 1319, the other splits as the launcher's split sizes) or the run's `limit` when that is smaller; `scored` is never shown above `total`. Given no `predictions.jsonl` yet, a run that is not RUNNING, a split with no known size, or a `config.json` that is missing or cannot be read, then `evaluation` is null and the rest of the status is unchanged; reading these files never makes the status request fail. `last_run` carries `evaluation: null`.
- **AC3.1.7** Given a RUNNING run whose `predictions.jsonl` gains lines, when the stream polls, then it sends a new `status` event carrying the new `scored`, so evaluation progress reaches the page within 5 seconds (NFR10).

### US3.2 Start a run in two steps

As Nico, I want to check a run's summary and exact command before it launches, so that I only start the runs I meant to.

- **Priority:** Must Have
- **Requirements:** FR3.2, FR3.3, NFR6
- **Depends on:** US2.1, US2.3, US3.1
- **INVEST:** one vertical slice (check, then launch); testable with a stub training command.

- **AC3.2.1** Given a valid configuration, when it is checked, then the service returns the attempt id, model, method, the changes against the last run, the estimate and the exact command, and launches nothing.
- **AC3.2.2** Given a checked configuration, when Nico confirms, then the service launches the run as a separate process with `--run-id <base id>-<n>`, and the run keeps going if the browser closes.
- **AC3.2.3** Given earlier attempts `q06-sft-dev-1` and `q06-sft-dev-2`, when a new `q06-sft-dev` run is checked, then its attempt id is `q06-sft-dev-3`.
- **AC3.2.4** Given an invalid configuration, when it is checked, then the service rejects it with the dial and its allowed range; given a confirm with no matching check, then nothing is launched.
- **AC3.2.5** Given a configuration value containing shell characters such as `; rm -rf`, when a run is launched, then the command is built only from the project's own training and evaluation entry points as an argument list and no shell interprets the value.

### US3.3 Only one GPU run at a time

As Nico, I want the GPU used by one run at a time, however it was started, so that two runs never crash each other.

- **Priority:** Must Have
- **Requirements:** FR3.4, FR3.7, NFR1
- **Depends on:** US3.2
- **INVEST:** small; testable with a lock file and a stub process.

- **AC3.3.1** Given a run holds the lock file under `outputs/`, when a second start comes from the website, then no second GPU process starts and the run is put in the queue instead (US3.7).
- **AC3.3.2** Given a run holds the lock file, when a training or evaluation command is started from the terminal, then it refuses with "A run is already active" and the active run id, and exits without touching the GPU.
- **AC3.3.3** Given a free lock whose file content still names a run (its process ended without finishing, and the kernel released the lock), when the status is requested, then that run is shown as FAILED with "The run process ended without finishing", and the status reads IDLE.
- **AC3.3.4** Given a run still alive after the service restarts, when the status is requested, then it reads RUNNING with that run's id and its metrics stream resumes.

### US3.7 Queue runs from the website

As Nico, I want runs I start from the website while the GPU is busy to wait in line and start on their own, so that I can line up an evening of runs without watching for each one to end.

- **Priority:** Must Have
- **Requirements:** FR3.4
- **Depends on:** US3.2, US3.3
- **INVEST:** one queue rule set; testable with a temporary queue folder and stub processes. Added 2026-10-31 (inception/changes.md; domain-design Q3, Q5).

- **AC3.7.1** Given a run is active, when Nico confirms a start from the website, then the run is added to the queue as waiting with its attempt id and its position, and no second GPU process starts.
- **AC3.7.2** Given waiting runs, when the active run ends (finished, stopped or failed), then the worker starts the oldest waiting run and the others move up one place.
- **AC3.7.3** Given 10 runs already waiting, when another start is confirmed, then it is refused with "The queue is full (10 waiting)" and nothing is added.
- **AC3.7.4** Given a waiting run, when Nico removes it, then it leaves the queue, never starts, and no row is written for it.
- **AC3.7.5** Given waiting runs, when the service or the worker restarts, then the same runs are still waiting in the same order.
- **AC3.7.6** Given a run started from the terminal holds the lock, when the worker is ready for the next waiting run, then it waits until the lock is free and starts the run then.
- **AC3.7.7** Given no run of this project holds the lock but another long run or a GPU process is on this PC (another project's run, or other GPU use: `scripts/run-detached.sh --check` exits 3, or 4 when nvidia-smi fails; a check that times out after 30 seconds counts as 4), when the worker is ready for the next waiting run, then it starts nothing, the waiting runs keep their order, the worker log names what holds the GPU (once, until that changes), it checks again at most every 10 seconds, and it starts the run once the check exits 0. A check that cannot run at all (the script missing or broken) leaves the lock alone to decide, as before.

### US3.4 Stop a run

As Nico, I want to stop a run, so that I can free the GPU when a run is clearly going nowhere.

- **Priority:** Must Have
- **Requirements:** FR3.5
- **Depends on:** US3.2, US3.3
- **INVEST:** small; testable with a stub process.

- **AC3.4.1** Given a running run, when Nico stops it, then its process ends, its status reads STOPPED, the metrics logged so far are kept, and no score row is appended.
- **AC3.4.2** Given a stopped run, when the status is next requested, then the lock is free and a new run can start.
- **AC3.4.3** Given no active run, when a stop is requested, then the response is "No run is active" and nothing changes.

### US3.5 See why a run failed

As Nico, I want a failed run to show its reason and its last log lines, so that I can fix it without digging through files.

- **Priority:** Must Have
- **Requirements:** FR3.7
- **Depends on:** US3.2
- **INVEST:** small; testable with a stub process that exits with an error.

- **AC3.5.1** Given a run whose process exits with a non-zero code, when the status is requested, then it reads FAILED with the exit reason and the last 20 lines of the run's log.
- **AC3.5.2** Given a run that failed with a CUDA out-of-memory error in its log, when the status is requested, then the exit reason reads "GPU out of memory".
- **AC3.5.3** Given a run whose log cannot be read, when the status is requested, then it shows "Run log could not be read" and names the file.

### US3.6 Mark finalists and score them on test

As Nico, I want to mark a run as a finalist and only then score it on the test split, after a second confirmation, so that I never tune on test by accident.

- **Priority:** Must Have
- **Requirements:** FR3.6, NFR8
- **Depends on:** US3.2
- **INVEST:** one rule end to end; testable with a temporary finalists file and a stub evaluation.

- **AC3.6.1** Given a run, when Nico marks it as a finalist, then its run id is saved in `results/finalists.json`; when he unmarks it, then it is removed.
- **AC3.6.2** Given a run that is not a finalist, when a test-split evaluation of it is requested, then it is refused with "Only finalists can be scored on the test split".
- **AC3.6.3** Given a finalist, when a test-split evaluation is requested without the second confirmation, then nothing is launched; with the second confirmation, then the evaluation launches.
- **AC3.6.4** Given a training run or a tuning trial, when it is requested with the test split as its data or early-stopping set, then it is refused (US2.1).
- **AC3.6.5** Given no `results/finalists.json`, when finalists are listed, then there are none; given an unreadable file, then the response names the file and no test-split evaluation can start.

---

## 4. Results Website

### US4.1 Move between the pages

As Nico, I want the same top bar on every page and full keyboard use, so that I can get anywhere in one click or a few keys.

- **Priority:** Must Have
- **Requirements:** FR4.1, FR4.6, NFR9
- **Depends on:** none
- **INVEST:** small; testable with component tests.

- **AC4.1.1** Given any page, when it renders, then the top bar shows the wordmark linking to the landing page, "Scores" and "Training".
- **AC4.1.2** Given any page, when Nico presses Tab from the top, then a skip link comes first, then the top bar links, and every control on the page is reachable by keyboard.
- **AC4.1.4** Given any page (landing, scores, training, reasoning, lab, course; added 2026-11-08: every later page too) and the top bar, when it renders, then no page container and not the top bar's row sets a fixed maximum width (no `max-w-[1280px]`, no `--content-width` cap): the content spans the window's full width less the side gutter (`--gutter`, 24 px); prose paragraphs keep their readable line length (at most 75 characters).
- **AC4.1.5** Given a window about 2,500 px wide, when Nico opens the training page and the other pages, then the content fills the window from side to side instead of a centred column. [manual] Verify: Nico looks at each page full screen.
- **AC4.1.3** Given each of the three pages and the confirm dialog, when Nico compares them with his screenshots in `inputs/design/`, then the colours, type and spacing follow those screenshots. [manual] Verify: Nico checks each page side by side with `inputs/design/` and approves at the website unit's checkpoint

### US4.2 See the best result on the landing page

As Nico, I want the landing page to show the halftone headline and my best result so far, so that I see at a glance where the project stands.

- **Priority:** Must Have
- **Requirements:** FR4.2, FR4.5, NFR9
- **Depends on:** US3.1, US4.1
- **INVEST:** one page; testable with component tests and a mocked run list.

- **AC4.2.1** Given scored runs, when the landing page renders, then it shows the wordmark as a real `h1` (the halftone canvas is `aria-hidden`), the one-line description, the "best so far" line with model, method, dev accuracy and gain over that model's baseline, and buttons to Training and Scores.
- **AC4.2.2** Given no runs, when the landing page renders, then "best so far" reads "No runs yet: start with a baseline on the training page" with the Go to training button.
- **AC4.2.3** Given the run list cannot be read, when the landing page renders, then "best so far" reads "Run log could not be read" naming the file, and the headline still renders.
- **AC4.2.4** Given the operating system's reduce-motion setting is on, when the landing page renders, then the halftone dots stay still and no pointer or click animation runs.
- **AC4.2.5** Given the landing page, when it renders, then it fills the window height below the top bar (`min-h-[calc(100svh-3.5rem)]`) and the halftone wordmark sits vertically centred in the free height above the description and buttons, not at the top: the headline section grows into that height (`flex-1`), centres its canvas and carries `data-align="center"`, and the halftone component draws the word in the middle of its canvas (`align="center"`; the default `"bottom"` keeps the old placement).
- **AC4.2.6** Given a window about 2,500 px wide, when Nico opens the landing page full screen and moves the pointer over the wordmark, then `gsm8k` sits in the middle of the screen and the dots follow the pointer smoothly, with no stutter. [manual] Verify: Nico, on his own screen.
- **AC4.2.7** Given the landing halftone at any window size, when it lays out and animates, then it holds at most 16,000 dots (`hwfGap` widens the 6 px gap only as far as needed), each frame fills its dots in at most 4 `fill()` calls whatever the dot count (at-rest dots in one path, displaced dots in a few colour steps), plus at most one fill for the grain, and the grain pattern is created once per layout, not per frame; with nothing moving and no pointer over it, no frame is requested.
- **AC4.2.8** Given a dot pushed by the pointer, when the animation steps it, then it moves by elapsed time: `hwfStep` takes an optional elapsed time in milliseconds (default one 60 Hz frame, which gives the old result), clamped to at most 50 ms, so a dot's position over one second differs by less than 5% of its largest displacement between 60 and 144 frames per second.

### US4.3 Rank runs on the scores page

As Nico, I want a ranked table of my runs with the baseline always shown, so that I can see which change helped and by how much.

- **Priority:** Must Have
- **Requirements:** FR4.3, FR4.5, FR3.6, NFR9
- **Depends on:** US3.1, US4.1
- **INVEST:** one page; testable with component tests and a mocked run list.

- **AC4.3.1** Given scored runs, when the scores page renders, then runs are ranked by dev accuracy (ties by date), each row shows run id, model, method, dev accuracy, test accuracy, gain over the same model's baseline, minutes and date, and each model's baseline row is always shown and marked BL.
- **AC4.3.2** Given a run with no test score, when the table renders, then its test cell shows "--", not 0%, and every gain carries a + or − sign so it never relies on colour alone.
- **AC4.3.3** Given a model filter and a method filter, when Nico applies them, then only matching runs are listed and the baseline row stays.
- **AC4.3.4** Given no scored runs, when the page renders, then it reads "No scored runs yet. Run a baseline from the training page." with a link; given the run list cannot be read, then it reads "Run log could not be read" naming the file, with a Retry button.
- **AC4.3.5** Given a run row, when Nico marks or unmarks it as a finalist, then the mark is saved through the service and shown on the row.

### US4.4 Compare two runs

As Nico, I want to pick two runs and see their settings, accuracy difference and curves together, so that I understand what one change did.

- **Priority:** Must Have
- **Requirements:** FR4.3
- **Depends on:** US4.3
- **INVEST:** small; testable with component tests.

- **AC4.4.1** Given two picked runs, when Nico presses Compare, then their settings show side by side with changed dials highlighted by text, the accuracy difference shows with its sign, and both training curves are overlaid.
- **AC4.4.2** Given fewer than two picked runs, when the page renders, then Compare is disabled with "Pick two runs to compare"; given two already picked, then a third pick is refused until one is unpicked.
- **AC4.4.3** Given a picked run with no metrics file, when the runs are compared, then its curve area reads "No curve recorded" and the other run's curve still shows.

### US4.5 Watch a run live

As Nico, I want the training page to show live curves and my past runs, so that I can see a run learning while it trains.

- **Priority:** Must Have
- **Requirements:** FR4.4, FR4.5, FR2.3, NFR10
- **Depends on:** US2.2, US3.1, US4.1
- **INVEST:** one panel; testable with component tests and a mocked metrics stream.

- **AC4.5.1** Given metrics lines for a supervised run, when the training page renders, then it draws loss, learning rate and dev accuracy curves with step, elapsed time and time remaining; given a reinforcement-learning run, then it also draws reward, KL and answer length.
- **AC4.5.2** Given an open metrics stream, when a new line arrives, then the curves and the step counter update without a page reload.
- **AC4.5.3** Given the metrics stream drops, when the page notices, then it shows "Live updates paused, reconnecting" with the time of the last update, and it resumes when the stream comes back.
- **AC4.5.4** Given a run has started but no metrics line has arrived, when the page renders, then it shows "Waiting for first step..."; given no run has ever happened, then it reads "No run yet. Set the dials and press Start run." and the past runs list reads "None yet".
- **AC4.5.5** Given past runs, when the training page renders, then they are listed with run id, status, start time, minutes and dev accuracy (course runs as AC12.3.8 says, added 2026-11-08), and opening one shows its curves labelled with its run id.
- **AC4.5.6** Given a real run in progress, when a new metrics line is written, then it appears on the training page within 5 seconds. [manual] Verify: Nico watches a live run and checks the step counter against `outputs/<run_id>/metrics.jsonl` at the website unit's checkpoint
- **AC4.5.7** Given metrics lines for a run (live, or a past run opened from Past runs), when the training page renders, then a "Live numbers" panel shows progress (step, total steps, percent), epoch, speed (seconds per step and steps per minute over the last 10 steps), elapsed time, time remaining and the clock time the run should end, loss (latest, lowest, average of the last 10 steps, change since the first step), learning rate (latest, and whether it is warming up, decaying or steady), gradient norm (latest and highest), and the latest and best dev accuracy, plus reward, KL and answer length when the lines carry them; each number carries a one-line plain-language meaning, and a number no line carries reads "—". The panel updates with each stream line.
- **AC4.5.8** Given metrics lines for a run, when the training page renders, then a "Recent steps" table lists the 10 newest step lines, newest first, with step, loss, learning rate, gradient norm and elapsed time; given a new stream line, then it appears at the top without a page reload.
- **AC4.5.9** Given a machine with an NVIDIA GPU, when `GET /api/v1/gpu` is called, then it answers `available: true` with the GPU name, utilisation percent, memory used and total in MiB, temperature in °C, power draw and limit in W and the current and maximum shader clock in MHz, read from `nvidia-smi` (a value `nvidia-smi` reports as unavailable is null); given no `nvidia-smi`, a failing or slow one, or output that does not parse, then it answers 200 with `available: false` and a reason, never a 500.
- **AC4.5.11** Given the band's status is RUNNING and the reduce-motion setting is off, when the training page shows the hourglass band, then dots keep flowing down through the waist from the top half into the bottom half on every animation frame, also between metrics lines and while the run scores problems, and the band carries `data-flow="on"`; the share of lit dots below the waist stays the progress share (`data-fraction`). Given the reduce-motion setting is on, or the band is IDLE, STOPPED, FAILED or loading, then nothing flows, no animation frame is requested once the drawing is settled, and the band carries `data-flow="off"`.
- **AC4.5.12** Given a RUNNING run whose status carries `evaluation` (AC3.1.6), when the training page renders, then the band shows `scoring <split> <scored> / <total>` with the percent instead of the step counter, its progressbar named "Run progress" has `aria-valuenow` scored, `aria-valuemax` total and `aria-valuetext` "scored <scored> of <total> problems", `data-fraction` is scored / total, and the line under the status reads "Training done, scoring the <split> split" when the run has metrics lines, else "Scoring the <split> split" (an evaluation run, so it no longer reads "Waiting for first step..."). Given `evaluation` is null, the band shows the step counter as before.
- **AC4.5.10** Given the training page is open, when it renders, then a "GPU" panel shows the GPU name, utilisation, memory used of total, temperature, power draw of limit and clock, each with a one-line plain-language meaning, and refreshes every 3 seconds while the page is open; given `available: false` or a failed read, then the panel reads "GPU stats unavailable" with the reason and the rest of the page keeps working.

### US4.6 Start and stop runs from the training page

As Nico, I want to set the dials, confirm and start a run, or stop it, from the training page, so that I do not need the terminal for everyday runs.

- **Priority:** Must Have
- **Requirements:** FR4.4, FR3.2, FR3.4, FR3.5, NFR9
- **Depends on:** US3.2, US3.4, US3.7, US4.5
- **INVEST:** one panel and dialog; testable with component tests and a mocked service.

- **AC4.6.1** Given the training page, when it renders, then the dials panel shows all eleven dials from the Training Dials table, each with a visible label and its default; given an invalid value, then the field names the allowed range and Start stays disabled.
- **AC4.6.2** Given valid dials, when Nico presses Start run, then the confirm dialog shows the attempt id, model, method, changes against the last run, the estimate and the exact command; given a run is active, then it also says the run will wait in the queue and at which position; Cancel closes it and launches or queues nothing.
- **AC4.6.3** Given an estimate above 3 hours, when the confirm dialog opens, then it shows a warning line and Start needs a second confirmation.
- **AC4.6.4** Given an active run, when the page renders, then the Start button reads "Add to queue", Stop is enabled, and the status sits in a polite live region.
- **AC4.6.5** Given the launch fails, when Nico confirms, then the dialog stays open and shows why.
- **AC4.6.6** Given the confirm dialog is open, when Nico uses the keyboard, then focus stays inside the dialog, Escape cancels, and focus returns to the Start button on close.
- **AC4.6.7** Given waiting runs, when the training page renders, then a "Queued runs" list shows each one's position, attempt id, model and method with a Remove button; given no waiting runs, then the list is hidden.
- **AC4.6.8** Given the dials panel, when it renders, then the method choice and each of the eleven dials has an "Explain <label>" button (`aria-expanded`) that shows a plain-language explanation of what the dial does, what a higher and a lower value do, and a tip for this 8 GB GPU; one "Explain all settings" button opens every explanation and then reads "Hide all explanations"; the explanations never change a value or block Start.
- **AC4.6.9** Given the dials panel, when it renders, then a "How training uses your NVIDIA GPU" button (`aria-expanded`) opens a list of what every fine-tune on the GPU already does: bf16 mixed precision, the fused AdamW optimiser, gradient checkpointing, LoRA adapters (only they get gradients) and a linear learning-rate decay after warm-up, each with one line on why.

### US4.7 See the model being fine-tuned

As Nico, I want the training page to draw how the model is being fine-tuned, so that I see what stays frozen, what is trained and what one step does to the model, not only a progress band and curves.

- **Priority:** Must Have
- **Requirements:** FR4.7, FR4.4, NFR9
- **Depends on:** US4.5
- **INVEST:** one panel; testable with component tests and a mocked metrics stream (the drawing is decorative, so tests read its text and `data-*` markers).

- **AC4.7.1** Given a run with method `sft`, `terse`, `optuna`, `selfcot` or `grpo` and at least one step line (a metrics line with a loss), when the training page renders, then a region named "How the model is fine-tuned" draws one layer for each decoder layer of the run's model (28 for both Qwen3 models), each marked frozen, and one LoRA adapter per layer marked trained; and it states the weight counts worked out from the model's shape and the run's LoRA rank: for `Qwen/Qwen3-1.7B-Base` at rank 16 "17,432,576 trained", "1,720,574,976 frozen" and "1.0%", for `Qwen/Qwen3-0.6B-Base` at rank 16 "10,092,544 trained", "596,049,920 frozen" and "1.7%".
- **AC4.7.2** Given a fine-tune run with step lines, when the panel renders, then it lists five stages of one step, Read, Guess, Score, Blame and Nudge, each with a one-line plain-language meaning, and the newest step line's figures: Read shows the examples per step (the run's batch size), Score shows the loss, the average chance it gave the right next word (e to the power of minus the loss, as a whole percent) and how the loss changed since the first step line, Blame shows the gradient norm ("—" when the line has none), Nudge shows the learning rate; and it shows the step, the total steps and the examples seen so far (step times batch size).
- **AC4.7.3** Given an open metrics stream for the live run, when a new step line arrives, then the panel's step and every figure update without a reload and the passes of the drawing start again for the new step.
- **AC4.7.4** Given a fine-tune run, when the panel renders, then a "One layer up close" figure names the query projection of a layer: the frozen matrix with its size (for 1.7B, 2048 × 2048 = 4,194,304 weights), the two adapter matrices A and B with their sizes (16 × 2048 and 2048 × 16), the adapter's weights in total (65,536) and the scale alpha divided by rank (2 for alpha 32 and rank 16), all worked out from the model's shape and the run's settings.
- **AC4.7.5** Given a run that does not change the model (method `cotgen`, `base` or `best`), when the panel renders, then it says "This run does not change the model" with one line on what the run does instead, draws the layers with no adapter marked trained, shows how far the run is (for `cotgen` the problems written out of the problems to write, for the others the problems scored out of the problems to score), and shows no Score, Blame or Nudge stage.
- **AC4.7.6** Given a fine-tune run with no step line yet, when the panel renders, then it reads "Waiting for the first logged step" and shows no figures; given a fine-tune that has ended with no step line recorded, then it reads "No step lines were recorded for this run."; given no run has ever happened, then it reads "Nothing to show yet: start a fine-tune to watch the model change."
- **AC4.7.7** Given a run that is not live (the last run after it ended, or a past run opened from Past runs) with at least two step lines, when the panel renders, then a slider named "Replay step" runs from its first to its last step line and a button "Play replay" steps through them to the last one; moving the slider shows that step's figures and the panel reads "Replaying step N of M"; given the live run, then no slider shows and the panel reads "Following the live run".
- **AC4.7.8** Given any run, when the panel renders, then the drawing is hidden from assistive technology and the same facts are text; the panel says which parts are measured (step, loss, gradient norm, learning rate) and which are drawn for illustration (the layers and the moving dots; every adapter is updated on every step and per-layer sizes are not recorded); and with the operating system's reduce-motion setting on the panel carries `data-motion="still"` and plays no passes, otherwise `data-motion="live"`.
- **AC4.7.9** Given the next real fine-tune run on this PC, when Nico watches the panel from its first step, then he can say in his own words what stays frozen, what is trained and what one step does to the model, and he tells the lead if the picture does not show it. [manual] Verify: Nico watches the live run `q17-selfcot-dev-1` (or any fine-tune) and answers in session.
- **AC4.7.10** Given any window width, when the training page renders the "How the model is fine-tuned" panel, then its main drawing is at most two-thirds of the window width (`max-w-[66vw]`; about 2,500 px on a 3,840 px window, 1,580 px on a 2,400 px window) and centred in its column, so it grows with the screen without filling it (changed 2026-11-08 from a fixed 1,100 px, which Nico found far too small on his screen); at narrow widths it keeps its minimum width and scrolls sideways as before, and the "One layer up close" figure stays at most 280 px wide.

### US4.8 Walk through one step, token by token

As Nico, I want the training page to animate what happens inside one training step, token by token, and how a model writes an answer, so that I see how fine-tuning works mechanically and that the training text is tokenized once, not every batch.

- **Priority:** Must Have
- **Requirements:** FR4.8, NFR9
- **Depends on:** US4.7
- **INVEST:** one panel under "How the model is fine-tuned"; testable with component tests, fake timers and a mocked metrics stream (the drawing is decorative, so tests read its text and `data-*` markers).

- **AC4.8.1** Given a run with method `sft`, `terse`, `optuna` or `selfcot`, when the training page renders, then a region named "One training step, token by token" lists eight phases in this order, each with a one-line plain-language meaning: Tokenize, Batch, Embed, Forward, Predict, Loss, Backward, Update; the phase being shown carries `aria-current="step"`, and the region carries `data-phase` with the shown phase's name in lower case.
- **AC4.8.2** Given the walkthrough of a fine-tune, when the Tokenize phase is shown, then it says that the whole training set was tokenized once, before step 1, and that each step only pads its batch of token ids into a rectangle (no text is tokenized again); and it shows a sample training example as token chips, the question's tokens marked `data-role="prompt"` in a group labelled "no loss" and the answer's tokens marked `data-role="answer"`.
- **AC4.8.3** Given a fine-tune run with step lines, when the phases are shown, then Batch shows the run's batch size and padding chips marked `data-role="pad"`; Predict shows, for every answer token, the next token it must guess (the text shifted by one); Loss shows the newest step line's loss and says that only answer tokens count; Backward shows the newest gradient norm ("—" when the line has none) and says the gradient stops at the frozen weights; Update shows the newest learning rate and says that only the LoRA matrices A and B change; and with no step line yet, the phases still show with "—" in place of the figures.
- **AC4.8.4** Given either walkthrough (AC4.8.1 or AC4.8.5) with the reduce-motion setting off, when it is shown, then it carries `data-motion="live"` and moves to the next phase every 1.8 seconds, from the last phase back to the first; a button "Pause walkthrough" stops it and then reads "Play walkthrough"; buttons "Previous phase" and "Next phase" move one phase at any time; a new step line from the live stream does not move the phase. With reduce-motion on, it carries `data-motion="still"`, starts paused and never moves by itself.
- **AC4.8.5** Given a run that does not change the model (method `cotgen`, `base` or `best`), when the training page renders, then a region named "How the model writes an answer, token by token" lists the phases Tokenize, Forward, Choose, Append and Stop, and for `cotgen` a sixth phase Check (the answer is kept only when its final number is right); Choose says the model takes the most likely token for `base` and `best`, and samples at the run's temperature for `cotgen` (the config's `cot_temperature`, 0.7 when absent); the answer's tokens grow by one at each Append up to the sample answer's length, then the walkthrough starts again at Tokenize; the region carries `data-phase` as in AC4.8.1; and it says "The weights do not change."
- **AC4.8.6** Given any walkthrough, when it renders, then its drawing is hidden from assistive technology and the same facts are text; it says that the sample text is an illustration and that the loss, gradient norm and learning rate are the run's measured figures.
- **AC4.8.7** Given no run has happened, or a run whose method has no walkthrough, when the training page renders, then the walkthrough region reads "Start a run to see how a step works." and shows no phases.

---

## 5. Generalisation Check

### US5.1 Check generalisation on unseen math sets

As Nico, I want the baseline and my final model scored on GSM-Plus and GSM-Symbolic, so that I can tell real learning from memorising GSM8K's style.

- **Priority:** Must Have
- **Requirements:** FR5.1, FR5.2
- **Depends on:** US1.4, US6.1
- **INVEST:** independent once the evaluation exists; the long runs are detached runs.

- **AC5.1.1** Given GSM-Plus testmini and GSM-Symbolic p1 with a limit of 5 problems each, when they are evaluated, then each is loaded, prompted and scored with the same protocol as GSM8K and writes one row with data `gsmplus-testmini` or `gsmsym-p1` (contract C1) to the results file.
- **AC5.1.2** Given any training or tuning data build, when it is checked, then it is refused if it would include a GSM-Plus or GSM-Symbolic problem.
- ~~**AC5.1.3** Given the baseline `Qwen/Qwen3-1.7B-Base`, when it is scored on GSM-Plus testmini, then the result is recorded with no pass or fail mark. [manual] Verify: results/runs.csv row q17-base-gsmplus~~ Deferred (Nico, 2026-11-07): run later from the website, outside this build.
- ~~**AC5.1.4** Given the baseline `Qwen/Qwen3-1.7B-Base`, when it is scored on GSM-Symbolic p1, then the result is recorded with no pass or fail mark. [manual] Verify: results/runs.csv row q17-base-gsmsym~~ Deferred (Nico, 2026-11-07): run later from the website, outside this build.
- ~~**AC5.1.5** Given the best tuned checkpoint, when it is scored on GSM-Plus testmini, then the result is recorded with no pass or fail mark. [manual] Verify: results/runs.csv row q17-best-gsmplus~~ Deferred (Nico, 2026-11-07): run later from the website, outside this build.
- ~~**AC5.1.6** Given the best tuned checkpoint, when it is scored on GSM-Symbolic p1, then the result is recorded with no pass or fail mark. [manual] Verify: results/runs.csv row q17-best-gsmsym~~ Deferred (Nico, 2026-11-07): run later from the website, outside this build.

---

## 6. Final Score, Write-up and Learning Checks

### US6.1 Score the best checkpoint on test

As Nico, I want my best tuned checkpoint scored once on the full test split and cross-checked with the harness, so that I know whether I beat the baseline.

- **Priority:** Must Have
- **Requirements:** FR6.2, FR1.9, FR3.6, NFR8
- **Depends on:** US1.5, US2.4, US3.6
- **INVEST:** independent once a finalist exists; the long runs are detached runs.

- **AC6.1.1** Given a finalist's adapter and a limit of 5 test problems, when the final evaluation runs, then it writes one row with method `best`, data `gsm8k-test` and the finalist's run id in the `adapter_run` field to the results file (contract C1).
- ~~**AC6.1.2** Given the best tuned checkpoint, when it is scored on all 1,319 test problems, then its test accuracy is higher than its own baseline's (`q17-base-test`), however small the gain. [manual] Verify: results/runs.csv row q17-best-test~~ Deferred (Nico, 2026-11-07): run later from the website, outside this build.
- ~~**AC6.1.3** Given the best tuned checkpoint, when the lm-evaluation-harness cross-check runs, then the harness accuracy is recorded beside the project's own number. [manual] Verify: results/runs.csv row q17-best-harness~~ Deferred (Nico, 2026-11-07): run later from the website, outside this build.

### US6.2 Write results.md

As Nico, I want `results.md` built from my run log, with the gain judged against noise, so that the write-up says honestly what moved the number and why.

- **Priority:** Must Have
- **Requirements:** FR6.1
- **Depends on:** US6.1, US5.1
- **INVEST:** small generator plus Nico's own write-up; the generator is testable with a temporary results file.

- **AC6.2.1** Given a results file, when the results generator runs, then it writes the run table into `results.md` with one line per row.
- **AC6.2.2** Given a baseline and a best test accuracy on 1,319 problems, when the gain is reported, then a gain smaller than about 3 points is labelled "within noise" and a larger one "outside noise".
- **AC6.2.3** Given harness rows, when `results.md` is built, then the harness numbers are shown labelled as a cross-check and are not used to compute the gain.
- **AC6.2.4** Given the finished project, when Nico reads `results.md`, then it holds the baselines (both models, dev and test, and the harness cross-check), the default-dial reference fine-tunes with their dev gains labelled against noise, what moved the number and why, and what to try next (changed 2026-11-07: the best checkpoint's test, harness and generalisation results are deferred). [manual] Verify: Nico reads `results.md` and approves it at the write-up unit's checkpoint

### US6.3 Check what each unit taught me

As Nico, I want one or two short questions after each unit, so that I actually learn the concepts and do not just collect scores.

- **Priority:** Must Have
- **Requirements:** FR6.3
- **Depends on:** none
- **INVEST:** independent of the code; checked by hand at each unit's end.

- **AC6.3.1** Given a unit has reached its checkpoint, when the build lead closes the unit, then Nico is asked one or two short questions on what the unit taught. [manual] Verify: the unit's line under "Done this run" in `STATE.md` lists the questions asked
- **AC6.3.2** Given Nico answered the check questions, when the unit is closed, then his answers are kept with the questions in that same `STATE.md` line. [manual] Verify: the unit's line under "Done this run" in `STATE.md` holds Nico's answers

---

## 7. Reinforcement Learning (Could)

### US7.1 Train with GRPO

As Nico, I want to train with GRPO using a correctness reward, so that I learn how reinforcement learning differs from supervised fine-tuning on the same task.

- **Priority:** Could Have
- **Requirements:** FR7.1, NFR1, NFR2
- **Depends on:** US2.2, US2.3
- **INVEST:** one method end to end; reward functions and a few steps are testable on a tiny model fixture.

- **AC7.1.1** Given a completion and its gold answer, when the rewards are computed, then the correctness reward is 1 for the right final number and 0 otherwise, and the format reward is given only when a `#### <number>` line is present.
- **AC7.1.2** Given a model (in tests the tiny model fixture) and a few steps, when GRPO runs, then each metrics line also holds reward, KL and answer length, and the run ends with one row with method `grpo`.
- **AC7.1.3** Given a starting checkpoint path, when GRPO starts, then it starts from the base model or that supervised adapter; given a path that does not exist, then it stops with a message naming the path.
- **AC7.1.4** Given saved step times, when a GRPO run is planned, then its step count is sized so the estimate fits 3 hours, and a larger count is flagged.
- **AC7.1.5** Given the model chosen after the first measurements, when GRPO with the default steps runs, then it finishes within 3 hours and records its dev accuracy (if the 1.7B model is chosen, the base id is q17-grpo-dev instead). [manual] Verify: results/runs.csv row q06-grpo-dev

---

## 8. Tuning Loop (Could)

### US8.1 Run an Optuna proxy study

As Nico, I want a small Optuna study of short proxy trials on the dev split, so that the dials I try next are chosen by evidence, not guesses.

- **Priority:** Could Have
- **Requirements:** FR8.1, NFR8
- **Depends on:** US2.1, US2.2
- **INVEST:** one study runner; testable with two tiny trials.

- **AC8.1.1** Given a study, when a trial runs, then it uses the 0.6B model, 100–200 training problems and the dev split only, and a trial over 10 minutes is stopped and recorded as pruned.
- **AC8.1.2** Given a study, when trials finish, then their results are stored in a local SQLite file under `outputs/`, and a study restarted after an interruption carries on from the stored trials.
- **AC8.1.3** Given a sampled trial configuration that fails the dial check, when the study runs, then that trial is recorded as invalid with the dial named and the study continues.
- **AC8.1.4** Given a study configuration that names the test split, when it starts, then it is refused.
- **AC8.1.5** Given the study's default number of trials, when the study runs, then the best trial's dials and dev accuracy are recorded. [manual] Verify: results/runs.csv row q06-optuna-dev

### US8.2 Get the next run proposed and checked

As Nico, I want a proposer and a reviewer helper to suggest my next run and check it against the rules, so that each run I start has a reason and stays within the limits.

- **Priority:** Could Have
- **Requirements:** FR8.2, NFR8
- **Depends on:** US2.1, US2.3
- **INVEST:** the rule checker is code and testable; the helpers run in a session Nico starts.

- **AC8.2.1** Given a proposed configuration with a written reason, when the rule checker runs, then it accepts it only if it passes the dial check, uses the dev split only, fits the 8 GB and 3-hour estimates, and changes one main dial from the last run.
- **AC8.2.2** Given a proposal that breaks a rule, when the rule checker runs, then it rejects it and names each broken rule.
- **AC8.2.3** Given a proposer and reviewer session, when it ends, then no run was started by either helper and the proposal is left as a file for Nico to start himself. [manual] Verify: Nico checks the session transcript and the training page's past runs after a proposer session

---

## 9. Ablations (Could)

### US9.1 Compare ablations on the dev split

As Nico, I want answer format, samples per problem and a calculator tool each compared on dev against the same baseline, so that I learn which ideas matter for math.

- **Priority:** Could Have
- **Requirements:** FR9.1, NFR8
- **Depends on:** US2.4
- **INVEST:** three small, separable comparisons; each transform is testable without a GPU.

- **AC9.1.1** Given a worked GSM8K answer, when training data is built with the `terse` answer format, then each target is reduced to its `#### <number>` line.
- **AC9.1.2** Given several sampled answers to one problem, when they are combined by majority vote, then the most common final number wins, a tie goes to the earliest sample, and samples with no number are ignored.
- **AC9.1.3** Given a calculator call such as `<<48/2=`, when the calculator tool fills it, then only arithmetic is evaluated (no other code runs) and division by zero returns "error" instead of crashing.
- **AC9.1.4** Given the terse format with otherwise default dials, when the fine-tune runs, then its dev accuracy is recorded for comparison with `q17-sft-dev`. [manual] Verify: results/runs.csv row q17-terse-dev
- **AC9.1.5** Given majority vote over several samples per problem, when the dev evaluation runs, then its dev accuracy is recorded for comparison with the same model's single-sample number. [manual] Verify: results/runs.csv row q17-vote-dev
- **AC9.1.6** Given the calculator tool switched on, when the dev evaluation runs, then its dev accuracy is recorded for comparison with the same model without it. [manual] Verify: results/runs.csv row q17-calc-dev

---

## 10. Self-Taught Chain of Thought (Could)

Added 2026-11-08 (Nico: "train a model with focus on chain of thought"; he picked self-taught chain of thought; "Make a page and explain how it affected the score"). The reference fine-tune copies GSM8K's terse written solutions and did not raise the dev score (`results.md`). Here the base model writes its own step-by-step solutions to training problems, only the correct ones are kept, and the model is fine-tuned on them (rejection-sampling fine-tuning, as in STaR without rationalisation). The training dials stay as in Training Dials; the training data differs from the reference fine-tune in its source (the model's own solutions) and its size (only the kept problems, against all 6,973), and the comparison states both. Generation never samples or keeps a dev problem; the four unscored dev exemplars appear only as the prompt, as in every evaluation.

Chain-of-thought dials (bounds inclusive; fields of `config.json`, contract C2):

| Dial | Allowed | Default |
|---|---|---|
| cot problems | 50 to the size of the training split (6,973), or `all` | 1500 (sized so 4 samples per problem at 1.7B stay under 3 hours even at the measured 1.6 s per answer without any batching gain) |
| cot samples | 1 to 8 (whole number) | 4 |
| cot temperature | 0.1 to 1.5 | 0.7 |

A sample's reasoning lines are its non-empty lines before its first `#### <number>` line; its words are the whitespace-separated words of those lines.

### US10.1 Generate the model's own reasoning

As Nico, I want the base model to write several step-by-step solutions to each training problem and keep only the correct ones, so that I can fine-tune on reasoning in the model's own words instead of GSM8K's terse notes.

- **Priority:** Could Have
- **Requirements:** FR10.1, NFR1, NFR2, NFR8
- **Depends on:** US1.4, US2.1
- **INVEST:** one command; sampling and the keep rule are testable on the tiny model fixture and on fixed strings.

- **AC10.1.1** Given a few training problems and the tiny model fixture, when `gsm8k cot-generate` runs with `cot_samples` 3, then each problem is prompted with the fixed 4-shot prompt and sampled 3 times at `cot_temperature` with the run's seed, each sample is cut by the stop rule (BR3.5) and scored against its gold answer, and the run folder holds `config.json`, `cot_data.jsonl`, `cot_stats.json`, `timings.json`, `status.json` and metrics lines with the problems done, the problems to do and the estimated seconds left.
- **AC10.1.2** Given the scored samples of one problem, when the keep rule runs, then a sample is kept only if its final number is correct and at least one reasoning line comes before its `#### <number>` line, at most one sample is kept per problem (the first such sample in sample order), and a problem with no such sample is left out of `cot_data.jsonl` and counted.
- **AC10.1.3** Given a finished generation, when it ends, then the results file gets one row with method `cotgen`, data `gsm8k-train` and metric `kept_fraction` (kept problems divided by problems tried), and `cot_stats.json` holds the problems tried, samples per problem, problems solved (at least one correct sample), problems kept, and the mean reasoning lines and words of the kept solutions and of GSM8K's reference solutions for the same kept problems (null when nothing was kept, with a kept fraction of 0).
- **AC10.1.4** Given any configuration, when generation picks its problems, then they are the first `cot_problems` problems of the training part of the split by index and never a dev, test, GSM-Plus or GSM-Symbolic problem; given a split other than `train`, or a `cot_problems`, `cot_samples` or `cot_temperature` outside its range, then it stops with exit code 2 and a message naming the dial and its allowed range, and writes no row.
- **AC10.1.5** [manual] Given `Qwen/Qwen3-1.7B-Base` and the default chain-of-thought dials, when the generation runs, then it finishes within 3 hours and records its kept fraction. Verify: results/runs.csv row q17-cotgen-train

### US10.2 Fine-tune on its own reasoning

As Nico, I want to fine-tune on the kept solutions with the same dials as the reference fine-tune, so that I can see what training on the model's own chain of thought does that copying GSM8K's solutions did not.

- **Priority:** Could Have
- **Requirements:** FR10.2, FR2.1, FR2.4, NFR1, NFR2, NFR8
- **Depends on:** US10.1, US2.2
- **INVEST:** reuses the supervised loop with a different data source; testable on the tiny model fixture with a small `cot_data.jsonl`.

- **AC10.2.1** Given a generation run folder with a `cot_data.jsonl` and the tiny model fixture, when `gsm8k train --method selfcot --cot-data-run <generation run id>` runs a few steps, then each training target is a kept solution in the zero-shot `Question: <q>` newline `Answer:` frame (BR2.3), the adapter is saved under `checkpoints/<run_id>/`, the dev split is scored, and the results file gets one row with method `selfcot` and data `gsm8k-dev`; a `selfcot` adapter counts as an adapter for finalists, method `best` and pruning like an `sft` adapter (C4, C5).
- **AC10.2.2** Given `train_examples` N, when self-taught training builds its data, then it takes the first N kept solutions in problem index order, and `all`, or an N larger than the number kept, takes every kept solution.
- **AC10.2.3** Given method `selfcot` without `cot_data_run`, or a `cot_data_run` whose folder has no readable `cot_data.jsonl`, when training starts, then it stops with exit code 2 and a message naming the missing field, run or file, and writes no row.
- **AC10.2.4** Given a `cot_data.jsonl` that holds a dev or test problem id, when training starts, then it stops before training with exit code 2 and a message naming the leaked problem ids, and writes no row (NFR8).
- **AC10.2.5** [manual] Given the kept solutions of q17-cotgen-train, batch size 2 and the other dials at their defaults, when the self-taught fine-tune runs, then it records its dev accuracy for comparison with q17-base-dev and q17-sft-dev. Verify: results/runs.csv row q17-selfcot-dev

### US10.3 Compare the reasoning runs

As Nico, I want the service to compare the self-taught run with the base model and the reference fine-tune problem by problem, so that the page can show how chain of thought moved the score and why.

- **Priority:** Could Have
- **Requirements:** FR10.3, NFR6
- **Depends on:** US3.1, US10.2
- **INVEST:** a pure comparison over the run log and run folders plus one read-only endpoint; testable with fixture files.

- **AC10.3.1** Given a results file with base, `sft` and `selfcot` dev accuracy rows of one model, when `GET /api/v1/reasoning?model=<model>` is called, then for each role (base, sft, selfcot) it returns the latest such row's run id, accuracy, correct and scored counts and 95% interval (normal approximation, clipped to 0–1), and for sft and selfcot the number of training problems the fine-tune learned from and the gain over base in points with the label "within noise" when its size is under 4 points and "outside noise" from 4 points.
- **AC10.3.2** Given those runs' `predictions.jsonl` files, when the comparison is built, then for sft and selfcot it counts the problems fixed (base wrong, run right), broken (base right, run wrong), both right and both wrong over the problems both scored, and for each role it gives the mean reasoning lines and words of its outputs.
- **AC10.3.3** Given a `selfcot` run whose `config.json` names its generation run, when the comparison is built, then it carries that run's `cot_stats.json` figures, up to 3 fixed problems in dev order as examples (problem id, gold answer, base output, self-taught output), and summary sentences that name the self-taught dev accuracy, the base accuracy, the gain with its noise label, the reference fine-tune's gain, the training problems each learned from, and the fixed and broken counts.
- **AC10.3.4** Given no `selfcot` dev row for the model, when the endpoint is called, then it answers 200 with `available` false and whatever base and sft figures exist; given an unreadable predictions or stats file, then only that part is null with an error naming the file; given a model outside the two allowed, then it answers 422 with error `invalid_dial`; and `POST /api/v1/runs/check` refuses methods `cotgen` and `selfcot` with 422 `invalid_dial` (field `method`), since the website does not start them in this unit.

### US10.4 See how chain of thought moved the score

As Nico, I want a Reasoning page that shows and explains how self-taught chain of thought changed the score, so that I can read the effect without opening files.

- **Priority:** Could Have
- **Requirements:** FR10.4, FR4.1, FR4.5, FR4.6, NFR9
- **Depends on:** US4.1, US10.3
- **INVEST:** one page reading one endpoint; testable with a fake API.

- **AC10.4.1** Given any page, when it renders, then the top bar shows a "Reasoning" link after "Training" that opens `/reasoning` and is marked as the current page there like the other links.
- **AC10.4.2** Given a comparison with all three runs, when the Reasoning page renders, then it shows a short explanation of self-taught chain of thought, a table of the base, reference fine-tune and self-taught dev accuracy with interval, gain and noise label in words (never by colour alone), the fixed and broken counts, the mean reasoning lines and words per run, the generation figures, and the summary sentences under the heading "How it affected the score".
- **AC10.4.3** Given examples in the comparison, when the page renders, then each example shows its problem id, gold answer and the base and self-taught outputs next to each other, and every control on the page is reachable by keyboard.
- **AC10.4.4** Given `available` false, when the page renders, then it shows "No self-taught chain-of-thought run yet" with the base and reference figures that exist; given a service error, then it shows an error state naming it; while the comparison loads, then it shows a loading state.
- **AC10.4.5** [manual] Given the finished q17-selfcot-dev run, when Nico reads the Reasoning page and the "Self-taught chain of thought" section of `results.md`, then both say how the dev score moved, whether the change is within noise, and why (answer length and style, problems fixed and broken). Verify: Nico reads the Reasoning page and `results.md` after q17-selfcot-dev ends

---

## 11. Fine-Tuning Lab (Could)

Nico, 2026-11-08: a way smaller model that trains in minutes, and a step-by-step learning path through what affects what in fine-tuning, without touching the current run (FR11). The lab is a side track: it runs on the CPU only, writes only under `outputs/lab/`, never touches `results/runs.csv`, the GPU lock or the queue, and its figures are not project results. Quick tests use the tiny model fixture, never the real lab model.

### Lab Defaults

Every variant is the default configuration below with the variant's changes. `EleutherAI/pythia-31m` (Apache-2.0, 30.5 M weights, 6 layers, width 256) at revision `e556ace21b489575e94e9d50b6dad2fcc7419679` measured about 1.4–1.7 s per step at batch size 8 on 4 CPU threads of this PC while a GPU run went on (2026-11-08).

| Field | Allowed | Default |
|---|---|---|
| method | `lora` or `full` | `lora` |
| lora_rank | 1 to 64 (whole number) | 8 |
| lora_alpha | 1 to 128 (whole number) | 16 |
| learning_rate | 1e-6 to 1e-1 | 1e-3 |
| batch_size | 1 to 64 (whole number) | 8 |
| train_examples | 16 to 6,973 (whole number) | 800 |
| epochs | 1 to 20 (whole number) | 1 |
| max_seq_len | 64 to 512 (whole number) | 256 |
| warmup_ratio | 0 to 0.5 | 0.1 |
| schedule | `linear` (warm-up, then linear decay to 0) or `constant` (warm-up, then flat) | `linear` |
| loss_on | `answer` (answer tokens only) or `all` (question and answer tokens) | `answer` |
| answer_format | `step-by-step` or `terse` (FR2.1) | `step-by-step` |
| batching | `random` or `by-length` | `random` |
| retokenize | `false` or `true` (tokenize each batch again at every step, to time it) | `false` |
| seed | 0 to 2³¹−1 (whole number) | 42 |
| dev_problems | 8 to 496 (whole number) | 64 |
| sample_problems | 0 to 8 (whole number) | 3 |
| max_new_tokens | 16 to 256 (whole number) | 128 |
| threads | 1 to 8 (whole number) | 4 |

### Lab Lessons

| Lesson | Title | Variants (name: changes) |
|---|---|---|
| l01 | What a fine-tune does | `baseline`: none |
| l02 | Learning rate | `lr-1e-5`: learning_rate 1e-5; `lr-1e-4`: 1e-4; `lr-1e-3`: 1e-3; `lr-1e-2`: 1e-2 |
| l03 | Epochs and overfitting | `few-many`: train_examples 64, epochs 12; `many-once`: train_examples 768, epochs 1 |
| l04 | How much data | `data-200`: train_examples 200; `data-800`: 800; `data-1600`: 1600 |
| l05 | LoRA rank | `rank-1`: lora_rank 1, lora_alpha 2; `rank-8`: lora_rank 8, lora_alpha 16; `rank-64`: lora_rank 64, lora_alpha 128 |
| l06 | LoRA or every weight | `lora`: none; `full`: method full, learning_rate 1e-4 |
| l07 | Batch size | `batch-1`: batch_size 1; `batch-8`: batch_size 8; `batch-32`: batch_size 32 |
| l08 | What the loss counts | `answer-only`: none; `whole-text`: loss_on all |
| l09 | Answer format | `step-by-step`: none; `terse`: answer_format terse |
| l10 | Warm-up and schedule | `warmup-decay`: none; `constant`: schedule constant, warmup_ratio 0; `hot-start`: learning_rate 3e-3, warmup_ratio 0 |
| l11 | Seed noise | `seed-1`: seed 1; `seed-2`: seed 2; `seed-3`: seed 3 |
| l12 | Where the time goes | `tokenize-once`: none; `by-length`: batching by-length; `retokenize`: retokenize true |

### US11.1 Lessons and their configurations

As Nico, I want a fixed path of lessons, each changing one thing against the same starting point, so that I learn what each dial does on its own.

- **Priority:** Could Have
- **Requirements:** FR11.1
- **Depends on:** none
- **INVEST:** pure data and validation; testable without a model.

- **AC11.1.1** Given the lab's lessons, when they are listed, then there are exactly the twelve lessons of the Lab Lessons table, in its order, with its ids, titles and variant names in its order; each lesson has a non-empty question, what to watch, a guess prompt with exactly three options, an explanation ("why"), what it means for the big runs ("big_run", which names a Training Dials dial or method) and a check question.
- **AC11.1.2** Given a lesson's variant, when its configuration is built, then it is the Lab Defaults with exactly the variant's changes (for example `l03` `few-many` has train_examples 64 and epochs 12 and every other field at its default); every variant of every lesson passes validation; and a configuration with a value outside the Allowed column (for example learning_rate 0.5, schedule `cosine`, or batch_size 0) is refused with a message naming the field.
- **AC11.1.3** Given a lesson, when its time is estimated, then the estimate in whole minutes is the sum over its variants of (train_examples × epochs × 0.2 seconds, doubled for method `full`) plus 60 seconds per variant, divided by 60 and rounded up, computed in whole tenths of a second so no float rounding enters (`l01`: 4 minutes; `l02`: 15 minutes).

### US11.2 Run a lesson on the CPU

As Nico, I want a lesson's variants to train a small model on the CPU in minutes and record what happened, so that I can learn from many short runs while the GPU keeps working on the big run.

- **Priority:** Could Have
- **Requirements:** FR11.2, NFR3, NFR5, NFR8
- **Depends on:** US11.1, US2.2
- **INVEST:** one command; testable with the tiny model fixture, a few training problems and a temporary outputs folder.

- **AC11.2.1** Given `gsm8k lab run <lesson>` with the tiny model fixture and a temporary outputs folder, when it ends, then for each variant in order `outputs/lab/<lesson>/<variant>/metrics.jsonl` and `summary.json` exist (contract C8), `outputs/lab/<lesson>/status.json` reads state `finished` with every variant listed as done, and the command exits 0; `--variant <name>` (repeatable) runs only those variants; an unknown lesson or variant exits 2 and writes nothing.
- **AC11.2.2** Given a lab run, when it trains, then it uses the CPU only: the `lab run` handler (never the module import, since `gsm8k` imports every command module when it builds its parser) sets `CUDA_VISIBLE_DEVICES` to an empty string before CUDA is first used, puts the model and every tensor on the CPU even when torch already sees a GPU, sets torch's thread count to the configuration's `threads` and lowers its own priority by 10 (`os.nice(10)`); and it never reads or writes `results/runs.csv`, `outputs/run.lock` or `outputs/queue/`.
- **AC11.2.3** Given a lab run that holds the lab lock (an exclusive `flock` on `outputs/lab/lab.lock` held for the process's life, as `run_records/lock.py` does for the GPU lock; contract C8), when a second `gsm8k lab run` starts, then it exits 3 naming the running lesson (read from the lock file) and writes nothing; a lock file left by a process that has ended holds no `flock` and is taken over.
- **AC11.2.4** Given a lab run, when it picks its problems, then the training problems are the first `train_examples` problems of the training part of the fixed split by index, the dev problems the first `dev_problems` of the 496 scored dev problems by index (the 500 dev problems without the 4 prompt exemplars), and the sample problems the first `sample_problems` of those dev problems; the training problems `load_lab_problems` returns go through `guard.check_training_problems` with all 500 dev ids and a check against the test split's ids, and a problem that fails it ends the run `failed` (exit 1) before any training; the test split's problems are never training or dev data.
- **AC11.2.5** Given a lab run, when it trains, then the text is tokenized once before the first step (training frame and answer as in FR2.1 and BR2.3, the end-of-text token appended, cut at `max_seq_len`; an example with no answer token left after the cut is dropped, and a run with no example left ends `failed`, exit 1, with a message; with `loss_on` `answer` the question's tokens are masked from the loss, with `all` only padding is); the examples are shuffled with the seed once per epoch, the last short batch is kept, and total_steps = epochs × ceil(kept examples / batch_size); each step pads one batch, runs one forward and backward pass, clips the gradient norm at 1.0 and takes one AdamW step (weight decay 0) under the schedule; with `retokenize` true each step tokenizes its batch's text again and times it. Method `lora` puts LoRA adapters with the configured rank and alpha on every `torch.nn.Linear` inside the decoder blocks (`model.get_decoder().layers`), never on the embeddings or the output head, and trains only them, on both the Qwen3 test fixture and a tiny random GPTNeoX (pythia) model; method `full` trains every weight.
- **AC11.2.6** Given a lab run, when it trains, then `metrics.jsonl` gets one line per step with the step, total steps, loss, learning rate, gradient norm and elapsed seconds, and a dev line at step 0 (before training) and at each distinct step of {max(1, ceil(k × total_steps / 10)) : k = 1 to 10} (so a run of 3 steps has dev lines at steps 0, 1, 2 and 3) with the dev loss: the token-weighted mean loss over the answer tokens of the dev problems in the variant's answer format, whatever `loss_on` is (contract C8).
- **AC11.2.7** Given a variant that has ended, when its `summary.json` is read, then it holds the C8 fields: its configuration, trainable and total weights (for `full` trainable equals total; for `lora` trainable is the adapters' weights only), steps, seconds, seconds per step, the seconds the one-time tokenization took, the re-tokenizing seconds per step (null unless `retokenize` is true), the padding fraction (padding tokens over all tokens of the run's batches), peak memory (`resource.getrusage(RUSAGE_SELF).ru_maxrss / 1024` MB), the first and last training loss (the last as the mean of the last 10 step losses), dev loss before, after and at its best with that step, and the dev accuracy and format rate (the share of answers with a `#### <number>` line) before and after training, scored under FR1.4 with the zero-shot training frame and greedy decoding up to `max_new_tokens`, plus the sample problems' answers before and after.
- **AC11.2.8** Given `batching` `by-length`, when the batches are formed, then the training examples start from the same seeded shuffle as `random` batching, are cut into chunks of 16 batches, sorted by length inside each chunk and cut into batches, and the batch order is shuffled with the seed; the run's padding fraction is lower than or equal to the same run's with `random` batching on the same examples, and lower when the examples' lengths differ and there are at least 2 batches.
- **AC11.2.9** Given a lab run, when it gets SIGTERM, then it ends after the current training step (or the current generation or dev-loss batch), writes state `stopped`, writes no `summary.json` for the stopped variant and leaves it out of `done`, releases the lab lock and exits 130; when a variant raises an error, then the state is `failed` with the error's message, the lab lock is released and the command exits 1; a run checks in this order: an unknown lesson or variant (exit 2), the lab lock (exit 3), then it removes that lesson's earlier folder and starts.
- **AC11.2.10** Given the lab on this PC with a GPU run going, when Nico starts lesson `l01` from the Lab page, then it finishes within about 6 minutes on the CPU, its summary shows the dev loss falling, and the GPU run's speed and result are unaffected. [manual] Verify: `outputs/lab/l01/baseline/summary.json` exists and Nico confirms in session; the GPU run's log shows no slowdown.

### US11.3 Serve and control the lab

As Nico, I want the local service to list the lessons, serve their figures and start or stop a lesson, so that the website can drive the lab.

- **Priority:** Could Have
- **Requirements:** FR11.3, NFR6
- **Depends on:** US11.2, US3.1
- **INVEST:** four endpoints on the existing service; testable with FastAPI's test client, a temporary outputs folder and a stubbed process launcher.

- **AC11.3.1** Given the service, when `GET /api/v1/lab` is called, then it answers the C6 `LabList`: the lab model, every lesson in order with its id, number, title, question, what to watch, guess prompt and options, variants (name, label, changes), why, big run, check question, estimated minutes and state (`not-run`, `running`, `finished`, `failed` or `stopped`, from its status file), and `active`, the lesson whose lab run is going (null when none): a lab run is going while the lab lock's `flock` is held, or while the process the service launched has not ended (the service reaps it with `Popen.poll()`).
- **AC11.3.2** Given a lesson, when `GET /api/v1/lab/{lesson}` is called, then it answers the C6 `LabLesson`: the lesson as in the list, its status (state, current variant, variants done, started and ended times, message), and per variant its metrics lines and its summary (null until it has ended); while `active` is this lesson, the status's state is `running` whatever the status file says (it may not be written yet right after the launch); a status file that says `running` while no lab run is going answers state `failed` with the message "The lab run ended without a status."; an unknown lesson answers 404 `not_found`.
- **AC11.3.3** Given no lab run going, when `POST /api/v1/lab/{lesson}/run` is called, then the service launches `[<python>, "-m", "gsm8k", "lab", "run", <lesson>]` as an argument list in its own session from the project root, with `CUDA_VISIBLE_DEVICES` set to an empty string in the child's environment and its output appended to `outputs/lab/<lesson>.log`, and answers 202 with the lesson's id and state `running`; while a lab run is going it answers 409 `lab_busy` naming the running lesson; an unknown lesson answers 404 `not_found`; the GPU lock and the queue play no part.
- **AC11.3.4** Given a lab run going, when `POST /api/v1/lab/stop` is called, then the service sends SIGTERM to the lab run's process and answers 200 with the lesson's id; with no lab run going it answers 409 `no_lab_run`.

### US11.4 Learn on the Lab page

As Nico, I want a Lab page that takes me through the lessons one by one, so that I guess, run, watch and read why, and learn what affects what.

- **Priority:** Could Have
- **Requirements:** FR11.4, FR4.5, NFR9
- **Depends on:** US11.3, US4.1
- **INVEST:** one page; testable with component tests and the fake API.

- **AC11.4.1** Given any page, when it renders, then the top bar has a "Lab" link after "Reasoning" that opens `/lab`; the Lab page lists the twelve lessons in order as "Lesson N · <title>", each with its state in words (Not run, Running, Done, Failed, Stopped), and names the lab model and that it runs on the CPU.
- **AC11.4.2** Given the Lab page with no `lesson` in the address, when it renders, then the first lesson that is not finished is shown (the first lesson when all are); choosing a lesson in the list shows it and sets `?lesson=<id>`; the shown lesson has the heading "Lesson N: <title>", its question, what to watch, and its variants with their changes.
- **AC11.4.3** Given a shown lesson, when it renders, then "Your guess" offers the lesson's three options as radio buttons; a chosen option is kept in this browser only (and the page works when the browser's storage is unavailable); once the lesson is finished the page reads "You guessed: <option>" (or "No guess made"); the "Why it happens" text shows once the lesson is finished, and before that only after "Show the explanation now" is pressed.
- **AC11.4.4** Given a shown lesson with no lab run going, when "Run this lesson" is pressed, then it calls `POST /lab/{lesson}/run`, and the button's note reads "On the CPU, about N minutes. It never uses the GPU, so a GPU run keeps going."; while the lesson runs the page shows "Variant i of n: <label>, step s of t", a button "Stop the lesson" that calls `POST /lab/stop`, and refreshes the lesson every 2 seconds until its state is not `running`; while another lesson runs, "Run this lesson" is disabled and names the running lesson; a 409 `lab_busy` answer shows its message.
- **AC11.4.5** Given a lesson with metrics lines, when it renders, then a "Training loss" chart and a "Dev loss" chart draw one line per variant, named by the variant's label in a legend, and a results table lists per variant: trainable weights (with thousands separators), steps, minutes (1 decimal), seconds per step (2 decimals), last training loss, dev loss before, after and best (with its step) (losses to 3 decimals), format rate and accuracy before and after (whole percents); for lesson `l12` it also lists the tokenize seconds, the re-tokenize seconds per step and the padding fraction as a percent.
- **AC11.4.6** Given a finished lesson, when it renders, then a "What happened" list states, worked out from the summaries (losses to 3 decimals): the variant with the lowest dev loss after training and its value (for `l09`, whose variants' dev losses are over different answer texts, the variant with the higher accuracy after training and the format rates instead); for each variant whose last dev loss is more than 0.05 above its best, that it overfitted (its best and last dev loss and the best step); for each variant whose last training loss is above its first or is missing, that training diverged; for `l11`, the spread of the last dev loss across seeds (largest minus smallest) and that smaller differences in the other lessons are noise; for `l12`, how long the one-time tokenization took, what re-tokenizing added per step as seconds and a percent of a step, and the padding fraction with random and with length-grouped batches.
- **AC11.4.7** Given a finished lesson, when it renders, then "Answers before and after" shows, for the variant chosen in a select (the one with the lowest dev loss first), each sample problem's question, its right answer, and the answers before and after training; "For the big runs" shows the lesson's big-run text and "Check question" its check question.
- **AC11.4.8** Given the Lab page, when the lab list is loading, fails or a lesson has never run, then it shows "Reading the lab…", the error's message with a "Try again" button, or "Not run yet: press Run this lesson to fill the charts." respectively; the charts are hidden from assistive technology and their facts are in the results table.

---

## 12. Learning Course (Could)

Nico, 2026-11-08: "a button ... to fine tune a small model and to be guided through all the steps", then "the training pipeline should walk me through different architectures and why one architecture is used and why not, basically a hands-on learning course with a tracker that displays my learning progress". His answers in session: architectures means both model designs and fine-tuning approaches; GRPO is included as a step; a step's run is short (minutes); a step is learned through multiple-choice questions the service checks plus an "in your own words" answer kept next to a model answer (FR12). The course is the guided path through the whole project: it reuses the evaluation and training commands on the GPU through the queue for short runs, the Fine-Tuning Lab (group 11) on the CPU for the lab lessons, and adds a CPU inspection of model designs. Course runs are learning runs, not project results: their rows go to `outputs/course/runs.csv` (never `results/runs.csv`) and they never appear on the Scores page or the landing page's best result.

### Course Steps

| Step | Part | Title | Kind | What it runs |
|---|---|---|---|---|
| c01 | 1. Scoring a base model | How a base model is scored | gpu | `base-06` |
| c02 | 2. Model designs | Tokens and the prompt | inspect | `gsm8k course inspect` |
| c03 | 2. Model designs | Inside a decoder-only transformer | inspect | `gsm8k course inspect` |
| c04 | 2. Model designs | Five designs side by side | inspect | `gsm8k course inspect` |
| c05 | 2. Model designs | Same test, five designs | gpu | `pythia`, `smollm2`, `qwen25`, `qwen3-17` |
| c06 | 2. Model designs | Why Qwen3-1.7B, and why not the others | read | none |
| c07 | 3. How fine-tuning works (lab, CPU) | What a fine-tune does | lab | lesson l01 |
| c08 | 3. How fine-tuning works (lab, CPU) | Learning rate | lab | lesson l02 |
| c09 | 3. How fine-tuning works (lab, CPU) | Epochs and overfitting | lab | lesson l03 |
| c10 | 3. How fine-tuning works (lab, CPU) | How much data | lab | lesson l04 |
| c11 | 3. How fine-tuning works (lab, CPU) | LoRA rank | lab | lesson l05 |
| c12 | 3. How fine-tuning works (lab, CPU) | LoRA or every weight | lab | lesson l06 |
| c13 | 3. How fine-tuning works (lab, CPU) | Batch size | lab | lesson l07 |
| c14 | 3. How fine-tuning works (lab, CPU) | What the loss counts | lab | lesson l08 |
| c15 | 3. How fine-tuning works (lab, CPU) | Answer format | lab | lesson l09 |
| c16 | 3. How fine-tuning works (lab, CPU) | Warm-up and schedule | lab | lesson l10 |
| c17 | 3. How fine-tuning works (lab, CPU) | Seed noise | lab | lesson l11 |
| c18 | 3. How fine-tuning works (lab, CPU) | Where the time goes | lab | lesson l12 |
| c19 | 4. Fine-tuning approaches | Memory budget: prompting, full, LoRA, QLoRA | read | none (memory calculator) |
| c20 | 4. Fine-tuning approaches | LoRA or QLoRA on the GPU | gpu | `lora`, `qlora` |
| c21 | 5. The training pipeline | Supervised fine-tune | gpu | `sft` |
| c22 | 5. The training pipeline | Self-taught reasoning | gpu | `cotgen`, then `selfcot` |
| c23 | 5. The training pipeline | Reinforcement learning with GRPO | gpu | `grpo` |
| c24 | 5. The training pipeline | What moved the score, and noise | read | none (comparison of the course runs) |

Kinds: `gpu` queues short runs on the GPU through the queue and the worker (US3.7, AC3.7.7); `inspect` runs `gsm8k course inspect` on the CPU; `lab` runs a lab lesson through the lab routes (US11.3); `read` runs nothing.

### Course Runs

Every course run uses the run configuration defaults (stories, Training Dials and C2) with exactly the changes below, the dev split, `limit` 100 (the first 100 scored dev problems) and seed 42. Its attempt id is `course-<step>-<run>-<n>` (for example `course-c05-pythia-1`), `n` counting up from 1 per step and run.

| Step | Run | Command | Changes |
|---|---|---|---|
| c01 | `base-06` | evaluate | model `Qwen/Qwen3-0.6B-Base`, method `base` |
| c05 | `pythia` | evaluate | model `EleutherAI/pythia-31m`, method `base` |
| c05 | `smollm2` | evaluate | model `HuggingFaceTB/SmolLM2-360M`, method `base` |
| c05 | `qwen25` | evaluate | model `Qwen/Qwen2.5-0.5B`, method `base` |
| c05 | `qwen3-17` | evaluate | model `Qwen/Qwen3-1.7B-Base`, method `base` |
| c20 | `lora` | train | model `Qwen/Qwen3-0.6B-Base`, method `sft`, train_examples 300 |
| c20 | `qlora` | train | model `Qwen/Qwen3-0.6B-Base`, method `sft`, train_examples 300, quantize `4bit` |
| c21 | `sft` | train | model `Qwen/Qwen3-0.6B-Base`, method `sft`, train_examples 400 |
| c22 | `cotgen` | cot-generate | model `Qwen/Qwen3-0.6B-Base`, method `cotgen`, split `train`, cot_problems 100, cot_samples 4, no `limit` |
| c22 | `selfcot` | train | model `Qwen/Qwen3-0.6B-Base`, method `selfcot`, train_examples 100 (an upper bound: it trains on min(kept solutions, 100), counting kept solutions, which are at most one per problem (the first correct of its 4 samples, AC10.1.2), so at most 100; with fewer than 50 kept solutions the step shows "Too few solutions were kept (<n>); run the step again" instead of queueing a run that fails), cot_data_run the `course-c22-cotgen-<n>` attempt queued with it (not checked for existence when the entry is written, since it has not run yet) |
| c23 | `grpo` | train | model `Qwen/Qwen3-0.6B-Base`, method `grpo`, adapter the latest finished `course-c21-sft-<n>` (the base model when there is none), grpo_steps 20, grpo_generations 4 |

### Course Timing

A course run's estimate is worked out by the course itself (not the confirm dialog's estimate, AC2.3.1, which has no timings for the course-only models): minutes = ceil((30 s model load + work seconds) / 60). Per-unit seconds are the model's saved timings from earlier runs when there are any (seconds per scored problem from evaluation runs, seconds per training step from `sft` runs at the same batch size), otherwise the fallback below, and the estimate is then marked "unmeasured". Work seconds: evaluate = 100 × seconds per problem; train `sft` = steps × seconds per step (× 1.5 with quantize `4bit`) + 100 × seconds per problem; `selfcot` = ceil(train_examples / batch size) × seconds per step + 100 × seconds per problem; `grpo` = grpo_steps × (grpo_generations × seconds per problem + 6) (6 s per step for the policy update and the reward pass, changed 2026-11-08 from 1 s after review: sampling plus the update is nearer 10 s a step) + 100 × seconds per problem; `cotgen` = cot_problems × cot_samples × seconds per problem.

Training steps have a fallback only for `Qwen/Qwen3-0.6B-Base`, the only model the course trains.

| Model | Fallback seconds per problem | Fallback seconds per training step (batch size 4) |
|---|---|---|
| `EleutherAI/pythia-31m` | 0.3 | — |
| `HuggingFaceTB/SmolLM2-360M` | 0.8 | — |
| `Qwen/Qwen2.5-0.5B` | 1.0 | — |
| `Qwen/Qwen3-0.6B-Base` | 1.2 | 0.5 |
| `Qwen/Qwen3-1.7B-Base` | 3.0 | — |

### Course Models

The course's model-design steps add three pinned open models (Apache-2.0, not gated, no account) to the two project models. They are used only by course runs with method `base` and by `gsm8k course inspect`; training stays on the two project models.

Every Course Models row has the licence Apache-2.0; `gsm8k course inspect` takes it from this table, not from a download.

| Model | Revision | Weights | Why it is in the course |
|---|---|---|---|
| `EleutherAI/pythia-31m` | `e556ace21b489575e94e9d50b6dad2fcc7419679` | 30.5 M | the lab's model (group 11): an older GPT-NeoX design, far too small for math |
| `HuggingFaceTB/SmolLM2-360M` | `f8027fd0eaeea54caa13c31d31b9fdc459c38b49` | 362 M | a Llama-style design trained on fewer, more curated tokens |
| `Qwen/Qwen2.5-0.5B` | `060db6499f32faf8b98477b0a26969ef7d8b9987` | 494 M | the previous Qwen generation, the same family a size step below |
| `Qwen/Qwen3-0.6B-Base` | (project pin) | 0.6 B | the project's small model |
| `Qwen/Qwen3-1.7B-Base` | (project pin) | 1.7 B | the project's main model |

### US12.1 Course steps and their content

As Nico, I want a fixed course of steps, each saying why before it asks me to do anything, so that I learn the pipeline in order and know what each step is for.

- **Priority:** Could Have
- **Requirements:** FR12.1
- **Depends on:** US11.1
- **INVEST:** pure data and validation; testable without a model.

- **AC12.1.1** Given the course, when its steps are listed, then there are exactly the 24 steps of the Course Steps table in its order, with its ids, parts, titles and kinds; each `gpu` step lists exactly its runs from the Course Runs table, each `lab` step names its lab lesson and that lesson exists in the lab's lessons (AC11.1.1), and each step has a non-empty "why" (read before acting), a body, two or three multiple-choice questions each with three or four options of which exactly one is right and an explanation of the right answer, an "in your own words" prompt and a model answer.
- **AC12.1.2** Given a course run of the Course Runs table, when its configuration is built, then it is the run configuration defaults with exactly the run's changes, the dev split, `limit` 100 and seed 42 (`cotgen`: split `train` and no limit), and it passes the C2 validation; its estimate follows the Course Timing rule, and with the fallback timings alone every run of the Course Runs table is estimated at 10 minutes or less (a run estimated above 10 minutes is shown with "over 10 minutes", never refused); given saved timings for a model (fixture runs) the estimate uses them and is not marked "unmeasured".
- **AC12.1.3** Given the content of the model-design and approach steps, when it is read, then c03 names the embeddings, the attention block with grouped-query attention, the MLP block, the norms, the residual stream and the output head (and that Qwen3-0.6B ties its output head to its embeddings); c04 explains what each compared column means; c06 gives, each in at least one sentence, why Qwen3-1.7B-Base was chosen (room to improve on GSM8K, fits LoRA training in 8 GB, Apache-2.0) and why not the alternatives: larger dense models do not fit in 8 GB, mixture-of-experts models must hold every expert in memory, encoder-decoder models are not built for few-shot step-by-step answers, gated models (Llama, Gemma) need an account (charter rule 4), and models already scoring 85–95 % leave little room and may have seen GSM8K (contamination, brief Risk 1); c19 compares prompting only, full fine-tuning, LoRA and QLoRA with what each trains and stores.
- **AC12.1.4** Given the course data modules (`gsm8k.course` and its `steps`, `configs` and `progress`, and `gsm8k.course_cmd`; C9), when each is imported, then it imports no torch, transformers, peft or bitsandbytes and changes no environment variable (the service imports it; ADR-006).

### US12.2 Inspect model designs on the CPU

As Nico, I want the course to read the real configuration and tokenizer of five models and lay out their designs, so that I see how they differ before I compare their scores.

- **Priority:** Could Have
- **Requirements:** FR12.2, NFR5, NFR6
- **Depends on:** US12.1
- **INVEST:** one CPU command; testable with tiny fixture configurations and tokenizers, no download.

- **AC12.2.1** Given `gsm8k course inspect` with fixture model configurations and tokenizers and a temporary outputs folder, when it ends, then `outputs/course/architectures.json` holds one entry per Course Models row in the table's order with the C9 fields: id, revision, licence (from the Course Models table), design family (`model_type`), layers, width, attention heads, key-value heads, attention kind (`multi-head` when key-value heads equal heads, `grouped-query` otherwise), head size, MLP width, the number of MLP matrices (`mlp_matrices`: 3 when the MLP is gated, as in Qwen and SmolLM, else 2, as in Pythia; added 2026-11-08 so AC12.3.6 can size the adapters), vocabulary size, context length, tied embeddings, position encoding (`rotary` when the configuration has `rope_theta` or `rotary_pct`, directly or inside its `rope_parameters` (transformers 5 keeps them there), otherwise `learned`), activation, total weights and weights by part (embeddings, attention, MLP, norms, `head` (the output head; 0 when tied); the parts sum to the total), the memory of the weights in bf16 (2 bytes a weight) and in 4-bit (0.5 bytes a weight) in GB (10^9 bytes), and for the first scored dev problem its token count, its first 20 tokens as text and the token count of the 4-shot prompt (FR1.2); the command exits 0.
- **AC12.2.2** Given `gsm8k course inspect` on this PC, when it reads a model, then it downloads only the configuration and tokenizer files at the pinned revision into the project cache (NFR5), counts the weights without loading them (the model built on the `meta` device), uses the CPU only (`CUDA_VISIBLE_DEVICES` empty in its handler, as AC11.2.2) and never reads or writes `results/runs.csv`, `outputs/run.lock` or `outputs/queue/`; a model whose files cannot be read ends the command with exit 1 and a message naming the model, and writes no partial `architectures.json`.

### US12.3 Course runs, quizzes and progress through the service

As Nico, I want the local service to start a step's runs, check my quiz answers and keep my progress, so that the website can guide me and remember where I am.

- **Priority:** Could Have
- **Requirements:** FR12.3, FR12.4, NFR6, NFR8
- **Depends on:** US12.1, US12.2, US3.7, US11.3
- **INVEST:** endpoints on the existing service; testable with FastAPI's test client, a temporary outputs folder, fixture course rows and a stubbed queue and launcher.

- **AC12.3.1** Given the service, when `GET /api/v1/course` is called, then it answers the C9 `CourseOverview`: the parts in order with each step's id, number, title, kind and state, the progress (steps done, total 24, percent rounded down, questions answered right on the first try and questions answered), and the next step (the first step that is not done; null when all are). A step's state is `done` when its run part is done and its quiz is passed, `in-progress` when it was opened or its run part has started, and `not-started` otherwise. The run part is done for a `read` step always; for an `inspect` step when `architectures.json` exists; for a `lab` step when its lesson's state is `finished` (AC11.3.1); for a `gpu` step when each of its runs has a finished row in `outputs/course/runs.csv`.
- **AC12.3.2** Given a step, when `GET /api/v1/course/{step}` is called, then it answers the C9 `CourseStep`: the step as in the overview, its why, body, questions with their options (the right option and the explanation only for questions already answered), the own-words prompt and saved answer (the model answer only once an answer is saved), and per kind: for `gpu` steps each run with its latest attempt id, its state (`not-run`, `queued`, `running`, `finished`, `failed` or `stopped`, from the queue, the run folder and the course rows) and its result row (null until finished); for `inspect` steps the `architectures.json` entries (null until it exists); for `lab` steps the lesson id and state; for c19 the memory table (AC12.3.6); for c24 the comparison (AC12.3.7). An unknown step answers 404 `not_found`.
- **AC12.3.3** Given a `gpu` step with none of its runs queued or running, when `POST /api/v1/course/{step}/run` is called, then the service adds one queue entry per run of the step, in the table's order, with the next attempt id, the run's configuration and `results` set to `outputs/course/runs.csv` (C3), and answers 202 with the attempt ids; the entries are added all or none: when the queue cannot take them all (at most 10 waiting entries, AC3.7.3) none is added and it answers 409 `queue_full` with the queue-full message; the worker launches them one at a time under the GPU lock and the GPU check (US3.3, AC3.7.7); for c22 the `selfcot` entry carries `after` set to the `cotgen` attempt id queued with it (C3), so the worker launches it only once that attempt has a row in `outputs/course/runs.csv`; when that attempt's `status.json` reads `failed` or `stopped`, or `finished` with no row, the `selfcot` entry is removed with the reason in `outputs/queue/queue.log`; while a run of the step is queued or running it answers 409 `course_busy`; for an `inspect` step it launches `[<python>, "-m", "gsm8k", "course", "inspect"]` as an argument list in its own session on the CPU (as AC11.3.3) and answers 202; for a `lab` step it answers 422 `use_lab` naming the lesson; for a `read` step 422 `nothing_to_run`.
- **AC12.3.4** Given a step with questions, when `POST /api/v1/course/{step}/quiz` is called with one chosen option per question, then the service answers per question whether it is right, the right option and the explanation, stores the attempt (answers, time) in `outputs/course/progress.json` (C9), and marks the quiz passed when every answer is right; a later attempt is allowed and counted; a body with the wrong number of answers or an option out of range answers 422 `invalid_answers`; first-try counts use only each question's first attempt.
- **AC12.3.5** Given a step, when `PUT /api/v1/course/{step}/own-words` is called with a text of 1 to 4,000 characters, then the text and its time are stored in `progress.json` and the answer holds the model answer; an empty or longer text answers 422 `invalid_text`; `POST /api/v1/course/{step}/open` records the first time the step was opened (later calls keep it). `progress.json` is written atomically (temporary file and rename), and a missing file reads as no progress; an unreadable one answers 500 `progress_unreadable` naming the file and is never overwritten.
- **AC12.3.6** Given step c19, when it is answered, then its memory table lists, for each Course Models row, the estimated GB to train it with full fine-tuning (16 bytes per weight: bf16 weights and gradients, fp32 AdamW states and master weights), LoRA (2 bytes per weight plus 16 bytes per adapter weight at rank 16 on every linear layer of the decoder blocks) and QLoRA (0.55 bytes per weight plus 16 bytes per adapter weight), each with "fits" or "does not fit" against 6.5 GB (the 8 GB card less 1.5 GB for the desktop and activations), worked out from `architectures.json` (null figures until it exists); the step says the figures leave out activations, which grow with batch size and sequence length.
- **AC12.3.7** Given step c24, when it is answered, then its comparison lists every finished course run's latest attempt except `cotgen` (whose row is a keep rate, not an accuracy) with its step, run, model, method, accuracy on its 100 problems and the 95 % interval (normal approximation, clipped to 0–1, as AC10.3.1), its gain over `course-c01-base-06` for Qwen3-0.6B runs with the label "within noise" when the intervals overlap, and minutes; and it says that 100 problems give intervals about ±10 points wide, so the reference runs in `results/runs.csv` (500 problems) are the ones to trust.
- **AC12.3.8** Given course runs, when the run list, the Scores page's ranking or the landing page's best result are built, then they read `results/runs.csv` only, so no course run is ranked or shown as a result; the Training page's past runs list course runs from their folders with their status only (no accuracy or minutes, which are in `outputs/course/runs.csv`), each marked "Course" because its run id starts with `course-`.

### US12.4 The course runs on the GPU

As Nico, I want each course run to be the project's own evaluation or training command with a few more options, so that what I run in the course is what the big runs do.

- **Priority:** Could Have
- **Requirements:** FR12.3, FR7.1, NFR1, NFR8
- **Depends on:** US12.1, US7.1, US10.1, US10.2
- **INVEST:** small changes to the existing commands and the worker; testable on the CPU with the tiny model fixture, fixture rows and a temporary outputs folder.

- **AC12.4.1** Given a course attempt id, when it is checked, then it matches `course-c[0-9]{2}-[a-z0-9-]+-[0-9]+` (C1), the run folder is `outputs/<attempt id>/` and its adapter (for training runs) `checkpoints/<attempt id>/`, like any run; a course run's row is appended to the `--results` file it was given, and the worker passes `--results` from the queue entry's `results` field (null: the default `results/runs.csv`); a queue entry whose `results` is anything other than null or `outputs/course/runs.csv` is refused when it is written.
- **AC12.4.2** Given `gsm8k evaluate` with method `base`, when the model is one of the Course Models, then it loads it at the table's revision and scores it like any base run (the fixed 4-shot prompt, greedy, BR3.4); the three course-only models are refused for any run id that is not a course attempt id and for every method other than `base`, with a message naming the model.
- **AC12.4.3** Given `gsm8k train` with `quantize` `4bit` (C2 field; default `none`, at its default it stays out of `config_hash`), when it loads the model, then the frozen base weights are loaded in 4-bit NF4 with bf16 compute through bitsandbytes and the LoRA adapters are trained in bf16 as for `none`; the run's `config.json` holds `quantize` and its row's `config_hash` covers it; `quantize` `4bit` with any method other than `sft`, `selfcot` or `grpo` is refused naming the field; in the quick tests the quantized load is replaced by a seam that records it was asked for.
- **AC12.4.6** Given `gsm8k prune`, when it runs, then it leaves every `checkpoints/course-*` and `outputs/course-*` folder alone (course runs have no row in `results/runs.csv` by design, AC12.3.8); given c23 whose c21 adapter folder is missing, then the step shows "Run step c21 again: its adapter is missing" instead of queueing a run that fails.
- **AC12.4.4** Given the course run c23 `grpo`, when it starts, then it runs `gsm8k train --method grpo` (US7.1) with grpo_steps 20 and grpo_generations 4 from the given adapter, its metrics lines hold reward, KL and answer length (AC7.1.2; the KL coefficient `beta` is above 0, fixed in the u7 batch plan, so that KL is computed and logged: trl's default 0 logs none), and it scores the first 100 dev problems at the end.
- **AC12.4.5** Given this PC, when Nico runs c20 and c23 from the Course page, then `course-c20-qlora-1` finishes within about 10 minutes with a lower peak GPU memory than `course-c20-lora-1`, and `course-c23-grpo-1` finishes within about 10 minutes with reward, KL and answer length on its metrics lines. [manual] Verify: rows `course-c20-lora-1`, `course-c20-qlora-1` and `course-c23-grpo-1` in `outputs/course/runs.csv` and their `outputs/<attempt id>/` peak memory, with Nico's confirmation in session.

### US12.5 Learn on the Course page with a progress tracker

As Nico, I want a Course page that walks me through the steps and shows my progress, so that I always know what I have learned and what comes next.

- **Priority:** Could Have
- **Requirements:** FR12.5, FR12.6, FR4.1, NFR9
- **Depends on:** US12.3, US4.1, US11.4
- **INVEST:** one page and a landing-page card; testable with component tests and the fake API.

- **AC12.5.1** Given any page, when it renders, then the top bar has a "Course" link after "Lab" that opens `/course`; the Course page shows "Your progress: N of 24 steps done (P %)", one progress bar per part with its done count, "First-try answers right: R of Q", and a button "Continue with step N: <title>" that opens the next step (it reads "Course complete" when there is none); the bars carry their numbers as text, not colour alone (NFR9).
- **AC12.5.2** Given the Course page, when it renders, then a list shows the five parts and their steps as "Step N · <title>", each with its state in words (Not started, In progress, Done) and its kind (GPU run, CPU inspection, Lab lesson, Reading); with no `step` in the address the next step is shown (the first step when all are done); choosing a step shows it, sets `?step=<id>` and calls `POST /course/{step}/open`.
- **AC12.5.3** Given a shown step, when it renders, then it shows, in this order, "Why this step" (its why), the body, what the step runs, the run area, "Check what you learned" (its questions) and "In your own words"; the questions stay hidden behind "I have read this, show the questions" until the step's run part is done (always shown for `read` steps).
- **AC12.5.4** Given a shown `gpu` step, when it renders, then the run area lists each run with its model, what it changes and its estimate ("about N min on the GPU", with "(estimate, not measured yet)" when it is unmeasured), a button "Run this step" that calls `POST /course/{step}/run`, and per run its state in words with a link "Watch it on the Training page" (`/training`, which shows the run that holds the GPU) while it runs; while a run of any kind holds the GPU the page says which and that the step's runs wait in the queue; a 409 `course_busy` answer shows its message; once finished each run shows its accuracy on 100 problems with its interval and minutes.
- **AC12.5.5** Given a shown `inspect` step, when `architectures.json` exists, then c02 shows the sample problem's first tokens as separate chips and the token counts of the problem and of the 4-shot prompt per model; c03 shows Qwen3-0.6B's parts as a stacked bar of weights by part with the numbers in a table; c04 shows the Course Models side by side in a table with every C9 field; before it exists the run area offers "Read the model designs (CPU, under a minute)".
- **AC12.5.6** Given a shown `lab` step, when it renders, then it shows the lesson's title, question and state and a link "Open lesson N in the Lab" (`/lab?lesson=<id>`); the step's run part is done once the lesson is finished.
- **AC12.5.7** Given a shown step's questions, when Nico chooses one option per question and presses "Check my answers", then each question shows "Right" or "Not quite" in words, the right option and the explanation; with all right the step reads "Quiz passed"; otherwise "Try again" clears the choices; the step reads "Done" once its run part is done and its quiz passed.
- **AC12.5.8** Given "In your own words", when Nico types an answer and presses "Save my answer", then it is saved through `PUT /course/{step}/own-words` and the model answer appears under it as "One way to say it"; a saved answer is shown when the step is opened again and can be changed.
- **AC12.5.9** Given c19 and c24, when they render, then c19 shows the memory table of AC12.3.6 with "Fits in 8 GB" or "Does not fit" in words, and c24 shows the comparison of AC12.3.7 with each interval drawn as a bar and its numbers in the table.
- **AC12.5.10** Given the landing page, when it renders, then a "Your course" card shows the progress line of AC12.5.1 and a link "Continue the course"; the card is its own block after the description and buttons block, inside the window-height container and not inside the headline section, which stays `flex-1` with `data-align="center"` (AC4.2.5), and it spans the window less the gutter (AC4.1.4); when the card makes the page taller than the window, the page scrolls; when the course overview fails to load the card shows the error's message and the rest of the page still renders.
- **AC12.5.11** Given the Course page, when the overview is loading, fails or a step fails to load, then it shows "Reading the course…", or the error's message with a "Try again" button; every control works by keyboard (NFR9).
- **AC12.5.13** Given the Course page, when it renders, then its container sets no fixed maximum width and spans the window less `--gutter` (`px-[var(--gutter)]`, AC4.1.4), and the step's prose (why, body, explanations, model answers) keeps at most 75 characters per line (`max-w-[75ch]`).
- **AC12.5.12** Given the Course page on this PC after the merge and a service restart, when Nico opens it, then he can run c01 from it, answer its questions and see his progress change on the Course page and the landing page. [manual] Verify: `outputs/course/progress.json` shows c01's quiz passed and the row `course-c01-base-06-1` is in `outputs/course/runs.csv`; Nico confirms in session.

---

## Dependencies and Critical Path

The critical path follows the learning path, with the walking skeleton first (team-practices.md, Walking Skeleton):

US1.1 → US1.2 → US1.3 → **US1.4 (walking skeleton)** → US1.5 → US2.1 → US2.2 → US2.3 → US2.4 → US3.1 → US3.2 → US3.3 → US4.1 → US4.5 → US4.6 → US3.6 → US6.1 → US5.1 → US6.2.

Stories off the critical path: US2.5, US3.4, US3.5, US3.7, US4.2, US4.3, US4.4 (after their dependencies) and US6.3 (every unit). The could-haves US7.1, US8.1, US8.2 and US9.1 come only after US6.2 is written; group 10 (US10.1 → US10.2 → US10.3 → US10.4) comes after it too (2026-11-08).

## Assumptions

- The 1.7B model is the final one (inception/brief.md), so final long-run ids use `q17`; if the best checkpoint is 0.6B, the same criteria use `q06`.
- Excluding the four exemplars leaves 496 scored dev problems (requirements.md Assumptions); dev long runs score those 496.
- The "about 3 points" noise cut-off comes from the brief's Evaluation plan (a 95% interval of about ±2.5 points on 1,319 test problems; a gain under about 3 points is reported as noise) and requirements.md FR6.1.
- The finalists file `results/finalists.json` is written by the service and committed by the build lead, like `results/runs.csv`.
- Nico's screenshots in `inputs/design/` (now holding `training-live-gateway-flow.png`) are complete before the website unit is built; AC4.1.3 cannot pass without them.
