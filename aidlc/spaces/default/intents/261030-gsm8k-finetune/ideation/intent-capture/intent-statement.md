# Intent Statement: Fine tune model for grade math

## Problem Statement

Nico wants to fine-tune a model for grade-school math, built from the brief in `inception/brief.md`. [desc]

The problem is learning, first: Nico wants to understand and do every step of post-training a small open base model on grade-school math on his own PC (baseline evaluation, LoRA SFT, GRPO, and tuning the dials) and to see each run while it trains. [Q1]

When learning and score pull apart, learning leads: a step that teaches more is preferred over one that only raises the score. [Q1]

## Target Customer

Nico alone. This is a personal learning project in a private repo, not a product for other users. [Q2]

In Nico's words: "it's very important that this project is a personal project just for me to learn how to fine tune and not more more." [Q8]

## Success Metrics

| Metric | Target | Source |
|---|---|---|
| Accuracy gain on the full GSM8K test split | The best tuned checkpoint scores higher than its own baseline, however small the gain | [Q3] [Q9] |
| Honest reading of the gain | `results.md` states whether the gain is within noise | [Q9] |
| Run log | Every run is logged in `results/runs.csv`, which the website reads | [Q10] |
| Understanding | Nico answers short check questions after each step | [Q10] |

## Initiative Trigger

A personal learning goal that is feasible now: small open base models and free tools (TRL, Unsloth, Optuna) make SFT and GRPO possible on an 8 GB consumer GPU at no cost. [Q4]

## Initial Scope Signal

**Workflow-selected scope:** `mvp`. [scope]

**User-confirmed product boundary for this first version:** [Q8]

- No deploy or hosting: the website runs only locally. [Q8]
- No big-model training: no full fine-tuning of the 1.7B model, and no bf16 LoRA on models of 3B and up. [Q8]
- Only what Nico's PC can do: no rented hardware and no big models. [Q8]
- Reporting stays light: `results.md` is the only written report, alongside the run log and the check questions. [Q7] [Q10]

## Assumptions & Open Questions

None.
