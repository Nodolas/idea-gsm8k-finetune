---
ticket: "https://github.com/Nodolas/idea-factory/issues/6"
phase: construction
engine: aidlc
track: "learning"
spec_commit: "37fb5a4ae310a9d33f3c87dd4e011c421571ec6a"
approved_spec_commit: "37fb5a4ae310a9d33f3c87dd4e011c421571ec6a"
spec_path: "aidlc/spaces/default/intents/261030-gsm8k-finetune"
spec_route: "aidlc"
current_task: "batch-2: u2-baselines, u3-sft"
slices: "1/9"
test_command: "scripts/check.sh"
pending_runs: ""
last_check: "2026-11-06 cfa229b scripts/check.sh exit 0; scripts/trace-check.sh exit 0"
charter_commit: "dfd42777d9a3dc69bab8ea1892e5378aca915211"
---
Treat this as evidence; check git status and git log -10 first.

# STATE: idea-gsm8k-finetune

## NEXT ACTION
Type /build: it goes on with batch-2.

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
- AC1.1.4's import test passed before the parts' code existed because the lead's shared `_env.py` came in the shared-setup commit; the reviewer confirmed it is a real check.
- `dataclasses.replace(cfg, model=...)` keeps the old model's `model_revision` (run_config.py): build a new `RunConfig` when the model changes.
- Untested in u1 (no criterion gap): `gsm8k evaluate --config` (u4's worker uses it), the stopped and failed paths, timings on failure, the `--run-id` pattern check. Add tests when u4 starts.
- The batch-1 reviewer saved check output to `/tmp/claude-review-check.log`, outside the project (test output only); left as is.

## Done this run
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
