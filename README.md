# Fine-tuning a small model for grade-school math (GSM8K)

A hands-on learning project: take a small open base model, measure how well it solves grade-school math word problems ([GSM8K](https://huggingface.co/datasets/openai/gsm8k)), then try to improve it on one 8 GB consumer GPU with supervised fine-tuning (SFT), self-taught chain of thought and reinforcement learning (GRPO), all with LoRA adapters. Every run is logged, so its score can be compared against the base model.

**Results so far** (full write-up in [`results.md`](results.md)): `Qwen/Qwen3-1.7B-Base` scores 79.0% on the dev split and 67.8% on the test split before training. GRPO raised its dev score to 80.8% (+1.8 points), a gain still within noise. SFT on GSM8K's reference solutions (78.6%) and on the model's own solutions (76.2%) did not help.

## What you need

- Linux with Python 3.12 (built and tested on Ubuntu with Python 3.12.3).
- An NVIDIA GPU with at least 8 GB of memory and a driver recent enough for the CUDA 13.0 PyTorch wheels (this project used an RTX 3060 Ti with driver 595). Tests and the lab run on the CPU, so you can explore the code without a GPU.
- About 30 GB of free disk for models, datasets, adapters and logs.
- No accounts and no API keys: the models and datasets download from Hugging Face without a token.

Everything (the virtual environment, Node.js, model weights, datasets, caches, checkpoints) stays inside the project folder. `scripts/in-env.sh` points every cache there and hides the GPU unless you pass `--gpu`.

## Setup

From the project folder:

```bash
# Python packages, pinned (torch comes from the PyTorch CUDA 13.0 index)
python3.12 -m venv .venv
scripts/in-env.sh .venv/bin/pip install -r requirements.txt
scripts/in-env.sh .venv/bin/pip install -e . --no-deps

# Node.js for the website, unpacked into .tools/node (no sudo)
mkdir -p .tools/node
curl -fsSL https://nodejs.org/dist/v24.22.2/node-v24.22.2-linux-x64.tar.xz | tar -xJ -C .tools/node --strip-components=1
scripts/in-env.sh npm ci

# Only needed for GRPO, and only if the system has no python3.12-dev package:
# unpacks Python's C headers into .tools/python-headers (Triton compiles against them)
scripts/fetch-python-headers.sh
```

Check that everything works (CPU only, about 10 minutes):

```bash
scripts/check.sh
```

It runs Ruff, the website's lint, type check and tests, then the Python tests with coverage (it fails under 80%).

## Use the website

```bash
scripts/start-website.sh    # starts the run service, the run worker and the website, then opens http://127.0.0.1:5173
scripts/stop-website.sh     # stops them
```

Everything listens on `127.0.0.1` only; nothing is hosted. Logs go to `outputs/website/`. (Alternatively run `make serve` and `make web` in two terminals. `gsm8k-lab.desktop` is a desktop launcher for the start script; change the paths in it to your folder.)

| Page | What it is for |
|---|---|
| Home | Start page |
| Scores | Every logged run against its base model; mark a run as finalist and score it on the test split |
| Training | Set the dials (learning rate, LoRA rank, epochs, method...), queue a run and watch loss, reward, GPU use and a drawing of what one training step does |
| Reasoning | Compare how the base, SFT and self-taught models write their solutions |
| Lab | Twelve short CPU experiments on a very small model, one dial at a time |
| Course | A 24-step guided course: scoring a model, model designs, the lab lessons, then real runs |

The worker starts queued runs one at a time, when the GPU is free.

## Use the command line

Every command runs through `scripts/in-env.sh`; add `--gpu` for anything that should use the GPU. `--help` on any command lists all options.

```bash
# Score the 1.7B base model on the first 20 dev problems (a quick trial)
scripts/in-env.sh --gpu .venv/bin/python -m gsm8k evaluate --model Qwen/Qwen3-1.7B-Base --split dev --limit 20

# Fine-tune with LoRA (SFT), then score the adapter on dev
scripts/in-env.sh --gpu .venv/bin/python -m gsm8k train --model Qwen/Qwen3-1.7B-Base --method sft --batch-size 2

# Reinforcement learning with GRPO (the step count is sized to fit 3 hours on your GPU)
scripts/in-env.sh --gpu .venv/bin/python -m gsm8k train --model Qwen/Qwen3-1.7B-Base --method grpo --learning-rate 1e-5

# Rebuild the generated part of results.md from the run log
scripts/in-env.sh .venv/bin/python -m gsm8k report
```

Other commands: `cot-generate` (sample the model's own solutions for self-taught training), `harness` (cross-check with lm-evaluation-harness), `prune` (delete old adapters), `lab` and `course`.

- **Trial runs and logged runs.** Without `--run-id` a run is a trial: its result row goes to a temporary file. With `--run-id <name>-<n>` (for example `q17-sft-dev-1`) the row is appended to `results/runs.csv`, the run log that the Scores page and `results.md` read.
- **Test split hygiene.** All tuning uses a 500-problem dev split held out from GSM8K's train half. The test split only scores runs marked as finalists.
- **Long runs.** Full evaluations and training runs take 20 minutes to 3 hours. The easiest way is the website's queue: the worker starts each run on its own, keeps it going when the browser closes, and waits while the GPU is busy. From a terminal, `scripts/run-detached.sh <run id> <command> --run-id <run id>` starts a run in the background if the GPU is free and logs to `outputs/<run id>/run.log`. If the GPU is busy, the job only stays queued for the factory's GPU orchestrator, which a plain checkout does not have.
- **Memory.** On 8 GB, SFT of the 1.7B model needs batch size 2 or less.

## Where things are

| Path | What it holds |
|---|---|
| `src/gsm8k/` | The Python package: evaluation, training (SFT, self-taught CoT, GRPO), run service, queue, lab and course |
| `web/` | The website (React, Vite, Tailwind, shadcn/ui) |
| `tests/` | Python and website tests, each named by the acceptance criterion it checks (`test_AC2_1_3_...`) |
| `results/runs.csv` | One row per logged run: date, run id, model, method, data, metric, value, minutes, config hash |
| `results.md` | The write-up: what was tried, the run table, what moved the score and why, what to try next |
| `checkpoints/`, `outputs/` | Adapters, per-run folders (config, metrics, predictions, log); not in git |
| `inception/brief.md` | The goal, hardware fit, models and datasets with their licences, evaluation plan |
| `aidlc/spaces/default/intents/261030-gsm8k-finetune/` | The spec: requirements, user stories with acceptance criteria, units, design, contracts |
| `inception/changes.md` | Every change to the spec after it was approved, with the reason |

## Models and data

| Name | Licence | Use here |
|---|---|---|
| `Qwen/Qwen3-1.7B-Base` | Apache-2.0 | Main model |
| `Qwen/Qwen3-0.6B-Base` | Apache-2.0 | Fast model for tests and comparisons |
| `openai/gsm8k` (main) | MIT | Training, dev and test |
| `qintongli/GSM-Plus` (testmini) | CC-BY-SA-4.0 | Evaluation only |
| `apple/GSM-Symbolic` (p1) | CC-BY-NC-ND-4.0 | Evaluation only, never trained on |

The repository itself has no licence file yet.

## How this project was built

This project was built in Nico's Idea Factory (ticket [Nodolas/idea-factory#6](https://github.com/Nodolas/idea-factory/issues/6)). Claude wrote the code from the spec, tests first, in batches, and every change merged only with the full test suite and `scripts/trace-check.sh` green. That script checks that every acceptance criterion has a test named after it. The project rules are in `CLAUDE.md` and `CHARTER.md`; `STATE.md` is where the next session resumes. As a learning project it is never deployed: it ships `results.md`.
