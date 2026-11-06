<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->
- 2026-10-31T16:51:33Z — Added an "Evaluate on dev" choice to the training page's method select so a dev-split evaluation can start from the website, as FR3.6 allows; the stories had no screen for it.
- 2026-10-31T16:51:33Z — For evaluation runs the hourglass fraction is problems scored over problems to score, so the same band works for training and evaluation.

## Deviations
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->
- 2026-10-31T16:51:33Z — Kept the Stop confirmation dialog from user-flow.md even though no story criterion requires it; a stray click on Stop would throw away a long run.

## Tradeoffs
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
