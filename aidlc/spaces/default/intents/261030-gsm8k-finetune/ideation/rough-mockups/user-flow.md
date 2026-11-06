# User Flows: Fine tune model for grade math

Upstream: `ideation/intent-capture/intent-statement.md`, `ideation/scope-definition/scope-document.md`, `ideation/scope-definition/intent-backlog.md`. Screens are in `wireframes.md`; answers in `rough-mockups-questions.md`.

Persona: Nico, the only user. Desktop browser on this PC (Q5).

## Core Flow: Start and Watch a Run

```
[Training page] -> set dials -> [Start run] -> [Confirm dialog] -> confirm
      -> run launches on this PC -> [Live curves update] -> run ends
      -> row added to run log -> [Scores page shows it]
```

<!-- Text fallback: on the training page Nico sets the dials and presses Start run. A confirm dialog appears, and on confirm the run launches on this PC. The live curves update until the run ends, the run log gets a new row, and the scores page shows it. -->

```
Flow: Start and watch a run
Persona: Nico
Trigger: Nico wants to try a setting
Steps:
  1. Training page (idle) -> adjusts dials -> each field checks its allowed range
  2. Training page -> presses Start run -> Confirm dialog with summary, estimate and command (Q7)
  3. Confirm dialog -> presses Start run -> run launches; status RUNNING; Start disabled, Stop enabled
  4. Training page (running) -> watches -> curves update live; step, elapsed time and ETA tick
  5. Run ends -> status IDLE; the result appears in Past runs and on the Scores page
Success outcome: a new scored row in the run log, visible on Scores
Error paths:
  - Invalid dial -> field names the allowed range -> Nico fixes it; Start stays disabled until valid
  - Another run active -> Start disabled with "A run is already active" -> wait or press Stop
  - Launch fails -> dialog shows why -> fix and retry
  - Run crashes -> status FAILED with last log lines -> adjust and start again
  - Live updates drop -> "reconnecting" banner -> curves resume; the run itself keeps going
```

## Flow: Stop a Run

```
Flow: Stop a run
Persona: Nico
Trigger: a run looks wrong (loss diverging, too slow)
Steps:
  1. Training page (running) -> presses Stop -> confirmation naming the run id
  2. Confirms -> run stops; status STOPPED; curves keep what was logged
Success outcome: the GPU is free; the stopped run is listed as stopped, not scored
Error paths:
  - Run already finished -> "Run has already ended" -> nothing to stop
```

## Flow: Compare Two Runs

```
Flow: Compare two runs
Persona: Nico
Trigger: Nico wants to see what a dial change did
Steps:
  1. Scores page -> ticks two runs -> Compare enabled
  2. Presses Compare -> settings side by side, accuracy difference, both curves overlaid (Q4)
Success outcome: Nico sees which setting changed and what it did
Error paths:
  - Fewer or more than two picked -> Compare disabled with "Pick two runs to compare"
```

## Flow: Check Progress

```
Flow: Check progress
Persona: Nico
Trigger: opening the site
Steps:
  1. Landing page -> reads "Best so far" -> Go to training or See scores
Success outcome: Nico knows the current best result in one glance
Error paths:
  - No runs yet -> "No runs yet" with Go to training
  - Run log unreadable -> message naming the file
```

## Assumptions & Open Questions

- [assumption] A run started from the website keeps running if the browser tab closes (constraint carried from feasibility, not re-asked here).
