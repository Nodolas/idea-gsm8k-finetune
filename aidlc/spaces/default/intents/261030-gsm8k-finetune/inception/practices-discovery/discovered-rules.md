# Discovered Rules

All rules below were affirmed by Nico in the Practices Discovery interview (Q8). Source notes name where each rule was already written.

## Mandated

- ALWAYS build each unit on its own branch `wip/<unit>` (Build and Test on `wip/build-and-test`, a gap on `wip/gap-<n>`) and commit in the order `spec(<unit>)`, `test(<unit>)`, `feat(<unit>)`, then `chore(state): <unit> done` as the branch's last commit. (source: CLAUDE.md Git)
- ALWAYS move `main` only by fast-forward from a green `wip/<unit>`, or by commits without code. (source: CLAUDE.md Git)
- ALWAYS end commit bodies with `Refs: Nodolas/idea-factory#6`. (source: CLAUDE.md Git)
- ALWAYS put tests in `tests/` and name each test by its criterion ID (`test_AC1_2_1_...`, or a JS/TS title starting `AC1.2.1`). (source: CLAUDE.md Tests; CHARTER rule 11)
- ALWAYS write a unit's tests before its implementation code. (source: CLAUDE.md Tests)
- ALWAYS change the spec before the code when reality differs: a dated `inception/changes.md` line (what, why, class) committed with the spec files as `spec(<unit>): ...`. (source: CLAUDE.md Spec first; CHARTER rule 11)
- ALWAYS mark a criterion whose run takes over about 10 minutes `[manual]` on the criterion's own line with `Verify: results/runs.csv row <base id>`, and give its long-run script a `--run-id` argument that it writes as the row's `run_id`. (source: CLAUDE.md Learning runs)
- ALWAYS keep tests quick (tiny samples, minutes) and write any run rows they make to a temp path. (source: CLAUDE.md Learning runs)
- ALWAYS set `HF_HOME`, `PIP_CACHE_DIR`, `XDG_CACHE_HOME`, `TRITON_CACHE_DIR`, `TORCHINDUCTOR_CACHE_DIR` and `TORCH_HOME` as absolute paths under the project root before any other import in every script, and as a prefix on shell commands. (source: CLAUDE.md Learning files; CHARTER Learning projects rule 8)
- ALWAYS write checkpoints, adapters, merged models and logs only under `checkpoints/` or `outputs/`, and keep models, datasets, caches and the venv inside the project folder and gitignored. (source: CLAUDE.md Learning files; CHARTER Learning projects rule 8)
- ALWAYS declare a unit done only after its tests, the full suite (the approved Construction Verification Command) and `scripts/trace-check.sh` pass in the same session, recorded in `STATE.md` `last_check`. (source: CLAUDE.md Done)
- ALWAYS write files, comments, commits and messages in English. (source: CHARTER rule 6, House rules)

## Forbidden

- NEVER edit or delete a test to make it pass; on a unit branch no file under `tests/` loses a line unless Nico ruled that test wrong and a `spec(<unit>)` changes.md line came first. (source: CLAUDE.md Tests)
- NEVER create `.github/workflows/`, and never start, skip or resume AI-DLC's CI Pipeline stage or any Operation stage. (source: CLAUDE.md CI Pipeline)
- NEVER deploy, spend money, rent compute, create accounts, use API keys or paid services, or run `gh workflow`, `gh release` or `gh secret`. (source: CHARTER rule 4, Learning projects; CLAUDE.md)
- NEVER read, print, commit or put into the environment any token, key, password or secret. (source: CHARTER House rules; CLAUDE.md)
- NEVER run a training or evaluation run of over about 10 minutes inside a session, and never append to `results/runs.csv` from a test or a session; only Nico's runs append to it. (source: CLAUDE.md Learning runs)
- NEVER use Construction worktrees, swarm, stage-major or "Continue automatically", and never let AI-DLC commit. (source: CLAUDE.md AI-DLC)
- NEVER answer AI-DLC's questions or approvals on Nico's behalf. (source: CLAUDE.md)
- NEVER read or write above the project folder. (source: CHARTER rule 8; CLAUDE.md)
- NEVER train or tune on the GSM8K test split; tuning and early stopping use the held-out dev split of train only. (source: brief and STATE.md; affirmed Q8)
- NEVER force-push. (source: build skill; affirmed Q8)
