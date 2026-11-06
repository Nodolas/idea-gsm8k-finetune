# Evidence

Lead: `aidlc-pipeline-deploy-agent`, 2026-10-30, at commit dd1428c. Greenfield, lead-only run (collaborators off for scope mvp): there are no support contributions.

## Inspected

- `aidlc/spaces/default/memory/org.md`: the five sections Way of Working, Walking Skeleton, Testing Posture, Deployment and Code Style, used as starting defaults (trunk-based with squash-merged Bolt worktrees; skeleton for `skeleton: on`; test-after, plus an 80% line floor and CI before merge for mvp; deploy on merge to staging; linter in CI before merge).
- `aidlc/spaces/default/memory/team.md` and `project.md`: empty templates, so this is a first run, not a re-run.
- `CLAUDE.md` (project rules): `wip/<unit>` branches, commit order spec/test/feat/state, fast-forward-only `main`, tests first and never weakened, tests named by criterion ID, no CI and no CI Pipeline stage, no deploys, no worktrees or "Continue automatically", in-folder caches, long runs `[manual]` with `--run-id`, Done definition.
- `CHARTER.md`: rules 4, 6, 8 and 11, House rules, and "Learning projects" (rules 1, 2, 5 and 9 off; ship is `results.md`; no money or accounts).
- `inception/brief.md`: Python stack, a local React/TypeScript website, Node.js under `.tools/node/`, an RTX 3060 Ti with 8 GB, run times per step, and the eval protocol and splits.
- `inception/changes.md`, `STATE.md` (`track: "learning"`, `test_command` and `spec_path` empty), `deploy/plan.md` (unused for learning projects), `.gitignore` (caches, `checkpoints/`, `outputs/`, weights, `.venv/` ignored).
- `scripts/trace-check.sh` (test names map to criterion IDs under `tests/`), `.claude/skills/build/SKILL.md` (`test_command` comes only from the approved Construction Verification Command; long-run hand-off), `.claude/scopes/aidlc-mvp.md` (`skeleton: on`, `collaborators: off`) and the intent's `aidlc-state.md`.
- Repository: `git log`, `git branch -a` (`main` and `origin/main` only), `src/` and `tests/` (only `.gitkeep`); no application code, CI config or linter config yet.

## Interview decisions

Nico answered all eight questions and confirmed the consolidated summary ("Looks correct").

- **Q1 Git:** A. One `wip/<unit>` branch per unit; commits spec, tests, code, state; `main` moves only by fast-forward when green.
- **Q2 Walking skeleton:** A. Yes, small: the first unit runs the evaluation end to end on 5–20 problems with the 0.6B model and writes its row to a temp file.
- **Q3 Tests:** A. Tests first, named by criterion, never weakened; the approved test command and the trace check run before each merge; 80% line coverage on Python under `src/`. Recorded as Methodology `atdd`.
- **Q4 Quick tests:** A. May download `Qwen3-0.6B-Base` and use the GPU on a few problems, minutes only.
- **Q5 Shipping:** A. No deploy and no cloud test pipeline; website local only; shipped means `results.md`; runs over about 10 minutes are started by Nico with a run id.
- **Q6 Code style:** A. Ruff (lint and format), no Python type checker; ESLint, Prettier and strict TypeScript; pip with pinned requirements in `.venv/`.
- **Q7 Checkpoints:** B. Keep only the baseline's and the best run's weights; delete the rest.
- **Q8 Hard rules:** A. Affirm all drafted rules, plus "never train or tune on the GSM8K test split" and "never force-push".

## Remaining uncertainty

- The website's test runner (Vitest or another) and whether lint and type checks are part of the verification command are not fixed here; they are settled when Code Generation proposes, and Nico approves, the Construction Verification Command.
- For the orchestrator, not a practice: `STATE.md` DO NOT names a local branch `wip/hello-file`, but `git branch -a` lists only `main` and `origin/main`; `STATE.md` may need a dated conflict note.
