# Practices Discovery — Questions

Context: a new project. The suggested answers come from the draft in `team-practices.md`, which follows this project's existing rules (`CLAUDE.md`, `CHARTER.md`) where they differ from the framework defaults. Your answers become the project's working practices.

## Q1. [Developer] How should work move through git?

A. One branch per unit of work (`wip/<unit>`), commits in the order spec, then tests, then code, then state; `main` moves only by fast-forward once the unit's checks are green (the project's current rule)
B. Short-lived branches squash-merged into `main` (the framework default)
C. Not yet defined
X. Other (please specify)

[Answer]: A. One wip/<unit> branch per unit; fast-forward only

## Q2. [Developer] Build a thin end-to-end slice first? A walking skeleton is a minimal version that runs the whole way through, built first to prove the pieces connect before the real features go in.

A. Yes, small: the first unit runs the evaluation end to end on 5–20 problems with the 0.6B model and writes its result row to a temporary file
B. Yes, wider: as A, plus one tiny fine-tuning step whose metrics line the website can read
C. No: build the units in order without a skeleton step
D. Not yet defined
X. Other (please specify)

[Answer]: A. Yes, small: evaluation end to end on 5–20 problems with the 0.6B model

## Q3. [Quality] How should tests work?

A. Tests come first, each named after the acceptance criterion it checks, and are never weakened to pass; before each merge the approved test command and the trace check run in the session; Python code under `src/` keeps at least 80% line coverage
B. As A, with no coverage floor
C. As A, with a 60% coverage floor
D. Not yet defined
X. Other (please specify)

[Answer]: A. Tests first, named by criterion, never weakened; test command and trace check before each merge; 80% line coverage on Python src/

## Q4. [Quality] May quick tests use the GPU and download a model?

Quick tests stay at minutes; this decides how real they are.

A. Yes: quick tests may download the 0.6B model and use the GPU on a few problems
B. No: quick tests run on the CPU with a tiny model; the GPU is used only in your long runs
C. Not yet defined
X. Other (please specify)

[Answer]: A. Yes: quick tests may download the 0.6B model and use the GPU

## Q5. [Release] How is the work shipped?

A. No deploy and no cloud test pipeline: the website runs locally only, "shipped" means `results.md` is written, and every run over about 10 minutes is started by you (terminal or dashboard button) with its run id
B. Not yet defined
X. Other (please specify)

[Answer]: A. No deploy and no cloud test pipeline; ship = results.md

## Q6. [Developer] Which code style and tools?

A. Python: Ruff for lint and format, no type checker; website: ESLint and Prettier with strict TypeScript checked by the compiler; Python packages pinned in a requirements file inside the project's own environment
B. As A, but use `uv` instead of pip for Python packages
C. As A, plus a Python type checker (mypy)
D. Not yet defined
X. Other (please specify)

[Answer]: A. Ruff, ESLint and Prettier, strict TypeScript, pip with pinned requirements

## Q7. [Developer] What happens to each run's saved model weights?

A. Keep every run's adapter in its own folder under `checkpoints/` (LoRA adapters are small)
B. Keep only the baseline and the best run; delete the rest
C. Not yet defined
X. Other (please specify)

[Answer]: B. Keep only the baseline and the best run

## Q8. [Product] Which hard rules should be recorded?

The draft lists 12 "always" and 8 "never" rules taken from your project rules (`discovered-rules.md`). Two more came up: never train or tune on the GSM8K test split, and never force-push.

A. Affirm all drafted rules plus both extra rules
B. Affirm the drafted rules only
C. Go through them one by one
D. Not yet defined
X. Other (please specify)

[Answer]: A. Affirm all drafted rules plus both extra rules

## Consolidated Summary Confirmation

- Git: one `wip/<unit>` branch per unit; commits spec, tests, code, state; `main` moves only by fast-forward when green (Q1).
- Walking skeleton: yes, small: the first unit runs the evaluation end to end on 5–20 problems with the 0.6B model and writes its row to a temporary file (Q2).
- Tests: tests first, named by acceptance criterion, never weakened; the approved test command and the trace check run before each merge; at least 80% line coverage on Python code under `src/` (Q3).
- Quick tests: may download the 0.6B model and use the GPU on a few problems, minutes only (Q4).
- Shipping: no deploy and no cloud test pipeline; website local only; shipped means `results.md`; runs over about 10 minutes are started by you with a run id (Q5).
- Code style: Ruff for Python lint and format, no Python type checker; ESLint, Prettier and strict TypeScript for the website; pip with pinned requirements in the project's own environment (Q6).
- Checkpoints: keep only the baseline and the best run's weights; delete the rest (Q7).
- Hard rules: affirm all drafted rules, plus never train or tune on the GSM8K test split, and never force-push (Q8).

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
