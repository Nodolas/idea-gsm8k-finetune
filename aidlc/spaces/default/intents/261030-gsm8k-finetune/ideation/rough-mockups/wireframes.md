# Wireframes: Fine tune model for grade math

Low-fidelity, structure only (Q1). The visual look comes later from Nico's screenshots in `inputs/design/`.

Upstream:
- `ideation/intent-capture/intent-statement.md`: Nico alone, local only, learning first.
- `ideation/scope-definition/scope-document.md`: the whole website is must-have.
- `ideation/scope-definition/intent-backlog.md`: IB-3 is the training page, IB-4 the landing and highest-scores pages.

Answers: `rough-mockups-questions.md` Q1–Q7.

Desktop browser on this PC only (Q5). Labels, numbers and the command line below are placeholders.

## Information Architecture

```
[Landing]  <---->  [Scores]  <---->  [Training]
   (top bar with wordmark, Scores, Training on every page)
                                       |
                                       +--> [Confirm run dialog]
                                       +--> [Run detail]
```

<!-- Text fallback: three pages, Landing, Scores and Training, all linked from a top bar on every page. The training page opens a confirm-run dialog and a run detail view. -->

Every page is one click from every other (Q2).

## Screen 1: Landing (IB-4)

```
+--------------------------------------------------------------------------------+
| [gsm8k wordmark]                                     Scores    Training        |
|--------------------------------------------------------------------------------|
|                                                                                |
|    . : : . . : : . . : : . . : : . . : : . . : : . . : : . . : :               |
|    HALFTONE WORDMARK HEADLINE (dots part around the pointer)                   |
|    . : : . . : : . . : : . . : : . . : : . . : : . . : : . . : :               |
|                                                                                |
| One line: what this project is (a personal fine-tuning lab on this PC)         |
|                                                                                |
| Best so far: [model] [method]   [dev acc]   [gain vs baseline]                 |
|                                                                                |
| [ Go to training ]     [ See scores ]                                          |
|                                                                                |
+--------------------------------------------------------------------------------+
```

<!-- Text fallback: top bar with wordmark, Scores and Training. A large halftone wordmark headline, a one-line description, a "best so far" summary line, and two buttons: Go to training and See scores. -->

| State | What shows |
|---|---|
| Empty (no runs yet) | "Best so far" reads "No runs yet: start with a baseline on the training page", with the Go to training button |
| Loading | Headline renders at once; the "best so far" line shows a skeleton bar |
| Populated | As drawn |
| Error (run log unreadable) | "Best so far" reads "Run log could not be read" and names the file; the headline still renders |
| Edge (reduce motion on) | Dots stay still; no pointer or click animation (Q6) |

Accessibility: h1 is the wordmark text (the canvas is decorative, `aria-hidden`, with the wordmark also as real text); landmarks are header with nav, and main; the keyboard entry point is a skip link, then the top bar (Q6).

## Screen 2: Highest Scores (IB-4)

```
+--------------------------------------------------------------------------------+
| [gsm8k wordmark]                                     Scores    Training        |
|--------------------------------------------------------------------------------|
| Highest scores                             Filter: [model v] [method v]        |
|                                                                                |
| Rank | Run id | Model | Method | Dev | Test | Gain | Min | Date | Pick         |
| -----+--------+-------+--------+-----+------+------+-----+------+-----         |
|  BL  | base-1 | 1.7B  | none   | xx% | xx%  |  --  | 25  | ...  | [ ]          |
|   1  | sft-2  | 1.7B  | SFT    | xx% | xx%  | +x.x | 41  | ...  | [ ]          |
|   2  | sft-1  | 1.7B  | SFT    | xx% |  --  | +x.x | 38  | ...  | [ ]          |
| (BL = baseline row, always shown)                                              |
|                                                                                |
| [ Compare selected (2) ]                                                       |
|--------------------------------------------------------------------------------|
| Compare: run A vs run B -> settings side by side, accuracy delta,              |
| both training curves overlaid                                                  |
|                                                                                |
+--------------------------------------------------------------------------------+
```

<!-- Text fallback: a ranked table of runs with columns rank, run id, model, method, dev accuracy, test accuracy, gain over baseline, minutes, date and a pick checkbox. The baseline row is always shown and marked BL. Picking two runs enables Compare, which shows their settings side by side, the accuracy difference and both training curves overlaid. -->

Ranking is by dev accuracy, with the test column shown where a run was scored on test (Q4). Gain is measured against the baseline of the same model (intent-statement.md).

