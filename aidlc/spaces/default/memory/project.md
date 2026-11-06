# Project-Level Rules

> Project-specific specialisation and corrections. Loaded after `org.md` and
> `team.md` as strict-additive guidance; contradictions with broader policy
> are rejected. Populated by practices-discovery and the self-learning loop.
>
> Use sparingly: most teams don't need a project layer. Reach for it
> only when this specific project needs stable, durable guidance beyond the
> team practice (for example, package-specific release checks or an additional
> regression suite for a legacy component).

## Way of Working

<!-- Project-specific specialisation. Example: -->
<!-- This monorepo requires package-scoped branch names and a package owner -->
<!-- review in addition to the team's normal merge policy. -->

## Walking Skeleton

<!-- Project-specific specialisation. Example: -->
<!-- The walking skeleton must exercise the legacy service adapter as well -->
<!-- as the new service boundary. -->

## Testing Posture

<!-- Project-specific specialisation. -->

## Guard Policy

<!-- Project-specific. Mode: strict, relaxed, or off. Strict here holds for every intent, whatever one person asks in chat; relaxed or off here applies to every intent whose policy came from its scope, unless the person sets another; changing this line changes it. A section under the retired Change Control heading, written by an earlier release, is still read. -->

## Deployment

<!-- Project-specific specialisation. -->

## Code Style

<!-- Project-specific specialisation. -->

## Tech Stack

<!-- Technology choices locked for this project. -->

## Decided

<!-- Decisions made in earlier stages that should not be re-asked. -->
<!-- Format: DECIDED: [decision] (Stage [slug], [date]) -->

## Scope Overrides

<!-- Custom scope rules for this project. -->

## Forbidden

<!-- Populated by practices-discovery affirmation gate. -->
<!-- Format: NEVER [behavior] (affirmed [date]) -->
<!-- Example: NEVER throw exceptions across service layer boundaries (affirmed 2026-05-17) -->

- NEVER edit or delete a test to make it pass; on a unit branch no file under `tests/` loses a line unless Nico ruled that test wrong and a `spec(<unit>)` changes.md line came first. (source: CLAUDE.md Tests) (affirmed 2026-10-30)

- NEVER create `.github/workflows/`, and never start, skip or resume AI-DLC's CI Pipeline stage or any Operation stage. (source: CLAUDE.md CI Pipeline) (affirmed 2026-10-30)

- NEVER deploy, spend money, rent compute, create accounts, use API keys or paid services, or run `gh workflow`, `gh release` or `gh secret`. (source: CHARTER rule 4, Learning projects; CLAUDE.md) (affirmed 2026-10-30)

- NEVER read, print, commit or put into the environment any token, key, password or secret. (source: CHARTER House rules; CLAUDE.md) (affirmed 2026-10-30)

- NEVER run a training or evaluation run of over about 10 minutes in a session's foreground, and never append to `results/runs.csv` from a test; only long runs (started detached by the lead, or from the website) append to it. (source: CLAUDE.md Learning runs) (affirmed 2026-10-30)

- NEVER resume AI-DLC after Delivery Planning or let AI-DLC commit; Construction is built by `/build` with parallel builder agents. (source: CLAUDE.md, Nico 2026-10-31) (affirmed 2026-10-30, changed 2026-10-31)

- NEVER answer AI-DLC's questions or approvals on Nico's behalf. (source: CLAUDE.md) (affirmed 2026-10-30)

- NEVER read or write above the project folder. (source: CHARTER rule 8; CLAUDE.md) (affirmed 2026-10-30)

- NEVER train or tune on the GSM8K test split; tuning and early stopping use the held-out dev split of train only. (source: brief and STATE.md; affirmed Q8) (affirmed 2026-10-30)

- NEVER force-push. (source: build skill; affirmed Q8) (affirmed 2026-10-30)

## Mandated

<!-- Populated by practices-discovery affirmation gate. -->
<!-- Format: ALWAYS [behavior] (affirmed [date]) -->
<!-- Example: ALWAYS use Result<T,E> for fallible operations in service layer (affirmed 2026-05-17) -->

