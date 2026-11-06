# Domain Design: Component Questions

Already settled and not asked again: Python with Transformers, TRL and PEFT for training and evaluation; a local FastAPI service that streams metrics to the website over Server-Sent Events; a React, TypeScript, Vite and Tailwind website with shadcn/ui (inception/brief.md, Learning path step 3; requirements.md Constraints); runs started from the terminal or the website, keeping on if the browser closes (FR3.2); one run at a time through a shared lock file (user-stories Q5); finalists in `results/finalists.json` (user-stories Q3). Deployment grouping (one package or several) is decided later, in Units Generation.

## Q1. [Architect] How finely should the Python side be split into building blocks?

Each building block owns its own logic and data and is tested on its own; Units Generation later groups them into units of work.

A. By concern, about 10 blocks: Datasets and prompts; Answer scoring; Evaluation; Training (supervised and reinforcement learning); Run configuration (dials and checks); Run records (run log, finalists, per-run files); Run control (lock, launch, stop, status, estimates); Run service (the HTTP and streaming API); Results report (`results.md`); Tuning (Optuna study and the proposal rule checker). The website is one more block
B. Coarse, 3 blocks: an ML core (data, scoring, evaluation, training, config), the run service (records, control, API) and the website
C. Fine, one block per story group in stories.md (about 15)
X. Other (please specify)

[Answer]: A. By concern, about 10 blocks plus the website

## Q2. [Architect] Who may read and write the run log and the other run files?

The run log (`results/runs.csv`), the finalists file and each run's folder under `outputs/` are read by the service, the website, the report and the pruning command, and written by training and evaluation runs.

A. One "Run records" block owns them all: it is the only code that writes or parses these files, and every other block goes through it (one place for the column format, the malformed-row rule and the attempt numbering)
B. Each block reads and writes the files it needs directly, following a documented format
X. Other (please specify)

[Answer]: A. One "Run records" block owns the run files; every other block goes through it

## Q3. [Architect] How should the service run training and evaluation?

A run must keep going if the browser closes, and terminal-started runs must behave the same as website-started ones.

A. The service launches the same command-line entry points Nico uses in the terminal, as separate processes, and follows them only through files (the lock file, `metrics.jsonl`, the log, the run log); it never imports training code
B. The service imports the training and evaluation code and runs it in a background thread of its own process
C. A separate worker process takes runs from a small local queue that the service fills
X. Other (please specify)

[Answer]: C. A separate worker process takes runs from a small local queue that the service fills

## Q4. [Architect] Should supervised fine-tuning and GRPO live in one training block or two?

GRPO is a could-have built after everything else (FR7). Both methods share the configuration check, metrics streaming, checkpoint saving, the end-of-run dev score and the run-log row.

A. One Training block with two methods (`sft`, `grpo`) behind a shared run loop for metrics, checkpoints and the closing evaluation
B. Two separate blocks, Supervised training and Reinforcement learning, each with its own run loop
X. Other (please specify)

[Answer]: A. One Training block with two methods behind a shared run loop (left to the architect: "What makes the most sense")

## Q5. [Architect] Follow-up to Q3: may runs wait in the queue, and how do terminal runs fit in?

Q3 chose a worker process that takes runs from a local queue. A queue lets runs wait in line, but the requirements refuse a second start while a run is active ("A run is already active", FR3.4, AC3.3.1), and runs started from the terminal must keep working (AC3.3.2).

A. Queue of one: the worker runs one job at a time and the service refuses a new start while a run is active or waiting, exactly as FR3.4 says. Terminal commands skip the queue and take the same lock file directly, so the worker and the terminal can never both use the GPU
B. A real queue: website starts while a run is active wait in line and the worker starts them in order. This changes FR3.4 (a dated `inception/changes.md` line first). Terminal commands still take the lock directly and are refused while any run holds it
X. Other (please specify)

[Answer]: B. A real queue: website starts wait in line and run in order; terminal commands take the lock directly and are refused while any run holds it; FR3.4 changes

## Consolidated Summary Confirmation

- About 10 Python building blocks by concern: Datasets and prompts, Answer scoring, Evaluation, Training, Run configuration, Run records, Run control, Run service, Results report and Tuning; the website is one more block.
- One Run records block is the only code that writes or parses `results/runs.csv`, `results/finalists.json` and each run's folder under `outputs/`; every other block goes through it.
- Website runs go through a separate worker process that takes jobs from a local queue the service fills; the service never imports training code and follows runs only through files.
- The queue is a real queue: a website start made while a run is active waits in line, first in first out, and the worker starts it when the GPU is free. Proposed details: the queue is kept as files under `outputs/queue/` so it survives a service or worker restart; at most 10 runs can wait; a waiting run can be removed before it starts; the training page lists waiting runs; a test-split evaluation of a finalist queues the same way.
- Terminal commands skip the queue and take the same lock file directly; they are refused with "A run is already active" while any run holds the lock, and the worker waits while a terminal run holds it.
- Supervised fine-tuning and GRPO share one Training block with two methods behind a shared run loop (left to me).
- Because the queue changes approved spec, I add a dated line to `inception/changes.md` (class `change`) and update: FR3.4 in `requirements.md`; AC3.3.1, AC4.6.2 and AC4.6.4 in `stories.md`, plus new criteria for queueing, the queue cap, removing a waiting run and the queue surviving a restart; and a "Queued runs" list on the training page in `refined-mockups/mockups.md`.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
