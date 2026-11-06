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

## Goal and done-when
<!-- Learning. What Nico wants to understand and be able to do at the end. Done-when: a measurable result
(metric, threshold, data split) and the baseline it is compared with. -->
Nico wants to understand and do every step of post-training a small open base model on grade-school math, on this PC: baseline eval, LoRA SFT, GRPO, and tuning the dials. He also wants to see each run while it trains.

Added by Nico in session, 2026-10-30 (his words, summarised):
- A front end that shows training live.
- Dials he can tweak to get a better score.
- Two agents, one proposing changes and one reviewing them, that push the score up across the whole pipeline.
- Scoring against an answer test set.
- Installing Node is OK.
- The website has three pages: a landing page with a halftone wordmark headline, a highest-scores page and a training page (`inputs/website-request.md`).
- For the 21st.dev look, Nico provides screenshots and pasted component source himself (`inputs/`).

What the charter changes in that request:
- Agents never install from the 21st.dev registry or use its Magic MCP, because both need a 21st.dev API key and account (rule 4).
- The UI is built on shadcn/ui (MIT; 21st.dev's components are built on it). It matches Nico's screenshots and adapts the component source he pasted into `inputs/`.
- The agents are Claude subagents in a build session. Nothing calls an LLM API from inside the app.
- Tuning uses a held-out dev split of train, never the test set.

Done-when (Nico, 2026-10-30: "any measurable gain", intent-capture Q3 and Q9, answer C; generalisation "report only", requirements Q5, answer A):
- The best tuned checkpoint of `Qwen/Qwen3-1.7B-Base` (SFT and/or GRPO) scores **higher than that model's own baseline**, however small the gain, on the full GSM8K test split (1,319 problems), under the same fixed eval protocol (Evaluation plan). `results.md` says whether the gain is within noise (FR6.2).
- GSM-Plus testmini and GSM-Symbolic p1 are scored on the baseline and the final model and reported with no pass or fail (FR5.1).
- `results.md` explains what moved the number and why.

## What to learn
<!-- Learning. The concepts and skills, in the order the units teach them; what Nico knows already. -->
Nico knows Python and is new to training LLMs. Order:
1. Tokens, prompts and greedy decoding; how a base model is evaluated (few-shot, answer extraction, exact match); why test-set hygiene and contamination matter.
2. SFT: the loss on completions only, LoRA (rank, alpha, target modules), learning rate and epochs, gradient checkpointing, and bf16 versus 4-bit.
3. Watching training: what loss, reward, KL and completion length curves say, and spotting divergence or reward hacking early.
4. GRPO, read alongside nanochat's `scripts/chat_rl.py`: group sampling, advantage as reward minus the group mean, the KL `beta`, the clipping `epsilon`, `num_generations` and temperature.
5. Hyperparameter search: proxy runs, Optuna's TPE sampler, why to change one dial at a time, and noise between seeds.
6. Ablations and writing up: LoRA rank, CoT versus terse answers, samples per problem, and optionally a Python calculator tool.

## Hardware fit on this PC
<!-- Learning. GPU, VRAM and RAM from `nvidia-smi --query-gpu=name,memory.total --format=csv,noheader` and `free -g`.
Per planned run: model size, method (full, LoRA or QLoRA), precision, sequence length, batch size, estimated VRAM
and time; disk space for models, datasets and checkpoints. What does not fit, and the fallback. -->
**PC:** NVIDIA GeForce RTX 3060 Ti, 8,192 MiB VRAM (Ampere, bf16), 31 GB RAM, about 164 GB free disk. All times and VRAM below are estimates from similar 8–12 GB GPUs [assumption]; unit 1 measures them.

| Run | Model | Method | Seq len, batch | VRAM est. | Time est. | Who runs it |
|---|---|---|---|---|---|---|
| Full test eval | 1.7B / 0.6B | bf16, greedy, HF generate | 512 new tokens, batch 8–16 | ~5 / ~2 GB | 15–40 min | detached long run ([manual]) |
| SFT, 1 epoch of 7.0k | 1.7B | bf16 LoRA r16–32, all linear layers | 512, micro-batch 4, grad accum 4, grad ckpt | ~6–7 GB | 20–60 min | detached long run |
| GRPO, ~300 steps | 1.7B | bf16 LoRA r1–16, beta 0, 8 generations | 384–512 completion | ~7–8 GB (tight) | ~60–90 s/step, 5–7 h: over the 3 h cap, so steps are cut to fit | detached long run |
| GRPO, ~300 steps | 0.6B | bf16 LoRA | 384–512 | ~4–5 GB | ~30–45 s/step, 3–4 h: steps cut to fit 3 h | detached long run |
| Tuning proxy trial | 0.6B | SFT or GRPO on 100–200 train, 200 dev | as above | ~4 GB | under 10 min | inside the detached Optuna study (the agents only propose runs) |
| Quick tests | 0.6B on the CPU, or tiny fixtures | 3 dev problems (skeleton), else fixtures or mocks | up to 256 new tokens | CPU only | minutes | session, on the CPU |

- **Run cap (Nico, 2026-10-30: feasibility Q3, answer B; Q9, answer D):** every run takes up to about 3 hours. Real step times are measured first, then GRPO's step count (and model size) is set so a run fits the cap (NFR2, FR7.1).
- **Who runs it:** a detached long run is started by the `/build` lead with `scripts/run-detached.sh` (one GPU run at a time) or by Nico from the website; Nico never types a command in a terminal (inception/changes.md, 2026-10-31).
- **Doesn't fit:** full fine-tuning of 1.7B; bf16 LoRA at 3B and up; vLLM colocated with 1.7B GRPO [assumption].
- **Fallback:** GRPO on `Qwen3-0.6B-Base`; QLoRA 4-bit for `SmolLM3-3B-Base`; fewer generations or shorter completions.
- **Disk:** under 30 GB for models (~4.5 GB for 1.7B and ~1.5 GB for 0.6B in bf16), datasets, adapters and logs, all under `.cache/`, `checkpoints/` and `outputs/`.
- **Node.js** (LTS, for the dashboard): unpacked from the official tarball into `.tools/node/` (gitignored), with npm's cache in `.cache/npm`. That keeps it inside the folder (rules 7 and 8) and needs no sudo.

## Models and datasets with licences
<!-- Learning. One line each: name, size, licence and whether it allows this use, downloads without an account
or token (rule 4), published score on the done-when metric, source. Downloads stay inside the folder (.cache/). -->
- **`Qwen/Qwen3-1.7B-Base` (primary):** 1.72B params, Apache-2.0 (fine-tuning and publishing allowed), not gated (no token). GSM8K 75.44 (4-shot CoT, Qwen3 report); 65.88 (5-shot, SmolLM3 table).
- **`Qwen/Qwen3-0.6B-Base` (fast model for tests and tuning proxies, GRPO fallback):** 0.6B, Apache-2.0, not gated. GSM8K 59.59 (4-shot CoT).
- **`HuggingFaceTB/SmolLM3-3B-Base` (optional second family, QLoRA):** 3B, Apache-2.0, not gated. GSM8K 67.63 (5-shot).
- **Excluded:**
  - Llama 3.2 (gated, needs an account).
  - Phi-4-mini (no base checkpoint).
  - Gemma 4 E2B (5.1B params in memory).
  - Qwen3.5 small (multimodal hybrid architecture, no vLLM, no published GSM8K score).
- **`openai/gsm8k`, config `main`:** 7,473 train and 1,319 test, MIT, not gated. Answers end in `#### <number>`.
- **`qintongli/GSM-Plus`, testmini (~2.4k):** CC-BY-SA-4.0, not gated. Eval only.
- **`apple/GSM-Symbolic`, p1:** CC-BY-NC-ND-4.0, not gated. Eval only: never trained on and never redistributed modified. Its rows ask to be kept out of training data.
- **Tools, all free with no account:**
  - TRL 1.17 (SFTTrainer, GRPOTrainer), Apache-2.0
  - PEFT
  - Unsloth 2026.10 (optional), Apache-2.0 core
  - lm-evaluation-harness 0.4.13, MIT, for one cross-check
  - Optuna 5.0, MIT, local SQLite
  - FastAPI
  - shadcn/ui charts (Recharts), MIT
- **UI design input:** the 21st.dev "Halftone Wordmark Footer" (React plus TypeScript, no npm dependencies beyond React), pasted by Nico into `inputs/halftone-wordmark-footer.tsx.txt`; its licence is not stated, and Nico cleared it for this personal use (Risks 8). Nico's design screenshots go to `inputs/design/`.
- **Avoided:** W&B and installs from the 21st.dev registry (both need an account), and nanochat's training stack (read only, as a reference).

## Evaluation plan
<!-- Learning. The metric and how it is computed; the splits (the test set is never used during training: tune
on a held-out part of train); baselines; a check for real generalisation; sample counts; how a quick test checks
the same code on a tiny sample. Quick tests write their rows to a temp path; only a long run (started detached by the `/build` lead, or by Nico from the website) appends one row to `results/runs.csv` (run_id = an attempt id `<base id>-<n>`). -->
- **Metric:** exact-match accuracy of the final number. The prediction is taken from `#### <n>`, with a fallback to the last number in the output; commas are stripped and values compared numerically. The gold answer comes from GSM8K's `####` line.
- **One fixed protocol for every checkpoint:** the same 4-shot prompt (fixed exemplars from train-dev), greedy decoding, 512 max new tokens.
- **Cross-check:** lm-eval `gsm8k` 5-shot flexible-extract, run once on the baseline and once on the final model.
- **Splits:**
  - **train-dev:** 500 problems held out from train (fixed seed). It is the only split used for tuning, early stopping and every dial or agent decision.
  - **train-fit:** the remaining ~6,973 problems, used for training.
  - **test:** the 1,319 test problems, scored once per finalist: the baseline, the best SFT, the best GRPO and the final model. Never inside a training or tuning loop.
- **Baselines:** the 0.6B and 1.7B base models under the same protocol.
- **Generalisation:** GSM-Plus testmini and GSM-Symbolic p1 on the baseline and the final model.
- **Noise:** 1,319 problems give a 95% confidence interval of about ±2.5 points. A gain under ~3 points is reported as noise.
- **Run log:** `results/runs.csv`, columns `date,run_id,model,method,data,metric,value,minutes` plus the config hash. Only long runs append to it (started detached by the `/build` lead, or by Nico from the website), each with run_id `<base id>-<n>` passed as `--run-id`. Quick tests run on the CPU (`scripts/in-env.sh` hides the GPU): the skeleton test runs the same code with the 0.6B model on 3 dev problems, other tests use tiny fixtures or mocks, and all write their rows to a temp path. GPU use is first proven by the first detached long run, the 0.6B baseline evaluation.

## Learning path
<!-- Learning. Ordered steps, each a likely unit: what it builds, what it teaches, the number it should move, and
whether a run takes over about 10 minutes (then it is a detached long run, never in a session's foreground). -->
1. **Data and eval harness.** Builds the GSM8K splits, the answer extractor, the evaluator and the `runs.csv` writer.
   - Teaches: evaluation and contamination.
   - Number: the baselines for 0.6B and 1.7B on test and dev. The full runs are [manual], 15–40 min each.
2. **SFT with LoRA.** A TRL SFT script driven by a run config (the dials), with a metrics callback writing JSONL under `outputs/<run_id>/`.
   - Teaches: SFT and LoRA.
   - Number: dev, then test accuracy of the best SFT model. [manual], 20–60 min. SFT can lower accuracy (seen at 1.5B); that is a valid result.
3. **Results website with live training.** A local FastAPI server streams the JSONL over Server-Sent Events to a React app (Vite, TypeScript, Tailwind, shadcn/ui charts) with three pages:
   - **Landing:** a halftone wordmark headline, adapted from Nico's pasted component as a hero (no link columns).
   - **Highest scores:** the best runs from `runs.csv`, ranked, with side-by-side comparison.
   - **Training:** live curves (loss, learning rate, reward, KL, completion length, dev accuracy), per-run detail, and a dials panel that writes a validated run config and shows the exact command to start it.
   - The look follows Nico's screenshots in `inputs/design/` [assumption: he adds them before this unit's Code Generation].
   - Teaches: reading training curves.
   - Number: none; quick tests only.
   - Local only (`npm run dev`), never deployed, an add-on to `results.md`. The site may start training runs and dev evaluations, and a test evaluation only for a finalist after a second confirmation (Nico, 2026-10-30, requirements Q4).
4. **GRPO.** A TRL GRPOTrainer script: correctness reward plus a format reward, from base or from the best SFT model, with the same callback and config.
   - Teaches: RL from verifiable rewards, read alongside nanochat.
   - Number: dev, then test accuracy. [manual], up to about 3 h: the step count is sized from measured step times to fit the cap, on 0.6B if 1.7B cannot learn enough in 3 h (Nico, 2026-10-30: feasibility Q3 and Q9).
5. **Tuning loop.**
   - An Optuna study over proxy trials (0.6B, 100–200 train, scored on train-dev only, under 10 min each) with local SQLite. The study as a whole is [manual].
   - Two project agents: a proposer reads `runs.csv`, the study and the curves and writes the next run config with a reason; a reviewer checks it against the rules (dev only, VRAM fit, one main change, budget) and approves or sends it back.
   - Nico starts a round in a Claude Code session; the agents only propose and check, and the proposed run is started by Nico from the website or by the `/build` lead as a detached run.
   - Dials across the pipeline:
     - SFT: learning rate, epochs, LoRA rank and alpha, CoT versus terse targets.
     - GRPO: learning rate, `num_generations`, `beta`, temperature, `max_completion_length`, LoRA rank.
   - Number: the dev accuracy of the configs it proposes.
6. **Final runs, ablations and write-up.** The best config at 1.7B on test, the generalisation sets, and ablations. Then `results.md`.
   - Number: the done-when. [manual].

## Risks
<!-- Learning. Each tagged [assumption], riskiest first; start with the ticket record's riskiest_assumption.
Also: data contamination of the base model, VRAM, run time, licences. -->
1. [assumption] **Headroom:** the 1.7B base model has room for a measurable gain. Qwen3 base models may already have seen GSM8K-style data (contamination). Done-when is any measurable gain over the model's own baseline, labelled within or outside noise in `results.md` (Nico, 2026-10-30: intent-capture Q9, answer C); the generalisation sets are reported only (Nico, 2026-10-30: requirements Q5, answer A). Mitigations: report GSM-Plus and GSM-Symbolic, and keep 0.6B as a model with more headroom (the same done-when then applies to it).
2. [assumption] **GRPO at 1.7B fits 8 GB** with 8 generations and 384–512 tokens. Fallbacks: 4 generations, shorter completions, or GRPO on 0.6B.
3. [assumption] **Run times:** every run is capped at about 3 h (Nico, 2026-10-30: feasibility Q3, answer B), so GRPO gets only as many steps as fit (about 120–180 at 1.7B, 240–360 at 0.6B, from the estimates above); the assumption is that this is enough for GRPO to move the dev score. Real step times are measured before the plan is fixed (Q9, answer D). Tuning needs proxies small enough to stay under 10 min, and proxy rankings may not carry over to 1.7B.
4. **SFT on terse GSM8K answers can hurt accuracy** (seen at 1.5B). That's why GRPO from base is also tried.
5. **Reward hacking or format collapse in GRPO.** Mitigations: watch completion length and format reward on the dashboard, and spot-check samples.
6. **Licences:** GSM-Symbolic is NC-ND, so it is eval only. All models and training data allow this use.
7. **Agents overfitting the dev split** through many proposals. Mitigations: a budget of rounds, and test scored only for finalists.
8. **Licence of the pasted 21st.dev component:** its source names no licence. Cleared: Nico confirmed its author allows this personal use, and it is adapted as the landing headline, used only locally in this private repo (Nico, 2026-10-30: requirements Q6, "A. Yes: cleared for this personal use").

## Sources
<!-- One line per source: the claim, the link, the date read. -->
- Qwen3 base GSM8K (4-shot CoT: 0.6B 59.59, 1.7B 75.44, 4B 87.79): https://arxiv.org/html/2505.09388, read 2026-10-30
- Qwen3-1.7B-Base, Apache-2.0, not gated, 1.72B params: https://huggingface.co/api/models/Qwen/Qwen3-1.7B-Base, read 2026-10-30
- SmolLM3-3B-Base, Apache-2.0, GSM8K 5-shot 67.63 (Qwen3-1.7B-Base 65.88, Llama3.2-3B 25.92): https://huggingface.co/HuggingFaceTB/SmolLM3-3B-Base, read 2026-10-30
- Llama 3.2 is gated: https://huggingface.co/meta-llama/Llama-3.2-1B, read 2026-10-30
- Qwen3.5 small models, hybrid multimodal architecture, Unsloth VRAM and no-QLoRA advice: https://huggingface.co/Qwen/Qwen3.5-0.8B-Base and https://unsloth.ai/docs/models/qwen3.5/fine-tune, read 2026-10-30
- Gemma 4 E2B, 5.1B params with embeddings: https://huggingface.co/google/gemma-4-E2B, read 2026-10-30
- GSM8K, MIT, 7,473/1,319, not gated: https://huggingface.co/api/datasets/openai/gsm8k, read 2026-10-30
- GSM-Plus, CC-BY-SA-4.0, testmini: https://huggingface.co/datasets/qintongli/GSM-Plus, read 2026-10-30
- GSM-Symbolic, CC-BY-NC-ND-4.0, main/p1/p2: https://huggingface.co/datasets/apple/GSM-Symbolic, read 2026-10-30
- lm-eval 0.4.13 and its gsm8k task (5-shot, strict and flexible extract): https://pypi.org/project/lm-eval/ and https://raw.githubusercontent.com/EleutherAI/lm-evaluation-harness/main/lm_eval/tasks/gsm8k/gsm8k.yaml, read 2026-10-30
- nanochat `scripts/chat_rl.py` (16 samples per question, advantage as reward minus mean, no KL): https://raw.githubusercontent.com/karpathy/nanochat/master/scripts/chat_rl.py, read 2026-10-30
- TRL 1.17.1 and GRPOConfig defaults (num_generations 8, beta 0.0, max_completion_length 512): https://pypi.org/project/trl/ and https://huggingface.co/docs/trl/main/en/grpo_trainer, read 2026-10-30
- LoRA ranges (all linear layers, RL rank 1–32, LoRA learning rate about 10x full fine-tuning): https://huggingface.co/docs/trl/main/en/lora_without_regret, read 2026-10-30
- Unsloth 2026.10.11, GRPO about 5 GB for 1.5B and under, 300+ steps before reward rises: https://pypi.org/project/unsloth/ and https://unsloth.ai/docs/get-started/reinforcement-learning-rl-guide, read 2026-10-30
- GRPO on an 8 GB RTX 4060 Laptop, about 38 s/step at 0.5B: https://github.com/XXG666/grpo-reward-design, read 2026-10-30
- GRPO at 1.5B on 12 GB (65 s/step; SFT 59.67 below the 68.99 base; GRPO 74.37): https://github.com/hennyi-yin/llm-reasoning-grpo, read 2026-10-30
- Qwen2.5-0.5B SFT then GRPO, 35.0 to 47.7: https://github.com/JuaniLlaberia/slm-post-training, read 2026-10-30
- 21st.dev install needs an API key and has a paid plan: https://21st.dev/@shadcnspace/components/default.md and https://21st.dev/pricing.md, read 2026-10-30
- shadcn/ui charts (Recharts) and its MIT licence: https://ui.shadcn.com/docs/components/chart and https://raw.githubusercontent.com/shadcn-ui/ui/main/LICENSE.md, read 2026-10-30
- Trackio is local-first (not used; noted as an alternative): https://huggingface.co/docs/trackio/index, read 2026-10-30
- Nico's website request and the pasted Halftone Wordmark Footer source: `inputs/website-request.md` and `inputs/halftone-wordmark-footer.tsx.txt` (commit e8b7cfc), read 2026-10-30
- W&B needs an API key: https://docs.coreweave.com/models/quickstart, read 2026-10-30
- Optuna 5.0.0 (MIT) and optuna-dashboard: https://pypi.org/project/optuna/ and https://github.com/optuna/optuna-dashboard, read 2026-10-30
- Node.js LTS v26: https://nodejs.org/en/about/previous-releases, read 2026-10-30
