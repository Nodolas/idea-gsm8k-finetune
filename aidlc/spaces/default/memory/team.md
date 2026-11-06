# Team-Level Rules

> This team's affirmed practices and corrections. Loaded after `org.md` as
> strict-additive guidance; contradictions with broader policy are rejected.
> Populated by the practices-discovery affirmation gate. Edit at the gate,
> not directly.

## Way of Working

We work trunk-based on `main`. `/build` builds the units in parallel batches (every unit whose dependencies are built, several builder agents at once, each file with one owner), on one short-lived branch per batch, and `main` moves only by fast-forward (Nico, 2026-10-31). This replaces the `org.md` default of squash-merged Construction worktrees.

- **Branches:** each batch is built on `wip/batch-<n>`; a Converge gap runs on `wip/gap-<n>`. The branch is cut from current `main` and closes when every unit of the batch is green and reviewed.
- **Commit order on a unit branch:** changed spec files first as `spec(<unit>): ...` (with a dated `inception/changes.md` line, class `change`), then `tests/` as `test(<unit>): ...`, then everything else as `feat(<unit>): ...`. The branch's last commit carries AI-DLC's state and `STATE.md`: `chore(state): <unit> done` (a gap closes with `chore(state): gap-<n> closed`).
- **Commit bodies** end with `Refs: Nodolas/idea-factory#6`.
- **Merging:** `main` moves only by fast-forward from `wip/<unit>` once the unit is green (see Done under Testing Posture), and directly only for commits without code (spec, state, charter, inputs, results write-up). No squash and no merge commits, so the spec, test and feat commits stay visible on `main`. We never force-push.
- **Who commits:** the `/build` lead alone commits, merges and pushes. AI-DLC never commits; subagents use read-only git (status, diff, log).
- **AI-DLC execution:** AI-DLC stops after Delivery Planning and is not resumed; Construction is built by `/build` with parallel builder agents in this working tree (Nico, 2026-10-31). No AI-DLC Construction, worktrees or swarm.
- **Spec first:** when reality differs from the spec, the spec changes before the code (a changes.md line plus a `spec(<unit>)` commit). A class `stop` change (needs money, an account or a deploy) is a blocker: no new code until Nico answers.
- **Blocked work:** a blocker on a unit branch commits spec and tests first, then the rest as `chore(<unit>): blocked work in progress`, and pushes the branch.

## Walking Skeleton

We build a small walking skeleton first.

- **The skeleton:** the first unit runs the evaluation end to end on 5–20 GSM8K problems with `Qwen/Qwen3-0.6B-Base`: load the split, build the fixed few-shot prompt, generate greedily, extract the final number, score exact match, and write one result row to a temporary file (never to `results/runs.csv`). This proves the Python environment, the in-folder caches, the model download, GPU use, scoring and the run log connect before training goes in.
- **Proof:** the skeleton passes when the approved Construction Verification Command runs green in the session (quick test, minutes) and Nico approves the skeleton checkpoint. The full baseline evaluation is a `[manual]` long run that Nico starts later; the skeleton does not wait for it.
- **After the skeleton:** later units are built batch after batch without per-unit checkpoints; a reviewer agent checks each unit before its batch merges (Nico, 2026-10-31).

## Testing Posture

Tests come before code, each is named by the acceptance criterion it checks, and none is ever weakened to pass. This replaces the `org.md` test-after default and its CI-before-merge step.

