# Contract Summary

The formal contracts between the units in `inception/units-generation/unit-of-work.md`, following the edges and integration points in `inception/units-generation/unit-of-work-dependency.md`. Entity shapes come from `inception/domain-design/components.md`; limits and rules from `inception/requirements-analysis/requirements.md` (FR1.6, FR2.3, FR3.1–FR3.7 with FR3.4 as changed on 2026-10-31, NFR6, NFR10). Answers: `contract-design-questions.md` Q1–Q4.

Nothing is exposed outside this PC: the service binds to 127.0.0.1 and there is no external API (NFR6). Hugging Face downloads are consumed, not provided, and need no contract here.

## Contracts

| # | Provider Unit | Consumer | Mechanism | Owner |
|---|---|---|---|---|
| C1 | u1-eval-skeleton (RunRecords) | u2, u3, u4, u6, u7, u8, u9, u10 | Shared file: `results/runs.csv` | u1-eval-skeleton |
| C2 | u1-eval-skeleton (RunRecords), extended by u3-sft and u10-self-taught-cot | u3, u4, u6, u7, u8, u9, u10 | Shared files: `outputs/<run_id>/` (`config.json`, `metrics.jsonl`, `status.json`, `predictions.jsonl`, `timings.json`, `run.log`) | u1-eval-skeleton |
| C3 | u1-eval-skeleton (lock), extended by u4-run-service (queue) | u2, u3, u4, u6, u8 | Shared files: `outputs/run.lock`, `outputs/queue/*.json` | u1 (lock), u4 (queue) |
| C4 | u4-run-service | u3 (prune), u6 | Shared file: `results/finalists.json` | u4-run-service |
| C5 | u1-eval-skeleton (`evaluate`), u3-sft (`train`) | u4-run-service (worker) | Process launch: `gsm8k` commands, arguments and exit codes | u1-eval-skeleton |
| C6 | u4-run-service, extended by u10-self-taught-cot (`/reasoning`) and u5-website (`/gpu`) | u5-website, u10-self-taught-cot | HTTP JSON on 127.0.0.1, `/api/v1` | u4-run-service |
| C7 | u4-run-service | u5-website | Server-Sent Events on 127.0.0.1 | u4-run-service |

## Common Rules

- **Versioning (Q1).** The run files are versioned and append-only. Run-log columns are only ever added at the end, and old rows stay valid with the new cells empty. Every JSON file and metrics line carries `"v": 1`. A breaking change needs a dated `inception/changes.md` line and a `gsm8k migrate` command that rewrites old files.
- **Atomic writes.** Every file is written to a temporary name in the same folder and renamed into place. Appends to `results/runs.csv` and `metrics.jsonl` write one whole line at a time, so readers never see a half line as data.
- **Encoding.** UTF-8, `\n` line endings, times in ISO 8601 UTC (`2026-11-04T20:41:07Z`). Accuracy is a fraction from 0 to 1 with 4 decimals; minutes have 1 decimal.
- **Unknown fields.** Readers ignore fields they do not know (additive changes are safe).

## C1 Run Log (`results/runs.csv`)

```yaml
shared-schema: run-log
version: 1
file: results/runs.csv            # committed; tests point it at a temporary path (FR1.6)
format: csv, header row, comma-separated, RFC 4180 quoting
columns:                          # order fixed; new columns only at the end
  - name: date
    type: string                  # ISO 8601 UTC, when the run ended
  - name: run_id
    type: string                  # attempt id "<base id>-<n>", e.g. q06-sft-dev-2; unique across the file
    pattern: '^(q06|q17)-[a-z0-9]+-[a-z0-9]+-[0-9]+$'
  - name: model
    type: string
    enum: [Qwen/Qwen3-0.6B-Base, Qwen/Qwen3-1.7B-Base]
  - name: method
    type: string
    enum: [base, sft, grpo, best, terse, vote, calc, optuna, cotgen, selfcot]   # cotgen, selfcot added 2026-11-08 (US10.1, US10.2)
  - name: data
    type: string
    enum: [gsm8k-dev, gsm8k-test, gsm8k-test-harness, gsmplus-testmini, gsmsym-p1, gsm8k-train]   # gsm8k-train added 2026-11-08: cotgen rows only
  - name: metric
    type: string
    enum: [accuracy, harness_flexible_accuracy, kept_fraction]   # kept_fraction added 2026-11-08: cotgen rows only (kept problems / problems tried)
  - name: value
    type: number                  # 0..1, 4 decimals
  - name: minutes
    type: number                  # 1 decimal
  - name: config_hash
    type: string                  # sha256 hex of the normalised config (C2 config.json without run_id and v)
  - name: adapter_run             # added in v1 for best-checkpoint and generalisation rows; empty otherwise
    type: string
rules:
  - exactly one row per scored run; a stopped or failed run writes no row (FR3.5)
  - a row whose field count, enum or number does not parse is skipped and counted, never fatal (AC3.1.3)
  - no file means an empty log; an unreadable file is an error naming the file (AC3.1.4)
```

