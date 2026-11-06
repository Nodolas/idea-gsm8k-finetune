<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->
- 2026-10-31T18:05:00Z — config.json carries the evaluation options (limit, vote_samples, calculator) and the GRPO settings, and config_hash covers every field but run_id and v; this settles the domain-design review's R-01 (ablation runs would otherwise share the baseline's hash).
- 2026-10-31T18:05:00Z — Any lock taker clears a stale lock whose process is gone, not only the service's status check; this settles the domain-design review's R-03.

## Deviations
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
- 2026-10-31T18:05:00Z — AC6.1.1 puts the finalist's run id in the run log's data column; the contract proposes a separate adapter_run column instead, which needs a changes.md line before u6's tests.
