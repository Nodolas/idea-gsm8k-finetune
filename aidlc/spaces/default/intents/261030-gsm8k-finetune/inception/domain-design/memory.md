<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->
- 2026-10-31T17:23:14Z — Added an eleventh Python block, RunCommands, and moved the lock and the estimates out of Run control; keeping them there would make the service import training code or create a dependency cycle (ADR-006, ADR-007).
- 2026-10-31T17:23:14Z — Edited the approved requirements, stories and mockups for the run queue in this stage, with a dated inception/changes.md line first; Nico confirmed the edits in the summary.

## Tradeoffs
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->
- 2026-10-31T17:23:14Z — Queued runs keep the configuration checked at queue time rather than rechecking at start; simpler and predictable, but a dial-table change made while runs wait is not re-applied (ADR-003).

## Open questions
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
