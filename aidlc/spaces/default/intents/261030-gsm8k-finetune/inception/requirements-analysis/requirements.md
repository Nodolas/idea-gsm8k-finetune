# Requirements: Fine tune model for grade math

Sources:
- the request ("Fine tune model for grade math: build it from the brief in inception/brief.md") and `inception/brief.md`;
- `ideation/intent-capture/intent-statement.md` (learning first, Nico alone, any measurable gain, no deploy, no big-model training);
- `ideation/scope-definition/scope-document.md` (must-haves IB-1 to IB-6, could-haves IB-7 to IB-9);
- `ideation/feasibility/constraint-register.md` (3-hour runs, PC-only, licences);
- `inception/practices-discovery/team-practices.md` (tests first, named by criterion; 80% Python coverage; no deploy, no cloud CI; long runs carry a run id; inception/changes.md 2026-10-31: long runs are started detached by the `/build` lead or by Nico from the website, and units are built in parallel batches by `/build`);
- answers in `requirements-analysis-questions.md` Q1–Q6.

## Intent Analysis

Nico wants to learn, hands-on, how a small open base model is post-trained for grade-school math on his own PC (intent-statement.md). The goal is understanding first and a measurable score gain second. Every run should be visible while it trains, tunable with dials, and startable from a local website. The project ships as `results.md`, not a deploy (team-practices.md, Deployment).

- **Type:** new build (greenfield).
- **Scope:** multi-component (Python training and evaluation, a local service, a React website).
- **Complexity:** standard.
- **Depth:** Standard.

## Functional Requirements

Priorities follow `scope-document.md`: FR1–FR6 are Must, FR7–FR9 are Could. A requirement whose run takes over about 10 minutes is verified by a row in `results/runs.csv` from a long run started detached by the `/build` lead (`scripts/run-detached.sh`) or by Nico from the website, never typed by Nico in a terminal (team-practices.md, Testing Posture; inception/changes.md, 2026-10-31); its acceptance criteria in User Stories carry `[manual]`.

### FR1 Data and Evaluation (IB-1)

- **FR1.1** The system shall load GSM8K (`openai/gsm8k`, config `main`) from Hugging Face without a login or token, with every cache under the project folder.
- **FR1.2** The system shall split the 7,473 training problems into a 500-problem dev split and a training split of the rest. The split uses a fixed seed and is saved as a list of problem ids, so it is identical on every run. The 1,319 test problems are never used for training or tuning (Q2).
- **FR1.3** The system shall build one fixed 4-shot prompt whose four exemplars are taken from the dev split. Those four problems are excluded from dev scoring, so a model is never scored on its own exemplars (Q1).
- **FR1.4** The system shall extract the predicted answer from `#### <number>`, falling back to the last number in the output. It strips commas and compares numerically with the gold answer from GSM8K's `####` line. An output with no number counts as wrong (Q1).
- **FR1.5** The system shall evaluate a model (a base model, or a base model plus a saved adapter) on a named split (dev, test, or a generalisation set). It uses greedy decoding with up to 512 new tokens and an optional limit of N problems. It reports accuracy, the number scored, and minutes, and writes per-problem predictions to `outputs/<run_id>/` (Q1).
- **FR1.6** An evaluation or training run started with `--run-id <base id>-<n>` shall append exactly one row to `results/runs.csv` with `date, run_id, model, method, data, metric, value, minutes, config_hash`. A run started without a run id, and every test, writes its row to a temporary path instead (team-practices.md, Testing Posture).
- **FR1.7** The system shall record measured time per evaluated problem and per training step for a run, so the 3-hour sizing decision rests on measured numbers (feasibility Q9; constraint-register.md TC-2).
- **FR1.8** The baselines of `Qwen/Qwen3-0.6B-Base` and `Qwen/Qwen3-1.7B-Base` shall be scored on the dev split and the full test split under FR1.3–FR1.5 (long runs).
- **FR1.9** The baseline and the final model shall each be cross-checked once with the lm-evaluation-harness `gsm8k` task (5-shot, flexible extract), and both numbers recorded (Q1; long runs).

