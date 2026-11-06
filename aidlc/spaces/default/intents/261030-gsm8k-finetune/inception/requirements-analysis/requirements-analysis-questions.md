# Requirements Analysis — Questions

Context: the request is "Fine tune model for grade math: build it from the brief in inception/brief.md". The brief, the intent statement, the feasibility work, the scope (must-have: evaluation and baseline, supervised fine-tuning, the three-page website with start button, the generalisation check, `results.md`; could-have: reinforcement learning, tuning loop, ablations) and the affirmed practices are settled and not asked again. These questions close the gaps that decide testable requirements.

## Q1. [Quality] Which evaluation protocol scores every model?

Every number is only comparable if it is computed the same way.

A. The brief's protocol: the same 4-shot prompt (exemplars from the held-out dev split), greedy decoding, up to 512 new tokens; the answer is taken from `#### <number>` with a fallback to the last number, commas stripped, compared numerically; plus one cross-check with the standard lm-evaluation-harness `gsm8k` task on the baseline and the final model
B. As A, without the lm-evaluation-harness cross-check
C. Zero-shot instead of 4-shot
D. Not yet defined
X. Other (please specify)

[Answer]: A. The brief's 4-shot protocol plus one lm-evaluation-harness cross-check on baseline and final

## Q2. [Quality] How large is the held-out dev split taken from the training data?

All tuning and every dial decision use this split; the test split is scored only for finalists.

A. 500 problems held out with a fixed seed (about 6,973 left for training)
B. 1,000 problems (about 6,473 left for training)
C. 250 problems (faster dev evaluation, noisier)
D. Not yet defined
X. Other (please specify)

[Answer]: A. 500 problems held out with a fixed seed

## Q3. [Product] Which dials does the training page offer for supervised fine-tuning?

A. Model (0.6B or 1.7B), learning rate, epochs, LoRA rank and alpha, max sequence length, and number of training examples
B. As A, plus batch size, warmup, random seed and answer format (step-by-step versus terse)
C. Only model, learning rate and epochs
D. Not yet defined
X. Other (please specify)

[Answer]: B. Standard set plus batch size, warmup, random seed and answer format

## Q4. [Product] Which runs may the website start?

A. Training runs and dev-split evaluations; a test-split evaluation only for a run you mark as a finalist, with a second confirmation
B. Training runs only; every evaluation runs from the terminal
C. Any run, including test-split evaluations, with no extra step
D. Not yet defined
X. Other (please specify)

[Answer]: A. Training runs and dev-split evaluations; test-split evaluation only for a finalist, with a second confirmation

## Q5. [Quality] How is the generalisation check judged?

It scores the baseline and the final model on reworded problems (GSM-Plus testmini, about 2,400, and GSM-Symbolic p1, about 5,000).

A. Report only: both sets are scored and the results go in `results.md`, with no pass or fail
B. The final model must not score below the baseline on GSM-Plus testmini (the brief's check); GSM-Symbolic is reported only
C. GSM-Plus testmini only, report only
D. Not yet defined
X. Other (please specify)

[Answer]: A. Report only

## Q6. [Product] Is the pasted 21st.dev halftone component cleared for use?

Its source names no licence.

A. Yes: I confirm its author allows this personal use; adapt it as the landing headline
B. Not yet: build the rest first and decide before the website is built; a plain text headline stands in until then
C. No: write the halftone headline from scratch
D. Not yet defined
X. Other (please specify)

[Answer]: A. Yes: cleared for this personal use; adapt it as the landing headline

## Consolidated Summary Confirmation

- Evaluation protocol: the same 4-shot prompt (exemplars from the dev split), greedy decoding, up to 512 new tokens, answer from `#### <number>` with a last-number fallback, compared numerically; plus one lm-evaluation-harness `gsm8k` cross-check on the baseline and the final model (Q1).
- Dev split: 500 problems held out from training with a fixed seed; about 6,973 left for training (Q2).
- Training-page dials for supervised fine-tuning: model (0.6B or 1.7B), learning rate, epochs, LoRA rank and alpha, max sequence length, number of training examples, batch size, warmup, random seed, and answer format (step-by-step versus terse) (Q3).
- Website-startable runs: training runs and dev-split evaluations; a test-split evaluation only for a run marked as a finalist, with a second confirmation (Q4).
- Generalisation check: GSM-Plus testmini and GSM-Symbolic p1 scored on baseline and final model, report only, no pass or fail (Q5).
- Halftone component: you confirm its author allows this personal use; it is adapted as the landing headline (Q6).

Does this all look correct before I generate the requirements artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
