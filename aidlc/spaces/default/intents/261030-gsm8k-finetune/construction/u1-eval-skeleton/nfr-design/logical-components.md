# Logical Components: u1-eval-skeleton

The modules of the walking skeleton and where the NFR patterns in `security-design.md` apply. The components come from `inception/domain-design/components.md`, the package layout from `inception/units-generation/unit-of-work.md`, and the behaviour from `construction/u1-eval-skeleton/functional-design/functional-spec.md`. The requirements are in `construction/u1-eval-skeleton/nfr-requirements/security-requirements.md`, the stack in `construction/u1-eval-skeleton/nfr-requirements/tech-stack-decisions.md`, and the file contracts in `inception/contract-design/contract-summary.md`.

## Module Inventory

| Module (under `src/gsm8k/`) | Building block | Responsibility | NFR patterns |
|---|---|---|---|
| `_env.py` | (bootstrap) | Sets the caches and the token and telemetry switches before any import | NFR5.1, NFR6.2 |
| `cli.py` | RunCommands | The `gsm8k evaluate` entry point: parses arguments, takes the lock, runs the evaluation, maps errors to exit codes | NFR5.3 (via `paths`), C5 |
| `datasets_prompts/hub.py` | DatasetsAndPrompts | The only Hub access: pinned, safetensors-only, no remote code | NFR6.1, NFR6.3, NFR6.4 |
| `datasets_prompts/split.py` | DatasetsAndPrompts | Seeded split with checks; split file read and write | NFR7.1, NFR8.1 |
| `datasets_prompts/prompt.py` | DatasetsAndPrompts | Exemplars and the fixed 4-shot template | NFR7.1 |
| `scoring.py` | AnswerScoring | Extraction and numeric comparison; pure | — |
| `run_config.py` | RunConfiguration | Defaults, checks, canonical hash | NFR7.1 |
| `run_records/paths.py` | RunRecords | Run-id pattern, adapter confinement, results path | NFR5.2, NFR5.3 |
| `run_records/log.py` | RunRecords | Run-log rows: append one whole line, parse with skip-count | C1 |
| `run_records/folder.py` | RunRecords | `config.json`, `predictions.jsonl`, `timings.json`, `status.json`, all written atomically | C2, BR5.4 |
| `run_records/lock.py` | RunRecords | `flock` on `outputs/run.lock`; content written by the holder | C3, NFR1 |
| `evaluation.py` | Evaluation | Batched greedy generation with the stop rule; memory and time measurement | NFR1.1, NFR2.1 |

## Failure Domains

| Domain | What fails | Blast radius | Containment |
|---|---|---|---|
| GPU process | Out of memory, CUDA error, crash | That run only | Run marked failed (or no status on a hard crash); the kernel releases the lock; no row written |
| Hub download | Network down, revision missing | That run only | Exit code 1 naming the repository; cached files untouched |
| Run-log file | Unreadable or malformed rows | Readers of the log | Malformed rows skipped and counted; an unreadable file names itself (C1) |
| Split file | Missing or corrupt | That run only | Rebuilt from the seed, or the run stops naming the file (BR1.6) |

## Shared Resources

- **The GPU**, guarded by the single OS lock (C3). Only one holder at a time, across every unit's commands.
- **`results/runs.csv`**, appended one whole line at a time. A writer holds the GPU lock while writing, so two of this unit's evaluations can never append at once.
- **`.cache/huggingface`**, shared read-mostly by every run. Downloads are atomic in the Hub library.

## Isolation

Each run writes only inside its own `outputs/<run_id>/` folder, plus one line in the results file. Nothing in this unit runs as a long-lived process, and nothing in it is imported by the run service. The service and worker reach the evaluation only by launching `gsm8k evaluate` as a process (ADR-006).