- **Methodology**: atdd
- **Methodology evidence**: Nico affirmed (Q3) that tests come first, each named after the acceptance criterion it checks, and are never weakened to pass; the `test(<unit>)` commit lands before `feat(<unit>)`. That is acceptance-test-driven development; no separate unit-level test-first cadence was chosen.
- **Ordering**: For each unit, write the unit's tests in `tests/` first, one or more per acceptance criterion and named by its ID, run them and see them fail, then write the implementation until they and the full suite pass.
- **Gate before every fast-forward (no cloud CI):** the Construction Verification Command Nico approved (and only that command) and `scripts/trace-check.sh` both run in the session before each fast-forward of `main`. There is no cloud CI.
- **Coverage:** at least 80% line coverage on the Python code under `src/`. The website has no coverage floor.
- **Naming:** Python `test_AC1_2_1_rejects_empty_amount`; a JS/TS test title starts with the ID, `AC1.2.1 ...`; FR IDs (`FR1_2`) when User Stories was skipped. Only the test name counts for traceability (`scripts/trace-check.sh`).
- **Never weakened:** a test is never edited or deleted to pass. On a unit branch no file under `tests/` loses a line (`git diff --numstat main...HEAD -- tests/`); new tests are fine. A test Nico rules wrong needs a dated changes.md line and a `spec(<unit>)` commit before the changed test.
- **Quick tests:** tests stay at minutes. They may download `Qwen/Qwen3-0.6B-Base` and use the GPU on a few problems, and they write any run row to a temp path, never to `results/runs.csv`.
- **Long runs:** a run over about 10 minutes is a `[manual]` criterion, marked on the criterion's own line with `Verify: results/runs.csv row <base id>`. Nico runs it himself with `--run-id <base id>-<n>`; the script writes that id as the row's `run_id` and appends the row to `results/runs.csv`. The lead commits the row.
- **Untestable criteria:** a criterion no automated test can check carries `[manual]` on its own line with how to verify it.
- **Done:** a unit is done when its tests and the full suite (the approved verification command) are green and `scripts/trace-check.sh` passes, both run in the session, recorded in `STATE.md` `last_check` as `<date> <sha7> <command> exit <n>; scripts/trace-check.sh exit <n>`.
- **Tooling:** all tests live under `tests/`; Python tests run with pytest, with line coverage measured by pytest-cov.

## Guard Policy

<!-- Affirmed by the team. Mode: strict, relaxed, or off. Strict here holds for every intent, whatever one person asks in chat; relaxed or off here applies to every intent whose policy came from its scope, unless project.md or the person sets another; changing this line changes it. A section under the retired Change Control heading, written by an earlier release, is still read. -->

## Deployment

We do not deploy. This is a learning project: shipped means `results.md` is written. This replaces the `org.md` default of deploy on merge to staging.

- **No deploys:** no production, no staging, no hosted environment. The results website runs only locally and is never deployed.
- **No cloud test pipeline:** no `.github/workflows/`, no `gh workflow`, `gh release` or `gh secret`. AI-DLC's CI Pipeline stage stays parked and all Operation stages are skipped.
- **Release:** a unit "releases" when `wip/<unit>` is fast-forwarded into `main` after the in-session checks pass, and `main` is pushed. The project ships when `results.md` explains what moved the GSM8K score and why.
- **Long runs:** every run over about 10 minutes is started by Nico, from a terminal or the dashboard button, with a run id. Runs execute on this PC's GPU only; their outputs go to `checkpoints/` or `outputs/` (gitignored) and their result is one row in `results/runs.csv`, committed by the lead.
- **Checkpoints:** we keep only the baseline's and the best run's weights and delete the rest; every run's result row stays in `results/runs.csv`.
- **Rollback:** code rolls back by not fast-forwarding (`main` only moves when green) or by a revert commit on `main`. Models roll back to the kept baseline or best-run weights; every result is compared against the baseline row.
- **Money and accounts:** no rented compute, no paid services, no accounts, no API keys. Work that needs any of them is a blocker for Nico.

## Code Style

We defer to the project's own formatter and linter configs in the repo root. Lint and format checks run locally, not in CI.

- **Python:** Ruff for linting and formatting, configured in `pyproject.toml`; snake_case names. No Python type checker.
- **TypeScript/React (website):** ESLint and Prettier; TypeScript in strict mode, checked by the compiler; camelCase for values, PascalCase for components.
- **Dependencies:** Python packages installed with pip into `.venv/` from a pinned requirements file. Node.js from `.tools/node/` with npm's cache in `.cache/npm`. Nothing is installed or cached above the project folder.
- **Caches:** every script sets `HF_HOME` (`.cache/huggingface`), `PIP_CACHE_DIR` (`.cache/pip`), `XDG_CACHE_HOME` (`.cache`), `TRITON_CACHE_DIR` (`.cache/triton`), `TORCHINDUCTOR_CACHE_DIR` (`.cache/torchinductor`) and `TORCH_HOME` (`.cache/torch`) as absolute paths under the project root before any other import; a shell command takes the same values as a prefix.
- **Language:** English in every file, comment, commit and message. No secrets in code; `.env*` and `.dev.vars*` stay gitignored.
## Forbidden

<!-- Team-specific forbidden patterns -->

## Mandated

<!-- Team-specific mandates -->

## Corrections

<!-- Self-learning loop appends here. -->
