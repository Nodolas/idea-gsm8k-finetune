# Scope Document: Fine tune model for grade math

Upstream:
- `ideation/intent-capture/intent-statement.md`: learning first, Nico alone, any measurable gain, no deploy, no big-model training.
- `ideation/feasibility/feasibility-assessment.md`: feasible on €0 and this PC; measure run times first.
- `ideation/feasibility/constraint-register.md`: 3-hour runs, PC-only, dashboard-started runs, licences.

Answers: `scope-definition-questions.md` Q1–Q5.

## Minimum Viable Scope

The first version is done when Nico can:
- evaluate a small open base model on GSM8K and measure run times on this PC;
- fine-tune it with supervised fine-tuning (LoRA);
- watch, tune and start runs from a local three-page website;
- check that any gain carries over to reworded problems;
- read the result in `results.md`.

The scorecard is the intent's success metric: any measurable gain over the model's own baseline on the full GSM8K test split, with the write-up saying whether it is within noise (intent-statement.md).

## In Scope (must-have)

| Capability | Why it is in | Source |
|---|---|---|
| Evaluation harness, held-out dev split, baseline, and run-time measurement | Everything is compared against the baseline. Run times decide model size under the 3-hour cap | intent-statement.md; feasibility-assessment.md (recommendation) |
| Supervised fine-tuning with LoRA | The core training step that fits the 3-hour cap | feasibility-assessment.md; constraint-register.md TC-2 |
| Website: landing page with the halftone headline, highest-scores page, and training page with live curves, dials and a start button | Nico chose all of it as must-have | Q3 |
| Generalisation check on GSM-Plus and GSM-Symbolic (evaluation only) | Shows whether gains are real, not memorised | Q4; constraint-register.md LC-2 |
| Run log, `results.md` write-up, and short check questions after each step | The intent's reporting choice | intent-statement.md |

## Could-Have (after the must-haves work)

| Capability | Condition | Source |
|---|---|---|
| Reinforcement learning (GRPO) | Only after everything else works, and only if a useful run fits in 3 hours | Q1; constraint-register.md TC-2 |
| Tuning loop: Optuna search plus a proposer and a reviewer agent | Later, if time allows | Q2 |
| Ablations (for example terse versus step-by-step answers, samples per problem, a calculator tool) | Later, if time allows | Q4 |

## Out of Scope

- Any deploy or hosting; the website runs locally only (intent-statement.md).
- Full fine-tuning of the 1.7B model, and bf16 LoRA on models of 3B and up (intent-statement.md; constraint-register.md TC-1).
- Rented hardware, paid services, accounts and API keys (constraint-register.md LC-5, TC-3).
- Training on GSM-Plus or GSM-Symbolic (constraint-register.md LC-2).
- Long runs launched by an automated agent; runs over about 10 minutes are started by Nico (constraint-register.md OC-4).

## Sequencing

Learning order (Q5):
1. Evaluation and baseline.
2. Supervised fine-tuning.
3. The website.
4. The could-haves, if time allows: reinforcement learning, the tuning loop, ablations.
5. Final runs, the generalisation check, and the write-up.

## Value Stream

```
[Base model] -> [Evaluate + measure run times] -> [Supervised fine-tuning] -> [Watch and tune on the website]
     -> (optional: reinforcement learning / tuning loop / ablations) -> [Final test + generalisation check] -> [results.md]
```

<!-- Text fallback: the base model is evaluated and timed, then fine-tuned. Runs are watched and tuned on the website, with optional reinforcement learning, tuning loop and ablations. The best model gets a final test and generalisation check, and the result is written to results.md. -->

Each step teaches one concept (learning first, intent-statement.md) and produces a row in the run log that the website shows.

## Deadlines

None: the pace is set by run times (feasibility Q8, carried in constraint-register.md OC-2).

## Assumptions & Open Questions

- [assumption] Run-time measurement in the first step settles which model size the later steps use (feasibility-assessment.md).
