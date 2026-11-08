# batch-12: GRPO training (u7-grpo)

Branch `wip/batch-12`, built in the git worktree `.cache/worktrees/batch-12` (`node_modules`, `.venv`, `.tools` and `.cache/huggingface` are symlinks to the main tree: never install anything). `S` = `aidlc/spaces/default/intents/261030-gsm8k-finetune/inception`. Criteria: US7.1 in `S/user-stories/stories.md` (AC7.1.1–AC7.1.5) and AC12.4.4 (the course's GRPO run needs KL logged); design: `S/domain-design/components.md` (Training block, AnswerScoring rewards), ADR-005 in `S/domain-design/decisions.md` (one training block, shared run loop), contract C2 (`grpo_steps`, `grpo_generations`, metrics `reward`, `kl`, `answer_length`) in `S/contract-design/contract-summary.md`.

`test_command`: `scripts/check.sh`. In the worktree run single Python files as `PYTHONPATH=$PWD/src scripts/in-env.sh .venv/bin/python -m pytest -q tests/<file>`. The gate runs in the main folder at the branch's commit (`git switch --detach wip/batch-12` there, then back): in a worktree three env tests in `tests/test_u1_env.py` fail because the shared `.venv` points the caches at the main folder.

Why now (Nico, 2026-11-08): the learning course (u12) has a GRPO step, so GRPO came back from the deferred list. Subagents run on Sonnet (Nico, 2026-11-09).

Teach: GRPO samples several answers per problem, scores each with a reward (right final number 1, else 0; plus a small format reward for a `#### <number>` line), and pushes the model toward the answers that scored above their group's average; the KL term keeps it close to where it started. Numbers that move: mean reward (should rise), KL (grows slowly from 0), answer length (often changes), dev accuracy at the end.

## GRPO settings (fixed here, contract C2 open question)

trl `GRPOTrainer` (trl 1.17.1, installed) with a peft LoRA adapter on the run's rank and alpha: `beta` (KL coefficient) 0.04, so KL is computed and logged (trl's default 0 logs none, AC12.4.4); sampling temperature 0.7; `num_generations` = `grpo_generations` (default 4 when null); `max_steps` = `grpo_steps` (default from AC7.1.4's plan when null); completion length = the run's `max_new_tokens` (default 512); per-device batch = `num_generations` prompts' completions as trl requires (one problem per step, generations divisible); learning rate = the run's `learning_rate`; prompts = the fixed 4-shot prompt for the training problems (train part of the fixed split, never dev or test, through the training-data guard). Rewards: correctness 1.0 or 0.0 (`scoring.score`), format 0.1 when a `#### <number>` line is present, else 0 (AC7.1.1). Logged per step to metrics.jsonl through the shared loop's callback: `loss`, `learning_rate`, `reward` (mean total reward), `kl`, `answer_length` (mean completion tokens), `step`, `total_steps`, `elapsed_s`, `eta_s`.

## Criteria

- AC7.1.1, AC7.1.4 (part R); AC7.1.2, AC7.1.3 (part G). AC7.1.5 is `[manual]`: after the merge the lead starts `q17-grpo-dev-<n>` detached (`scripts/run-detached.sh`), its row in `results/runs.csv`.

## Parts

### Part R: rewards and the step plan (Python), u7-grpo

Owns: `src/gsm8k/training/grpo_rewards.py` (new), `src/gsm8k/training/grpo_plan.py` (new).
Tests: `tests/test_u7_grpo_rewards.py` (AC7.1.1, AC7.1.4).

- `grpo_rewards.py`: `correctness_reward(completion, gold) -> float`, `format_reward(completion) -> float`, `total_reward(...)`, plus trl-shaped reward functions `(completions, gold, **kwargs) -> list[float]` built on them; uses `gsm8k.scoring` only.
- `grpo_plan.py`: `plan_grpo_steps(model, generations, outputs=None, budget_s=3*3600) -> GrpoPlan` (a NamedTuple `steps, estimate_s, flagged, measured`; `measured` False when no saved timings were found and the fallback was used): from saved step times (`timings.json` of earlier runs of the model, as `src/gsm8k/estimates.py` reads them; GRPO runs' own `seconds_per_step` when present, else sampling time from evaluation runs' `seconds_per_problem` × generations + update time) size the step count so the estimate fits the budget, and `check_grpo_steps(requested, ...)` flags a count whose estimate is over the budget. Pure, no torch import.

### Part G: the GRPO trainer and `gsm8k train --method grpo` (Python), u7-grpo

Owns: `src/gsm8k/training/grpo.py` (new), and in `src/gsm8k/train_cmd.py` only the lines that dispatch method `grpo` to it (and accept `--adapter` as the starting checkpoint for grpo, with the missing-path message of AC7.1.3), and in `src/gsm8k/training/loop.py` only what the callback needs to log `reward`, `kl`, `answer_length` (ADR-005 says the shared loop allows them).
Tests: `tests/test_u7_grpo_train.py` (AC7.1.2, AC7.1.3), with the session `tiny_model` fixture (deep copy), a handful of fixture problems, 2–3 steps, 2 generations, tiny completion length, CPU, temp outputs and a temp results file (never `results/runs.csv`); patch the model/problem loaders as the SFT tests do (`tests/test_u3_*.py`).

- `train_grpo(cfg, ...)` mirrors `train_sft`: checks the config, loads the base model (or the given supervised adapter, trainable), builds prompts, runs `GRPOTrainer` with the settings above and the shared callback, saves the adapter under `checkpoints/<run_id>/`, scores dev (or the run's split and limit) like SFT, and appends one row with method `grpo`. A starting path that does not exist stops before loading anything with a message naming the path.
- The long-run command for AC7.1.5 (lead, after merge): `.venv/bin/python -m gsm8k train --model Qwen/Qwen3-1.7B-Base --method grpo --learning-rate 1e-5 --batch-size 1 --run-id q17-grpo-dev-<n>` (steps from the plan when `--grpo-steps` is not given). Part G makes sure the flags exist and `--run-id` is written as the row's run_id.

## Lead

No shared files expected. A new dependency is not needed (trl, peft installed).

## Rules

Tests named by criterion ID (`test_AC7_1_1_...`); no existing test line changed or deleted; tests committed before the code; CPU only; Ruff clean (line length 110). Builders write only their owned files and use read-only git.
