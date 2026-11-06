# Units Generation: Decomposition Questions

Already settled and not asked again: units are built one at a time, serial and unit-major, each on its own `wip/<unit>` branch (team-practices.md, Way of Working); the first unit is the walking skeleton, the evaluation end to end on 5–20 problems with the 0.6B model (team-practices.md, Walking Skeleton); every later unit is reviewed at its own checkpoint. The building blocks are the twelve in `inception/domain-design/components.md`. Which unit to build first after the skeleton, and why, is decided in Delivery Planning.

## Q1. [Architect] How should the stories be grouped into units of work?

Each unit is one `wip/<unit>` branch, built and checked in a session or two, with its tests named by the stories' criteria.

A. Nine units along the learning path: `u1-eval-skeleton` (US1.1–US1.4: data, prompt, scoring, evaluation, run log, the evaluate command and the lock), `u2-baselines` (US1.5: harness cross-check and the baseline long runs), `u3-sft` (US2.1–US2.5: dials, LoRA fine-tuning, estimates, pruning), `u4-run-service` (US3.1–US3.7: queue, worker, stop, status, finalists, HTTP and stream), `u5-website` (US4.1–US4.6), `u6-final-and-report` (US5.1, US6.1–US6.3: generalisation, final test score, results.md), then the could-haves `u7-grpo` (US7.1), `u8-tuning` (US8.1–US8.2) and `u9-ablations` (US9.1)
B. Five coarser units: skeleton plus baselines; fine-tuning; service plus website; final score and report; all could-haves together
C. Finer: as A, but `u4-run-service` split into `u4-run-queue` (lock, queue, worker, stop, status) and `u5-run-api` (HTTP endpoints and stream), and the website split into one unit per page (eleven or twelve units)
X. Other (please specify)

[Answer]: A. Nine units along the learning path

## Q2. [Architect] Should the skeleton unit wait for the baseline long runs?

A unit is done only when all its criteria pass, and a `[manual]` long-run criterion passes only when Nico's row is in `results/runs.csv`. The four baseline runs plus the harness cross-check may take several hours in total.

A. No: the long baseline runs live in their own unit (`u2-baselines`), so the skeleton closes as soon as its quick tests pass and the baselines can run while the next unit is built
B. Yes: the skeleton unit also holds the baseline long runs and closes only after Nico has run them
X. Other (please specify)

[Answer]: A. The baseline long runs live in their own unit, `u2-baselines`

## Q3. [Architect] How should the code be packaged and run?

This sets the folder layout Code Generation follows. The service and the worker are separate processes (domain-design ADR-003).

A. One Python package `gsm8k` under `src/gsm8k/` with one subpackage per building block and console commands for evaluate, train, tune, prune, report, serve and worker; one `make serve` starts the service and the worker together; the website is a separate Vite app in `web/`
B. One Python package per building block, each with its own `pyproject.toml`; the website in `web/`
X. Other (please specify)

[Answer]: A. One `gsm8k` package under `src/gsm8k/` with a subpackage per building block and console commands; `make serve` starts the service and the worker; the website in `web/`

## Consolidated Summary Confirmation

- Nine units along the learning path, each one `wip/<unit>` branch:
  - `u1-eval-skeleton` (library; US1.1–US1.4): data, fixed split, prompt, scoring, run configuration basics, run log, the evaluate command and the lock. This is the walking skeleton.
  - `u2-baselines` (library; US1.5): the lm-evaluation-harness cross-check and the baseline long runs. Depends on u1.
  - `u3-sft` (library; US2.1–US2.5): the full dial table, LoRA fine-tuning, estimates and pruning. Depends on u1.
  - `u4-run-service` (service; US3.1–US3.7): queue, worker, stop, status, finalists, HTTP API and stream. Depends on u1 and u3.
  - `u5-website` (ui; US4.1–US4.6). Depends on u4.
  - `u6-final-and-report` (library; US5.1, US6.1–US6.3): generalisation sets, the final test score and `results.md`. Depends on u2, u3 and u4.
  - Could-haves: `u7-grpo` (library; US7.1), `u8-tuning` (library; US8.1–US8.2) and `u9-ablations` (library; US9.1), each depending on u3.
- The baseline long runs sit in `u2-baselines`, so the skeleton closes as soon as its quick tests pass.
- One Python package `gsm8k` under `src/gsm8k/`, one subpackage per building block, console commands evaluate, train, tune, prune, report, serve and worker; `make serve` starts the service and the worker; the website is a Vite app in `web/`.
- Units without a dependency between them (u2 and u3 after u1; u7, u8 and u9 after u3) could be built in either order; the order itself is chosen in Delivery Planning, and units are still built one at a time.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
