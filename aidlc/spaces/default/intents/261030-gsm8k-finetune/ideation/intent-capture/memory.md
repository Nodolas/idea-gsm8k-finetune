<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->
- 2026-10-30T17:48:44Z — The brief is the source the person named, so the questions offer its content as options; nothing from the brief reaches the artifacts unless an answer confirms it. This keeps the grounding rule and lets a brief-heavy request finish in one round of questions.
- 2026-10-30T17:48:44Z — Q8's "Test or eval-set training" option was not ticked, so the artifacts do not list it as an exclusion. The person's own words ("Only what my pc is capable of... No rented hardware not big models") are recorded as the boundary instead.

## Deviations
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->
- 2026-10-30T17:48:44Z — Two vague or conflicting answers became follow-ups (Q9 measurable threshold for "started to improve", Q10 run log versus "Only results.md") instead of being resolved silently; the person picked "Any measurable gain" and "Log + check questions".

## Open questions
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
