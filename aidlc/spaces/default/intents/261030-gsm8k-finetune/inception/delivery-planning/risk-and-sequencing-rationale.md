# Risk and Sequencing Rationale

Why the Bolts in `bolt-plan.md` come in this order. A **Bolt** is one build pass over one unit of work, ending in something that runs. The order has to respect the unit graph in `inception/units-generation/unit-of-work-dependency.md`; the units are in `inception/units-generation/unit-of-work.md` and the requirements in `inception/requirements-analysis/requirements.md`.

## Heuristic

**Walking skeleton first, then learning-path order, with the GPU risk retired first inside each Bolt.**

- **Walking skeleton first** (Cockburn, *Crystal Clear*): the first Bolt is the smallest end-to-end slice, so the environment, caches, download, GPU, scoring and run log are proven before anything is built on them (`inception/practices-discovery/team-practices.md`, Walking Skeleton).
- **Learning-path order (value-first):** this is a learning project, so value is what Nico learns next. Scope Definition chose "Learning order", with the could-haves only after everything else works.
- **Risk-first inside each Bolt** (Boehm): Nico's biggest worry is a default run that does not fit 8 GB or 3 hours (Q2). B1 measures memory and seconds per problem. B3 measures memory and seconds per step on a short default fine-tune before any long run is listed.
- **No formal scoring model.** A weighted scoring model such as WSJF (value plus urgency plus risk reduction, divided by size) adds nothing when the order is already fixed by learning order and the dependencies.

## Order Against the Dependency Graph

| Bolt | Unit | Depends on | All dependencies earlier? |
|---|---|---|---|
| B1 | u1-eval-skeleton | — | yes |
| B2 | u2-baselines | u1 | yes |
| B3 | u3-sft | u1 | yes |
| B4 | u4-run-service | u1, u3 | yes |
| B5 | u5-website | u4 | yes |
| B6 | u6-final-and-report | u2, u3, u4 | yes |
| B7 | u7-grpo | u3 | yes |
| B8 | u8-tuning | u3 | yes |
| B9 | u9-ablations | u3 | yes |

The sequence is a valid topological order; nothing deviates from the graph. Two choices were open where the graph allows either order:

- **B2 before B3:** baselines come first in the learning path, and their long runs can fill the GPU while B3's code is written.
- **B4 and B5 before B6:** the final test score needs a finalist, and finalists are marked through the service (FR3.6).

## Risk Register

| Risk | Likelihood | Impact | Mitigation | Retired in |
|---|---|---|---|---|
| A default run does not fit 8 GB of GPU memory (NFR1) | Medium | High | Peak memory recorded on the first evaluation and on a short default fine-tune; the dial table changes through `inception/changes.md` before any long run | B1, B3 |
| A default run takes over 3 hours (NFR2) | Medium | High | Seconds per problem and per step measured first; estimates with a 3-hour flag before every run | B1, B3 |
| Fine-tuning gives no gain over the baseline (FR6.2) | Medium | Medium | Dev scores after B3's first fine-tunes show the direction early; could-haves (GRPO, tuning, ablations) remain as further levers | B3, B6 |
| Long runs pile up and block the end | Medium | Medium | Long runs never hold a Bolt open (Q1); each is listed with its exact command as soon as its Bolt closes | every Bolt |
| The queue, lock and worker let two jobs onto the GPU | Low | High | Atomic lock (C3), exit codes (C5), stub-process tests for races and restarts; contract review findings settled in B4's Functional Design | B4 |
| Contract gaps from the contract review (stale-lock takeover, harness command, run-list joins) | High | Medium | Fixed in the Functional Design of the Bolt that owns each contract (B1 for C3 and C5, B2 for the harness, B4 for C6) before its tests are written | B1, B2, B4 |
| Nico's screenshots are missing when the website is built | Low | Medium | `inputs/design/` already holds one screenshot; the rest are needed before B5's Code Generation | B5 |
| A dataset or model download fails or changes upstream | Low | Medium | Downloads cached in `.cache/`; the split is saved as problem ids | B1 |

## Pending Long Runs

Under Q1 a Bolt closes on its quick checks, and its long runs stay pending in `STATE.md`. Only B6 needs other Bolts' long-run results: the baseline rows from B2 and a fine-tuned finalist from B3. The GPU is free while the AI developer writes the next Bolt's code, so these runs can overlap with B3–B5.
