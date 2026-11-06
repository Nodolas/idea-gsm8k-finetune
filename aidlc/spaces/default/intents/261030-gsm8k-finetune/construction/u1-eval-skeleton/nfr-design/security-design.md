# Security and NFR Design: u1-eval-skeleton

How the walking skeleton meets the NFRs in `construction/u1-eval-skeleton/nfr-requirements/security-requirements.md`. It uses the stack in `construction/u1-eval-skeleton/nfr-requirements/tech-stack-decisions.md` and the behaviour in `construction/u1-eval-skeleton/functional-design/functional-spec.md`, within the contracts in `inception/contract-design/contract-summary.md` (C2 with `split_seed`, `model_revision` and `dataset_revision`; C3 as an OS lock; C5 with `--config` and `--started-by`). Code here is illustrative only; the real code comes at Code Generation.

## Design Overview

Three choke points carry the security of this unit. Each check has one owner and cannot be skipped.

1. **The environment bootstrap** (`gsm8k._env`). The console command imports it before anything else.
2. **The loader** (`gsm8k.datasets_prompts.hub`). It is the only module that talks to the Hugging Face Hub.
3. **The run-records guard** (`gsm8k.run_records.paths`). It is the only module that turns a run id or adapter path into a file path.

## Solutions

### NFR5.1 Caches in the project folder

`gsm8k._env.bootstrap()` runs first in the `gsm8k` entry point, before PyTorch, Transformers or datasets are imported. It sets the six variables to absolute paths under the project root, which it finds from the package location (`<root>/src/gsm8k/`). It sets them unconditionally, so outside values cannot point the caches elsewhere. Tests start the command as a subprocess and read the variables back (AC1.1.4).

### NFR6.2 No ambient token

The same bootstrap sets `HF_HUB_DISABLE_IMPLICIT_TOKEN=1` and `HF_HUB_DISABLE_TELEMETRY=1`, and removes `HF_TOKEN` and `HUGGING_FACE_HUB_TOKEN` from the process environment. The shipped command therefore never sends a token, even if one is set in Nico's shell. No code path reads, prints or logs a token.

### NFR6.1 Network use

The unit imports no server library and opens no socket for listening. The loader is the only module that downloads: through `huggingface_hub` and `datasets`, over HTTPS, without login. After the first download, `HF_HUB_OFFLINE=1` may be set to prove that a run needs no network. The design supports this because every load passes an exact revision.

### NFR6.3 and NFR6.4 Safe, pinned loading

The loader holds one table of pins: `MODEL_REVISIONS = {model_id: commit}` and `DATASET_REVISION = commit`. Each value is the 40-character commit hash resolved from the Hub at Code Generation. Every load goes through two functions:

```
load_model(model_id) -> from_pretrained(model_id, revision=MODEL_REVISIONS[model_id],
                                        use_safetensors=True, trust_remote_code=False, torch_dtype=bfloat16)
load_gsm8k()         -> load_dataset("openai/gsm8k", "main", revision=DATASET_REVISION)
```

- An unknown model id raises a configuration error (exit code 2). There is no path for loading an unpinned model.
- The run's `config.json` records `model_revision` and `dataset_revision` (C2). At the pinned defaults they stay out of `config_hash`, and moving a pin changes later hashes.
- A test checks that both loaders pass a 40-character revision and the two safety flags.

### NFR5.2 and NFR5.3 Paths stay inside the project

`run_records.paths` is the only place that builds paths from user input:

- **`run_dir(run_id)`** checks the id against `^[a-z0-9][a-z0-9-]{0,80}$`, then returns `<root>/outputs/<run_id>`. The command's own fallback id is `adhoc-<YYYYMMDD>-<HHMMSS>` in UTC, for example `adhoc-20261101-201530`. It matches the pattern by construction.
- **`adapter_dir(path)`** resolves the path, following symlinks, and requires it to lie inside `<root>/checkpoints/`. Anything else is refused with exit code 2.
- **`results_path(arg)`** is either the default `<root>/results/runs.csv` or a path given by a test. Tests may write outside the project only to their own temporary directory, which pytest provides.

Every write is write-then-rename in the same folder (BR5.4), so a crash never leaves a half file.

### NFR8.1 Test split hygiene

The unit has no training code. The test split is loaded only when `--split test` is given, and the dev evaluation draws its problems only from the dev ids (BR2.2). The split builder refuses any `gsm8k-test-` id in dev or train (BR1.5).

### NFR1.1 and NFR2.1 Memory and time

- **Batch size.** Evaluation runs in fixed batches per model: 8 for the 0.6B model, as chosen at Functional Design (`functional-design-questions.md`, settled details), and 4 for the 1.7B model, to leave headroom in 8 GB. The batch size is a code constant per model. It is not a dial and not in the hash.
- **Measurement.** `torch.cuda.reset_peak_memory_stats()` runs before the first batch and `max_memory_allocated()` after the last. Both measured values go to `timings.json` (BR4.4).
- **Out of memory.** A CUDA out-of-memory error ends the run as failed with "GPU out of memory" (exit code 1). It is not retried automatically, so the measured limit stays visible. u2-baselines measures the 1.7B model on its first long run, and changing a batch size is a spec change.

### NFR3.1 and NFR4.1 Quick suite and coverage

- Pure logic (scoring, split, prompt, hash, paths) is tested without a GPU.
- Only AC1.4.1's test loads the 0.6B model and scores 10 problems. It has no time budget of its own (NFR Requirements Q2); the whole suite must stay under 10 minutes.
- Coverage on `src/` is measured by `scripts/check.sh` and fails under 80%.

### NFR7.1 Reproducibility

Several things keep two runs of the same configuration comparable:

- pinned revisions (NFR6.4)
- the fixed `split_seed` (BR1.3)
- greedy decoding with the stop rule (BR3.5)
- a fixed batch size per model (above)
- the configuration hash (BR4.5)

The design also calls `torch.manual_seed(seed)` before generation and sets `torch.backends.cuda.matmul.allow_tf32 = False`. Exact bit-identity across GPU runs is still not promised.

## Residual Risks

| Risk | Why accepted |
|---|---|
| A pinned revision is deleted upstream | Downloads stay cached in `.cache/`; a new pin is a spec change |
| The 1.7B model does not fit at batch 4 | Found on u2's first run, which fails cleanly with "GPU out of memory"; the batch size then changes through `inception/changes.md` |
| Dependencies from PyPI are compromised | Versions are pinned exactly in `requirements.txt`; installs only from PyPI and the PyTorch index |
