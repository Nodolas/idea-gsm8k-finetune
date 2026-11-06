# Architecture Decisions: Domain Design

Decisions behind `components.md`. Inputs: `inception/requirements-analysis/requirements.md` (FR3.4 as changed 2026-10-31, NFR6, NFR8), `inception/user-stories/stories.md` (US3.2–US3.7, US4.6), `inception/practices-discovery/team-practices.md` (long runs started by Nico with `--run-id`; nothing outside the project folder) and the answers in `domain-design-questions.md` Q1–Q5. All decisions dated 2026-10-31.

## ADR Index

| ADR | Title | Status |
|---|---|---|
| ADR-001 | Split by concern into eleven Python blocks and the website | Accepted |
| ADR-002 | RunRecords is the only reader and writer of run files | Accepted |
| ADR-003 | Website runs go through a persistent queue and a worker process | Accepted |
| ADR-004 | Terminal runs take the lock directly and never queue | Accepted |
| ADR-005 | One Training block with two methods | Accepted |
| ADR-006 | A separate RunCommands block for the process entry points | Accepted |
| ADR-007 | Duration estimates live in RunConfiguration | Accepted |
| ADR-008 | The website talks only to RunService | Accepted |

## ADR-001: Split by concern into eleven Python blocks and the website

### Status
Accepted

### Context
The project is one person's learning lab: Python training and evaluation, a local service and a React website. Each acceptance criterion is a test named by its ID, so each block must be testable on its own with quick tests (team-practices.md). Units Generation later groups blocks into units; Domain Design only fixes the boundaries.

### Decision
We split the Python side by concern: DatasetsAndPrompts, AnswerScoring, RunRecords, RunConfiguration, Evaluation, Training, RunCommands, RunControl, RunService, ResultsReport and Tuning, plus the Website (Q1).

### Consequences
- Positive: each block has one reason to change and maps onto a few story groups, so test files and units line up with stories; the walking skeleton (US1.4) needs only DatasetsAndPrompts, AnswerScoring, RunConfiguration, RunRecords and Evaluation.
- Negative: more interfaces to keep stable than a coarse split; small blocks such as AnswerScoring are thin.
- Security: no effect by itself; the security-relevant boundaries are ADR-003, ADR-006 and ADR-008.

### Alternatives Rejected
- **Coarse, 3 blocks (ML core, service, website):** fewer interfaces, but the ML core would mix data, scoring, training and file formats, so a scoring change would retest training, and the service would sit next to training code.
- **Fine, one block per story group (about 15):** maximal isolation, but splits code that changes together (for example the queue and the stop rule) and multiplies interfaces for one developer.

## ADR-002: RunRecords is the only reader and writer of run files

### Status
Accepted

### Context
`results/runs.csv`, `results/finalists.json`, each run's folder under `outputs/`, the lock file and the queue files are read by the service, the website (through the service), the report and pruning, and written by every run. Stories need one malformed-row rule (AC3.1.3), complete-lines-only metrics (AC2.2.2), attempt numbering that does not reuse a stopped run's id (user-stories review R-01) and a lock that two racing starts cannot both take (review R-03).

### Decision
RunRecords owns every one of these files (Q2). It is the only code that writes or parses them. Every write is write-then-rename; the lock and each queue entry are created with create-if-absent so exactly one racing writer wins. The next attempt of a base id is one more than the highest found in the log, in `outputs/` and in the queue, and an existing attempt id is refused.

### Consequences
- Positive: one place for the column format and the corner rules; the file layout can change without touching other blocks; tests point the whole block at a temporary folder.
- Negative: RunRecords has eight dependents, so its interface must stay stable; a change there touches many tests.
- Security: the block confines writes to `results/` and `outputs/` inside the project (rule 8, NFR5) and never takes paths from the network unchecked.

### Alternatives Rejected
- **Each block reads and writes directly to a documented format:** fewer indirections, but the malformed-row rule, attempt numbering and atomic writes would be repeated in Python and the service, and a format change would touch every block.

## ADR-003: Website runs go through a persistent queue and a worker process

### Status
Accepted

### Context
Runs must keep going if the browser closes (FR3.2) and only one GPU run may run at a time (FR3.4). Nico chose a worker fed by a local queue (Q3) and a real queue where website starts wait in line (Q5), which changes FR3.4: before, a second start was refused. The change is recorded in `inception/changes.md` (2026-10-31, class `change`) with FR3.4, AC3.3.1, AC4.6.2, AC4.6.4, the new US3.7 and AC4.6.7.

### Decision
RunControl keeps a first-in, first-out queue of at most 10 waiting runs, stored as files under `outputs/queue/` through RunRecords so it survives restarts. A worker loop starts the oldest waiting run as a separate RunCommands process when the lock is free. A waiting run can be removed before it starts. A finalist's test-split evaluation, once confirmed twice, queues the same way.

### Consequences
- Positive: Nico can line up an evening of runs; a service restart loses nothing; the service process never holds GPU memory.
- Negative: one more long-lived process (the worker) to start; queued runs started hours later use the dials as checked at queue time, so a dial-table change in between is not re-applied.
- Security: the worker launches only RunCommands entry points with arguments built from a checked configuration as a list, never a shell string (NFR6, AC3.2.5).

