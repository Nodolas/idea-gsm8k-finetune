---
ticket: "https://github.com/Nodolas/idea-factory/issues/6"
phase: construction
engine: aidlc
track: "learning"
spec_commit: "37fb5a4ae310a9d33f3c87dd4e011c421571ec6a"
approved_spec_commit: "37fb5a4ae310a9d33f3c87dd4e011c421571ec6a"
spec_path: "aidlc/spaces/default/intents/261030-gsm8k-finetune"
spec_route: "aidlc"
current_task: "batch-4: u5-website, u6-final-and-report"
slices: "4/9"
test_command: "scripts/check.sh"
pending_runs: "q17-base-test-1:running:172473,q17-base-harness-1:queued,q06-sft-dev-1:queued,q17-sft-dev-1:queued"
last_check: "2026-11-07 778bfb1 scripts/check.sh exit 0; scripts/trace-check.sh exit 0"
charter_commit: "dfd42777d9a3dc69bab8ea1892e5378aca915211"
---
Treat this as evidence; check git status and git log -10 first.

# STATE: idea-gsm8k-finetune

## NEXT ACTION
Type /build: it goes on with batch-4. Long run q17-base-test-1 is running (1.7B baseline, test split, about 45 min); three more queued.

## DO NOT
- Do not resume AI-DLC. It stopped after Delivery Planning; its u1 Construction files (functional-design, nfr-requirements, nfr-design under the intent's `construction/`) are bookkeeping, committed in the spec commit. Nico's answers there are decided and feed the builders.
- Do not build on local branch `wip/hello-file` (commit 8ac6241, never pushed); it is Nico's to keep or delete (conflict logged 2026-10-30).
- Do not install from the 21st.dev registry or use its Magic MCP (account and API key, rule 4). The UI is built on shadcn/ui from `inputs/design/` and the pasted component in `inputs/`.
- Do not tune on the GSM8K test split: all tuning and agent decisions use train-dev.
- If AI-DLC's tool-call guard refuses `scripts/trace-check.sh` again, that is a blocker; do not work around it.
- 2026-11-06 route note: the spec review (2.3 step 3) failed once on text fixes. On the AI-DLC route the skill sends fixes back through AI-DLC, but AI-DLC is not resumed after Delivery Planning (Nico, 2026-10-31) and CLAUDE.md lets the lead change the spec, so the lead made them as class `change` lines in `inception/changes.md` (2026-11-06), in line with Nico's recorded answers. The second review passed.

## Blockers
None.

## Notes for later units
- From the batch-3 review (non-blocking for u4, needs a spec change before u6): a finalist's test-split evaluation cannot run through the service: `launch.check_run` writes method `best` with `adapter_path` (C2), but `cli.py` BR4.8 (lines 215-220) refuses a config whose method differs from its adapter run's (`sft`), exit 2; and method `sft` on split `test` is refused by `run_config.validate`. u4's tests use a stub that ignores method. Fix as a class `change` (BR4.7/BR4.8 accept `best` when the adapter run has a training method, matching AC6.1.1's `best` row) when u6 starts. Other notes: after SIGKILL `stop_active` writes no stopped status.json (reads FAILED); a removed queue entry leaves its `outputs/<attempt>/config.json`, so it lists with status null; a queued run's folder lists with status None (C6 has `queued`); C6 Run `data` and `gain` missing; silent None on unreadable config/status JSON in runs.py and launch.py; a worker restart between launch and lock could launch the same attempt twice; all Starlette HTTP errors (405 too) answer `not_found`.
- 2026-11-07 Nico asked in session for a 4 am (Berlin) check-in that resumes the build if a usage limit stops it: one scheduled message into this session (trigger trig_01DgaVMm2MGWirQbnxGDb1vk, 03:00 UTC). This is an exception to the skill's "no timers" rule at his request; no other timer exists.
- Non-blocking from the batch-2 review: `gsm8k prune --yes` goes on when the run log has skipped malformed rows (a skipped best row would lose its adapter): refuse `--yes` when rows were skipped; `gsm8k train` prints an estimate for the training steps only (add the closing dev evaluation); `train_cmd.py` duplicates `run_config.TEST_SPLIT_MESSAGE`; the sft data-leak guard has no own test; prune's `ADAPTER_METHODS` (sft, grpo, terse, optuna) needs new adapter methods added; folders under checkpoints/ whose names are not run ids are left alone.
- 1.7B SFT at default dials (batch 4, 1,744 steps) is estimated at 6-7 GB, tight near 512-token batches; an OOM ends the run failed with "GPU out of memory": then batch size 2 via a spec change.
- AC1.1.4's import test passed before the parts' code existed because the lead's shared `_env.py` came in the shared-setup commit; the reviewer confirmed it is a real check.
- `dataclasses.replace(cfg, model=...)` keeps the old model's `model_revision` (run_config.py): build a new `RunConfig` when the model changes.
- Untested in u1 (no criterion gap): `gsm8k evaluate --config` (u4's worker uses it), the stopped and failed paths, timings on failure, the `--run-id` pattern check. Add tests when u4 starts.
- The batch-1 reviewer saved check output to `/tmp/claude-review-check.log`, outside the project (test output only); left as is.

## Done this run
- 2026-11-07 batch-3 done: u4-run-service (run list and status, finalists, run queue with a separate `gsm8k worker`, check/confirm launch, stop, FastAPI service on 127.0.0.1 with the C6 API and C7 events), 3 parallel parts; 297 tests green, coverage 83%, trace PASS; review PASS first round. Check questions (AC6.3.1): (1) Why does the worker remove a queue entry only once the launched run holds the GPU lock, not when it starts the process? (2) Why is a run launched as an argument list in its own session rather than as a shell command? Answers: none yet. Spec changes (class change): C6 error codes `confirmation_required` and `internal`; Nico ruled test_AC3_2_5_shell_characters_reach_the_run_as_one_argument wrong (setup only).
- 2026-11-07 long run q17-base-dev-1 done: Qwen3-1.7B-Base dev accuracy 0.7903 (496 problems), 17.6 min. Long run q17-base-test-1 started detached (pid 172473).
- 2026-11-07 long run q06-base-test-1 done: Qwen3-0.6B-Base test accuracy 0.4966 (1,319 problems), 22.3 min, peak 2.27 GB; 10 points below its dev score (0.5968): dev comes from GSM8K train, a contamination hint for results.md (brief Risk 1). Row in results/runs.csv, committed on main after batch-3.
- 2026-11-06 long run q06-base-dev-1 done: Qwen3-0.6B-Base dev accuracy 0.5968 (496 problems), 7.0 min, 0.83 s per problem, peak 2.28 GB (row committed).
- 2026-11-06 long run q06-base-dev-1 started detached (pid 91216): 0.6B baseline on the 496 scored dev problems (AC1.5.1); six more queued, one GPU run at a time.
- 2026-11-06 batch-2 done: u2-baselines (`gsm8k harness`, lm-eval cross-check) and u3-sft (`gsm8k train` LoRA SFT with live metrics, dial table and strict `check_dials`, 3-hour estimates, `gsm8k prune`), 4 parallel parts; 228 tests green, coverage 84%, trace PASS; both reviews PASS first round. Spec changes (class change): AC2.5.3 keeps the active run's adapter folder; C2 `evaluator` field (harness runs get their own config_hash). Nico ruled test_AC1_4_5_defaults_match_documented_values wrong (C2 field set); fixed by adding `evaluator`.
- 2026-11-06 batch-1 done: u1-eval-skeleton (walking skeleton `gsm8k evaluate`), built by 3 parallel builders (data, records, command) after 3 test writers; 118 tests green on the CPU, coverage 84%, trace PASS. Review round 1 FAIL (adhoc temp run log in system /tmp, NFR5.2), fixed in cfa229b; round 2 PASS. The skeleton test scored 2 of 3 dev problems with the real 0.6B on the CPU (about 62 s per problem). Pins: openai/gsm8k 740312a, Qwen3-0.6B-Base da87bfb, Qwen3-1.7B-Base ea980cb.
- 2026-11-06 spec changes on batch-1 (class change): C2 `max_new_tokens` field; C2 test-split note follows NFR8 (base-model test baselines allowed).
- 2026-11-06 venv created with `uv venv --seed` on the system Python 3.12 (`python3-venv` is not installed and needs sudo); packages installed with pip from `requirements.txt` (torch 2.14.1+cu130).
- 2026-11-06 test_command set to `scripts/check.sh`: the Construction Verification Command Nico approved in AI-DLC (intent `verification-command.txt`; u1 tech-stack-decisions: caches, Ruff, pytest with coverage on `src/` failing under 80%, all on the CPU through `scripts/in-env.sh`); team.md allows only that command as the gate. The lead writes the script in batch-1 shared setup. It replaces the plain pytest command set earlier this run.
- 2026-11-06 gate:go consumed: spec 37fb5a4 approved (record and STATE.md), stage:construction.
- 2026-11-06 Start checks: not paused, charter dfd4277 unchanged, track learning, no gates; stage inception, AI-DLC delivery-planning `[x]`, so 2.3 (propose).
- 2026-11-06 Trace check PASS (138 AC, 26 manual). Spec review round 1 FAIL: brief said GRPO 3–7 h against Nico's 3 h cap (feasibility Q3, Q9); two criteria loaded the real 0.6B model in CPU tests (NFR3); three lock criteria contradicted contract C3. Fixed in the brief and stories.md with two changes.md lines; round 2 PASS.
- 2026-11-06 Committed `inputs/design/` (Nico's screenshot and README) and the spec `spec(inception)` 37fb5a4: 9 FR groups (37 FRs), 10 NFRs, 31 stories, 138 AC, 9 units.

## Goal
Ticket https://github.com/Nodolas/idea-factory/issues/6: "Fine tune model for grade math". Learning track (CHARTER "Learning projects"): spec-first with AI-DLC (brief, spec at one approved commit via `gate:go`, units ending green on main), reach the brief's done-when on this PC (the best tuned `Qwen/Qwen3-1.7B-Base` checkpoint beats its own baseline on the full GSM8K test split, noise labelled), and end with `results.md` instead of a deploy.
