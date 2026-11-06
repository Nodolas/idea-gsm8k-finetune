## Review

**Verdict:** NOT-READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-10-31T17:52:56Z
**Iteration:** 1
**Verdict Dictated:** no

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Major | aidlc/spaces/default/intents/261030-gsm8k-finetune/inception/contract-design/contract-summary.md > C3 Lock and Queue > lock.take | The stale-lock takeover is racy. "If the file exists and its pid is gone -> rename it to run.lock.stale-<timestamp> ... then retry the take once" is run by "any taker" (terminal, worker, status check). Taker A renames the stale file and creates a fresh lock. Taker B, which read the old content earlier, then renames A's new live lock as "stale" and takes it. Two runs hold the GPU, which breaks FR3.4 and the "exactly one wins" claim. The status check is also a taker, so it can do this while idle. | Specify a takeover that cannot remove a live lock. For example, compare run_id, pid and started_at before the rename and re-read after it, or use a separate takeover guard, or never let the status check take over. Say what a taker does when its rename finds the file already gone. | New |
| R-02 | Major | aidlc/spaces/default/intents/261030-gsm8k-finetune/inception/contract-design/contract-summary.md > C5 commands, C2 config.json, C1 data enum | The lm-evaluation-harness cross-check has no launch contract. C1 has `data: gsm8k-test-harness` and `metric: harness_flexible_accuracy`. C5 only defines `evaluate` and `train`, and the C2 `split` enum (dev, test, gsmplus-testmini, gsmsym-p1) and method enum have no harness value. AC1.5.5 and AC1.5.6 need a harness run with `--limit 5` and a `--run-id` such as `q17-base-harness-1`. U2 and U6 own six `[manual]` harness runs. There is no way to state which command, argument or config field selects the harness path, or what the Run folder holds for it. | Add a `gsm8k` harness command, or an evaluate mode and a config field, to C5 and C2. Define its arguments, exit codes, run-folder files, and the method and data values it writes (AC1.5.5: method `base`; AC6.1.3: `best`). | New |
| R-03 | Major | aidlc/spaces/default/intents/261030-gsm8k-finetune/inception/contract-design/contract-summary.md > C6 schemas Run (dev_accuracy, test_accuracy, gain) vs C1 | The Run object carries `dev_accuracy`, `test_accuracy` and `gain` on one record, but C1 has one row per scored run, each with a single `data` and `value`. A dev run (`q17-sft-dev-1`) and its test run (`q17-best-test-1`) are different run_ids. Nothing says how the service joins them. `adapter_run` is not described as that join key, and nothing says what the gain is measured against. The Scores page (US4.x) and the ranking depend on these three fields. | State the derivation rule in the contract. Say which row populates each field, how a test row links to its dev run (via `adapter_run`, with it required on test rows), and which baseline row the gain uses. Or split Run into per-row records and let the website join them. | New |
| R-04 | Minor | aidlc/spaces/default/intents/261030-gsm8k-finetune/inception/contract-design/contract-summary.md > C3 queue.rules vs C5 worker_rules | "An entry is removed only after the process it launched holds the lock" conflicts with "exit code 3 puts the queue entry back at the head". If the entry is still present until the lock is held, exit 3 never has anything to put back. How the worker learns that the child holds the lock (lock run_id and pid matching the child) is not defined. | Rewrite the two rules so they agree. Say exit 3 leaves the entry in place, and give the observable condition for removal. | New |
| R-05 | Minor | aidlc/spaces/default/intents/261030-gsm8k-finetune/inception/contract-design/contract-summary.md > C6 Error mapping and Error enum | `check_expired` and a missing second confirmation have no HTTP status. `needs_second_confirmation` appears in CheckedRun, but `/runs/confirm` has no error code for a test-split confirm made without it. The 409 and 404 are listed on /runs/confirm without saying which code each carries. Several endpoints (/dials, /queue, /finalists) have no response schema. | Add status codes for `check_expired` and for a missing second confirmation. Add 200 response schemas for /dials, /queue and /finalists, since the website is built against them. | New |
| R-06 | Minor | aidlc/spaces/default/intents/261030-gsm8k-finetune/inception/contract-design/contract-summary.md > Open Questions, C1 (AC6.1.1) | The contract departs from AC6.1.1 (the finalist's run id in `data`) by adding `adapter_run`. The fix is an `inception/changes.md` line before u6 writes tests. Until then the contract and the approved story disagree. | Add the dated changes.md line and amend AC6.1.1 in the same spec commit, or confirm that this is deferred to the u6 spec step before approving. | New |

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| Cross-reference check of cited AC IDs against stories.md (AC3.1.1 to AC3.1.4, AC3.2.x, AC3.6.x, AC3.7.x, AC2.5.3, AC4.4.3, AC4.5.3, AC4.6.x, AC6.1.1) | PASS: all 18 resolve | Citations are valid. |
| Contract vs component entities (RunRow, RunFolder, FinalistMark, RunLock, QueueEntry in components.md) | PASS with one addition | The contract adds `adapter_run` to RunRow. That is additive and is not an entity mismatch. |
| required-sections / upstream-coverage sensors | Not run by me | The embedded OpenAPI, AsyncAPI and shared-schema blocks were checked by reading only. |

### Summary

The contract set is coherent and traces well to the units and components. There are three gaps a developer would otherwise have to guess at. The stale-lock takeover can remove a live lock. The harness runs have no launch contract. The Run record's test and gain fields cannot be derived from the one-row-per-run log. Fix these, and tidy the queue and exit-code rules and the missing error codes, before approving.
