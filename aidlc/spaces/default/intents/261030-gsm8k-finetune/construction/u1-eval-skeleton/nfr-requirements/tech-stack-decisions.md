# Tech Stack Decisions: u1-eval-skeleton

The tools the walking skeleton is built with. The stack follows the brief and `inception/requirements-analysis/requirements.md` (Constraints: Python with Transformers, TRL and PEFT), the behaviour in `construction/u1-eval-skeleton/functional-design/functional-spec.md` and `construction/u1-eval-skeleton/functional-design/rules.md`, and the contracts in `inception/contract-design/contract-summary.md`. The package layout is from `inception/units-generation/unit-of-work.md`; the tooling rules are from `inception/practices-discovery/team-practices.md` (Code Style, Testing Posture). Exact versions are pinned in `requirements.txt` at Code Generation, using the latest stable release that works on this PC on that day; this design names no version it has not checked.

## Decisions

| Area | Choice | Why |
|---|---|---|
| Language | Python 3.12 (this PC's system interpreter, 3.12.3) in a venv at `.venv/` | Already installed; supported by PyTorch and Transformers; the venv stays inside the project (rule 8) |
| Package install | pip from a pinned `requirements.txt`, with `PIP_CACHE_DIR` under `.cache/pip` | Team practice; nothing installed above the folder |
| Deep learning | PyTorch, CUDA 12 build, from the official PyTorch wheel index | The RTX 3060 Ti (driver 595) supports CUDA 12, and bfloat16 runs on Ampere GPUs |
| Models | Hugging Face Transformers with Accelerate | Loads Qwen3 base models and their tokenizer; `generate` gives greedy decoding with stop strings |
| Data | Hugging Face `datasets` | Loads `openai/gsm8k` `main` at a pinned revision into `.cache/huggingface` |
| Command line | `argparse` from the standard library, exposed as the `gsm8k` console command in `pyproject.toml` | No extra dependency; subcommands (`evaluate`, then `train`, `serve` and others in later units) |
| GPU lock | `fcntl.flock` from the standard library | The OS lock chosen in Functional Design Q1; Linux only |
| Seeded randomness | `random.Random(42)` from the standard library | The generator named in BR1.3 and BR2.1 |
| Hashing | `hashlib.sha256` over canonical JSON (`json.dumps` with sorted keys and compact separators) | BR4.5; standard library |
| Tests | pytest and pytest-cov | Team practice; tests named `test_AC1_x_y_...` |
| Lint and format | Ruff, configured in `pyproject.toml` | Team practice |
| Verification | `scripts/check.sh` | The approved Construction verification command. It sets the six cache variables, runs Ruff, then pytest with coverage on `src/` (fails under 80%), and later also the website's tests |

## Not Chosen

- **TRL and PEFT:** not needed for evaluation alone. They come in with u3-sft, together with loading a LoRA adapter for `--adapter`. Until then, an adapter evaluation is refused by the existing checks: there is no adapter yet.
- **vLLM or other fast inference servers:** faster generation, but a heavy extra dependency with its own memory behaviour on 8 GB. Transformers `generate` with batches of 8 is enough for 496 to 1,319 problems within 3 hours. Revisit only if the measured seconds per problem say otherwise.
- **lm-evaluation-harness:** belongs to u2-baselines.
- **`uv` or conda:** the team chose pip with a pinned requirements file.

## Pinned Revisions (Q1)

| Repository | Pin |
|---|---|
| `Qwen/Qwen3-0.6B-Base` | Commit hash resolved from the Hub at Code Generation, written once in the code |
| `Qwen/Qwen3-1.7B-Base` | Same |
| `openai/gsm8k` (`main`) | Same |

Changing a pin later is a spec change. It needs a dated `inception/changes.md` line, and it changes the configuration hash of every later run.
