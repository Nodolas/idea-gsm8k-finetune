# User Stories: Fine tune model for grade math

Sources: `inception/requirements-analysis/requirements.md` (FR1–FR9, NFR1–NFR10), `inception/practices-discovery/team-practices.md` (tests first and named by criterion; long runs are `[manual]`), the wireframes in `ideation/rough-mockups/wireframes.md` (page states), and the answers in `user-stories-questions.md` (Q1–Q7). The single persona is Nico (`personas.md`).

## Conventions

- **Format:** "As Nico, I want …, so that …". Each story has a stable `US{group}.{seq}` ID, and each acceptance criterion an `AC{group}.{seq}.{k}` ID written on one line in Given/When/Then form.
- **Tests:** every criterion is checked by at least one test named by its ID (Python `test_AC1_4_1_...` with pytest; website `AC4.2.1 ...` with Vitest and React Testing Library), or carries `[manual]` on its own line with how to verify it (Q6).
- **Long runs:** a criterion whose run takes over about 10 minutes carries `[manual]` and `Verify: results/runs.csv row <base id>`. Base ids follow `<model>-<method>-<split>` (Q7): model `q06` (`Qwen/Qwen3-0.6B-Base`) or `q17` (`Qwen/Qwen3-1.7B-Base`); method `base`, `sft`, `grpo`, `best` (the best tuned checkpoint, whichever method made it), or an ablation name; split `dev`, `test`, `harness` (lm-evaluation-harness on the test split), `gsmplus` or `gsmsym`. Each attempt is started detached by the `/build` lead (`scripts/run-detached.sh`) or by Nico from the website, never typed by Nico in a terminal, with `--run-id <base id>-1`, `-2`, and so on (inception/changes.md, 2026-10-31); the row's `run_id` is the attempt id. The `q17` ids assume the 1.7B model is the final one (inception/brief.md); if the best checkpoint turns out to be 0.6B, the same criteria use `q06`.
- **Quick tests:** tests run on the CPU in under 10 minutes; only the walking-skeleton test loads a real model (3 dev problems), others use tiny fixtures, mocks or a few training steps. Wherever a test runs a model on a few problems or steps ("a limit of 5 problems", "a few steps"), the model is a tiny model fixture: a Qwen3-architecture model with random weights and a few small layers, built by the test (with the 0.6B tokenizer), never the real 0.6B or 1.7B weights. All tests point the results file at a temporary path, never `results/runs.csv` (NFR3, team-practices.md).
- **Run results file:** "the results file" below means `results/runs.csv` for long runs and a temporary file in tests (FR1.6).
- **Priority:** groups 1–6 are Must Have (scope-document.md IB-1 to IB-6); groups 7–9 are Could Have, built only after everything else works (IB-7 to IB-9, Q2). No story is Should Have or Won't Have; exclusions are listed in requirements.md Out of Scope.

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
| 4. Results website | US4.1–US4.6 | Must |
| 5. Generalisation check | US5.1 | Must |
| 6. Final score, write-up and learning checks | US6.1–US6.3 | Must |
| 7. Reinforcement learning | US7.1 | Could |
| 8. Tuning loop | US8.1–US8.2 | Could |
| 9. Ablations | US9.1 | Could |

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
- **AC4.5.5** Given past runs, when the training page renders, then they are listed with run id, status, start time, minutes and dev accuracy, and opening one shows its curves labelled with its run id.
- **AC4.5.6** Given a real run in progress, when a new metrics line is written, then it appears on the training page within 5 seconds. [manual] Verify: Nico watches a live run and checks the step counter against `outputs/<run_id>/metrics.jsonl` at the website unit's checkpoint

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
- **AC5.1.3** Given the baseline `Qwen/Qwen3-1.7B-Base`, when it is scored on GSM-Plus testmini, then the result is recorded with no pass or fail mark. [manual] Verify: results/runs.csv row q17-base-gsmplus
- **AC5.1.4** Given the baseline `Qwen/Qwen3-1.7B-Base`, when it is scored on GSM-Symbolic p1, then the result is recorded with no pass or fail mark. [manual] Verify: results/runs.csv row q17-base-gsmsym
- **AC5.1.5** Given the best tuned checkpoint, when it is scored on GSM-Plus testmini, then the result is recorded with no pass or fail mark. [manual] Verify: results/runs.csv row q17-best-gsmplus
- **AC5.1.6** Given the best tuned checkpoint, when it is scored on GSM-Symbolic p1, then the result is recorded with no pass or fail mark. [manual] Verify: results/runs.csv row q17-best-gsmsym