| State | What shows |
|---|---|
| Empty | "No scored runs yet. Run a baseline from the training page." with a link |
| Loading | Table skeleton of 3 rows |
| Populated | As drawn |
| Error | "Run log could not be read" naming the file, with a Retry button |
| Edge | One run only: the Compare button is disabled with "Pick two runs to compare"; a run with no test score shows "--", not 0%; ties are ordered by date |

Accessibility: h1 "Highest scores"; a real table with column headers; Pick checkboxes are labelled by run id; gain shows a + or - sign, never colour alone (Q6).

## Screen 3: Training (IB-3)

```
+--------------------------------------------------------------------------------+
| [gsm8k wordmark]                                     Scores    Training        |
|--------------------------------------------------------------------------------|
| Training                                              Status: RUNNING  sft-3   |
| +--------------------------------------------+ +-----------------------------+ |
| | LIVE CURVES                                | | DIALS                       | |
| | loss, learning rate, dev accuracy          | | Model     [0.6B | 1.7B v]   | |
| | (reward, KL, answer length if RL)          | | Method    [SFT v]           | |
| |                                            | | LR        [2e-4      ]      | |
| |   \__                                      | | Epochs    [1         ]      | |
| |      \____.___                             | | LoRA rank [16        ]      | |
| |                                            | | Max len   [512       ]      | |
| | step 120/400   elapsed 0:19   eta 0:21     | | [ Start run ]  [ Stop ]     | |
| +--------------------------------------------+ +-----------------------------+ |
|--------------------------------------------------------------------------------|
| Past runs: run id | status | started | minutes | dev acc | open >              |
|                                                                                |
+--------------------------------------------------------------------------------+
```

<!-- Text fallback: the training page shows run status at the top right. Live curves sit in a large panel at the left (loss, learning rate, dev accuracy, plus reward, KL and answer length for reinforcement learning) with step, elapsed time and estimated time remaining. The dials panel at the right holds model, method, learning rate, epochs, LoRA rank and max length, with Start run and Stop buttons. A list of past runs is below. -->

Layout follows Q3: curves first and large, status with start and stop beside them, dials at the right, past runs below. The dials shown are examples; the full set is decided in requirements.

| State | What shows |
|---|---|
| Empty (no run ever) | Curves panel: "No run yet. Set the dials and press Start run." Past runs: "None yet" |
| Idle (last run finished) | Status "IDLE"; curves show the last run, labelled with its run id; Start enabled, Stop disabled |
| Running | As drawn; Start disabled with "A run is already active" (one at a time, Q7); Stop enabled |
| Loading | Curves skeleton until the first metric arrives; "Waiting for first step..." |
| Error (run failed) | Status "FAILED" with the last log lines and the exit reason; curves stop at the last step |
| Edge | Live updates drop: "Live updates paused, reconnecting" with the time of the last update; invalid dial: the field names the allowed range and Start stays disabled |

Accessibility: h1 "Training"; the status sits in a polite live region; every dial has a visible label; each chart has a text summary (latest value per curve) for screen readers; Start and Stop are real buttons reachable by Tab (Q6).

## Screen 4: Confirm Run Dialog (IB-3)

```
+--------------------------------------------------------------------------------+
| Confirm run                                                                    |
|--------------------------------------------------------------------------------|
| Run id:   sft-3                                                                |
| Model:    Qwen3-1.7B-Base          Method: SFT (LoRA rank 16)                  |
| Changes vs last run: LR 1e-4 -> 2e-4                                           |
| Estimated time: ~40 min (cap 3 h)                                              |
| Command:  python -m train.sft --config runs/sft-3.yaml --run-id sft-3          |
|                                                                                |
| [ Cancel ]                                                     [ Start run ]   |
+--------------------------------------------------------------------------------+
```

<!-- Text fallback: a confirmation dialog shows the run id, model, method, what changed since the last run, the estimated time against the 3-hour cap, and the exact command, with Cancel and Start run buttons. -->

This dialog checks the dials, shows the summary and the exact command, and launches only on confirm (Q7). The command line is a placeholder; the real one is defined in later stages.

| State | What shows |
|---|---|
| Valid | As drawn |
| Over the cap | Estimated time above 3 h: a warning line, and Start needs a second confirm |
| Busy | Another run is active: the dialog does not open; the page says why |
| Error on launch | The dialog stays open and shows why the launch failed |

Accessibility: dialog role with focus trapped inside; Escape cancels; focus returns to the Start button on close (Q6).

## Assumptions & Open Questions

- [assumption] Ranking by dev accuracy (test shown where scored) keeps the test split out of everyday decisions (scope-document.md out-of-scope list).
- [assumption] Nico adds screenshots to `inputs/design/` before the website is built (Q1).
