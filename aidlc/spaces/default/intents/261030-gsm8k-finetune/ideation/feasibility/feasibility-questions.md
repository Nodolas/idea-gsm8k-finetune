# Feasibility & Constraints — Questions

Context: the approved intent statement (`ideation/intent-capture/intent-statement.md`) sets learning first, you alone, success as any measurable gain over the model's own baseline, no deploy, no big-model training, and only what this PC can do. These questions pin down the constraints that decide what is technically feasible.

## Q1. [Product] What is the money budget?

A. €0: this PC's GPU, free datasets and open models only; no rented compute, no accounts, no API keys, no paid services
B. A small budget for something specific (name it under Other)
C. Not yet defined
X. Other (please specify)

[Answer]: A. €0

## Q2. [Product] Is there a timeline?

A. No deadline: the pace is set by the long runs you start in your terminal (a reinforcement-learning run can take several hours)
B. A target of a few weeks (say how many under Other)
C. Not yet defined
X. Other (please specify)

[Answer]: X. Other: "I want it to kick off the runs via the dashboard"

## Q3. [Developer] How long may a single training or evaluation run take on this PC?

This decides model size. On this 8 GB GPU, reinforcement learning (GRPO) on the 1.7B model is estimated at 5–7 hours per run, on the 0.6B model 3–4 hours; a full test-set evaluation 15–40 minutes. These are estimates from similar GPUs, not measured yet.

A. Overnight is fine: up to about 8 hours per run
B. Up to about 3 hours per run (likely forces the 0.6B model for reinforcement learning)
C. Under about 1 hour per run (small models and short runs only)
D. Not yet defined
X. Other (please specify)

[Answer]: B. Up to about 3 hours per run

## Q4. [Developer] Is the PC free while a long run trains?

If you use the PC for other things during a run (desktop work, games), the GPU memory is shared and runs need to survive a pause or crash by resuming from a checkpoint.

A. Mostly free: I leave it alone while long runs train
B. Shared: I keep using it, so runs must be able to resume from a saved checkpoint
C. Not yet defined
X. Other (please specify)

[Answer]: A. Mostly free

## Q5. [Developer] What is your skill profile for the parts outside Python?

The plan includes a local website (React with TypeScript). This decides how much of the website you need to understand versus only use.

A. Python yes, new to LLM training, little or no React: Claude writes the website and you mainly use it; the learning focus stays on training
B. Comfortable with both Python and React: you want to understand the website code too
C. Python only, and keep the website as small as possible
D. Not yet defined
X. Other (please specify)

[Answer]: B. Comfortable with both Python and React

## Q6. [Compliance] Which licence and data rules must the project respect?

No regulation applies to a personal project, but models, datasets and pasted code carry licences.

A. Use only models and data whose licences allow personal fine-tuning (the planned ones are Apache-2.0 models and the MIT-licensed GSM8K). Use the CC-BY-SA GSM-Plus and the NonCommercial-NoDerivatives GSM-Symbolic for evaluation only, never for training. The pasted 21st.dev component names no licence: you confirm its author allows this use, or it is rewritten from scratch
B. Option A, but drop the pasted 21st.dev component now and build the headline from scratch
C. No licence checks needed
D. Not yet defined
X. Other (please specify)

[Answer]: A. Open licences that allow personal fine-tuning; GSM-Plus and GSM-Symbolic for evaluation only; you confirm the pasted component's licence or it is rewritten

## Q7. [Developer] What must the project integrate with?

A. Nothing outside this PC: a Python environment and Node inside the project folder, the local GPU, and public downloads that need no login or token (Hugging Face, npm)
B. Also an external service (name it under Other)
C. Not applicable
X. Other (please specify)

[Answer]: A. Nothing outside this PC

## Q8. [Product] Follow-up to Q2: is there a deadline?

Your Q2 answer, "I want it to kick off the runs via the dashboard", is recorded as a wish for the website (start runs from the dashboard). The timeline itself is still open.

A. No deadline: the pace is set by how long the runs take
B. A target of a few weeks (say how many under Other)
C. Not yet defined
X. Other (please specify)

[Answer]: A. No deadline

## Q9. [Developer] Follow-up to Q3: how should the 3-hour cap shape the model plan?

With runs capped at about 3 hours (Q3), reinforcement learning (GRPO) on the 1.7B model (estimated 5–7 hours for about 300 steps) does not fit; on the 0.6B model (estimated 3–4 hours) it is borderline. Supervised fine-tuning on the 1.7B model (estimated 20–60 minutes) fits.

A. Mixed: supervised fine-tuning and evaluation on the 1.7B model; reinforcement learning on the 0.6B model, with step counts cut to fit 3 hours
B. Everything on the 0.6B model: more headroom to improve, every run fits comfortably
C. Keep the 1.7B model for everything, cutting reinforcement-learning steps to fit 3 hours (smaller expected gain)
D. Not yet defined: measure real run times in the first step, then decide
X. Other (please specify)

[Answer]: D. Measure real run times in the first step, then decide

## Consolidated Summary Confirmation

- Budget: €0; this PC's GPU, free datasets and open models only (Q1).
- Timeline: no deadline (Q8).
- Website wish: start runs from the dashboard, in your words "I want it to kick off the runs via the dashboard" (Q2).
- Run length: up to about 3 hours per run (Q3); the PC is mostly free while a run trains (Q4).
- Model plan: measure real run times in the first step, then decide how the 3-hour cap shapes model size (Q9).
- Skills: comfortable with Python and React; new to training LLMs (Q5).
- Licences: only models and data that allow personal fine-tuning; GSM-Plus and GSM-Symbolic for evaluation only; you confirm the pasted 21st.dev component's licence, or it is rewritten (Q6).
- Integration: nothing outside this PC; public downloads with no login or token (Q7).

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
