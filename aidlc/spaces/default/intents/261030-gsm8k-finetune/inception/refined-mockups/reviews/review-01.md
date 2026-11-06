## Review

**Verdict:** READY
**Reviewer:** aidlc-product-lead-agent
**Date:** 2026-10-31T16:51:44Z
**Iteration:** 1
**Verdict Dictated:** no

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Major | aidlc/spaces/default/intents/261030-gsm8k-finetune/inception/refined-mockups/mockups.md > Screen 3 > Dials panel (Method select) | The "Evaluate on dev" choice is said to evaluate "the base model or a chosen adapter", but the dials panel has no adapter picker. Nothing says which dials are disabled or hidden for an evaluation (learning rate, epochs and LoRA rank mean nothing there). The Confirm Run dialog also shows no evaluation variant. Yet the landing and scores empty states send Nico to "start with a baseline on the training page", so this is the first run he will ever start. | Add the evaluation variant of the dials panel: an adapter field (or "base model only"), which dials are inactive and how they look, what the Confirm Run dialog shows for an evaluation, and the base-id naming it produces (for example q06-base-dev-1). | New |
| R-02 | Minor | mockups.md > Screen 3 dials panel vs stories.md > Training Dials and AC4.6.1 | The panel draws 12 controls (Method plus the 11 dials), while the text and AC4.6.1 say "all eleven dials". Method is not in the Training Dials table, so a test counting dials would disagree with the mockup. | Say explicitly that Method is a twelfth control outside the eleven dials, or change AC4.6.1 wording at the next spec edit. | New |
| R-03 | Minor | mockups.md > Screen 2 (q06-sft-dev-3, q06-base-dev-1 rows) vs Screen 3 (RUNNING q06-sft-dev-3; past runs) | The example data contradicts itself. q06-sft-dev-3 is RUNNING at 30% on Training but is a scored 47.0% row on Scores. q06-base-dev-1 is FAILED with no score on Training but is the scored 0.6B baseline (41.3%) on Scores. Developers may copy these into fixtures. | Make the example runs consistent across the screens, or mark the sample data as unrelated per screen. | New |
| R-04 | Minor | mockups.md > Dialog: Score a Finalist on Test; interaction-spec.md > TestSplitDialog | The test-split run is launched from the Scores page and takes about 1 h 52 min. Nothing says what Nico sees after confirming (stay on Scores, go to Training, only the top-bar RUNNING tag). | Add one line saying where he lands and how he follows the run after "Score on test". | New |
| R-05 | Minor | interaction-spec.md > CurvesPanel > Accessibility | The chart is `role="img"`, yet arrow keys are meant to move the read-out point inside it. An img is not focusable and takes no key input. | Specify a focusable element with a suitable role (or a slider-like control) for the read-out, and keep the "Latest" text line. | New |
| R-06 | Minor | interaction-spec.md > PastRunsList > Responsive Behaviour | "Shows 10 rows, then Show all" appears in no mockup, state table or AC (AC4.5.5 lists all past runs), so it is small unrequested scope. | Drop it, or add the "Show all" state to the mockup and a criterion. | New |
| R-07 | Minor | mockups.md > Dialog: Confirm Run, Command line | The command (`python -m gsm8k.train --config ...`) is invented and flagged illustrative. That is fine, but it must not harden into a fixture. | Keep the "illustrative" note, and have Functional Design set the real entry points before tests quote the command. | New |

### Summary

The refined mockups cover every website story (US4.1–US4.6, US3.4–US3.6) with real labels and states for empty, loading, error and reduce-motion. They also give each component a spec, a token set and a shadcn/ui mapping. The look follows Nico's five answers. They are implementable as they stand, with the evaluation-only mode the one real gap and the rest small cleanups.
