# Feasibility Assessment: Fine tune model for grade math

Upstream: `ideation/intent-capture/intent-statement.md` (learning first, Nico alone, success = any measurable gain over the model's own baseline on the full GSM8K test split, no deploy, no big-model training, only what this PC can do). Answers: `feasibility-questions.md` Q1–Q9. No market research ran for this workflow.

## Verdict

**Feasible, with one open sizing question.** Every part of the intent fits a €0 budget and this single PC (Q1, Q7). The open question is model size under the 3-hour run cap (Q3). It is settled by measuring real run times in the first step, not by estimate (Q9).

## Technical Viability

| Capability | Feasible? | Basis | Confidence |
|---|---|---|---|
| Evaluating a small open base model on GSM8K on this PC | Yes | 8 GB GPU; small models (0.6B–1.7B parameters) fit for inference; a full test pass is estimated at 15–40 minutes | Medium: estimate from similar GPUs, not measured [hypothesis] |
| Supervised fine-tuning with LoRA on the 1.7B model within 3 hours | Likely | Estimated 20–60 minutes per epoch | Medium [hypothesis] |
| Reinforcement learning (GRPO) within 3 hours | Uncertain | Estimated 5–7 h for ~300 steps at 1.7B and 3–4 h at 0.6B: over or at the cap (Q3). Fewer steps or the smaller model would fit | Low until measured (Q9) |
| Live training view and run log in a local website | Yes | Local web stack; Nico is comfortable with React (Q5); no hosting (intent) | High |
| Starting runs from the dashboard (Q2) | Yes, with care | A local server can launch a training process on this PC. The process must outlive the browser tab, write its own log, and refuse to start a second GPU run while one is active | Medium: design detail for later stages |
| Tuning loop (proposals checked by a reviewer) | Yes | Short proxy runs on a small sample fit well under the cap | Medium |

## Key Findings

- **The 3-hour cap is the binding constraint**, not money or VRAM (Q3). The plan should measure real step times before committing to the reinforcement-learning model size (Q9).
- **The PC is mostly free during runs** (Q4), so resuming after an interruption is a nice-to-have, not a requirement.
- **Licences allow the planned use.** The planned models are Apache-2.0 and GSM8K is MIT. GSM-Plus (CC-BY-SA) and GSM-Symbolic (NonCommercial, NoDerivatives) are for evaluation only (Q6). One item is unresolved: the pasted 21st.dev component names no licence (Q6).
- **No external integration**: public downloads with no login or token only (Q7). There is no cloud account, so no cloud landscape assessment applies.
- **"Any measurable gain" is reachable but can sit inside noise.** About ±2.5 points at 95% on 1,319 test problems (intent-statement.md, success metrics). The write-up must say which.

## Recommendation

Proceed to scope definition. Make the first unit of work measure real evaluation and training step times on this PC. Its numbers decide which model reinforcement learning uses under the 3-hour cap (Q3, Q9).

## Assumptions & Open Questions

- [assumption] The VRAM and time estimates (from 8–12 GB GPUs in public reports) hold within about 2x on this RTX 3060 Ti. Checked by the first measurement step.
- [assumption] Nico confirms the pasted 21st.dev component's licence allows this use before the website is built; otherwise the headline is rewritten from scratch (Q6).
