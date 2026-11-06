# NFR Design: u1-eval-skeleton

The design follows the confirmed NFR requirements (`construction/u1-eval-skeleton/nfr-requirements/`). One choice is left open.

## Q1. [Developer] Should runs work offline once the files are downloaded?

The model and dataset are pinned to exact revisions, so after the first download every file a run needs is already in `.cache/`.

A. Yes: when the pinned files are already cached, the command turns on Hugging Face's offline mode, so normal runs never contact the network. Only the first run of a model or dataset downloads
B. No: every run may check the Hub, which only matters if a cached file is damaged
X. Other (please specify)

[Answer]: B. No offline mode; runs may contact the Hub and download as needed. Nico: "No download the models as we are not using big ones that should be fine"

## Consolidated Summary Confirmation

- No offline mode. Runs may contact the Hugging Face Hub and download as needed; the models are small. Every load still uses the pinned revision, so what a run loads cannot change.
- The design (`security-design.md`, `logical-components.md`):
  - A bootstrap module sets the six cache variables, turns off implicit tokens and telemetry, and removes token variables, before any other import.
  - One loader module is the only Hub access. It loads at the pinned revisions, from safetensors only, with no remote code.
  - One paths module checks run ids against `^[a-z0-9][a-z0-9-]{0,80}$`. The fallback id is `adhoc-YYYYMMDD-HHMMSS` in UTC. Adapters must sit inside `checkpoints/`.
  - Evaluation batch size is fixed per model: 8 for 0.6B, 4 for 1.7B. Peak memory and time are measured, and an out-of-memory error fails the run cleanly without a retry.
  - Reproducibility rests on the pins, `split_seed`, greedy decoding, the fixed batch size, the hash, a seeded torch, and TF32 off.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
