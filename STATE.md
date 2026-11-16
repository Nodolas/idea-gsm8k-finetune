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
pending_runs: ""
last_check: "2026-11-16 56400d6 scripts/check.sh exit 0 (870 Python tests, 421 website tests, coverage 88.2%; run in the main folder at this commit); scripts/trace-check.sh exit 0"
charter_commit: "94aa5fdb54b14bf788eadbd66140e1d8692851df"
---
Treat this as evidence; check git status and git log -10 first.

# STATE: idea-gsm8k-finetune

## NEXT ACTION
All 10 units built. Nico: start the website with the desktop launcher (gsm8k-lab.desktop: service, worker, website), open the Course page and run c01 (AC12.5.12), later c20 and c23 (AC12.4.5); say in session when done. Then type /build for Converge (4.1). Open there: q17-grpo-dev-1 (AC7.1.5) failed at start because Triton could not compile its CUDA helper (`Python.h` missing; the system package python3.12-dev is not installed): a gap, unless Nico installs python3.12-dev. The course's c23 GRPO run will likely hit the same error. Sessions on Sonnet 5.5, Auto.

## DO NOT
- Do not resume AI-DLC (stopped after Delivery Planning; its u1 Construction files are bookkeeping).
- Do not build on local branch `wip/hello-file` (8ac6241, never pushed); it is Nico's.
- Do not use the 21st.dev registry or its Magic MCP (rule 4). shadcn parts come from ui.shadcn.com.
- Do not tune on the GSM8K test split.
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
- 2026-11-16 batch-13 done: u12-learning-course, the Course page. 24 steps in five parts (scoring, model designs, the lab lessons, fine-tuning approaches, the pipeline on Qwen3-0.6B), each with why, a body, a short run, quiz and own-words answer; progress tracker on the Course page and a landing card; `gsm8k course inspect` (real run: weights match the published sizes); /api/v1/course routes and progress.json; course queue entries (`results`, `after`; removing an awaited entry removes its waiting entries; cotgen launches as cot-generate); three course-only models for base runs; 4-bit QLoRA through bitsandbytes 0.50.2. Six parts in parallel on Sonnet; Nico ruled three tests wrong (each a pinned detail, logged in changes.md); spec changes: rotary from `rope_parameters`, weight memory units, attempt numbers without a leading zero, the removal cascade. Reviews: website PASS round 1; Python FAIL round 1 (three wrong course sentences, a queue that could stick), PASS round 3. 2026-11-16 56400d6 scripts/check.sh exit 0 (870 Python, 421 website, coverage 88.2%), trace PASS. Check questions: (1) Why does QLoRA use less GPU memory than LoRA but take longer per step? (2) Why are two course runs on 100 problems "within noise" unless they are about 20 points apart?

## Goal
Ticket https://github.com/Nodolas/idea-factory/issues/6: "Fine tune model for grade math". Learning track: spec-first with AI-DLC, units ending green on main, reach the brief's done-when on this PC (the best tuned `Qwen/Qwen3-1.7B-Base` checkpoint beats its own baseline on the full GSM8K test split, noise labelled), and end with `results.md` instead of a deploy.
