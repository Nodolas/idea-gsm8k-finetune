# Scope Definition — Questions

Context: the intent statement (learning first, any measurable gain, no deploy, no big-model training, PC-only) and the feasibility work (€0, runs capped at about 3 hours, measure run times first, start runs from the dashboard, no deadline) are settled and not asked again. These questions decide what is must-have versus later, and in what order.

Capabilities in play (from the brief and earlier answers): evaluation harness and baseline with run-time measurement; supervised fine-tuning with LoRA; reinforcement learning (GRPO); a local website (landing page with halftone headline, highest-scores page, training page with live curves, dials and a start button); a tuning loop (Optuna search plus a proposer and a reviewer agent); a generalisation check (GSM-Plus, GSM-Symbolic); ablations; the `results.md` write-up with check questions.

## Q1. [Product] How essential is reinforcement learning (GRPO) in this first version?

Feasibility found it may not fit the 3-hour cap until run times are measured.

A. Must-have: the project is not done without a reinforcement-learning run
B. Should-have: do it if the measurement shows a useful run fits in 3 hours (on either model size)
C. Could-have: only after everything else works
D. Not yet defined
X. Other (please specify)

[Answer]: C. Could-have: only after everything else works

## Q2. [Product] How essential is the tuning loop (Optuna search plus the proposer and reviewer agents)?

A. Must-have: it is central to what you want to learn
B. Should-have: build it once supervised fine-tuning works and the website shows runs
C. Could-have: later, if time allows
D. Won't have in this version
X. Other (please specify)

[Answer]: C. Could-have: later, if time allows

## Q3. [Product] Which parts of the website are must-have?

A. All of it: landing page with the halftone headline, highest-scores page, and training page with live curves, dials and a start button
B. The training page (live curves, dials, start button) is must-have; the landing and highest-scores pages are should-have
C. Only the training page; the other pages are could-have
D. Not yet defined
X. Other (please specify)

[Answer]: A. All of it: landing page with the halftone headline, highest-scores page, and training page with live curves, dials and a start button

## Q4. [Product] How essential are the generalisation check and the ablations?

The generalisation check scores the best model on GSM-Plus and GSM-Symbolic, to see whether gains carry over to reworded problems. Ablations compare variants (for example terse versus step-by-step answers, number of samples per problem, a Python calculator tool).

A. Generalisation check must-have; ablations could-have
B. Both should-have
C. Both could-have
D. Not yet defined
X. Other (please specify)

[Answer]: A. Generalisation check must-have; ablations could-have

## Q5. [Product] In what order should the work go?

A. Learning order: evaluation and baseline, then supervised fine-tuning, then the website, then reinforcement learning, then the tuning loop, then final runs and write-up
B. Website early: evaluation and baseline, then the website, so every later training run is watched live
C. Risk first: measure run times and check that reinforcement learning fits before anything else, then the rest in learning order
D. Not yet defined
X. Other (please specify)

[Answer]: A. Learning order

## Consolidated Summary Confirmation

- Reinforcement learning (GRPO): could-have, only after everything else works (Q1).
- Tuning loop (Optuna plus the proposer and reviewer agents): could-have, later if time allows (Q2).
- Website: all of it is must-have: landing page with the halftone headline, highest-scores page, and training page with live curves, dials and a start button (Q3).
- Generalisation check (GSM-Plus, GSM-Symbolic): must-have; ablations: could-have (Q4).
- Order: learning order: evaluation and baseline, then supervised fine-tuning, then the website, then the could-haves, then final runs and the write-up (Q5).

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