## C2 Run Folder (`outputs/<run_id>/`)

```yaml
shared-schema: run-folder
version: 1
folder: outputs/<run_id>/           # gitignored
files:
  config.json:                      # written before the run starts; input to config_hash
    v: 1
    run_id: string
    model: string                   # C1 enum
    method: string                  # C1 enum
    split: string                   # dev | test | gsmplus-testmini | gsmsym-p1 | train (train: cotgen only, added 2026-11-08); test only through the finalist flow (method best) or an explicit command such as the base-model baselines (NFR8, AC1.5.2, AC1.5.4) (changed 2026-11-06)
    adapter_path: string|null       # checkpoints/<run_id>/ of the adapter evaluated or continued
    learning_rate: number           # the eleven dials, ranges in stories.md Training Dials
    epochs: integer
    lora_rank: integer
    lora_alpha: integer
    max_seq_len: integer
    train_examples: integer|"all"
    batch_size: integer
    warmup_ratio: number
    seed: integer                   # training and sampling seed (a dial); does not move the split
    split_seed: integer             # fixed 42; decides the dev/train split and the prompt exemplars (added 2026-10-31)
    model_revision: string          # pinned Hub commit hash of the model; default = the pin in the code (added 2026-10-31)
    dataset_revision: string        # pinned Hub commit hash of openai/gsm8k; default = the pin in the code (added 2026-10-31)
    answer_format: string           # step-by-step | terse
    limit: integer|null             # evaluation problem limit; null = whole split
    vote_samples: integer           # 1 = single greedy sample; >1 = majority vote (US9.1)
    calculator: boolean             # calculator tool on or off (US9.1)
    max_new_tokens: integer         # generation cap per answer; default 512 (BR3.5); quick tests use 256 (AC1.4.1) (added 2026-11-06)
    evaluator: string               # project | lm-eval-harness; default project; the harness cross-check uses its own prompt and token cap (AC1.5.5) (added 2026-11-06)
    grpo_steps: integer|null        # GRPO only (US7.1)
    grpo_generations: integer|null  # GRPO samples per problem (US7.1)
    cot_problems: integer|"all"     # cotgen: first N training problems by index; 50..6973 or "all"; default 1500 (added 2026-11-08)
    cot_samples: integer            # cotgen: samples per problem, 1..8; default 4 (added 2026-11-08)
    cot_temperature: number         # cotgen: sampling temperature, 0.1..1.5; default 0.7 (added 2026-11-08)
    cot_data_run: string|null       # selfcot: run id of the cotgen run whose cot_data.jsonl is trained on; required for selfcot, null otherwise; default null (added 2026-11-08)
  metrics.jsonl:                    # one JSON object per line, appended as the run goes (FR2.3)
    line:
      v: 1
      step: integer
      total_steps: integer          # for evaluations: problems scored and problems to score
      loss: number|null
      learning_rate: number|null
      elapsed_s: number
      eta_s: number|null            # null = no estimate yet
      dev_accuracy: number|null     # present on evaluation lines
      reward: number|null           # GRPO only
      kl: number|null               # GRPO only
      answer_length: number|null    # GRPO only
      grad_norm: number|null        # fine-tune lines: the trainer's gradient norm; null when not reported (added 2026-11-08)
      epoch: number|null            # fine-tune lines: the fractional epoch of the step; null when not reported (added 2026-11-08)
                                    # A line without grad_norm and epoch (written before 2026-11-08) is valid; readers treat a missing field as null.
  status.json:                      # written when the run ends
    v: 1
    run_id: string
    status: string                  # finished | failed | stopped
    exit_code: integer              # C5 codes
    reason: string|null             # e.g. "GPU out of memory"
    ended_at: string
  timings.json:
    v: 1
    seconds_per_step: number|null
    seconds_per_problem: number|null
    peak_gpu_memory_gb: number
  predictions.jsonl:                # evaluations only: problem_id, output, predicted, gold, correct
  cot_data.jsonl:                   # cotgen only (added 2026-11-08): one line per kept problem, problem index order
    line:
      v: 1
      problem_id: string            # a training-part id, never dev or test
      question: string
      gold: string
      solution: string              # the kept sample as generated (cut by BR3.5), ending with its "#### <number>" line
      correct_samples: integer      # how many of the problem's samples were correct
      samples: integer              # samples drawn for the problem (cot_samples)
  cot_stats.json:                   # cotgen only (added 2026-11-08), written when generation ends
    v: 1
    run_id: string
    problems: integer               # problems tried
    samples_per_problem: integer
    solved: integer                 # problems with at least one correct sample
    kept: integer                   # problems with a kept sample (= lines of cot_data.jsonl)
    kept_fraction: number           # kept / problems, the row's value
    mean_lines_kept: number|null    # mean reasoning lines of the kept solutions; null when kept = 0
    mean_words_kept: number|null    # mean reasoning words of the kept solutions; null when kept = 0
    mean_lines_reference: number|null   # the same for GSM8K's reference solutions of the kept problems, without <<...>> notes; null when kept = 0
    mean_words_reference: number|null
  run.log:                          # plain text log; the last 20 lines are shown on failure (FR3.7)
rules:
  - config_hash = sha256 of the canonical JSON of {model, method} plus every other field whose value differs from its documented
    default, keys sorted, without run_id and v; every option that changes results changes the hash, and a field added later in v1
    with a default leaves earlier hashes unchanged (changed 2026-10-31)
  - a missing metrics.jsonl reads as no lines, never an error (AC4.4.3)
  - reasoning lines of a text are its non-empty lines before the first "#### <number>" line; its words are the whitespace-separated words of those lines (US10.1, US10.3; added 2026-11-08)
  - split "train" exists only for method cotgen, and cotgen only takes split "train"; selfcot is a training method (dev split, never test) like sft (added 2026-11-08)
  - a cotgen run's timings.json leaves seconds_per_problem null (several samples per problem would skew evaluation estimates, as the harness note says) and adds seconds_per_generated_problem (added 2026-11-08)
```

