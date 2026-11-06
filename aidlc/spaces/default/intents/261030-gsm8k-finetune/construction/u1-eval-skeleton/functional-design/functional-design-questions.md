# Functional Design: u1-eval-skeleton

The unit covers US1.1–US1.4 (`inception/user-stories/stories.md`): data and the fixed split, the 4-shot prompt, answer scoring, and the `gsm8k evaluate` command with its run log, run folder and lock. It owns contracts C1, C2, the lock part of C3, and C5 (`inception/contract-design/contract-summary.md`). These three choices change behaviour and the stories leave them open.

## Q1. [Architect] How should the GPU lock work?

The contract review found a race in the lock design (contract-design R-01). The design lets any taker rename a lock whose process looks dead. Two takers could then race, one could rename a lock the other has just made, and two runs would share the GPU.

A. An operating-system file lock (`flock`) on `outputs/run.lock`, held by the run's process for its whole life. The kernel releases it the moment the process ends, even on a crash, so a stale lock cannot exist and nobody ever renames one. The file still holds `run_id`, `pid`, `started_at` and `started_by` for display. Linux only, which is this PC
B. Keep the exclusive-create lock file and add a guarded takeover. A taker creates `run.lock.takeover` exclusively, re-reads the lock, and only renames it if `run_id`, `pid` and `started_at` are unchanged and the pid is dead. The status check only reports a stale lock and never takes it over
X. Other (please specify)

[Answer]: A. An operating-system file lock (`flock`) on `outputs/run.lock`, held for the run's life

## Q2. [Architect] What should happen to GSM8K's calculator annotations in the prompt examples?

GSM8K's worked answers carry inline calculator notes such as `<<48/2=24>>`. The four prompt examples, and later the training targets in u3, either keep them or drop them. The calculator ablation in u9 can use them.

A. Strip them: examples read as plain worked steps ending in `#### <number>`. u9 brings them back on purpose for its calculator ablation
B. Keep them exactly as in the dataset
X. Other (please specify)

[Answer]: A. Strip them

## Q3. [Architect] When should generation stop for each problem?

A base model keeps writing after its answer and often starts a new "Question:" of its own. Where generation stops changes speed, and which number the "last number" fallback picks.

A. Stop at the end of the first `#### <number>` line, or when the model starts a new `Question:`, whichever comes first, capped at 512 new tokens. Only the text before the stop is scored
B. Always generate up to 512 new tokens and score the whole output
X. Other (please specify)

[Answer]: A. Stop at the first `#### <number>` line or a new `Question:`, capped at 512 new tokens

## Consolidated Summary Confirmation

Your three answers:
- The GPU lock is an operating-system file lock (`flock`) on `outputs/run.lock`, held by the run's process for its whole life and freed by the kernel when it ends, so no stale lock is ever renamed. The file shows `run_id`, `pid`, `started_at` and `started_by`.
- GSM8K's `<<…>>` calculator notes are stripped from prompt examples and training targets.
- Generation stops at the end of the first `#### <number>` line or when a new `Question:` starts, capped at 512 new tokens, and only the text before the stop is scored.

Smaller details I settle unless you say otherwise:
- Problem ids are `gsm8k-train-<index>` and `gsm8k-test-<index>`, by the dataset's own row order.
- The split sorts the ids, then a seeded shuffle picks the 500 dev ids. The four exemplars are a seeded sample from the sorted dev ids.
- Prompt format: `Question: …` then `Answer: …` per example, a blank line between examples, then the target question and `Answer:`.
- The model runs in bfloat16, with evaluation batches of 8 problems.
- A run without `--run-id` is named `adhoc-<UTC timestamp>`, and its row goes to a temporary file.
- Numbers are compared as decimals after removing commas, `$` and `%`.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
