<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->
- 2026-10-31T18:14:37Z [unit u1-eval-skeleton] — A missing adapter path exits with code 2 (invalid configuration) rather than 1, since it is caught before any work starts; AC1.4.6 only requires the stop and the named path.
- 2026-10-31T18:14:37Z [unit u1-eval-skeleton] — The lock, exit-code and run-id rules (BR5.1–BR5.4) have no u1 criterion; they are traced as contract rules in the reverse list and tested through u4's criteria.

## Deviations
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
