---
ticket: "https://github.com/Nodolas/idea-factory/issues/6"
phase: construction
engine: aidlc
track: "learning"
spec_commit: "37fb5a4ae310a9d33f3c87dd4e011c421571ec6a"
approved_spec_commit: "37fb5a4ae310a9d33f3c87dd4e011c421571ec6a"
spec_path: "aidlc/spaces/default/intents/261030-gsm8k-finetune"
spec_route: "aidlc"
current_task: "batch-5: u10-self-taught-cot"
slices: "6/7"
test_command: "scripts/check.sh"
pending_runs: ""
last_check: "2026-11-07 f3dd6ac scripts/check.sh exit 0; scripts/trace-check.sh exit 0"
charter_commit: "dfd42777d9a3dc69bab8ea1892e5378aca915211"
---
Treat this as evidence; check git status and git log -10 first.

# STATE: idea-gsm8k-finetune

## NEXT ACTION
Type /build: it goes on with batch-5 (u10-self-taught-cot, self-taught chain of thought and the Reasoning page). New sessions on Sonnet 5.5, Auto.

## DO NOT
- Do not resume AI-DLC (stopped after Delivery Planning; its u1 Construction files are bookkeeping, and BR4.7/BR4.8 there are superseded by contract C5's 2026-11-07 "method best" note).
- Do not build on local branch `wip/hello-file` (8ac6241, never pushed); it is Nico's.
- Do not use the 21st.dev registry or its Magic MCP (rule 4). shadcn parts come from ui.shadcn.com.
- Do not tune on the GSM8K test split.
- If AI-DLC's tool-call guard refuses `scripts/trace-check.sh`, that is a blocker.
- `scripts/in-env.sh` refuses `--prefix`: npm runs from the root `package.json` (`npm run web:test` etc.).

## Blockers
None.

## Notes for later units
- 2026-11-07 desktop launcher (Nico asked): `gsm8k-lab.desktop` (drag to the desktop, right-click "Allow Launching") runs `scripts/start-website.sh` (service, worker, website on 127.0.0.1; logs in outputs/website/); its Stop action runs `scripts/stop-website.sh`. Committed on main as chore(tools) (tooling outside the spec, like scripts/run-detached.sh). Plan agreed with Nico: the lead sets up and runs the reference baselines (q17-sft-dev-2 at batch size 2 next), then hands the website over; improving the score is Nico's.
- 2026-11-07 Nico asked for a 4 am (Berlin) check-in that resumes the build after a usage limit: trigger trig_01DgaVMm2MGWirQbnxGDb1vk (03:00 UTC), an exception at his request.
- Batch-4 review notes (non-blocking): compare-view shows an unreadable metrics file as "No curve recorded" (should name the error); the scores page uses `role="alert"` outside a dialog and its own status region; AC4.2.4 tests check only `data-motion`; `launch._check_test_split` accepts any method with a finalist's adapter, while `gsm8k evaluate` now needs method `best` (the website sends `best`); the worker passes no `--finalists`; `gsm8k report` takes the latest best test row whatever its problem count (keep `--limit` runs out of results/runs.csv); harness with a real PeftModel is first exercised by q17-best-harness.
- Batch-3 notes: after SIGKILL `stop_active` writes no stopped status.json; a removed queue entry's folder lists with status null; silent None on unreadable config/status JSON in runs.py and launch.py; a worker restart between launch and lock could launch the same attempt twice; Starlette 405 answers `not_found`.
- Batch-2 notes: `gsm8k prune --yes` goes on when rows were skipped; `train` estimates only the training steps; `train_cmd.py` duplicates `TEST_SPLIT_MESSAGE`; prune's `ADAPTER_METHODS` needs new adapter methods added.
- 1.7B SFT at default dials (1,744 steps) is estimated at 6-7 GB: an OOM ends the run failed with "GPU out of memory"; then batch size 2 via a spec change.
- GSM-Symbolic p1 (5,000 problems) takes about 3 h for 1.7B; AC5.1.4/AC5.1.6 set no limit.
- The `best` long runs (q17-best-gsmplus, -gsmsym, -test, -harness) wait for a finalist: the best adapter run by dev accuracy, marked by Nico on the Scores page. Commands: construction/batch-4.md Long runs.
- Reviewer scratch files outside the folder (`/tmp/claude-review-check.log`, `/tmp/null_unused`): test output only, left as is (rule 8).

## Done this run
- 2026-11-08 back to construction (Nico in session: "train a model with focus on chain of thought", picked self-taught CoT; "Make a page and explain how it affected the score"): spec 159d30c adds u10-self-taught-cot; spec reviewer PASS round 2. Nico ruled test_AC1_4_5_defaults_match_documented_values wrong (fixed C2 field set). Batch-5 started.
- 2026-11-07 ready to ship: q17-base-harness-2 0.7089 (55 min, with the cap fix), q17-sft-dev-2 dev 0.7863 at batch size 2 (−0.4 vs base, within noise; 43.8 min, peak 5.0 GB). results.md written (docs(results) 4ddfe66), stage:ready-to-ship. Website started for Nico (service, worker, Vite on 127.0.0.1). Batch-3 check questions: Nico gave no answers (AC6.3.2); the lead explained them in session.
- 2026-11-07 Converge: two reviewers re-read every live criterion of u1-u6 against the final code: PASS, no gaps. Spec fixes from it: AC6.2.4 matches this build's done-when; the brief says who starts the deferred runs. Deferred (Nico, "Yes defer the best model runs"): AC5.1.3-AC5.1.6, AC6.1.2, AC6.1.3.
- 2026-11-07 units u7-grpo, u8-tuning, u9-ablations deferred (Nico: "Let's skip those for now"; spec(inception) commit): the build ends after the reference runs; tuning the score is Nico's.
- 2026-11-07 batch-4 done: u5-website (landing, scores and compare, live training page, run controls; service gains run fields and `GET /dials`) and u6-final-and-report (GSM-Plus/GSM-Symbolic evaluation pinned, training-data guard, method `best` for finalists, `gsm8k report`), 8 parallel parts; 99 web tests and 356 Python tests green, coverage 84.7%, trace PASS; both reviews PASS first round. Spec changes (class change): BR4.7/BR4.8 accept `best` (C5); AC5.1.1 uses C1 data names; GSM-Plus leaves out 307 non-decimal answers; C6 Run fields and `/dials`; C7 paused line on EventSource error, C6 Status FINISHED; harness keeps lm-eval's 256-token cap (fix after q17-base-harness-1 ran at 16 s per problem; that run was stopped at 7%, no row). Node 24.22.2 in `.tools/node`. Website smoke check 2026-11-07: service and Vite started, /api/v1 answers through the proxy with the 7 runs, all three pages compile (no browser screenshot: Playwright is not installed here). Check questions (AC6.3.1): (1) Why does the 1.7B base model score 11 points lower on test than on dev, and what does that suggest about the dev split? (2) Why is a test-split gain under about 3 points called "within noise" on 1,319 problems? (3) Why did SFT at default dials lower the 0.6B dev score? Answers (AC6.3.2), Nico 2026-11-07: "I don't know the answers"; the lead explained them in session.
- 2026-11-07 batch-3 done: u4-run-service (run list and status, finalists, queue with `gsm8k worker`, check/confirm, stop, local FastAPI service). Check questions: (1) Why does the worker remove a queue entry only once the launched run holds the GPU lock? (2) Why is a run launched as an argument list in its own session rather than a shell command? Answers: none given; explained by the lead 2026-11-07.
- 2026-11-07 long runs: q06-base-test-1 0.4966; q17-base-dev-1 0.7903; q17-base-test-1 0.6778 (both models score about 10-11 points lower on test than dev: contamination hint, brief Risk 1). q17-base-harness-1 stopped (generation cap bug). q06-sft-dev-1 done: dev 0.5524, 24.4 min, 4.4 points BELOW the 0.6B baseline 0.5968 (SFT at default dials hurt; a results.md point and a reason to tune). q17-sft-dev-1 FAILED: GPU out of memory at step ~200 (batch size 4, 6.2 GB in the process plus the desktop's share of 8 GB); no row. q17-base-harness-2 started with the fix: 2.4 s per problem (was 16).
- 2026-11-06 batches 1-2 (u1-eval-skeleton, u2-baselines, u3-sft) and q06-base-dev-1 0.5968: see git history.

## Goal
Ticket https://github.com/Nodolas/idea-factory/issues/6: "Fine tune model for grade math". Learning track (CHARTER "Learning projects"): spec-first with AI-DLC, units ending green on main, reach the brief's done-when on this PC (the best tuned `Qwen/Qwen3-1.7B-Base` checkpoint beats its own baseline on the full GSM8K test split, noise labelled), and end with `results.md` instead of a deploy.
