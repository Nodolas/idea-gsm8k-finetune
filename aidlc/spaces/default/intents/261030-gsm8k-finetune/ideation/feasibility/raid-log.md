# RAID Log: Fine tune model for grade math

Upstream: `ideation/intent-capture/intent-statement.md`; constraints in `constraint-register.md`; answers in `feasibility-questions.md`.

## Risks

| ID | Risk | Likelihood | Impact | Mitigation | Source |
|---|---|---|---|---|---|
| R-1 | Reinforcement learning does not fit the 3-hour cap at a useful step count | High | Medium | Measure first; fall back to the smaller model or fewer steps | Q3, Q9 |
| R-2 | The base model has little headroom (it may already have seen GSM8K-style data), so gains are small | Medium | Medium | Compare against its own baseline; check generalisation sets; the smaller model has more headroom | intent-statement.md |
| R-3 | The gain sits inside noise (about ±2.5 points) | Medium | Low | Success is "any measurable gain"; the write-up states whether it is within noise | intent-statement.md |
| R-4 | Supervised fine-tuning on terse answers lowers accuracy | Medium | Low | Treat as a learning result; also try reinforcement learning from the base model | intent-statement.md (learning first) |
| R-5 | GPU memory runs out during reinforcement learning (several sampled answers per problem) | Medium | Medium | Fewer samples per problem, shorter answers, smaller model | Q3, TC-1 |
| R-6 | A dashboard-started run dies when the browser or server closes, or two runs start at once | Medium | Medium | Detached process with its own log; one-run-at-a-time lock | Q2, TC-4 |
| R-7 | The tuning loop overfits the held-out dev split through many proposals | Low | Medium | Limit rounds; score the test split only for finalists | intent-statement.md |

## Assumptions

| ID | Assumption | How it is checked | Source |
|---|---|---|---|
| A-1 | Public estimates of run time and memory hold within about 2x on this GPU | The first measurement step | Q9 |
| A-2 | Nico confirms the pasted 21st.dev component's licence, or accepts a rewrite | Asked before the website unit | Q6 |
| A-3 | The PC stays mostly free during long runs | Nico's own practice | Q4 |

## Issues

| ID | Issue | Owner | Source |
|---|---|---|---|
| I-1 | Model size for reinforcement learning is undecided until run times are measured | Nico, after the first step | Q9 |

## Dependencies

| ID | Dependency | Needed for | Source |
|---|---|---|---|
| D-1 | Public model and dataset downloads that need no login | All training and evaluation | Q7 |
| D-2 | Node installed inside the project folder (Nico agreed) | The local website | Q5, TC-5 |
| D-3 | Nico's design screenshots for the website | The website's look | intent-statement.md (website) |

## Assumptions & Open Questions

None beyond the Assumptions table above.
