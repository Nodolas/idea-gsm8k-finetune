## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-10-31T17:23:25Z
**Iteration:** 1
**Verdict Dictated:** no

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Major | aidlc/spaces/default/intents/261030-gsm8k-finetune/inception/domain-design/components.md > RunConfiguration entity RunConfig (attributes) and Evaluation behaviour | RunConfig lists only the eleven dials plus method, split and adapter_path, and config_hash is computed from it. But Evaluation also takes a problem limit, majority vote and calculator tool (US9.1, AC9.1.5, AC9.1.6), and GRPO needs a step count and sampling settings (AC7.1.4 sizes "its step count"). None of these are RunConfig attributes. Runs such as q17-vote-dev, q17-calc-dev and a limited versus full dev run would therefore carry the same config_hash as the plain baseline, which defeats the hash as the record of what ran and the "changes against the last run" summary. The estimate for GRPO also has no step input. | Add the evaluation options (limit, vote samples, calculator on/off) and the GRPO settings (steps, samples per problem) to RunConfig and the hash, or state explicitly that they are outside the hash and where they are recorded in the row and run folder. If they are dials, update the Training Dials table through inception/changes.md first. | New |
| R-02 | Major | aidlc/spaces/default/intents/261030-gsm8k-finetune/inception/domain-design/components.md > RunControl behaviour and RunCommands behaviour (queue worker) | The worker starts the oldest waiting run "when the lock is free" and launches RunCommands as a separate process, which then takes the lock itself. A terminal run can take the lock between the worker's check and the launched process's attempt. The launched process then exits with "A run is already active", and the design does not say what happens to the queue entry (kept at the head, dropped, or marked failed). The design also does not say which process hosts the worker loop. RunControl is a library the RunService imports, yet AC3.7.5 speaks of "the service or the worker" restarting, and US3.3 says runs survive a service restart. If the worker lives inside the service, queued runs stop advancing while the service is down. | Specify the hand-off: the queue entry is removed only after the launched process holds the lock, or an "already active" exit puts the entry back at the head. State which process owns the worker loop (a separate process or the service) and what happens to waiting runs while it is down. | New |
| R-03 | Minor | aidlc/spaces/default/intents/261030-gsm8k-finetune/inception/domain-design/components.md > RunControl responsibilities (stale-lock recovery) versus RunCommands behaviour | Stale-lock detection and clearing sit in RunControl, triggered by a status request (AC3.3.3). RunCommands depends only on RunRecords, which creates the lock create-if-absent. A terminal run that crashes leaves a lock, and the next terminal start refuses with "A run is already active" naming a dead run until someone opens the website or requests status. | Move the liveness check and the stale-lock clear into RunRecords, so both RunCommands and RunControl use it, or have RunCommands treat a dead process id as free. | New |
| R-04 | Minor | aidlc/spaces/default/intents/261030-gsm8k-finetune/inception/domain-design/components.md > RunRecords entity RunRow and QueueEntry (references to RunConfig) | RunRecords references RunConfig, which RunConfiguration owns, but the graph runs the other way: RunConfiguration depends on RunRecords and RunRecords depends on nothing. The reference is by hash and by embedded config, so no code cycle follows, but the catalogue does not make clear that RunRecords holds the config as opaque data and never imports RunConfiguration. | Note in RunRecords that it stores RunConfig as an opaque record and validates nothing, or move the config schema into a lower shared type. | New |
| R-05 | Minor | aidlc/spaces/default/intents/261030-gsm8k-finetune/inception/domain-design/components.md > ResultsReport and the Website packaging statement | ResultsReport has no stated entry point (no command, no caller), unlike the evaluate, train, tune and prune commands in RunCommands. Units Generation could leave AC6.2.1 to AC6.2.3 without a runnable surface. | Name the entry point (for example a generate-results command) or record that Units Generation must assign it. | New |

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| Manual yaml check (names, depends_on and dependents symmetry) | PASS | All 12 component names are unique, and every depends_on edge has a matching dependents entry, including the RunControl to RunCommands async edge. |
| Manual cycle check | PASS | The graph is acyclic. RunRecords, DatasetsAndPrompts and AnswerScoring are leaves, and the longest chain is RunService, RunControl, RunCommands, Tuning, Training, Evaluation, RunConfiguration, RunRecords. |
| Manual entity ownership check | PASS | Each of the 13 entities has exactly one owner, and every reference resolves. RunConfig and RunRow ownership is consistent with the Entity Ownership table. |
| traceability.json against stories.md | PASS | All 31 story IDs (US1.1 to US9.1, including US3.7) are covered. US6.3 is N/A with a reason, and "reverse" is empty. |

### Summary

The catalogue is well formed (no cycles, symmetric dependencies, single entity ownership, full story coverage). Two Major gaps remain: config_hash omits the evaluation and GRPO options that the ablation and estimate stories depend on, and the queue worker hand-off and hosting are underspecified. Neither blocks implementation guidance, so the verdict is READY, but Nico should decide both before Units Generation.