---

## 6. Final Score, Write-up and Learning Checks

### US6.1 Score the best checkpoint on test

As Nico, I want my best tuned checkpoint scored once on the full test split and cross-checked with the harness, so that I know whether I beat the baseline.

- **Priority:** Must Have
- **Requirements:** FR6.2, FR1.9, FR3.6, NFR8
- **Depends on:** US1.5, US2.4, US3.6
- **INVEST:** independent once a finalist exists; the long runs are detached runs.

- **AC6.1.1** Given a finalist's adapter and a limit of 5 test problems, when the final evaluation runs, then it writes one row with method `best`, data `gsm8k-test` and the finalist's run id in the `adapter_run` field to the results file (contract C1).
- **AC6.1.2** Given the best tuned checkpoint, when it is scored on all 1,319 test problems, then its test accuracy is higher than its own baseline's (`q17-base-test`), however small the gain. [manual] Verify: results/runs.csv row q17-best-test
- **AC6.1.3** Given the best tuned checkpoint, when the lm-evaluation-harness cross-check runs, then the harness accuracy is recorded beside the project's own number. [manual] Verify: results/runs.csv row q17-best-harness

### US6.2 Write results.md

As Nico, I want `results.md` built from my run log, with the gain judged against noise, so that the write-up says honestly what moved the number and why.

- **Priority:** Must Have
- **Requirements:** FR6.1
- **Depends on:** US6.1, US5.1
- **INVEST:** small generator plus Nico's own write-up; the generator is testable with a temporary results file.

- **AC6.2.1** Given a results file, when the results generator runs, then it writes the run table into `results.md` with one line per row.
- **AC6.2.2** Given a baseline and a best test accuracy on 1,319 problems, when the gain is reported, then a gain smaller than about 3 points is labelled "within noise" and a larger one "outside noise".
- **AC6.2.3** Given harness rows, when `results.md` is built, then the harness numbers are shown labelled as a cross-check and are not used to compute the gain.
- **AC6.2.4** Given the finished project, when Nico reads `results.md`, then it holds the baseline and best test accuracy, the gain with its noise label, the generalisation results, what moved the number and why, and what to try next. [manual] Verify: Nico reads `results.md` and approves it at the write-up unit's checkpoint

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

## Dependencies and Critical Path

The critical path follows the learning path, with the walking skeleton first (team-practices.md, Walking Skeleton):

US1.1 → US1.2 → US1.3 → **US1.4 (walking skeleton)** → US1.5 → US2.1 → US2.2 → US2.3 → US2.4 → US3.1 → US3.2 → US3.3 → US4.1 → US4.5 → US4.6 → US3.6 → US6.1 → US5.1 → US6.2.

Stories off the critical path: US2.5, US3.4, US3.5, US3.7, US4.2, US4.3, US4.4 (after their dependencies) and US6.3 (every unit). The could-haves US7.1, US8.1, US8.2 and US9.1 come only after US6.2 is written.

## Assumptions

- The 1.7B model is the final one (inception/brief.md), so final long-run ids use `q17`; if the best checkpoint is 0.6B, the same criteria use `q06`.
- Excluding the four exemplars leaves 496 scored dev problems (requirements.md Assumptions); dev long runs score those 496.
- The "about 3 points" noise cut-off comes from the brief's Evaluation plan (a 95% interval of about ±2.5 points on 1,319 test problems; a gain under about 3 points is reported as noise) and requirements.md FR6.1.
- The finalists file `results/finalists.json` is written by the service and committed by the build lead, like `results/runs.csv`.
- Nico's screenshots in `inputs/design/` (now holding `training-live-gateway-flow.png`) are complete before the website unit is built; AC4.1.3 cannot pass without them.
