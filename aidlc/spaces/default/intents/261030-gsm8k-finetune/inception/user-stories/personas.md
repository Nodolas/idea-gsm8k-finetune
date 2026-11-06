# Personas

Sources: `inception/requirements-analysis/requirements.md` (Intent Analysis, Constraints), the Ideation answers that settled the audience (intent-capture: "Only you (Nico)", "You alone"; feasibility: "Comfortable with both Python and React"), `inception/practices-discovery/team-practices.md`, and `inception/changes.md` (2026-10-31: who starts long runs).

## Nico, the hands-on learner

| Field | Detail |
|---|---|
| Role | The only user and the only decision maker. Owns the project, its PC (RTX 3060 Ti, 8 GB) and every long run's result; never types a command in a terminal. |
| Goals | Learn, hands-on, how a small open base model is post-trained for grade-school math. See which changes move the GSM8K score and understand why. End with a `results.md` that explains it. |
| Pain points | A training run is a black box until it ends. Hours can be lost to a run that was never going to fit in 8 GB or 3 hours. Scores from different runs are hard to compare fairly, and it is easy to tune on the test split by accident. |
| Tech comfort | High: comfortable with both Python and React. |
| Frequency | A few sessions a week, with no deadline. Long runs (often over 10 minutes, up to 3 hours) start in the evening, from the website by Nico or detached by the `/build` lead, and are checked later. |
| Settings | On this PC only: the local results website (desktop browser) for watching, starting, stopping and comparing runs, and Claude Code sessions in which the `/build` lead runs the training and evaluation commands for him. |

**Persona relationships and priority:** Nico is the single persona and the primary one; every story is written for him. No other human uses the system. Claude Code helpers (the build lead, and the could-have proposer and reviewer agents) work for Nico but are not personas: the `/build` lead starts long runs only as detached runs (`scripts/run-detached.sh`, one GPU run at a time), the proposer and reviewer agents never start a run, and none of them answers his questions (constraint-register.md OC-4; project.md Forbidden; inception/changes.md, 2026-10-31).
