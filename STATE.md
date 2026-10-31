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
Clear the blocker below (remove the AI-DLC sensor block from `scripts/trace-check.sh` outside a Claude session), then type `/build` in this folder (Opus 5.5, Auto): it runs the trace check and proposes AI-DLC's spec (2.3).

## DO NOT
- Do not build on local branch `wip/hello-file` (commit 8ac6241, `hello-i-am-here.txt`, never pushed). It is not a build task; it is left untouched for Nico to keep or delete. Conflict logged 2026-10-30: the session started on it while STATE.md named no task.
- Do not install from the 21st.dev registry or use its Magic MCP: both need a 21st.dev API key and account (rule 4). The UI is built on shadcn/ui and styled from Nico's screenshots (`inputs/design/`) and the component source he pasted into `inputs/` (brief [[brief]]).
- Conflict logged 2026-10-30: commit e8b7cfc `chore(inputs)` (Nico's website request and the pasted halftone component) was made by another session on main during the brief run; it holds data only and is kept.
- Do not tune on the GSM8K test split: all tuning and agent decisions use train-dev (brief, Evaluation plan).
- 2026-10-31: AI-DLC's tool-call guard (`aidlc engine hook guard-tool-call`) refuses a session's Bash call that runs `scripts/trace-check.sh`, and any Edit of that file, because the script sets `AIDLC_SESSION_OVERRIDE_SOURCE` and calls `aidlc engine sensor-traceability` (lines 143-162). Do not retry it another way (no env prefix, no copy of the script, no `bash` wrapper).
- Uncommitted on main, left for 2.3 step 4 (not a conflict): the whole intent folder `aidlc/spaces/default/intents/` (untracked), `aidlc/spaces/default/memory/{team,project}.md`, `inception/changes.md` (5 AI-DLC change lines of 2026-10-31) and `inputs/design/` (Nico's screenshot and README). AI-DLC was resumed into u1 Construction stages; those files are bookkeeping, not needed (Nico, 2026-10-31).

## Blockers
- REQUEST: outside a Claude session (an editor is enough), delete the AI-DLC sensor from `scripts/trace-check.sh`: lines 143-162 (the comment, `sensor()`, `verdict()`, `aidlc_sensor()`) and ` && aidlc_sensor` on line 164; also the two header lines (11-12) that mention the sensor. Its result was info only, so PASS/FAIL does not change. Nico chose this in session (2026-10-31, "Sensor opt-in"), but the guard refuses agent edits of the file. The factory copy of the script needs the same fix for later projects. Then type `/build`.
- Open for Nico (not blocking): confirm the pasted 21st.dev component's licence allows this use (brief Risks 8). The training-page screenshot is in `inputs/design/`.

## Done this run
- 2026-10-31 Start checks: track learning, charter dfd4277 unchanged, no gates; AI-DLC intent `261030-gsm8k-finetune` has delivery-planning `[x]`, so the run went to 2.3 (propose).
- 2026-10-31 `spec_path` set to the intent folder.
- 2026-10-31 blocked at 2.3 step 2: the trace check cannot run in a session (see Blockers).

## Goal
Ticket https://github.com/Nodolas/idea-factory/issues/6: "Fine tune model for grade math". Learning track (CHARTER "Learning projects"): spec-first with AI-DLC (brief, spec at one approved commit via `gate:go`, units ending green on main), reach the brief's done-when on this PC, and end with `results.md` instead of a deploy.
