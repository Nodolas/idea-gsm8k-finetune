# Intent Capture & Framing — Questions

## Sources

- [desc] Initial description: "Fine tune model for grade math: build it from the brief in inception/brief.md"
- [scope] Workflow-selected scope: `mvp`.

The options below are drawn from the brief at `inception/brief.md`. Nothing from the brief counts as decided until you pick it here.

## Q1. [Product] What problem is this work solving?

The brief describes both a learning goal and a score goal; this settles which one leads when they pull apart (for example, a run that would teach a lot but is unlikely to raise the score).

A. Learning first: understand and do every step of post-training a small open base model on grade-school math on this PC (baseline eval, LoRA SFT, GRPO, tuning the dials), and see each run while it trains
B. Score first: get the highest GSM8K score this PC can reach; understanding each step is secondary
C. Both equally: learn every step, and push the score as high as possible with the tuning loop (Optuna plus the proposer and reviewer agents)
D. Not yet defined
X. Other (please specify)

[Answer]: A. Learning first

## Q2. [Product] Who is this for?

This decides how polished the website and the write-up need to be.

A. Only you (Nico): a personal learning project in a private repo
B. You, plus a few people you may show the results to (the local website and `results.md`)
C. Not identified
X. Other (please specify)

[Answer]: A. Only you (Nico)

## Q3. [Product] What does success look like?

The brief proposes a done-when; this confirms it or replaces it.

A. The brief's done-when: the best tuned `Qwen/Qwen3-1.7B-Base` checkpoint scores at least 5 points above that model's own baseline on the full GSM8K test split (1,319 problems) under one fixed eval protocol, its GSM-Plus testmini accuracy does not fall below the baseline's, and `results.md` explains what moved the number and why
B. Option A, plus a learning check: you can answer one or two check questions after each unit
C. An absolute target instead (for example at least 80% on the GSM8K test split), whatever the baseline is
D. Not yet defined
X. Other (please specify)

[Answer]: X. Other: "Once I have started to improve the results"

## Q4. [Product] Why now?

A. Personal learning goal; small open base models and free tools (TRL, Unsloth, Optuna) now make SFT and GRPO feasible on an 8 GB consumer GPU at no cost
B. Preparation for a job, course or another project that needs these skills
C. Not applicable
X. Other (please specify)

[Answer]: A. Personal learning goal, now feasible

## Q5. [Product] Who are the stakeholders, and what does each care about?

A. You alone: learner and owner; you care about understanding each step, seeing training live, and a better score. Claude builds as your assistant and is not a stakeholder
B. You, plus others who will look at the results (name them under Other)
C. Not identified
X. Other (please specify)

[Answer]: A. You alone

## Q6. [Product] Who decides scope and priority?

A. You alone, through your answers and approvals in this workflow and the gate labels on the factory ticket
B. You, with input from someone else (name them under Other)
C. Not yet defined
X. Other (please specify)

[Answer]: A. You alone

## Q7. [Product] How should progress be reported?

A. A comment on the factory ticket at the end of each build run, every long run logged as a row in `results/runs.csv`, one or two check questions after each unit, and `results.md` at the end
B. Only `results.md` at the end
C. None
X. Other (please specify)

[Answer]: B. Only `results.md` at the end

## Q8. [Product] What should this first version leave out? (select all that apply)

The plan is already `mvp`; this asks only what the product itself should not do yet.

A. Any deploy or hosting: the website runs only locally
B. Anything that needs money, an account or an API key (rented GPUs, W&B, installing from the 21st.dev registry), and any LLM call from inside the app: the tuning agents run only as Claude Code helpers in a session
C. Full fine-tuning of the 1.7B model, and bf16 LoRA on models of 3B and up
D. Training on GSM-Plus or GSM-Symbolic, and tuning on the GSM8K test split
E. None of these
X. Other (please specify)

[Answer]: A, C, and X. Other: "And it’s very important that this project is a personal project just for me to learn how to fine tune and not more more. Only what my pc is Calle in Oder to fine tune. No rented hardware not big models etc"

## Q9. [Product] Follow-up to Q3: what counts as "started to improve the results"?

You answered Q3 with "Once I have started to improve the results". Done needs a number to check against; on 1,319 test problems a gain under about 3 points can be noise (about ±2.5 points at 95%).

A. Clearly above noise: the best tuned checkpoint beats its own baseline by at least 3 points on the full GSM8K test split, under the same fixed eval protocol
B. The brief's bar: at least 5 points above its own baseline on the full GSM8K test split
C. Any measurable gain: the best tuned checkpoint scores higher than its own baseline on the full GSM8K test split, however small, and `results.md` says whether the gain is within noise
D. Not yet defined
X. Other (please specify)

[Answer]: C. Any measurable gain

## Q10. [Product] Follow-up to Q7: does "Only results.md" drop the run log and the check questions?

You chose "Only `results.md` at the end" for reporting (Q7). Your ticket also says "Log every run (W&B or a simple CSV) and compare against the baseline" and "quiz me briefly at the end of each one". The planned highest-scores page also reads its ranking from a run log.

A. Keep a run log (`results/runs.csv`, which the website reads) and the short check questions after each step; `results.md` is the only written report
B. Keep the run log, drop the check questions; `results.md` is the only written report
C. Drop both: only `results.md` (the highest-scores page would then need another source)
D. Not yet defined
X. Other (please specify)

[Answer]: A. Keep the run log and the check questions; `results.md` is the only written report

## Consolidated Summary Confirmation

- Problem: learning comes first. You understand and do every step of post-training a small open base model on grade-school math on this PC, and see each run while it trains (Q1).
- Audience: only you; a personal learning project in a private repo (Q2).
- Success: any measurable gain. The best tuned checkpoint scores higher than its own baseline on the full GSM8K test split, however small, and `results.md` says whether the gain is within noise (Q3, Q9).
- Why now: a personal learning goal that small open base models and free tools now make feasible on an 8 GB consumer GPU at no cost (Q4).
- Stakeholders and decisions: you alone (Q5, Q6).
- Reporting: `results.md` is the only written report, with a run log (`results/runs.csv`, which the website reads) and short check questions after each step (Q7, Q10).
- Left out of this first version: any deploy (the website runs only locally), and big-model training (no full fine-tuning of 1.7B, no bf16 LoRA at 3B and up). In your words: "it's very important that this project is a personal project just for me to learn how to fine tune and not more more. Only what my pc is Calle in Oder to fine tune. No rented hardware not big models etc" (Q8).

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