### FR2 Supervised Fine-Tuning (IB-2)

- **FR2.1** The system shall fine-tune a base model with LoRA on the training split from a run configuration whose dials are: model (0.6B or 1.7B), learning rate, epochs, LoRA rank, LoRA alpha, max sequence length, number of training examples, batch size, warmup, random seed, and answer format (step-by-step or terse) (Q3).
- **FR2.2** The system shall validate a run configuration before training. Each dial has an allowed range or set, and an invalid value is rejected with a message naming the dial and the allowed range (corner checklist: invalid input).
- **FR2.3** A training run shall stream metrics as one JSON line per logging step to `outputs/<run_id>/metrics.jsonl`. Each line holds step, total steps, loss, learning rate, elapsed seconds and estimated seconds remaining. A line with dev accuracy is added whenever the run evaluates.
- **FR2.4** When training ends, the run shall save its adapter under `checkpoints/<run_id>/`, evaluate it on the dev split (FR1.5), and append its row (FR1.6).
- **FR2.5** The system shall keep only the baseline and the best run's weights. A command prunes every other run's adapter, while their rows in `results/runs.csv` stay (team-practices.md, Deployment).
- **FR2.6** Before a run starts, the system shall estimate its duration from measured step times (FR1.7) and flag an estimate above 3 hours (constraint-register.md TC-2).

### FR3 Run Control Service (IB-3)

- **FR3.1** A local service shall expose the run list (from `results/runs.csv` and `outputs/`), the current run status, and a live stream of the current run's metrics lines.
- **FR3.2** Starting a run shall be a two-step action. First the service validates the configuration (FR2.2) and returns a summary: run id, model, method, changes against the last run, estimated time and the exact command. Only on confirmation does it launch the run as a process that keeps running if the browser closes (rough-mockups Q7; constraint-register.md TC-4).
- **FR3.3** The service shall assign each run the attempt id `<base id>-<n>` and pass it as `--run-id`, so dashboard-started runs append their row like terminal-started runs (team-practices.md, Deployment).
- **FR3.4** Only one GPU run may be active at a time. A start from the website while a run is active joins a first-in, first-out run queue (at most 10 waiting runs) that a worker process starts in order when the GPU is free; a waiting run can be removed before it starts, and the queue survives a restart of the service or the worker. A run started from the terminal does not queue: it is refused with "A run is already active", naming the active run id, while any run holds the lock (inception/changes.md, 2026-10-31; domain-design Q3, Q5).
- **FR3.5** Stopping a run shall end its process, set its status to STOPPED, keep the metrics logged so far, and append no score row.
- **FR3.6** The website may start training runs and dev-split evaluations. It may start a test-split evaluation only for a run marked as a finalist, after a second confirmation (Q4).
- **FR3.7** Run status shall be one of IDLE, RUNNING, STOPPED or FAILED. A failed run shows its exit reason and the last 20 lines of its log.

### FR4 Results Website (IB-3, IB-4)

