# NFR Requirements: u1-eval-skeleton

The unit is a library with a command (`inception/units-generation/unit-of-work.md`), so its non-functional work is security and the tech stack. Performance, scalability, reliability and observability documents apply to service and UI units only. Settled already:
- Python packages from a pinned requirements file into `.venv/`, with caches in the project folder (team-practices.md)
- no accounts, keys or paid services (NFR6)
- every default run fits 8 GB and 3 hours (NFR1, NFR2)
- the whole quick suite runs in under 10 minutes (NFR3)

This PC has Python 3.12.3 and an RTX 3060 Ti with 8 GB.

## Q1. [Developer] Should the model and dataset versions be pinned?

Hugging Face repositories can change under the same name. A pinned revision (a commit hash) makes every run use exactly the same weights and problems (NFR7), and protects against a changed upstream file.

A. Pin both: `Qwen/Qwen3-0.6B-Base`, `Qwen/Qwen3-1.7B-Base` and `openai/gsm8k` are loaded at fixed commit hashes recorded in the code and in each run's `config.json`; weights load only from safetensors files, never pickle, and no remote code runs
B. Track the latest revision; record whatever revision was loaded in `config.json`
X. Other (please specify)

[Answer]: A. Pin both; safetensors only; no remote code

## Q2. [Quality] How long may the skeleton's GPU test take?

AC1.4.1's test loads the 0.6B model and scores 10 dev problems on the GPU. The whole quick suite has a 10-minute budget (NFR3) that later units share.

A. At most 3 minutes with the model already cached (the first download is not counted); the test records its own time so a slowdown shows up
B. At most 10 minutes; no separate budget for this test
X. Other (please specify)

[Answer]: X. Other: "No budget"

## Consolidated Summary Confirmation

- Model and dataset versions are pinned. `Qwen/Qwen3-0.6B-Base`, `Qwen/Qwen3-1.7B-Base` and `openai/gsm8k` load at fixed commit hashes recorded in the code and in each run's `config.json`. Weights load only from safetensors files, and no remote code runs.
- The skeleton's GPU test gets no time budget of its own ("No budget"). The whole quick suite still has to finish within 10 minutes (NFR3); this unit does not tighten that.
- Settled by me unless you say otherwise:
  - Python 3.12 (this PC's), with a venv in `.venv/`
  - PyTorch with a CUDA 12 build
  - Transformers, Accelerate and datasets
  - pytest with pytest-cov, and Ruff
  - all of the above pinned to exact versions in `requirements.txt`
  - every download over HTTPS from Hugging Face or PyPI, with no login
  - nothing listens on the network in this unit
  - run files written only under `outputs/` and `results/`, and the run id checked against a strict pattern before it is used in a path

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
