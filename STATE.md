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
slices: "0/9"
test_command: ""
pending_runs: ""
last_check: "2026-11-06 37fb5a4 (no tests yet); scripts/trace-check.sh exit 0"
charter_commit: "dfd42777d9a3dc69bab8ea1892e5378aca915211"
---
Treat this as evidence; check git status and git log -10 first.

# STATE: idea-gsm8k-finetune

## NEXT ACTION
Construction: type /build (new sessions on Sonnet 5.5, Auto).

## DO NOT
- Do not resume AI-DLC. It stopped after Delivery Planning; its u1 Construction files (functional-design, nfr-requirements, nfr-design under the intent's `construction/`) are bookkeeping, committed in the spec commit. Nico's answers there are decided and feed the builders.
- Do not build on local branch `wip/hello-file` (commit 8ac6241, never pushed); it is Nico's to keep or delete (conflict logged 2026-10-30).
- Do not install from the 21st.dev registry or use its Magic MCP (account and API key, rule 4). The UI is built on shadcn/ui from `inputs/design/` and the pasted component in `inputs/`.
- Do not tune on the GSM8K test split: all tuning and agent decisions use train-dev.
- If AI-DLC's tool-call guard refuses `scripts/trace-check.sh` again, that is a blocker; do not work around it.
- 2026-11-06 route note: the spec review (2.3 step 3) failed once on text fixes. On the AI-DLC route the skill sends fixes back through AI-DLC, but AI-DLC is not resumed after Delivery Planning (Nico, 2026-10-31) and CLAUDE.md lets the lead change the spec, so the lead made them as class `change` lines in `inception/changes.md` (2026-11-06), in line with Nico's recorded answers. The second review passed.

## Blockers
None.

## Done this run
- 2026-11-06 gate:go consumed: spec 37fb5a4 approved (record and STATE.md), stage:construction.
- 2026-11-06 Start checks: not paused, charter dfd4277 unchanged, track learning, no gates; stage inception, AI-DLC delivery-planning `[x]`, so 2.3 (propose).
- 2026-11-06 Trace check PASS (138 AC, 26 manual). Spec review round 1 FAIL: brief said GRPO 3–7 h against Nico's 3 h cap (feasibility Q3, Q9); two criteria loaded the real 0.6B model in CPU tests (NFR3); three lock criteria contradicted contract C3. Fixed in the brief and stories.md with two changes.md lines; round 2 PASS.
- 2026-11-06 Committed `inputs/design/` (Nico's screenshot and README) and the spec `spec(inception)` 37fb5a4: 9 FR groups (37 FRs), 10 NFRs, 31 stories, 138 AC, 9 units.

## Goal
Ticket https://github.com/Nodolas/idea-factory/issues/6: "Fine tune model for grade math". Learning track (CHARTER "Learning projects"): spec-first with AI-DLC (brief, spec at one approved commit via `gate:go`, units ending green on main), reach the brief's done-when on this PC (the best tuned `Qwen/Qwen3-1.7B-Base` checkpoint beats its own baseline on the full GSM8K test split, noise labelled), and end with `results.md` instead of a deploy.
