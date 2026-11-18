---
ticket: "https://github.com/Nodolas/idea-factory/issues/6"
phase: construction
engine: aidlc
track: "learning"
spec_commit: "37fb5a4ae310a9d33f3c87dd4e011c421571ec6a"
approved_spec_commit: "37fb5a4ae310a9d33f3c87dd4e011c421571ec6a"
spec_path: "aidlc/spaces/default/intents/261030-gsm8k-finetune"
spec_route: "aidlc"
current_task: none
slices: "10/10"
test_command: "scripts/check.sh"
pending_runs: "q17-grpo-dev-3"
last_check: "2026-11-18 281fa27 scripts/check.sh exit 0 (907 Python tests, 436 website tests, coverage 88.6%; main folder, gap-2 code uncommitted on top, committed unchanged as 77ed7d0); scripts/trace-check.sh exit 0"
charter_commit: "94aa5fdb54b14bf788eadbd66140e1d8692851df"
---
Treat this as evidence; check git status and git log -10 first.

# STATE: idea-gsm8k-finetune

## NEXT ACTION
Type /build after q17-grpo-dev-3 ends (about 12:15 UTC 2026-11-18; running on this PC, step 122/601 at 09:36 UTC, about 14 s per step, then the 496-problem dev score). Keep the PC on until then. It commits the row, checks AC7.1.5 (within 3 h) and goes on to results.md (4.2). Sonnet 5.5, Auto.

## DO NOT
- Do not resume AI-DLC (stopped after Delivery Planning; its u1 Construction files are bookkeeping).
- Do not build on local branch `wip/hello-file` (8ac6241, never pushed); it is Nico's.
- Do not use the 21st.dev registry or its Magic MCP (rule 4). shadcn parts come from ui.shadcn.com.
- Do not tune on the GSM8K test split.
- `outputs/q17-grpotrial-dev-1` and `checkpoints/q17-grpotrial-dev-1` are Nico's trial run (10 GRPO steps, row only in `outputs/trial/runs.csv`); its timings sized q17-grpo-dev-2's step plan. Not a project result; prune may delete its adapter.
- `scripts/in-env.sh` refuses `--prefix`: npm runs from the root `package.json`.
- Website batches build in a worktree (`.cache/worktrees/`); three tests in tests/test_u1_env.py fail there by design, so the gate runs in the main folder at the branch's commit.

## Blockers
None.

## Notes for later
- Batch-13 review notes (non-blocking): a step shown by default (no `?step=`) is not sent `POST /open`, so it stays "Not started" until chosen; the c04 table shortens the revision to 7 characters; the page does not poll for an inspection started elsewhere (a second click answers course_busy); the service's `memory_note` and `comparison_note` are not shown (the same text is in the step bodies); the inspection launch and queue.log writes catch few OS errors; the QLoRA load (`prepare_model_for_kbit_training` casts the tied embedding to fp32) may leave QLoRA's peak only a few hundred MB below LoRA's on 0.6B; c04's wording on Pythia's norms is loose.
- Batch-12: `train_cmd._print_estimate` prints a GRPO run's estimate from SFT step times (too optimistic).
- Batch-10: a dev run ends at 496 / 500 in the band (the 4 exemplars are left out); changing `total` needs Nico to rule `test_AC3_1_6_progress_total_is_each_split_size` wrong.
- Batch-8: no test pins `GPU_CHECK_TIMEOUT_SECONDS` at 30; a timed-out check leaves nvidia-smi running.
- Batch-4: `gsm8k report` takes the latest best test row whatever its problem count; the `best` long runs (q17-best-gsmplus, -gsmsym, -test, -harness) wait for a finalist marked by Nico (construction/batch-4.md).
- Deferred by Nico: AC5.1.3-AC5.1.6, AC6.1.2, AC6.1.3 (best-model runs); u8-tuning, u9-ablations.

## Done this run
- 2026-11-18 q17-grpo-dev-2 was cut off at step 107/601 by a PC shutdown (20:38 CET 2026-11-17; log clean, no row): submitted again as q17-grpo-dev-3 (same command), running since 09:07 UTC.
- 2026-11-18 Converge (4.1) on main 35577a9: check.sh exit 0 (907 Python, 431 website, coverage 88.6%), trace PASS; four reviewers re-read every criterion of the 10 units: all PASS except AC11.4.6 (l12 had no lowest-dev-loss sentence; l11 did not say smaller differences in the other lessons are noise). AC7.1.5 pending (q17-grpo-dev-3).
- 2026-11-18 gap-2 closed: lab-verdicts.ts fixed (u11), 5 new tests; check.sh exit 0 (907 Python, 436 website), trace PASS, review PASS round 1. Converge has no other gap; only the run is left before results.md.
- Flaky: `AC11.4.2 shows the lesson named by ?lesson=` (tests/web/lab.test.tsx:570) failed once under heavy CPU load (GPU run plus four reviewers) and passed 3/3 alone: it checks `getLabLesson` right after the heading, which renders from the list first. Not a code gap.

## Goal
Ticket https://github.com/Nodolas/idea-factory/issues/6: "Fine tune model for grade math". Learning track: spec-first with AI-DLC, units ending green on main, reach the brief's done-when on this PC (the best tuned `Qwen/Qwen3-1.7B-Base` checkpoint beats its own baseline on the full GSM8K test split, noise labelled), and end with `results.md` instead of a deploy.