## C3 Lock and Queue (`outputs/run.lock`, `outputs/queue/`)

```yaml
shared-schema: lock-and-queue
version: 1
lock:                                # changed 2026-10-31 (inception/changes.md; u1 Functional Design Q1)
  file: outputs/run.lock             # the file persists; holding it means holding an OS lock on it
  mechanism: operating-system advisory lock (flock, exclusive, non-blocking) held by the run's process for its whole life
  content:                           # rewritten by the holder right after it takes the lock; for display only
    v: 1
    run_id: string
    pid: integer
    started_at: string
    started_by: string              # terminal | worker
  take:
    - try the exclusive non-blocking lock; of two racing takers exactly one wins
    - if it is held -> refuse with "A run is already active" and the run_id read from the file; exit code 3
  release: the kernel releases the lock when the process ends, also on a crash; the holder clears the content on a clean exit
  status: a reader that can take and at once release the lock knows no run is active; a file whose content names a run
    while the lock is free means that run ended without finishing (reported as failed, "The run process ended without finishing")
  rules:
    - nothing ever renames or deletes a lock to take it over
    - Linux (this PC) is the only supported platform
queue:
  folder: outputs/queue/
  entry_file: <position:03d>-<attempt_id>.json   # e.g. 002-q17-sft-dev-3.json
  content:
    v: 1
    attempt_id: string
    config: object                  # C2 config.json fields, already checked
    added_at: string
  rules:
    - first in, first out by position; at most 10 entries (AC3.7.3)
    - an entry is removed only after the process it launched holds the lock
    - removing a waiting entry deletes its file; positions of the others move up
```

## C4 Finalists (`results/finalists.json`)

```yaml
shared-schema: finalists
version: 1
file: results/finalists.json        # committed by the build lead
content:
  v: 1
  finalists:
    - run_id: string                # must exist in results/runs.csv
      marked_at: string
rules:
  - no file means no finalists; an unreadable file blocks every test-split evaluation and names the file (AC3.6.5)
  - pruning keeps every finalist's adapter (AC2.5.3)
```

