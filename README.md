# Fine tune model for grade math

Project `idea-gsm8k-finetune` of Nico's Idea Factory, kicked off 2026-10-26 from Nodolas/idea-factory#6.
Ticket: https://github.com/Nodolas/idea-factory/issues/6 (its `stage:*` label shows where the project is).

- `inception/brief.md`: the idea, value case, data loop and test of interest. Written first.
- The spec: AI-DLC 2.11.1 files under `aidlc/` (the intent folder is `spec_path` in `STATE.md`). Changes after approval: `inception/changes.md`.
- `src/` and `tests/`: code, and tests named by criterion ID (`AC1_2_1`). `scripts/trace-check.sh` checks that spec and tests stay in step.
- `STATE.md`: the resume point. `CHARTER.md`: the factory's rules (a copy). `CLAUDE.md`: this project's rules.
- `deploy/plan.md`: the free test-of-interest deploy. Nico runs it by hand; agents never do.
- A learning project (`learning` label, `STATE.md` `track: "learning"`, CHARTER "Learning projects") differs: its brief has the learning sections (goal and done-when, what to learn, hardware fit, models and datasets with licences, evaluation plan, learning path, risks), and it ships `results.md` (the write-up) and `results/runs.csv` (one row per long run) instead of `deploy/plan.md`. No deploy.

Work happens in sessions Nico starts: Claude app > Code > New session > folder `~/Projects/idea-gsm8k-finetune` > Auto > `/build`. Model: Opus 5.5 for Inception (until `gate:go`), Sonnet 5.5 for Construction. `STATE.md` NEXT ACTION names the model when a new session is due.
