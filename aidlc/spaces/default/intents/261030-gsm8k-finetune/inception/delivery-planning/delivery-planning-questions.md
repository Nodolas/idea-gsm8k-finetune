# Delivery Planning: Questions

A Bolt is one build pass over a piece of the work that ends in something that runs. Here each Bolt is one unit of work on its own `wip/<unit>` branch.

Already settled, so not asked again:
- **The walking skeleton comes first:** `u1-eval-skeleton`, the evaluation end to end on a few problems (team-practices.md, Walking Skeleton).
- **Bolts are built one at a time, one unit per Bolt** (team-practices.md, Way of Working: serial, unit-major, one `wip/<unit>` branch per unit).
- **After the skeleton, the order follows the learning path:** baselines, fine-tuning, run service, website, then the final score and report, with the could-haves last (scope-definition: "Learning order"; scope-document: could-haves only after everything else works). No scoring model is needed on top of that.
- **Every Bolt is built by the AI developer** (Claude Code under `/build`). Nico runs the long jobs and approves each checkpoint. There is no team-formation stage in this scope.

The questions below are the ones your earlier answers leave open.

## Q1. [Delivery] Should a unit with long manual runs hold up the next unit?

A unit is done when its tests, the full suite and the trace check pass. A long run (over about 10 minutes) is a `[manual]` criterion that passes only when your row is in `results/runs.csv`. The trace check counts `[manual]` criteria separately. `u3-sft` holds two fine-tunes of up to 3 hours each, and `u4-run-service` depends on `u3-sft` (units-generation review R-01).

A. No. A unit closes and merges once its quick tests and the trace check pass. Its long runs go into `STATE.md` `pending_runs` with the exact commands, so you can run them whenever the GPU is free while the next unit is built. A pending run blocks only the unit that needs its result: `u6-final-and-report` needs the baselines and a fine-tuned finalist.
B. Yes. A unit with long runs stays open until your rows are committed, and the next unit waits.
X. Other (please specify)

[Answer]: A. A unit closes on its quick tests and the trace check; its long runs are pending in `STATE.md` and block only the unit that needs their result

## Q2. [Delivery] What worries you most about this build?

The answer sets which risks get checked earliest in each Bolt's definition of done.

A. The GPU limits: a default run that does not fit in 8 GB or 3 hours. Check memory and time on the very first runs in the skeleton and the first fine-tune.
B. The run service and its queue: the most moving parts (lock, worker, stream). Give it extra failure tests.
C. Getting no gain over the baseline. Plan an early small fine-tune on the 0.6B model to see the score move before building the website.
X. Other (please specify)

[Answer]: A. The GPU limits: check memory and time on the very first runs

## Consolidated Summary Confirmation

- Bolts are built one at a time, one unit per Bolt, in learning-path order after the walking skeleton: `u1-eval-skeleton`, `u2-baselines`, `u3-sft`, `u4-run-service`, `u5-website`, `u6-final-and-report`, then the could-haves `u7-grpo`, `u8-tuning` and `u9-ablations` if there is time. This order respects every dependency in the unit graph.
- The skeleton Bolt's demo: `gsm8k evaluate` runs `Qwen/Qwen3-0.6B-Base` on 10 dev problems, prints accuracy, problems scored and minutes, and writes one row to a temporary run log. The real check is the approved verification command, run in the session.
- A unit closes and merges once its quick tests, the full suite and the trace check pass. Its long runs go into `STATE.md` `pending_runs` with exact commands for you to run when the GPU is free. A pending run blocks only the unit that needs its result: `u6-final-and-report` needs the baselines and a fine-tuned finalist.
- The GPU limits are the first risk to retire. The skeleton records peak GPU memory and seconds per problem. `u3-sft`'s done check includes a short default fine-tune on the 0.6B model that records peak memory and seconds per step, so the 8 GB and 3-hour limits are measured before any long run.
- Every Bolt is built by the AI developer (Claude Code under `/build`). You run the long jobs and approve each unit's checkpoint. The only things from outside are public model and dataset downloads, your long runs, and your screenshots in `inputs/design/` before the website Bolt.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