## C5 `gsm8k` Commands (worker launch)

```yaml
command-contract: gsm8k-cli
version: 1
invocation: argument list, never a shell string (AC3.2.5)
commands:
  evaluate:
    args: [--config <outputs/<run_id>/config.json>, --run-id <attempt id>, --results <path, default results/runs.csv>, --started-by worker]
  train:
    args: [--config <outputs/<run_id>/config.json>, --run-id <attempt id>, --results <path>, --started-by worker]
  notes:                            # added 2026-10-31
    - the worker always passes --config (written by the service before launch) and --started-by worker
    - a terminal run may omit --config and give options as flags; the command then writes config.json itself
    - --started-by defaults to terminal and is recorded only in the lock content
    - cot-generate (added 2026-11-08): `gsm8k cot-generate` takes the same --config, --run-id, --results and --started-by arguments as evaluate, plus terminal flags --model, --cot-problems, --cot-samples, --cot-temperature, --seed and --max-new-tokens; method cotgen, split train; it holds the lock like every GPU run and uses the same exit codes
    - selfcot (added 2026-11-08): `gsm8k train` takes --method sft|selfcot (default sft) and --cot-data-run <run id>; selfcot needs cot_data_run, else exit 2
    - method best (added 2026-11-07): evaluate and harness take --method base|best and --finalists <path>; best needs --adapter (or adapter_path) of a finalist run whose method makes an adapter (sft, grpo, terse, optuna, selfcot; selfcot added 2026-11-08); the row keeps method best with adapter_run = the adapter run id; a worker config.json with method best is used unchanged; a test-split evaluation with an adapter must be method best
environment: the six cache variables set to absolute project paths before any other import (NFR5)
exit_codes:
  0: finished, row written
  1: failed; reason in status.json
  2: invalid configuration; message names the dial and its allowed range
  3: lock held; message "A run is already active: <run_id>"; nothing written
  130: stopped (SIGTERM or SIGINT); metrics kept, no row
worker_rules:
  - exit code 3 puts the queue entry back at the head and the worker waits for the lock (AC3.7.6)
  - the worker stops a run with SIGTERM, then SIGKILL after 30 s
```

## C6 Run Service HTTP API