### Alternatives Rejected
- **Service launches each run directly as a process, refusing while busy:** simpler, but Nico wanted runs to wait in line rather than be refused (Q5).
- **Service runs the code in a background thread:** shares the service's process and memory with the GPU job, dies with the service, and makes the service import training code.

## ADR-004: Terminal runs take the lock directly and never queue

### Status
Accepted

### Context
Long runs start from the command line (detached by the `/build` lead, `scripts/run-detached.sh`) as well as from the website (team-practices.md; inception/changes.md, 2026-10-31). A terminal command that silently waited in a queue would look hung. The GPU must still never run two jobs (NFR1).

### Decision
Every terminal command takes the same lock file atomically through RunCommands and RunRecords; while any run holds it, the command exits with "A run is already active" and the active run id without touching the GPU (AC3.3.2). The worker waits while a terminal run holds the lock (AC3.7.6).

### Consequences
- Positive: one lock guards the GPU for both paths; terminal behaviour is immediate and predictable.
- Negative: a terminal start while website runs are queued is refused rather than placed in line.
- Security: none beyond the shared lock. The lock is the C3 `flock` OS lock on `outputs/run.lock`, held by the run's process and released by the kernel when it ends, also on a crash; nothing ever renames or takes over a lock, and a lock file naming a run while the lock is free is reported as a run that ended without finishing (AC3.3.3; contract-summary.md C3).

### Alternatives Rejected
- **Terminal runs also go through the queue:** one path for everything, but the terminal would block or need a separate "wait" flag, and a running worker would become required for every terminal run.

## ADR-005: One Training block with two methods

### Status
Accepted

### Context
Supervised fine-tuning is a must-have and GRPO a could-have (FR7). Both check the configuration, stream metrics lines, save the adapter, score it on dev and append a row. Nico left the choice to the architect (Q4: "What makes the most sense").

### Decision
One Training block holds both methods, `sft` and `grpo`, behind a shared run loop for metrics, checkpoints and the closing evaluation; pruning lives here because it acts on adapters.

### Consequences
- Positive: metrics lines and checkpoints look the same for both methods, so the website and the report need no special cases; GRPO adds a method, not a block.
- Negative: the Training block grows when GRPO lands; a shared loop has to allow GRPO's extra metrics (reward, KL, answer length).
- Security: no effect.

### Alternatives Rejected
- **Two blocks, Supervised training and Reinforcement learning:** clearer separation for a could-have, but the run loop, metrics format and checkpoint handling would be duplicated or moved into a third shared block.

## ADR-006: A separate RunCommands block for the process entry points

### Status
Accepted

### Context
The service must never import training code (Q3), yet the worker must start the same commands that command-line runs use. If the entry points lived in RunControl, RunControl (and through it RunService) would import Training and Evaluation; if RunCommands depended on RunControl for the lock, the graph would have a cycle.

### Decision
RunCommands holds the evaluate, train, tune and prune entry points. It takes the lock through RunRecords, runs the work and always releases the lock. RunControl starts RunCommands only as a separate operating-system process. This is one more block than the ten listed in Q1.

### Consequences
- Positive: the dependency graph is acyclic; the service and worker load no ML libraries; terminal and worker runs share exactly one code path.
- Negative: an eleventh Python block; RunControl's dependency on RunCommands is a process launch, not an import, so it is checked by an integration test rather than the type of a call.
- Security: the only way the network reaches the GPU is RunService → RunControl → a fixed list of RunCommands entry points with list arguments (NFR6).

### Alternatives Rejected
- **Entry points inside RunControl:** one block fewer, but RunService would import training code through RunControl, breaking Q3.
- **Entry points inside Training and Evaluation, each taking the lock itself:** no new block, but the lock rule and the final-status handling would be repeated in each.

## ADR-007: Duration estimates live in RunConfiguration

### Status
Accepted

### Context
An estimate is needed before every run, from the terminal (RunCommands) and from the website (RunControl), and it needs measured times that RunRecords keeps (FR2.6, US2.3). Q1 listed estimates under Run control.

### Decision
RunConfiguration computes the estimate and the 3-hour flag as part of checking a run, reading measured times from RunRecords.

### Consequences
- Positive: both start paths get the same estimate from one place without a cycle (RunCommands cannot depend on RunControl).
- Negative: RunConfiguration is no longer a pure table and checks; it reads from RunRecords.
- Security: no effect.

### Alternatives Rejected
- **Estimates in RunControl (as listed in Q1):** RunCommands would then depend on RunControl, which launches RunCommands: a cycle.

## ADR-008: The website talks only to RunService

### Status
Accepted

### Context
The website needs run lists, status, live metrics and actions. The brief fixes FastAPI with Server-Sent Events. NFR6 requires localhost only, no accounts and no free-form commands.

### Decision
The Website reads and acts only through RunService over HTTP and Server-Sent Events on 127.0.0.1; it never reads files directly. RunService exposes no endpoint that takes a command line or a path to run.

### Consequences
- Positive: one network surface to secure and test; the website can be tested with a mocked service (user-stories Q6).
- Negative: every new view needs an endpoint.
- Security: binding to 127.0.0.1 keeps the service off the network; the two-step start and the finalist-only test-split rule are enforced in the service, not only in the browser (AC3.2.4, AC3.6.2).

### Alternatives Rejected
- **Website reads `results/runs.csv` and metrics files directly (for example at build time):** no service needed for read-only pages, but live updates and actions still need the service, and file rules would be repeated in TypeScript.