- **FR4.1** Every page shall carry a top bar with the wordmark (linking to the landing page), "Scores" and "Training" (rough-mockups Q2).
- **FR4.2** The landing page shall show the halftone wordmark headline adapted from Nico's pasted 21st.dev component (cleared by Nico, Q6), a one-line description, and a "best so far" line (model, method, dev accuracy, gain over baseline). It also has buttons to the training and scores pages. The headline's animation stops when the operating system's reduce-motion setting is on.
- **FR4.3** The highest-scores page shall list runs ranked by dev accuracy with model, method, dev accuracy, test accuracy where scored, gain over the same model's baseline, minutes and date. The baseline row is always shown and marked. The page can filter by model and method, and compare two picked runs: settings side by side, accuracy difference, and both training curves overlaid (rough-mockups Q4).
- **FR4.4** The training page shall show live curves (loss, learning rate, dev accuracy; reward, KL and answer length for reinforcement-learning runs) that update within 5 seconds of a new metrics line. It also shows the run status with Start and Stop, the dials panel (FR2.1), the confirm-run dialog (FR3.2), and the list of past runs (rough-mockups Q3).
- **FR4.5** Each page shall show distinct empty, loading and error states as specified in `ideation/rough-mockups/wireframes.md`. Examples: "No runs yet" with a link to training; "Run log could not be read" naming the file; "Live updates paused, reconnecting" with the time of the last update.
- **FR4.6** The pages' visual look shall follow Nico's screenshots in `inputs/design/` (rough-mockups Q1).

### FR5 Generalisation Check (IB-5)

- **FR5.1** The baseline and the final model shall be scored with the protocol of FR1.5 on GSM-Plus testmini and GSM-Symbolic p1, and the results reported with no pass or fail threshold (Q5; long runs).
- **FR5.2** GSM-Plus and GSM-Symbolic shall never appear in any training data (constraint-register.md LC-2).

### FR6 Write-up and Learning Checks (IB-6)

- **FR6.1** `results.md` shall contain:
  - the run table from `results/runs.csv`;
  - the baseline and best test accuracy of the chosen model;
  - the gain, with a statement of whether it lies within noise (a 95% interval of about ±2.5 points on 1,319 problems; a gain under about 3 points is labelled within noise, inception/brief.md Evaluation plan);
  - the generalisation results;
  - what moved the number and why;
  - what to try next (intent-statement.md; scope-document.md).
- **FR6.2** Success: the best tuned checkpoint scores higher than its own baseline on the full GSM8K test split under FR1.3–FR1.5, however small the gain (intent-statement.md, success metrics).
- **FR6.3** After each unit, Nico is asked one or two short check questions on what the unit taught (intent-statement.md, reporting).

### FR7 Reinforcement Learning, Could (IB-7)

- **FR7.1** The system shall train with GRPO from the base model or the best supervised checkpoint. It uses a reward for a correct final number plus a format reward, streams metrics like FR2.3 (adding reward, KL and answer length), and uses step counts sized to fit 3 hours (scope-document.md; constraint-register.md TC-2).

### FR8 Tuning Loop, Could (IB-8)

- **FR8.1** An Optuna study shall run short proxy trials on the dev split only. It uses the 0.6B model with 100–200 training problems, each trial under 10 minutes, and stores results in local SQLite (inception/brief.md, Learning path step 5).
- **FR8.2** A proposer agent and a reviewer agent, run as Claude Code helpers in a session that Nico starts, shall propose the next run configuration with a reason and check it against the rules. The rules: dev split only, fits 8 GB and 3 hours, one main change. The agents never start a long run (constraint-register.md OC-4).

### FR9 Ablations, Could (IB-9)

- **FR9.1** Selected ablations (answer format step-by-step versus terse; samples per problem; a Python calculator tool) shall each be compared on the dev split against the same baseline (scope-document.md).

## Non-Functional Requirements