```yaml
openapi: 3.1.0
info:
  title: gsm8k run service
  version: 1.0.0
servers:
  - url: http://127.0.0.1:8000/api/v1
paths:
  /runs:
    get:
      summary: Run list from the run log and run folders (AC3.1.1, AC3.1.3)
      responses:
        '200':
          content:
            application/json:
              schema:
                type: object
                properties:
                  runs: { type: array, items: { $ref: '#/components/schemas/Run' } }
                  skipped_rows: { type: integer }
        '500': { $ref: '#/components/responses/Error' }
  /runs/{run_id}:
    get:
      summary: One run's config, status and timings
      responses:
        '200': { content: { application/json: { schema: { $ref: '#/components/schemas/RunDetail' } } } }
        '404': { $ref: '#/components/responses/Error' }
  /runs/{run_id}/metrics:
    get:
      summary: Metrics lines after a line number, for past runs and compare
      parameters:
        - { name: after, in: query, schema: { type: integer, default: 0 } }
      responses:
        '200':
          content:
            application/json:
              schema:
                type: object
                properties:
                  lines: { type: array, items: { $ref: '#/components/schemas/MetricsLine' } }
                  next: { type: integer }
  /status:
    get:
      summary: IDLE, RUNNING, STOPPED or FAILED with the active or last run (FR3.7)
      responses:
        '200': { content: { application/json: { schema: { $ref: '#/components/schemas/Status' } } } }
  /dials:
    get:
      summary: The dial table with ranges and defaults (AC4.6.1)
      description: 'Added 2026-11-07: returns {"dials": [DialSpec]}, the eleven dials in stories.md Training Dials order; DialSpec = {name, label, kind: select|number|integer, options: list|null, min: number|null, max: number|null, allow_all: bool, default, help}'
  /gpu:
    get:
      summary: The NVIDIA GPU's live figures for the training page (US4.5, added 2026-11-08); read-only
      description: >
        Runs `nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,power.limit,clocks.sm,clocks.max.sm --format=csv,noheader,nounits`
        for the first GPU with a 3 second timeout. Answers 200 with Gpu; `available` is false with a `reason` when nvidia-smi is missing,
        fails, times out or prints something that does not parse. A field nvidia-smi prints as `[N/A]` or `N/A` is null. Never 500.
      responses:
        '200': { content: { application/json: { schema: { $ref: '#/components/schemas/Gpu' } } } }
  /reasoning:
    get:
      summary: Self-taught chain of thought against base and the reference fine-tune for one model (US10.3, added 2026-11-08); read-only
      parameters:
        - { name: model, in: query, schema: { type: string, default: Qwen/Qwen3-1.7B-Base } }
      description: >
        Roles: base = the model's latest base gsm8k-dev accuracy row; sft = its latest sft gsm8k-dev accuracy row;
        selfcot = its latest selfcot gsm8k-dev accuracy row ("latest" = last in file order). Interval = accuracy
        ± 1.96·sqrt(p(1−p)/scored), clipped to 0..1; scored and correct come from the run's predictions.jsonl
        (scored null when it cannot be read). gain_pts = (accuracy − base accuracy)·100, 1 decimal; noise =
        "within noise" when |gain_pts| < 4, else "outside noise". /runs/check refuses methods cotgen and selfcot
        with 422 invalid_dial (field method): the website does not start them in this version. Flips are over problem ids in both runs'
        predictions. Examples: up to 3 problems fixed by selfcot, in base predictions order. Summary: plain
        English sentences built from these numbers.
      responses:
        '200': { content: { application/json: { schema: { $ref: '#/components/schemas/Reasoning' } } } }
        '422': { $ref: '#/components/responses/Error' }   # invalid_dial: model outside the two allowed
        '500': { $ref: '#/components/responses/Error' }   # run_log_unreadable
  /runs/check:
    post:
      summary: Step one of a start; checks and summarises, launches nothing (AC3.2.1)
      requestBody: { content: { application/json: { schema: { $ref: '#/components/schemas/RunRequest' } } } }
      responses:
        '200': { content: { application/json: { schema: { $ref: '#/components/schemas/CheckedRun' } } } }
        '422': { $ref: '#/components/responses/Error' }
  /runs/confirm:
    post:
      summary: Step two; queues the checked run, or starts it when the GPU is free (AC3.2.2, AC3.7.1)
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [check_id]
              properties:
                check_id: { type: string }
                second_confirmation: { type: boolean, default: false }
      responses:
        '200':
          content:
            application/json:
              schema:
                type: object
                properties:
                  attempt_id: { type: string }
                  state: { type: string, enum: [started, queued] }
                  position: { type: integer }
        '409': { $ref: '#/components/responses/Error' }
        '404': { $ref: '#/components/responses/Error' }
  /queue:
    get:
      summary: Waiting runs in order (AC4.6.7)
  /queue/{attempt_id}:
    delete:
      summary: Remove a waiting run (AC3.7.4)
      responses:
        '204': { description: removed }
        '404': { $ref: '#/components/responses/Error' }
  /stop:
    post:
      summary: Stop the active run (FR3.5)
      responses:
        '200': { content: { application/json: { schema: { $ref: '#/components/schemas/Status' } } } }
        '409': { $ref: '#/components/responses/Error' }
  /finalists:
    get:
      summary: Finalist run ids (C4)
  /finalists/{run_id}:
    put:
      summary: Mark a finalist (AC3.6.1)
    delete:
      summary: Unmark a finalist (AC3.6.1)
components:
  schemas:
    Run:
      type: object
      properties:
        run_id: { type: string }
        model: { type: string }
        method: { type: string }
        data: { type: string }
        dev_accuracy: { type: [number, 'null'] }
        test_accuracy: { type: [number, 'null'] }
        gain: { type: [number, 'null'] }
        minutes: { type: number }
        date: { type: string }
        status: { type: string, enum: [finished, failed, stopped, running, queued] }
        finalist: { type: boolean }
        adapter_run: { type: [string, 'null'] }   # added 2026-11-07
        started_at: { type: [string, 'null'] }    # added 2026-11-07: row date minus minutes, or the lock's started_at for the active run
      description: 'test_accuracy is the run''s own gsm8k-test row, else the latest gsm8k-test row whose adapter_run is this run, else (a base dev run) its model''s latest base gsm8k-test row with an empty adapter_run; gain is dev_accuracy minus the dev accuracy of the model''s latest base gsm8k-dev run, null for that baseline and for runs without a dev score (2026-11-07)'
    RunDetail:
      type: object
      properties:
        config: { type: object }
        status: { type: object }
        timings: { type: object }
    MetricsLine:
      type: object
      description: C2 metrics.jsonl line
    Status:
      type: object
      properties:
        status: { type: string, enum: [IDLE, RUNNING, STOPPED, FAILED, FINISHED] }   # FINISHED only in last_run (2026-11-07)
        run_id: { type: [string, 'null'] }
        reason: { type: [string, 'null'] }
        log_tail: { type: array, items: { type: string } }
        evaluation:   # 2026-11-08 (AC3.1.6): how far a RUNNING run's scoring has got; null otherwise and in last_run
          type: [object, 'null']
          properties:
            split: { type: string }
            scored: { type: integer, minimum: 0 }   # complete lines in predictions.jsonl, at most total
            total: { type: integer, minimum: 1 }    # split size, or the run's limit when smaller
    RunRequest:
      type: object
      description: C2 config.json fields without run_id; omitted dials take their defaults
    CheckedRun:
      type: object
      properties:
        check_id: { type: string }
        attempt_id: { type: string }
        model: { type: string }
        method: { type: string }
        changes: { type: array, items: { type: string } }
        estimate_s: { type: [number, 'null'] }
        over_cap: { type: boolean }
        command: { type: array, items: { type: string } }
        queue_position: { type: integer }
        needs_second_confirmation: { type: boolean }
    Gpu:                                          # added 2026-11-08 (US4.5)
      type: object
      properties:
        available: { type: boolean }
        reason: { type: [string, 'null'] }        # why it is not available; null when available
        name: { type: [string, 'null'] }
        utilization_pct: { type: [number, 'null'] }
        memory_used_mb: { type: [number, 'null'] }      # MiB, as nvidia-smi prints it
        memory_total_mb: { type: [number, 'null'] }
        temperature_c: { type: [number, 'null'] }
        power_w: { type: [number, 'null'] }
        power_limit_w: { type: [number, 'null'] }
        sm_clock_mhz: { type: [number, 'null'] }
        sm_clock_max_mhz: { type: [number, 'null'] }
    Reasoning:                                    # added 2026-11-08 (US10.3)
      type: object
      properties:
        v: { type: integer }                      # 1
        model: { type: string }
        available: { type: boolean }              # false when the model has no selfcot gsm8k-dev accuracy row
        roles:                                    # always base, sft, selfcot in this order; a role without a row has run_id null and null figures
          type: array
          items:
            type: object
            properties:
              role: { type: string, enum: [base, sft, selfcot] }
              run_id: { type: [string, 'null'] }
              accuracy: { type: [number, 'null'] }
              correct: { type: [integer, 'null'] }
              scored: { type: [integer, 'null'] }
              interval_low: { type: [number, 'null'] }
              interval_high: { type: [number, 'null'] }
              trained_on: { type: [integer, 'null'] }     # training problems the fine-tune learned from: train_examples of its config.json ("all" = 6973 for sft, = kept for selfcot), capped at what was available; null for base
              gain_pts: { type: [number, 'null'] }        # null for base
              noise: { type: [string, 'null'], enum: [within noise, outside noise, null] }
              mean_lines: { type: [number, 'null'] }      # mean reasoning lines of its outputs (C2 rule)
              mean_words: { type: [number, 'null'] }
              error: { type: [string, 'null'] }           # e.g. "Predictions could not be read: outputs/<run_id>/predictions.jsonl"
        flips:                                    # one per sft and selfcot role that has a run and readable predictions on both sides
          type: array
          items:
            type: object
            properties:
              role: { type: string, enum: [sft, selfcot] }
              run_id: { type: string }
              against: { type: string }           # the base run id
              fixed: { type: integer }            # base wrong, run right
              broken: { type: integer }           # base right, run wrong
              both_right: { type: integer }
              both_wrong: { type: integer }
        generation:                               # the selfcot run's cot_data_run figures (C2 cot_stats.json plus run_id); null without them
          type: [object, 'null']
        generation_error: { type: [string, 'null'] }   # names the unreadable config.json or cot_stats.json
        examples:                                 # up to 3
          type: array
          items:
            type: object
            properties:
              problem_id: { type: string }
              gold: { type: string }
              base_output: { type: string }
              selfcot_output: { type: string }
        summary: { type: array, items: { type: string } }
    Error:
      type: object
      required: [error, message]
      properties:
        error: { type: string, enum: [invalid_dial, queue_full, not_finalist, no_active_run, not_found, run_log_unreadable, finalists_unreadable, check_expired, confirmation_required, internal] }
        message: { type: string }
        field: { type: string }
        file: { type: string }
  responses:
    Error:
      description: Error object (Q4); 4xx for bad input, 5xx for the service's own failures
      content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } }
```

