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
last_check: "2026-11-17 7cd6cf6 scripts/check.sh exit 0 (907 Python tests, 431 website tests, coverage 88.6%; main folder, gap-1 code); scripts/trace-check.sh exit 0"
charter_commit: "94aa5fdb54b14bf788eadbd66140e1d8692851df"
---
Treat this as evidence; check git status and git log -10 first.

# STATE: idea-gsm8k-finetune

## NEXT ACTION
Type /build after q17-grpo-dev-2 ends (about 2.5 h from 19:22 UTC 2026-11-17; running on this PC, 601 GRPO steps at about 13 s each, then the 496-problem dev score): it commits the row and runs Converge again, then results.md. Meanwhile Nico can run course steps c01, c20, c23 from the Course page (AC12.5.12, AC12.4.5). Sonnet 5.5, Auto.

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
- 2026-11-17 Converge (4.1) on main 8f190b6: check.sh exit 0 (870 Python, 421 website, coverage 88.2%), trace PASS; four reviewers re-read every criterion of the 10 units. Gaps: AC7.1.5 (q17-grpo-dev-1 crashed: TRL's Triton kernel needs Python.h, python3.12-dev not installed), AC7.1.4 (the step plan filled 3 h with training alone), AC12.1.2 (no "over 10 minutes"), AC11.4.6 (no verdict for a one-variant lesson), AC4.2.4 (marker-only test).
- 2026-11-17 gap-1 closed: the Python headers are unpacked from Ubuntu's .deb files into .tools/python-headers/ (scripts/fetch-python-headers.sh, no root) and put on CPATH by every gsm8k process; a GPU GRPO run with no headers stops with exit 2 (new AC7.1.6); the GRPO step plan keeps the closing dev score inside 3 h and prints a GRPO estimate (AC7.1.4 changed); course runs above 10 minutes say so; a one-variant lab lesson names its dev loss; a real AC4.2.4 test. Spec change logged in inception/changes.md. 7cd6cf6 check.sh exit 0 (907 Python, 431 website, coverage 88.6%), trace PASS; reviews PASS round 1. Nico asked for a short trial training run once the build is done.
- 2026-11-17 trial run q17-grpotrial-dev-1 (Qwen3-1.7B-Base, GRPO, 10 steps, 20 dev problems) ended 0 in 3.8 min: 15.8 s per step, peak GPU 5.0 GB, reward/KL/answer length on each step line, 13/20 on dev (too few problems to mean anything); the Triton fix works. Submitted q17-grpo-dev-2 (AC7.1.5): 601 planned steps, estimate 3 h 00 min including the closing dev score; running at about 13 s per step.

## Goal
Ticket https://github.com/Nodolas/idea-factory/issues/6: "Fine tune model for grade math". Learning track: spec-first with AI-DLC, units ending green on main, reach the brief's done-when on this PC (the best tuned `Qwen/Qwen3-1.7B-Base` checkpoint beats its own baseline on the full GSM8K test split, noise labelled), and end with `results.md` instead of a deploy.
