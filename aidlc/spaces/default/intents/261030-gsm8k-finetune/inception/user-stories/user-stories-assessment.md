# User Stories Assessment

## Decision

Execute.

## Rationale

The requirements (`inception/requirements-analysis/requirements.md`) describe user-facing behaviour that Nico sees and drives: a three-page local results website, a run-control service he starts runs from, a training and evaluation command line he runs long jobs from, and a written report. The team's Testing Posture (`inception/practices-discovery/team-practices.md`) names every test after an acceptance criterion (`test_AC1_2_1_...`), so stories with stable `AC` IDs are what the tests and `scripts/trace-check.sh` hang on. Without stories, tests would fall back to FR IDs and lose the Given/When/Then detail the requirements leave open (for example the dial ranges and the finalist flow).

## Factors Considered

- **Project type:** greenfield, multi-component (Python training and evaluation, a local service, a React website).
- **User-facing scope:** yes. One person (Nico) uses every surface, in two settings: the terminal for long runs and the website for watching, starting and comparing runs.
- **Complexity signals:** a run lifecycle with states (IDLE, RUNNING, STOPPED, FAILED); a guarded test-split flow; long runs that must be `[manual]` criteria with `Verify: results/runs.csv row <base id>`; live updates within 5 seconds.
- **Personas:** one human user, already settled in Ideation (intent-capture: "Only you (Nico)"; "You alone").

## Where Stories Add the Most Value

- Turning each long run (baselines, fine-tuning, generalisation, final test) into a `[manual]` criterion with its own base run id, so Nico knows exactly which command to run and which `results/runs.csv` row proves it.
- Making the run-control rules testable: validation of the dials, one run at a time, stop, failure display, and the finalist-only test evaluation.
- Giving the website's empty, loading and error states concrete pass/fail criteria.
- Ordering the stories along the learning path chosen in Scope Definition, so the walking skeleton (evaluation on 5–20 problems) comes first.