Error mapping: invalid dial → 422 `invalid_dial` with `field`; queue full → 409 `queue_full`; test split for a non-finalist → 409 `not_finalist`; stop with nothing running → 409 `no_active_run`; unreadable run log or finalists → 500 with `file`. A check expires after 10 minutes (`check_expired`), so a stale summary is never confirmed. A finalist's test-split confirm without the second confirmation → 409 `confirmation_required`, nothing launched (AC3.6.3); any other failure of the service itself (a stop that does not end the run, an unreadable `metrics.jsonl`, `status.json` or `config.json`) → 500 `internal` with a message and, when a file is the cause, `file` (added 2026-11-07).

## C7 Live Event Stream

```yaml
asyncapi: 3.0.0
info:
  title: gsm8k live events
  version: 1.0.0
servers:
  local:
    host: 127.0.0.1:8000
    protocol: http
    pathname: /api/v1/stream
    description: Server-Sent Events (text/event-stream)
channels:
  stream:
    address: /api/v1/stream
    messages:
      metric:
        description: One complete metrics line of the active run (C2); SSE id = "<run_id>:<line number>"
        payload: { $ref: '#/components/schemas/MetricsLine' }
      status:
        description: Sent whenever the run status changes (IDLE, RUNNING, STOPPED, FAILED), including a new evaluation.scored (2026-11-08)
        payload: { $ref: '#/components/schemas/Status' }
      queue:
        description: Sent whenever the queue changes; the full ordered list
        payload: { type: object, properties: { entries: { type: array } } }
operations:
  receiveEvents:
    action: receive
    channel: { $ref: '#/channels/stream' }
components:
  schemas:
    MetricsLine: { type: object, description: C2 metrics.jsonl line plus run_id }
    Status: { type: object, description: C6 Status }
```