- ALWAYS build each unit on its own branch `wip/<unit>` (Build and Test on `wip/build-and-test`, a gap on `wip/gap-<n>`) and commit in the order `spec(<unit>)`, `test(<unit>)`, `feat(<unit>)`, then `chore(state): <unit> done` as the branch's last commit. (source: CLAUDE.md Git) (affirmed 2026-10-30)

- ALWAYS move `main` only by fast-forward from a green `wip/<unit>`, or by commits without code. (source: CLAUDE.md Git) (affirmed 2026-10-30)

- ALWAYS end commit bodies with `Refs: Nodolas/idea-factory#6`. (source: CLAUDE.md Git) (affirmed 2026-10-30)

- ALWAYS put tests in `tests/` and name each test by its criterion ID (`test_AC1_2_1_...`, or a JS/TS title starting `AC1.2.1`). (source: CLAUDE.md Tests; CHARTER rule 11) (affirmed 2026-10-30)

- ALWAYS write a unit's tests before its implementation code. (source: CLAUDE.md Tests) (affirmed 2026-10-30)

- ALWAYS change the spec before the code when reality differs: a dated `inception/changes.md` line (what, why, class) committed with the spec files as `spec(<unit>): ...`. (source: CLAUDE.md Spec first; CHARTER rule 11) (affirmed 2026-10-30)

- ALWAYS mark a criterion whose run takes over about 10 minutes `[manual]` on the criterion's own line with `Verify: results/runs.csv row <base id>`, and give its long-run script a `--run-id` argument that it writes as the row's `run_id`. (source: CLAUDE.md Learning runs) (affirmed 2026-10-30)

- ALWAYS keep tests quick (tiny samples, minutes) and write any run rows they make to a temp path. (source: CLAUDE.md Learning runs) (affirmed 2026-10-30)

- ALWAYS set `HF_HOME`, `PIP_CACHE_DIR`, `XDG_CACHE_HOME`, `TRITON_CACHE_DIR`, `TORCHINDUCTOR_CACHE_DIR` and `TORCH_HOME` as absolute paths under the project root before any other import in every script, and as a prefix on shell commands. (source: CLAUDE.md Learning files; CHARTER Learning projects rule 8) (affirmed 2026-10-30)

- ALWAYS write checkpoints, adapters, merged models and logs only under `checkpoints/` or `outputs/`, and keep models, datasets, caches and the venv inside the project folder and gitignored. (source: CLAUDE.md Learning files; CHARTER Learning projects rule 8) (affirmed 2026-10-30)

- ALWAYS declare a unit done only after its tests, the full suite (the approved Construction Verification Command) and `scripts/trace-check.sh` pass in the same session, recorded in `STATE.md` `last_check`. (source: CLAUDE.md Done) (affirmed 2026-10-30)

- ALWAYS write files, comments, commits and messages in English. (source: CHARTER rule 6, House rules) (affirmed 2026-10-30)

## Corrections

<!-- Project-specific corrections from human feedback. -->
<!-- Format: NEVER/ALWAYS [behavior] (learned [date]) -->
- Command-line entry points for GPU runs live in their own RunCommands block, launched by the worker as separate processes, so the service and the queue never import training code and the dependency graph stays acyclic (domain-design ADR-006). (learned 2026-10-31) <!-- cid:261030-gsm8k-finetune:domain-design:1d57b3df9f3f4afd225cd288134c420eaf843655d11b9ac71af04b379e6b458c -->
- The run-queue worker is its own `gsm8k worker` process, separate from the service, so queued runs keep advancing while the service is down (units-generation, u4-run-service). (learned 2026-10-31) <!-- cid:261030-gsm8k-finetune:units-generation:4f4839015ac2a5061a273263c38c693b1250d8811b8ba0ba3ab70c66e41bf9d8 -->
- Every option that changes a run's result (the eleven dials, split, adapter, evaluation limit, vote samples, calculator, GRPO settings) is a field of the run's config.json, and config_hash covers every field except run_id and v (contract-design C2). (learned 2026-10-31) <!-- cid:261030-gsm8k-finetune:contract-design:7b9ae94f486a2210c4a132a85f3d0f3085b72815bb9762f764dab46e2eb2fa49 -->
