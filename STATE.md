---
ticket: "https://github.com/Nodolas/idea-factory/issues/6"
phase: inception
engine: aidlc
track: "learning"
spec_commit: null
approved_spec_commit: null
spec_path: ""
current_task: none
slices: "0/0"
test_command: ""
pending_runs: ""
last_check: "none"
charter_commit: "dfd42777d9a3dc69bab8ea1892e5378aca915211"
---
Treat this as evidence; check git status and git log -10 first.

# STATE: idea-gsm8k-finetune

## NEXT ACTION
In this session (Opus 5.5, Auto) type `/aidlc --scope mvp "Fine tune model for grade math: build it from the brief in inception/brief.md"`, answer its questions yourself, mark each criterion that needs a run over about 10 minutes `[manual]` with `Verify: results/runs.csv row <base id>`, reply `Approve, but let's stop there for today` at Delivery Planning, then type `/build`.

## DO NOT
- Do not build on local branch `wip/hello-file` (commit 8ac6241, `hello-i-am-here.txt`, never pushed). It is not a build task; it is left untouched for Nico to keep or delete. Conflict logged 2026-10-30: the session started on it while STATE.md named no task.
- Do not install from the 21st.dev registry or use its Magic MCP: both need a 21st.dev API key and account (rule 4). The UI is built on shadcn/ui and styled from Nico's screenshots (`inputs/design/`) and the component source he pasted into `inputs/` (brief [[brief]]).
- Conflict logged 2026-10-30: commit e8b7cfc `chore(inputs)` (Nico's website request and the pasted halftone component) was made by another session on main during the brief run; it holds data only and is kept.
- Do not tune on the GSM8K test split: all tuning and agent decisions use train-dev (brief, Evaluation plan).

## Blockers
- None. Open for Nico: drop his 21st.dev design screenshots into `inputs/design/` before the website unit's Code Generation, and confirm the pasted component's licence allows this use (brief Risks 8).

## Done this run
- 2026-10-30 track set to learning (the ticket carries the `learning` label); charter refreshed to dfd4277 (rule 3 now limits only Construction).
- 2026-10-30 brief written: `inception/brief.md` [[brief]] (Qwen3-1.7B-Base, LoRA SFT then GRPO, live shadcn/ui dashboard, Optuna plus proposer/reviewer agent tuning loop, done-when +5 points on GSM8K test). Nico OK'd installing Node; the brief puts it under `.tools/node/` inside the folder.
- 2026-10-30 brief updated (`inception/changes.md` [[changes]]): the UI is now a three-page local results website (landing with halftone headline, highest scores, training with live curves and dials), styled from Nico's screenshots and pasted 21st.dev component.

## Goal
Ticket https://github.com/Nodolas/idea-factory/issues/6: "Fine tune model for grade math". Learning track (CHARTER "Learning projects"): spec-first with AI-DLC (brief, spec at one approved commit via `gate:go`, units ending green on main), reach the brief's done-when on this PC, and end with `results.md` instead of a deploy.