- **NFR1 Memory:** every run with default dials fits in the GPU's 8 GB (RTX 3060 Ti) without an out-of-memory error (constraint-register.md TC-1).
- **NFR2 Run length:** every default training or evaluation run finishes within 3 hours (constraint-register.md TC-2).
- **NFR3 Quick tests:** the full automated test suite runs on the CPU (through `scripts/in-env.sh`, which hides the GPU) and finishes in under 10 minutes on this PC. Only the walking-skeleton test loads a real model: `Qwen/Qwen3-0.6B-Base` on 3 dev problems, greedy, up to 256 new tokens; other tests use tiny fixtures or mocks. GPU use is first proven by the first detached long run, the 0.6B baseline evaluation (AC1.5.1) (CLAUDE.md, Learning runs; inception/changes.md, 2026-10-31).
- **NFR4 Coverage:** Python code under `src/` has at least 80% line coverage under the test suite (team-practices.md).
- **NFR5 Containment:** every script sets `HF_HOME`, `PIP_CACHE_DIR`, `XDG_CACHE_HOME`, `TRITON_CACHE_DIR`, `TORCHINDUCTOR_CACHE_DIR` and `TORCH_HOME` to paths under the project root before any other import. Models, datasets, the Python environment and Node live inside the project folder, gitignored (team-practices.md, Code Style).
- **NFR6 Local only and safe:**
  - The service and website listen on localhost only and use no accounts, API keys or paid services.
  - The only network access is public model, dataset and package downloads (constraint-register.md TC-3, LC-5).
  - The start endpoint runs only the project's own training and evaluation commands, built from a validated configuration, never a free-form command.
- **NFR7 Reproducibility:** a run with the same configuration and seed produces the same data split and records the same `config_hash` in its row.
- **NFR8 Test-split hygiene:** no code path trains, tunes or early-stops on the test split. Test-split evaluation happens only through the finalist flow (FR3.6) or an explicit terminal command (project.md, Forbidden).
- **NFR9 Accessibility basics:** every website function works by keyboard; text meets readable contrast; status is never shown by colour alone; the halftone animation respects reduce-motion (rough-mockups Q6).
- **NFR10 Live latency:** a new metrics line appears on the training page within 5 seconds (FR4.4).

## Constraints

- €0 budget: this PC, free datasets and open models only (constraint-register.md LC-5).
- Desktop browser on this PC only (rough-mockups Q5).
- Runs over about 10 minutes are started from the website by Nico, or detached from the command line by the `/build` lead (`scripts/run-detached.sh`), never in a session's foreground (constraint-register.md OC-4; inception/changes.md, 2026-10-31).
- No deploy and no cloud test pipeline; shipped means `results.md` (team-practices.md).
- Licences: Apache-2.0 models, MIT-licensed GSM8K; GSM-Plus (CC-BY-SA) and GSM-Symbolic (NonCommercial, NoDerivatives) for evaluation only (constraint-register.md LC-1, LC-2). The halftone component is cleared by Nico for personal use (Q6).
- Stack (inception/brief.md): Python with Transformers, TRL and PEFT; a local service (FastAPI); a React, TypeScript, Vite and Tailwind website with shadcn/ui charts.

## Assumptions

- The first unit's measured step times settle which model size reinforcement learning uses under the 3-hour cap (feasibility-assessment.md).
- Nico adds his design screenshots to `inputs/design/` before the website is built (rough-mockups Q1). Without them, FR4.6 cannot be checked.
- Excluding the four exemplar problems from dev scoring leaves 496 scored dev problems; this is enough for tuning decisions (FR1.3).
- The website's "best so far" and the scores ranking use dev accuracy, so the test split stays out of everyday decisions (wireframes.md).

## Out of Scope

- Any deploy, hosting or remote access (intent-statement.md).
- Full fine-tuning of the 1.7B model, and bf16 LoRA on models of 3B and up (intent-statement.md).
- Rented hardware, paid services, accounts and API keys (constraint-register.md).
- Training on GSM-Plus, GSM-Symbolic or the GSM8K test split (FR5.2, NFR8).
- Phone or tablet layouts (rough-mockups Q5).
- A pass or fail threshold on the generalisation check (Q5).

## Open Questions

- Which model reinforcement learning uses (0.6B or 1.7B) is decided after FR1.7's measurements, if FR7 is built.
- Settled: the test command (the website's test runner, and whether lint and type checks join it) is set by the `/build` lead from the spec when Construction starts (CLAUDE.md); it runs the whole suite on the CPU through `scripts/in-env.sh` (NFR3).
