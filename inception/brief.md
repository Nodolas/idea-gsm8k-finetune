# Brief: Fine tune model for grade math

Ticket https://github.com/Nodolas/idea-factory/issues/6. Written by `/build` before any requirement (charter rules 1 and 2; a learning project: CHARTER "Learning projects"), at most one page. Every market, model or dataset claim names its source under Sources. The prompts in comments adapt AI-DLC's intent-capture and market-research question lists (awslabs/aidlc-workflows 2.11.1, MIT-0) and the factory's v1 notes. Fill each section below its prompt; AI-DLC reads this file at Intent Capture.

<!-- Which sections: a product fills Problem through Assumptions, then Sources. A learning project (STATE.md track: "learning") fills Goal and done-when through Risks, then Sources. /build deletes the set it does not use. -->

## Idea (verbatim)
<!-- Nico's words from the ticket, copied by kickoff. Never edit this section. -->
GOAL
I want to fine-tune a small open model on grade-school math (GSM8K) as a
hands-on learning project. Help me (1) pick the best base model to fine-tune,
(2) run SFT and then RL, and (3) understand every step. Teach first, then build.

MY SETUP
- Hardware: [e.g. 1× 16–24 GB GPU / Colab / rented H100 — fill in]
- Budget: [€ amount]   Time: [weeks]
- Level: comfortable with Python, new to training LLMs

REPOS TO USE (verify each is current before relying on it)
Data
- openai/grade-school-math — GSM8K source (HF dataset: openai/gsm8k).
  7.5k train / 1.3k test, answers end in "#### <number>" (easy to grade).
Learning / reference implementation
- karpathy/nanochat — minimal, readable pipeline incl. SFT and a ~300-line
  GRPO-style RL loop on GSM8K (scripts/chat_rl.py). Read this first to
  understand the mechanics.
Fine-tuning on my own hardware
- huggingface/trl — SFTTrainer and GRPOTrainer
- unslothai/unsloth — LoRA/QLoRA + GRPO on a single GPU, Colab notebooks
Evaluation
- EleutherAI/lm-evaluation-harness — standard GSM8K eval (gsm8k, gsm8k_cot)
Optional deep-dive
- Jiayi-Pan/TinyZero — small-scale RL that shows reasoning emerging
- TinyGSM paper (Microsoft, 2023) — 1.3B model hit ~80% on GSM8K via
  synthetic data + a verifier

MODEL SELECTION (step 1, don't skip)
Shortlist small *base* (not instruct) models, roughly 0.5B–4B, e.g. the
current Qwen small models, Llama 3.2 1B/3B, Gemma (latest small), SmolLM3-3B,
Phi-4-mini. Check what's newest as of today.
For each: GSM8K score of the base model, license, VRAM for LoRA/full FT,
tooling support in TRL/Unsloth.
Important: many modern models already score 80–95% on GSM8K, partly from
data contamination. Pick a model with room to improve so I can actually see
the effect of my training. Also test on GSM-Symbolic or GSM-Plus to check
for real generalization.

LEARNING PATH
1. Baseline: evaluate 2–3 candidate models zero-shot and few-shot
2. Read nanochat's SFT + RL code with me; explain each part
3. SFT with LoRA on GSM8K train → re-evaluate
4. RL with GRPO (reward = correct final number) → re-evaluate
5. Ablations: LoRA vs full FT, with/without CoT, number of samples
   per problem, and adding a Python calculator tool
6. Write-up: what moved accuracy and why

HOW TO WORK WITH ME
- Explain the "why" before each step; quiz me briefly at the end of each one
- Log every run (W&B or a simple CSV) and compare against the baseline
- Never evaluate on test data during training; use a held-out split of train

## Problem
<!-- What problem does this solve, and for whom? What pain do they feel today?
How do people cope today: tools, workarounds, time or money spent?
The smallest useful first version, and what it leaves out. -->

## User
<!-- Who has the problem: only Nico, family, a group, or paying customers? Who is the early adopter?
How exactly do we reach the first 20 (channel, place, person)? -->

## Value case
<!-- Who pays: the budget owner, and roughly how much.
Why now: the trigger (market shift, new technology, regulation, a cost drop).
What it replaces: competing products and open-source alternatives, with strengths, weaknesses and pricing;
table stakes versus differentiators; build, buy or partner. Evidence level now: L0-L5, as in the ticket record. -->
- Who pays:
- Why now:
- What it replaces:
- Evidence now:

## Data loop
<!-- Signal captured (a person's ground truth, or model output) -> how the product improves (rules, then
aggregates, then examples from accepted outputs) -> the loop metric, plus a counter-metric.
Does one user's data improve the product for others? What does it do with zero data?
Personal data kept, why, and for how long. This becomes the requirement tagged (loop). -->

## Test of interest
<!-- Set before any deploy. A free first deploy on workers.dev (rule 9): fake door, waitlist, demo video
or concierge test; no live Claude calls. deploy/plan.md takes the metric, threshold and deadline from here. -->
- Hypothesis: At least <X>% of <Y> will <Z> within <T>.
- Metric, threshold, deadline:
- Kill: If by <date> <state>, we stop.

## Assumptions
<!-- Each tagged [assumption], riskiest first; start with the ticket record's riskiest_assumption. -->

## Goal and done-when
<!-- Learning. What Nico wants to understand and be able to do at the end. Done-when: a measurable result
(metric, threshold, data split) and the baseline it is compared with. -->

## What to learn
<!-- Learning. The concepts and skills, in the order the units teach them; what Nico knows already. -->

## Hardware fit on this PC
<!-- Learning. GPU, VRAM and RAM from `nvidia-smi --query-gpu=name,memory.total --format=csv,noheader` and `free -g`.
Per planned run: model size, method (full, LoRA or QLoRA), precision, sequence length, batch size, estimated VRAM
and time; disk space for models, datasets and checkpoints. What does not fit, and the fallback. -->

## Models and datasets with licences
<!-- Learning. One line each: name, size, licence and whether it allows this use, downloads without an account
or token (rule 4), published score on the done-when metric, source. Downloads stay inside the folder (.cache/). -->

## Evaluation plan
<!-- Learning. The metric and how it is computed; the splits (the test set is never used during training: tune
on a held-out part of train); baselines; a check for real generalisation; sample counts; how a quick test checks
the same code on a tiny sample. Quick tests write their rows to a temp path; only a long run Nico starts appends one row to `results/runs.csv` (run_id = an attempt id `<base id>-<n>`). -->

## Learning path
<!-- Learning. Ordered steps, each a likely unit: what it builds, what it teaches, the number it should move, and
whether a run takes over about 10 minutes (then Nico runs it in a Mint terminal). -->

## Risks
<!-- Learning. Each tagged [assumption], riskiest first; start with the ticket record's riskiest_assumption.
Also: data contamination of the base model, VRAM, run time, licences. -->

## Sources
<!-- One line per source: the claim, the link, the date read. -->
