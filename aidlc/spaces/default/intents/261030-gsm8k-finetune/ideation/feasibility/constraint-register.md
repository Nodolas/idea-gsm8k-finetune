# Constraint Register: Fine tune model for grade math

Upstream: `ideation/intent-capture/intent-statement.md`; answers in `feasibility-questions.md`.

## Technical Constraints

| ID | Constraint | Impact | Source |
|---|---|---|---|
| TC-1 | One GPU with 8 GB of memory, 31 GB of system RAM | Caps model size and batch size; no full fine-tuning of the 1.7B model; no bf16 LoRA at 3B and up | intent-statement.md (boundary), Q7 |
| TC-2 | A single run may take up to about 3 hours | Reinforcement learning must fit by step count or model size; decided after measuring (Q9) | Q3, Q9 |
| TC-3 | Everything runs on this PC; downloads need no login or token | No cloud, no hosted tracking (such as W&B), no registry installs that need a key | Q1, Q7 |
| TC-4 | Runs can be started from the local dashboard | The launched process must outlive the browser, log its own progress, and allow only one GPU run at a time | Q2 |
| TC-5 | Caches, models, datasets and the Node toolchain stay inside the project folder | Install and cache paths are set per project | Project rules (CLAUDE.md) |

## Organizational Constraints

| ID | Constraint | Impact | Source |
|---|---|---|---|
| OC-1 | Nico alone decides scope and priority | No other approvers | intent-statement.md |
| OC-2 | No deadline | Pace is set by run times | Q8 |
| OC-3 | The PC is mostly free during long runs | Resume-after-interruption is optional | Q4 |
| OC-4 | Runs longer than about 10 minutes are started by Nico (in a terminal or with a dashboard button he clicks), never by an automated agent | The tuning agents propose run settings but do not launch long runs | Project rules (CLAUDE.md), Q2 |
| OC-5 | Learning comes first | When a step teaches more but scores less, it is still worth doing | intent-statement.md |

## Licence and Regulatory Constraints

| ID | Constraint | Impact | Source |
|---|---|---|---|
| LC-1 | Only models and data whose licences allow personal fine-tuning | Planned: Apache-2.0 models, MIT-licensed GSM8K | Q6 |
| LC-2 | GSM-Plus (CC-BY-SA) and GSM-Symbolic (NonCommercial, NoDerivatives) are evaluation-only | Never in a training set; GSM-Symbolic never redistributed modified | Q6 |
| LC-3 | The pasted 21st.dev component's licence is unconfirmed | Nico confirms it, or the headline is rewritten from scratch | Q6 |
| LC-4 | No regulation applies (personal project, no personal data) | No compliance work | intent-statement.md, Q6 |
| LC-5 | €0 budget | No paid service, rented compute, account or API key | Q1 |

## Assumptions & Open Questions

None.
