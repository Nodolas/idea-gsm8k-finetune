# Contract Summary

The formal contracts between the units in `inception/units-generation/unit-of-work.md`, following the edges and integration points in `inception/units-generation/unit-of-work-dependency.md`. Entity shapes come from `inception/domain-design/components.md`; limits and rules from `inception/requirements-analysis/requirements.md` (FR1.6, FR2.3, FR3.1–FR3.7 with FR3.4 as changed on 2026-10-31, NFR6, NFR10). Answers: `contract-design-questions.md` Q1–Q4.

Nothing is exposed outside this PC: the service binds to 127.0.0.1 and there is no external API (NFR6). Hugging Face downloads are consumed, not provided, and need no contract here.

## Contracts

| # | Provider Unit | Consumer | Mechanism | Owner |
|---|---|---|---|---|
| C1 | u1-eval-skeleton (RunRecords) | u2, u3, u4, u6, u7, u8, u9 | Shared file: `results/runs.csv` | u1-eval-skeleton |
| C2 | u1-eval-skeleton (RunRecords), extended by u3-sft | u3, u4, u6, u7, u8, u9 | Shared files: `outputs/<run_id>/` (`config.json`, `metrics.jsonl`, `status.json`, `predictions.jsonl`, `timings.json`, `run.log`) | u1-eval-skeleton |
| C3 | u1-eval-skeleton (lock), extended by u4-run-service (queue) | u2, u3, u4, u6, u8 | Shared files: `outputs/run.lock`, `outputs/queue/*.json` | u1 (lock), u4 (queue) |
| C4 | u4-run-service | u3 (prune), u6 | Shared file: `results/finalists.json` | u4-run-service |
| C5 | u1-eval-skeleton (`evaluate`), u3-sft (`train`) | u4-run-service (worker) | Process launch: `gsm8k` commands, arguments and exit codes | u1-eval-skeleton |
| C6 | u4-run-service | u5-website | HTTP JSON on 127.0.0.1, `/api/v1` | u4-run-service |
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
    enum: [base, sft, grpo, best, terse, vote, calc, optuna]
  - name: data
    type: string
    enum: [gsm8k-dev, gsm8k-test, gsm8k-test-harness, gsmplus-testmini, gsmsym-p1]
  - name: metric
    type: string
    enum: [accuracy, harness_flexible_accuracy]
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
    split: string                   # dev | test | gsmplus-testmini | gsmsym-p1; test only for method best (NFR8)
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
    grpo_steps: integer|null        # GRPO only (US7.1)
    grpo_generations: integer|null  # GRPO samples per problem (US7.1)
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
  run.log:                          # plain text log; the last 20 lines are shown on failure (FR3.7)
rules:
  - config_hash = sha256 of the canonical JSON of {model, method} plus every other field whose value differs from its documented
    default, keys sorted, without run_id and v; every option that changes results changes the hash, and a field added later in v1
    with a default leaves earlier hashes unchanged (changed 2026-10-31)
  - a missing metrics.jsonl reads as no lines, never an error (AC4.4.3)
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
        status: { type: string, enum: [IDLE, RUNNING, STOPPED, FAILED] }
        run_id: { type: [string, 'null'] }
        reason: { type: [string, 'null'] }
        log_tail: { type: array, items: { type: string } }
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
    Error:
      type: object
      required: [error, message]
      properties:
        error: { type: string, enum: [invalid_dial, queue_full, not_finalist, no_active_run, not_found, run_log_unreadable, finalists_unreadable, check_expired] }
        message: { type: string }
        field: { type: string }
        file: { type: string }
  responses:
    Error:
      description: Error object (Q4); 4xx for bad input, 5xx for the service's own failures
      content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } }
```

Error mapping: invalid dial → 422 `invalid_dial` with `field`; queue full → 409 `queue_full`; test split for a non-finalist → 409 `not_finalist`; stop with nothing running → 409 `no_active_run`; unreadable run log or finalists → 500 with `file`. A check expires after 10 minutes (`check_expired`), so a stale summary is never confirmed.

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
        description: Sent whenever the run status changes (IDLE, RUNNING, STOPPED, FAILED)
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
- A comment line every 15 seconds keeps the connection alive. If the page sees nothing for 20 seconds it shows "Live updates paused, reconnecting" (AC4.5.3).

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