Stream rules:
- Only complete lines are sent.
- A new line is sent within 1 second of being written, inside the 5-second budget (NFR10).
- The server sends `retry: 3000`, so the browser reconnects after 3 seconds.
- On reconnect the browser sends `Last-Event-ID`, and the server resends the lines after it, so nothing is lost.
- A comment line every 15 seconds keeps the connection alive. When the browser's EventSource reports an error (the connection dropped; the browser never shows the keep-alive comments to the page) the page shows "Live updates paused, reconnecting" with the time of the last update, and clears it on reconnect or the next event (AC4.5.3; changed 2026-11-07).

## Contract Ownership Rules

- **u1-eval-skeleton** owns C1, C2, the lock part of C3, and C5. Later units (u3, u6, u7, u9) may add fields and columns in the same version. They may not rename, retype or remove any.
- **u4-run-service** owns the queue part of C3, plus C4, C6 and C7. u5-website consumes C6 and C7 and never reads files (ADR-008).
- **Breaking changes** need three things: a dated `inception/changes.md` line naming the contract, `"v"` raised by one, and a `gsm8k migrate` step. They land in the same `spec(<unit>)` commit as the tests that cover them.
- **Additive changes** are always safe, because readers ignore unknown fields and empty trailing columns.
- C6 and C7 have no compatibility promise beyond v1. The website and the service ship together from the same `main` (Q4).

## Open Questions

| Contract | Question | Blocks |
|---|---|---|
| C1 | Closed 2026-10-31: AC6.1.1 now matches this contract. `data` keeps the dataset (`gsm8k-test`) and the finalist's run id goes in the `adapter_run` column, so the website can filter on `data` (inception/changes.md, 2026-10-31). | none |
| C2 | The exact GRPO settings beyond `grpo_steps` and `grpo_generations` (KL coefficient, temperature) are fixed in the `/build` batch plan that builds u7 (`construction/batch-<n>.md`). They are added as fields in v1; by the C2 hash rule a field at its default leaves earlier hashes unchanged. | u7-grpo |
| C6 | The service port (8000) is a default. The `/build` batch plan that builds u4 and u5 (`construction/batch-<n>.md`) may make it a setting, as long as it stays on 127.0.0.1. | u5-website |
