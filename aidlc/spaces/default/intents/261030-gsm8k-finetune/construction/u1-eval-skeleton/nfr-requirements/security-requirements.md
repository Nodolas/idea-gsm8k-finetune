# Security and Other NFR Requirements: u1-eval-skeleton

Detailed requirements for the walking skeleton, derived from the inception NFRs in `inception/requirements-analysis/requirements.md`. They build on the behaviour in `construction/u1-eval-skeleton/functional-design/functional-spec.md` and the rules in `construction/u1-eval-skeleton/functional-design/rules.md`, and keep to the contracts in `inception/contract-design/contract-summary.md` (C1, C2, C3 as changed 2026-10-31, C5). Answers: `nfr-requirements-questions.md`. The unit is a library with a command, so it has no separate performance, scalability, reliability or observability document. The NFRs it does carry are listed below.

## Threat Picture

One person uses this code on one PC. It downloads public models and data, runs them on the GPU, and writes files into the project folder. It has no accounts, holds no secrets and opens no network listener. The realistic risks are:

- a changed or malicious upstream file
- a model repository that asks to run its own code
- a run id or path that escapes the project folder
- a run that silently uses another revision and breaks comparability

## Security Requirements

| ID | Requirement | Verified by |
|---|---|---|
| NFR6.1 | The unit opens no listening socket. Its only network use is HTTPS downloads from the Hugging Face Hub and PyPI, with no login and no token. | Code review at Code Generation; AC1.1.1's test runs with no token in the environment |
| NFR6.2 | The unit reads no token, key or password from any file or variable, and never prints or logs one. A Hugging Face token found in the environment is ignored, not used. | Code review; tests run with `HF_HUB_DISABLE_IMPLICIT_TOKEN=1` |
| NFR6.3 | Model weights load only from safetensors files (`use_safetensors=True`, no pickle weights), and remote code is never run (`trust_remote_code=False`). | Code review; a test asserts both loading flags |
| NFR6.4 | `Qwen/Qwen3-0.6B-Base`, `Qwen/Qwen3-1.7B-Base` and `openai/gsm8k` load at fixed commit hashes. The hashes live in one place in the code and are copied into every run's `config.json` (Q1). Each hash is resolved from the Hub once, at Code Generation; none is invented in this design. | A test checks that every load passes a 40-character revision and that `config.json` records it |
| NFR5.1 | The six cache variables are set to absolute paths under the project root before any other import (BR1.1). | AC1.1.4 |
| NFR5.2 | The unit writes only under `outputs/`, `results/` (or the temporary results path) and `.cache/`. It never writes above the project folder. | AC1.4.2, AC1.4.3; code review |
| NFR5.3 | A run id must match `^[a-z0-9][a-z0-9-]{0,80}$` before it is used in any path. Others are refused with exit code 2, so a run id can never contain `/`, `..` or other path characters. An adapter path must resolve inside `checkpoints/`. | A test for an id with `../` and one for an adapter path outside `checkpoints/` (BR4.6 family) |
| NFR8.1 | No code path in this unit trains or tunes. The test split is read only when `--split test` is given explicitly, and never during a dev evaluation (BR1.5, BR2.2). | AC1.1.3 |

## Other NFRs Carried by This Unit

| ID | Requirement | Verified by |
|---|---|---|
| NFR1.1 | Every evaluation records its peak GPU memory in `timings.json` (BR4.4). The 0.6B model in bfloat16, with batches of 8, must fit in 8 GB; the skeleton's demo run shows the measured value. | AC1.4.4; the skeleton demo |
| NFR2.1 | Every evaluation records seconds per problem (BR4.4), so later estimates for the full dev (496) and test (1,319) runs rest on measured numbers. | AC1.4.4 |
| NFR3.1 | The unit's tests use at most 20 problems and run in the quick suite. The GPU test has no time budget of its own (Q2: "No budget"), but the whole quick suite must still finish within 10 minutes (NFR3). | `scripts/check.sh` timing at the checkpoint |
| NFR4.1 | The unit's Python code under `src/` reaches at least 80% line coverage in the quick suite. | `scripts/check.sh` (pytest-cov, fails under 80%) |
| NFR7.1 | Reproducibility rests on four things: pinned revisions (NFR6.4), the fixed split seed (BR1.3), greedy decoding with batches of 8 (BR3.5), and the configuration hash (BR4.5). The same configuration gives the same hash and the same problems. GPU arithmetic may still vary in the last digits, so scores are expected to match, not guaranteed bit-identical. | AC1.1.2, AC1.4.5 |

## Not Applicable to This Unit

- **NFR9 (accessibility):** no user interface in this unit.
- **NFR10 (live latency):** no live stream in this unit; it comes with u4-run-service.
