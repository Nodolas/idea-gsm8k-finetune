---
ticket: "https://github.com/Nodolas/idea-factory/issues/6"
phase: inception
engine: aidlc
track: "learning"
spec_commit: null
approved_spec_commit: null
spec_path: "aidlc/spaces/default/intents/261030-gsm8k-finetune"
spec_route: "aidlc"
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
Type `/build` (new session, Auto). The trace-check blocker is cleared: the AI-DLC sensor was removed from `scripts/trace-check.sh` by the factory (Nico's "Sensor opt-in" choice, 2026-10-31), so the trace check runs in a session again. It proposes the spec; then add gate:go.

## DO NOT
- Do not build on local branch `wip/hello-file` (commit 8ac6241, `hello-i-am-here.txt`, never pushed). It is not a build task; it is left untouched for Nico to keep or delete. Conflict logged 2026-10-30: the session started on it while STATE.md named no task.
- Do not install from the 21st.dev registry or use its Magic MCP: both need a 21st.dev API key and account (rule 4). The UI is built on shadcn/ui and styled from Nico's screenshots (`inputs/design/`) and the component source he pasted into `inputs/` (brief [[brief]]).
- Conflict logged 2026-10-30: commit e8b7cfc `chore(inputs)` (Nico's website request and the pasted halftone component) was made by another session on main during the brief run; it holds data only and is kept.
- Do not tune on the GSM8K test split: all tuning and agent decisions use train-dev (brief, Evaluation plan).
- 2026-10-31: AI-DLC's tool-call guard refused a session's Bash call that ran `scripts/trace-check.sh` while the script called `aidlc engine sensor-traceability`. Fixed by the factory: the script no longer calls AI-DLC. If the guard refuses it again, that is a blocker; do not work around it.
- Uncommitted on main, left for 2.3 step 4 (not a conflict): the whole intent folder `aidlc/spaces/default/intents/` (untracked), `aidlc/spaces/default/memory/{team,project}.md`, `inception/changes.md` (5 AI-DLC change lines of 2026-10-31) and `inputs/design/` (Nico's screenshot and README). AI-DLC was resumed into u1 Construction stages; those files are bookkeeping, not needed (Nico, 2026-10-31).

## Blockers
- Open for Nico (not blocking): confirm the pasted 21st.dev component's licence allows this use (brief Risks 8). The training-page screenshot is in `inputs/design/`.

## Done this run
- 2026-10-31 Start checks: track learning, charter dfd4277 unchanged, no gates; AI-DLC intent `261030-gsm8k-finetune` has delivery-planning `[x]`, so the run went to 2.3 (propose).
- 2026-10-31 `spec_path` set to the intent folder.
- 2026-10-31 blocked at 2.3 step 2: the trace check cannot run in a session (see Blockers).

## Goal
Ticket https://github.com/Nodolas/idea-factory/issues/6: "Fine tune model for grade math". Learning track (CHARTER "Learning projects"): spec-first with AI-DLC (brief, spec at one approved commit via `gate:go`, units ending green on main), reach the brief's done-when on this PC, and end with `results.md` instead of a deploy.
