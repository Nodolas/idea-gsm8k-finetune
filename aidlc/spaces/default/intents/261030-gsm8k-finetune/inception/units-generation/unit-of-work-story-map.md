# Unit to Story Map

Every story in `inception/user-stories/stories.md` (US1.1–US10.4, including US3.7 added on 2026-10-31 and US10.1–US10.4 added on 2026-11-08) assigned to the unit that implements it. Units are defined in `unit-of-work.md`, built from the blocks in `inception/domain-design/components.md` and `inception/domain-design/decisions.md`. Requirement coverage follows from `inception/requirements-analysis/requirements.md` through the stories' traceability.

## Story Assignment

| Story | Unit ID | Directory |
|---|---|---|
| US1.1 | U1 | u1-eval-skeleton |
| US1.2 | U1 | u1-eval-skeleton |
| US1.3 | U1 | u1-eval-skeleton |
| US1.4 | U1 | u1-eval-skeleton |
| US1.5 | U2 | u2-baselines |
| US2.1 | U3 | u3-sft |
| US2.2 | U3 | u3-sft |
| US2.3 | U3 | u3-sft |
| US2.4 | U3 | u3-sft |
| US2.5 | U3 | u3-sft |
| US3.1 | U4 | u4-run-service |
| US3.2 | U4 | u4-run-service |
| US3.3 | U4 | u4-run-service |
| US3.4 | U4 | u4-run-service |
| US3.5 | U4 | u4-run-service |
| US3.6 | U4 | u4-run-service |
| US3.7 | U4 | u4-run-service |
| US4.1 | U5 | u5-website |
| US4.2 | U5 | u5-website |
| US4.3 | U5 | u5-website |
| US4.4 | U5 | u5-website |
| US4.5 | U5 | u5-website |
| US4.6 | U5 | u5-website |
| US4.7 | U5 | u5-website |
| US5.1 | U6 | u6-final-and-report |
| US6.1 | U6 | u6-final-and-report |
| US6.2 | U6 | u6-final-and-report |
| US6.3 | U6 | u6-final-and-report |
| US7.1 | U7 | u7-grpo |
| US8.1 | U8 | u8-tuning |
| US8.2 | U8 | u8-tuning |
| US9.1 | U9 | u9-ablations |
| US10.1 | U10 | u10-self-taught-cot |
| US10.2 | U10 | u10-self-taught-cot |
| US10.3 | U10 | u10-self-taught-cot |
| US10.4 | U10 | u10-self-taught-cot |

## Cross-Cutting Concerns

Each story sits in exactly one unit. These concerns are delivered in one unit and then reused by the later ones:

| Concern | Delivered in | Reused by |
|---|---|---|
| In-folder cache variables set before any import (NFR5, AC1.1.4) | U1 | every Python unit and command |
| Run log format, attempt ids and the atomic lock (AC1.4.3, AC3.3.2) | U1 (format, the C3 `flock` lock on `outputs/run.lock`); U4 (queue, reporting a run that ended without finishing) | every unit that runs on the GPU |
| Test-split guard (NFR8; AC1.1.3, AC2.1.5, AC3.6.4, AC8.1.4) | U1 (data), U3 (config) | U4, U6, U8 |
| Measured times and peak memory (FR1.7; AC1.4.4, AC2.2.5, AC2.4.1) | U1, U3 | U4 (estimates in the confirm dialog), U7 |
| US6.3 learning check questions | U6 (traced) | asked at the end of every unit |

## Implementation Order Within Each Unit

Within each unit, tests for every criterion come first and must fail, then the code (team-practices.md, Testing Posture). The story order inside a unit:

- **U1:** US1.3 (scoring, pure) → US1.1 (data and split) → US1.2 (prompt) → US1.4 (evaluate command, run log, lock).
- **U2:** AC1.5.5 (harness wrapper, quick test) → the `[manual]` runs AC1.5.1–AC1.5.4 and AC1.5.6.
- **U3:** US2.1 (dials) → US2.2 (training loop) → US2.3 (estimates) → US2.5 (pruning) → US2.4 (the `[manual]` first fine-tunes).
- **U4:** US3.1 (run list, status) → US3.3 (lock, and a run that ended without finishing) → US3.2 (two-step start) → US3.7 (queue and worker) → US3.4 (stop) → US3.5 (failure reasons) → US3.6 (finalists, test split).
- **U5:** US4.1 (top bar, tokens) → US4.2 (landing) → US4.3 (scores) → US4.4 (compare) → US4.5 (live view) → US4.6 (dials and dialogs) → US4.7 (fine-tuning view, added 2026-11-08).
- **U6:** US6.1 quick test (AC6.1.1) → US5.1 quick tests (AC5.1.1, AC5.1.2) → US6.2 generator (AC6.2.1–AC6.2.3) → the `[manual]` runs and AC6.2.4 → US6.3.
- **U7:** AC7.1.1 (rewards) → AC7.1.3, AC7.1.4 → AC7.1.2 → AC7.1.5 (`[manual]`).
- **U8:** US8.2 rule checker → US8.1 study → AC8.1.5 (`[manual]`).
- **U9:** AC9.1.1–AC9.1.3 (transforms) → AC9.1.4–AC9.1.6 (`[manual]`).
- **U10:** AC10.1.2 (keep rule, pure) → AC10.1.1, AC10.1.3, AC10.1.4 (generation) → US10.2 (self-taught training) → US10.3 (comparison and endpoint) → US10.4 (Reasoning page) → AC10.1.5, AC10.2.5 (`[manual]`) → AC10.4.5.

## Coverage Check

- All 36 stories are assigned: U1 has 4, U2 1, U3 5, U4 7, U5 7, U6 4, U7 1, U8 2, U9 1, U10 4 (US10.1–US10.4 added 2026-11-08).
- Every unit has at least one story.
- No story is split across units.
