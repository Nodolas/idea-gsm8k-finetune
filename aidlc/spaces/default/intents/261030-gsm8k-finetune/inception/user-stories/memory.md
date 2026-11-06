<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->
- 2026-10-31T16:22:38Z — Final-model long-run ids use the q17 model token with method `best`; the brief names Qwen3-1.7B-Base as the main model, and a stories.md assumption switches them to q06 if the best checkpoint is 0.6B.
- 2026-10-31T16:22:38Z — Each acceptance criterion is written on one line with its ID, and `[manual]` plus the Verify text on that same line; scripts/trace-check.sh reads `[manual]` per line, so a wrapped criterion would count as untested.

## Deviations
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->
- 2026-10-31T16:22:38Z — Wrote 30 stories, against the plan's estimate of about 20–25; full could-have stories (Q2) and separate stories for stop, failure display and finalists kept each story to 2–6 criteria instead of merging unrelated outcomes.

## Tradeoffs
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
