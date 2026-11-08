# Refined Mockups: Fine tune model for grade math

Mid-to-high fidelity: real labels, real states and the chosen look. Built from the rough screens in `ideation/rough-mockups/wireframes.md`, the flows in `ideation/rough-mockups/user-flow.md`, the stories in `inception/user-stories/stories.md` (US4.1–US4.6, US3.4, US3.6), the requirements in `inception/requirements-analysis/requirements.md` (FR4.1–FR4.6, NFR9, NFR10) and the testing posture in `inception/practices-discovery/team-practices.md` (website behaviour tested with Vitest, the look checked by hand). Answers: `refined-mockups-questions.md` Q1–Q5.

Desktop browser on this PC only (rough-mockups Q5). Numbers, run ids and dates below are examples. Component behaviour is in `interaction-spec.md`, tokens and shadcn/ui parts in `design-system-mapping.md`, accessibility in `accessibility-checklist.md`.

## Look and Feel

- **Theme (Q1):** dark "night" on every page. Background `#0c0c0b`, text and dots `#e9e4da`, muted text `#8c8882`, hairlines at 16% of the text colour, one orange accent `#e9762b` for the active run, the current curve and focus rings. The look follows Nico's inputs: the pasted Halftone Wordmark Footer (`inputs/halftone-wordmark-footer.tsx.txt`, preset `night`) and the Gateway Flow screenshot (`inputs/design/training-live-gateway-flow.png`), recreated from scratch (the screenshot has no source).
- **Type (Q1):** system sans for text; monospace with tabular figures for numbers, run ids, dials and commands; small uppercase tracked monospace labels (10.5 px, letter-spacing 0.18 em) for section labels, as in the pasted component.
- **Wordmark (Q2):** `gsm8k`, lowercase, in the top bar and as the landing headline.
- **Texture:** dotted, monochrome motifs only where they carry meaning (headline, hourglass); panels are flat with 0.5 px hairline borders and no shadows.
- **Layout grid:** content max width 1280 px, 24 px gutters, 8 px spacing scale (4, 8, 16, 24, 32, 48). Minimum supported width 1024 px; below that the page stacks in one column without further design (phones and tablets are out of scope).

## Top Bar (every page, US4.1)

```
+------------------------------------------------------------------------------------------+
| [Skip to content]  (visible only on focus)                                               |
| gsm8k                                                       Scores     Training          |
|------------------------------------------------------------------------------------------|  <- 0.5px hairline
```

<!-- Text fallback: a top bar with the lowercase wordmark gsm8k at the left, linking to the landing page, and the links Scores and Training at the right. A skip link appears first when focused. A hairline separates the bar from the page. -->

- Height 56 px, sticky. The current page's link is underlined with a 1 px accent line and marked `aria-current="page"`; colour is never the only marker.
- When a run is active, a small monospace tag `● RUNNING q06-sft-dev-3` sits left of "Scores" on every page and links to Training.

## Screen 1: Landing (US4.2)

```
+------------------------------------------------------------------------------------------+
| gsm8k                                       ● RUNNING q06-sft-dev-3   Scores   Training  |
|------------------------------------------------------------------------------------------|
|                                                                                          |
|   .:::::.   .::::::.  .::.   .::.   .:::::.   .::.  .::.                                  |
|  ::'  `::  ::'       ::::. .::::  ::'   `::  ::: .::'      HALFTONE WORDMARK  "gsm8k"    |
|  ::.  .::  `::::::.  :: `::' ::   `::::::'   ::::::.       full width, dots part         |
|   `:::::'        ::  ::      ::   ::'   `::  ::: `::.      around the pointer, warm      |
|  .:.  .::  ::::::::  ::      ::   `::::::'   :::  `::.     toward orange when pushed     |
|   `::::'                                                                                 |
|------------------------------------------------------------------------------------------|
|  A PERSONAL FINE-TUNING LAB ON THIS PC                                                   |
|  Teaching small open models grade-school math, one measured run at a time.               |
|                                                                                          |
|  BEST SO FAR   Qwen3-1.7B-Base · SFT · dev 68.1% · +9.4 pts vs baseline                  |
|                                                                                          |
|  [ Go to training ]   [ See scores ]                                                     |
+------------------------------------------------------------------------------------------+
```

<!-- Text fallback: the landing page shows the top bar, then a large halftone wordmark gsm8k across the full width whose dots move away from the pointer. Below a hairline: a small uppercase label "A personal fine-tuning lab on this PC", a one-line description, the "Best so far" line with model, method, dev accuracy and gain over the baseline, and two buttons, Go to training and See scores. -->

- The headline is the pasted component adapted as a hero: no link columns, no back-to-top, `crop` 0 so the whole word shows, about 40% of the viewport height, wordmark `gsm8k`, preset `night`.
- "Best so far" uses the best run by dev accuracy across both models (stories.md US2.5 definition), with its gain against that model's own baseline. The gain carries its sign (`+9.4 pts`).

| State | What shows |
|---|---|
| Empty (no runs yet) | "BEST SO FAR  No runs yet: start with a baseline on the training page", and Go to training is the primary button (AC4.2.2) |
| Loading | The headline renders at once; the best-so-far line is a 320 px skeleton bar |
| Populated | As drawn (AC4.2.1) |
| Only baselines scored | "BEST SO FAR  Qwen3-1.7B-Base · baseline · dev 58.7% · no tuned run yet" |
| Error (run log unreadable) | "BEST SO FAR  Run log could not be read: results/runs.csv"; the headline still renders (AC4.2.3) |
| Reduce motion on | The dots are drawn once and stay still; no pointer push, no click ring (AC4.2.4) |

## Screen 2: Highest Scores (US4.3, US4.4, US3.6)

```
+------------------------------------------------------------------------------------------+
| gsm8k                                                        Scores    Training          |
|------------------------------------------------------------------------------------------|
| Highest scores                                  Model [All ▾]   Method [All ▾]           |
| Ranked by dev accuracy. Gain is against the same model's baseline.                       |
|                                                                                          |
|  #   RUN ID            MODEL  METHOD  DEV     TEST    GAIN      MIN   DATE        PICK   |
|  ──  ────────────────  ─────  ──────  ──────  ──────  ────────  ────  ──────────  ────   |
|  BL  q17-base-dev-1    1.7B   base    58.7%   57.9%   —         24    2026-11-02  [ ]    |
|  BL  q06-base-dev-1    0.6B   base    41.3%   40.2%   —         11    2026-11-01  [ ]    |
|  1   q17-sft-dev-2 ★   1.7B   sft     68.1%   67.0%   +9.4 pts  52    2026-11-05  [x]    |
|  2   q17-sft-dev-1     1.7B   sft     65.9%   --      +7.2 pts  49    2026-11-04  [x]    |
|  3   q06-sft-dev-3     0.6B   sft     47.0%   --      +5.7 pts  23    2026-11-04  [ ]    |
|                                                                                          |
|  ★ = finalist                                                                            |
|  [ Compare selected (2) ]                                                                |
|------------------------------------------------------------------------------------------|
|  COMPARE   q17-sft-dev-2  vs  q17-sft-dev-1                    dev  +2.2 pts             |
|  ┌ Settings ──────────────────────────┐  ┌ Curves (loss) ───────────────────────────┐    |
|  │ dial          sft-dev-2  sft-dev-1 │  │  ─── q17-sft-dev-2 (orange)              │    |
|  │ learning rate 2e-4       1e-4  ◆   │  │  ┄┄┄ q17-sft-dev-1 (off-white, dashed)   │    |
|  │ epochs        1          1         │  │   \__                                     │    |
|  │ LoRA rank     16         16        │  │      \___.____                            │    |
|  │ ...                                │  │  [Loss] [Dev accuracy] [Learning rate]    │    |
|  └────────────────────────────────────┘  └───────────────────────────────────────────┘    |
+------------------------------------------------------------------------------------------+
```

<!-- Text fallback: the scores page has the title Highest scores with model and method filters. A table lists runs ranked by dev accuracy with columns rank, run id, model, method, dev accuracy, test accuracy, gain in points, minutes, date and a pick checkbox. Baseline rows are marked BL and always shown; finalists carry a star. A Compare selected button sits under the table. The compare panel shows the two runs' settings side by side, with changed dials marked by a diamond and the word "changed" for screen readers, the accuracy difference, and both curves overlaid with a switch between loss, dev accuracy and learning rate. -->

- Each baseline row (BL) sits at the top of the table, one per model, and stays under any filter (AC4.3.1, AC4.3.3). Other rows rank by dev accuracy, ties by date.
- Every number is monospace and right-aligned. A missing test score shows `--`, never 0% (AC4.3.2).
- A row's overflow menu `⋯` holds **Mark as finalist** or **Unmark finalist** (AC4.3.5) and, for finalists only, **Score on test…** (US3.6). For a non-finalist that item is disabled with the reason "Only finalists can be scored on the test split".
- The two compared runs are told apart by line style (solid and dashed) and by name, not only by colour.

| State | What shows |
|---|---|
| Empty | "No scored runs yet. Run a baseline from the training page." with a link (AC4.3.4) |
| Loading | A table skeleton of 3 rows |
| Populated | As drawn |
| Error | "Run log could not be read: results/runs.csv" with a Retry button (AC4.3.4) |
| Skipped rows | A muted line above the table: "1 malformed row in results/runs.csv was skipped" (AC3.1.3) |
| One or no run picked | Compare is disabled with "Pick two runs to compare" (AC4.4.2) |
| Third pick | The third checkbox is refused and the hint reads "Two runs are already picked. Unpick one first." (AC4.4.2) |
| Picked run without curves | Its curve area reads "No curve recorded for q06-base-dev-1"; the other curve still shows (AC4.4.3) |
| Filter matches nothing | "No runs match these filters." with a Clear filters button; baseline rows stay |

## Screen 3: Training (US4.5, US4.6, US3.4)

```
+------------------------------------------------------------------------------------------+
| gsm8k                                       ● RUNNING q06-sft-dev-3   Scores   Training  |
|------------------------------------------------------------------------------------------|
| Training                                                                                 |
| ┌──────────────────────────────────────────────────────────────────────────────────────┐ |
| │ .  .  .  .  .  .  .  .  .  .  . .:::::::. .  .  .  .  .  .  .  .  .  .  .  .  .  .   │ |
| │   .  .  .  .  .  .  .  .  .  . `:::::::' .  .  .  .  .  .  .  .  .  .  .  .  .  .   │ |
| │ RUNNING  q06-sft-dev-3     .  .  .  `:::'  .  .  .     step 120 / 400   30%         │ |
| │ SFT · Qwen3-0.6B-Base         .  .  . :  . .  .  .     elapsed 0:19   left ~0:44    │ |
| │   .  .  .  .  .  .  .  .  .  .  .  .:::. .  .  .  .  .  .  .  .  .  .  .  .  .  .   │ |
| │ .  .  .  .  .  .  .  .  .  .  . .:::::::. .  .  .  .  .  .  .  .  .  .  .  .  .  .   │ |
| └──────────────────────────────────────── hourglass band, 280 px ─────────────────────┘ |
| ┌ LIVE CURVES ─────────────────────────────────────────┐ ┌ DIALS ─────────────────────┐ |
| │ [Loss] [Learning rate] [Dev accuracy]                │ │ Model      [0.6B ▾]        │ |
| │                                                      │ │ Method     [SFT ▾]         │ |
| │ 1.8 ┤\                                               │ │ Learning rate [2e-4  ]     │ |
| │     ┤ \__                                            │ │ Epochs        [1     ]     │ |
| │ 0.9 ┤    \___.____.___                               │ │ LoRA rank     [16 ▾ ]     │ |
| │     ┼┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄  │ │ LoRA alpha    [32    ]     │ |
| │      0        100       200       300       400 step │ │ Max length    [512   ]     │ |
| │ Latest: loss 0.94 · lr 1.9e-4 · dev —                │ │ Examples      [all   ]     │ |
| └──────────────────────────────────────────────────────┘ │ Batch size    [4     ]     │ |
|                                                          │ Warmup        [0.03  ]     │ |
|                                                          │ Seed          [42    ]     │ |
|                                                          │ Answer format [step-by-step▾]│ |
|                                                          │ [ Add to queue ] [ Stop ]  │ |
|                                                          │ Runs after q06-sft-dev-3.  │ |
|                                                          └────────────────────────────┘ |
| PAST RUNS                                                                                |
|  RUN ID            STATUS    STARTED            MIN   DEV     ·                          |
|  q06-sft-dev-2     IDLE ✓    2026-11-04 20:10   23    47.0%   Open ›                     |
|  q06-sft-dev-1     STOPPED   2026-11-04 19:02   7     --      Open ›                     |
|  q06-base-dev-1    FAILED ✕  2026-11-03 21:40   2     --      Open ›                     |
+------------------------------------------------------------------------------------------+
```

<!-- Text fallback: the training page shows a full-width hourglass band at the top, 280 px tall: dotted lines converge to a narrow waist in the middle; dots drain from the top half through the waist into the bottom half as steps complete. Written over the band at the left: the status RUNNING, the run id and the method and model; at the right: step 120 of 400, 30%, elapsed time and time left. Below, the live curves panel is the largest panel at the left, with tabs for loss, learning rate and dev accuracy, a step axis and a "Latest" text line. The dials panel at the right lists all eleven dials with Start run and Stop buttons; while a run is active, the Start button reads "Add to queue" with the note "Runs after" the active run. Past runs are listed at the bottom with run id, status, start time, minutes, dev accuracy and an Open link. -->

### The hourglass band (Q3, Q4)

- **Shape:** the Gateway Flow look: about 48 dotted lines fanning from the top and bottom edges into a narrow waist at the centre, on black, with sparse brighter dots. Drawn on a canvas; decorative to assistive technology (the same facts are text over the band).
- **Meaning:** an hourglass of progress. The top half holds the steps still to come, the bottom half the steps done. As each metrics line arrives, dots drain from the top half through the waist into the bottom half, so the share of dots below the waist equals `step / total steps`. For an evaluation run, the fraction is `problems scored / problems to score`.
- **Motion:** dots travel through the waist in a short eased fall (under 300 ms per batch) when a new metrics line arrives; between lines the field rests. The brighter scattered dots fall with the others.
- **Text over the band:** left, status (RUNNING, IDLE, STOPPED, FAILED) with the run id and "method · model"; right, `step 120 / 400`, the percentage, elapsed time and time left (or "No estimate yet").

| Band state | What shows |
|---|---|
| No run ever | A full top half, an empty bottom half, the text "No run yet. Set the dials and press Start run." (AC4.5.4) |
| Waiting for the first step | Full top half; "Waiting for first step..." over the band (AC4.5.4) |
| Running | Dots drain as drawn; text as drawn |
| Finished (IDLE) | All dots below the waist; "IDLE · last run q06-sft-dev-2 finished · dev 47.0%" |
| STOPPED | The dots freeze at the stopped fraction and dim to 50%; "STOPPED at step 210 / 400 · no score recorded" |
| FAILED | The dots freeze at the failed fraction and dim; "FAILED at step 37 / 400 · GPU out of memory" with a "Show log" link that opens the failure panel (AC3.5.1, AC3.5.2) |
| Live updates paused | A banner across the band's top edge: "Live updates paused, reconnecting · last update 20:31:07" (AC4.5.3); the band keeps the last known fraction |
| Reduce motion on | Dots jump to the new fraction with no fall animation |

### The fine-tuning view (US4.7, added 2026-11-08)

The hourglass band only tells progress. Under it, full width, sits a panel "How the model is fine-tuned" that shows what a training step does (Nico, 2026-11-08: "make sure this visualization shows me how a neural model gets fine tuned").

```
+------------------------------------------------------------------------------------------+
| HOW THE MODEL IS FINE-TUNED   sft · Qwen3-1.7B-Base        Following the live run        |
| TRAINING TEXT        LoRA adapters: small, trained (orange)                  GUESS        |
| [tokens]  [embed]    ▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫  [head]   right word  ████░░ 39%    |
| 4 examples ········> ▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮ ·····>  other words ░░░░░░░         |
|                      28 decoder layers: frozen (dotted)                                  |
| 1 READ    2 GUESS      3 SCORE            4 BLAME         5 NUDGE        ┌ ONE LAYER ─────┐|
| 4 per     answer       loss 0.94, 39%     grad norm 0.42  lr 2e-4        │ W 2048 x 2048   │|
| step      words only   47.8% lower        ...             ...            │ + B x A  65,536 │|
| Step 120 of 400 · 480 examples seen                                      └─────────────────┘|
| 17,432,576 trained of 1,738,007,552 weights (1.0%)    Measured: ...  Drawn: ...          |
+------------------------------------------------------------------------------------------+
```

- **Picture** (hidden from assistive technology): the same dotted, monochrome look as the band. A page of tokens on the left feeds the model drawn as a row of 28 dotted columns (one per decoder layer, frozen) with a small orange outlined square above each (its LoRA adapter, trained), then the output head. On the right a bar shows the average chance the model gave the right next word (e to the power of minus the loss) against the other words.
- **Each step line** replays one pass, 0.7 s: a light sweeps forward through the layers (read, guess), the right-word bar settles (score), an orange sweep runs back through the layers (blame) and every adapter square flashes (nudge). Between lines the picture rests. With reduce motion on the picture does not move and the panel carries `data-motion="still"`.
- **Text**: the five stages as numbered cards, each with a one-line meaning and the newest figure; the step line "Step 120 of 400 · 480 examples seen"; the counts "17,432,576 trained of 1,738,007,552 weights (1.0%)"; a "One layer up close" figure with the frozen matrix and the adapter matrices A and B; a note that the figures are measured (step, loss, gradient norm, learning rate) and the picture is an illustration.
- **Not a fine-tune** (`cotgen`, `base`, `best`): the layers stay grey, no adapter is lit, a sweep goes forward only, the five stage cards give way to "This run does not change the model" with what it does instead, and the progress line reads "90 of 1500 problems written" (or "scored").
- **Ended run or a past run opened**: a slider "Replay step" and a "Play replay" button step through the run's step lines in about 20 seconds; the panel reads "Replaying step N of M". The live run reads "Following the live run".
- **States**: no run ever: "Nothing to show yet: start a fine-tune to watch the model change."; a fine-tune before its first line: "Waiting for the first logged step"; an ended fine-tune with no step line: "No step lines were recorded for this run."

### Live curves (Q5, AC4.5.1, AC4.5.2)

- Tabs: **Loss**, **Learning rate**, **Dev accuracy**; for reinforcement-learning runs also **Reward**, **KL**, **Answer length**. One curve per tab keeps each y-axis honest.
- Clean 1.5 px lines in the text colour; the run being watched live is drawn in the orange accent. Gridlines are faint dotted lines at 12% of the text colour. X axis: step. Hovering, or moving through the points with the arrow keys, shows the exact value at that step.
- Under the chart, a text line holds the latest value of every curve ("Latest: loss 0.94 · lr 1.9e-4 · dev —") for screen readers and quick reading.
- Opening a past run loads its curves into this panel with the heading "Viewing q06-sft-dev-1 (STOPPED)" and a "Back to live" button (AC4.5.5).

### Dials panel (AC4.6.1)

- All eleven dials from the stories.md Training Dials table, each with a visible label above the field, its default filled in, and its allowed range as helper text ("1e-5 to 5e-4"). Model, LoRA rank and answer format are selects; the rest are number fields.
- Checked when the field loses focus. An invalid value shows text under the field ("Learning rate must be between 1e-5 and 5e-4") with an error icon, and Start stays disabled with "Fix the highlighted dial to start".
- Method select: SFT, and GRPO once that could-have is built; an evaluation-only choice "Evaluate on dev" starts a dev-split evaluation of the base model or a chosen adapter.

| Panel state | What shows |
|---|---|
| Idle, valid | Start enabled; Stop disabled |
| Running | The Start button reads "Add to queue"; Stop enabled; the dials stay editable for the next run (AC4.6.4; changed 2026-10-31, inception/changes.md) |
| Queue full | "Add to queue" disabled with "The queue is full (10 waiting)" (AC3.7.3) |
| Invalid dial | Start disabled with the field-level message |
| Service unreachable | The panel disables Start with "The run service is not reachable at 127.0.0.1:8000. Start it with `make serve`." |

### Queued runs (AC4.6.7, US3.7)

Added 2026-10-31 with the run queue (inception/changes.md; domain-design Q3, Q5). A list between the panels and Past runs, shown only while runs are waiting:

```
| QUEUED RUNS                                                                             |
|  #  RUN ID            MODEL  METHOD   ADDED              ·                              |
|  1  q06-sft-dev-4     0.6B   sft      2026-11-04 20:41   [ Remove ]                     |
|  2  q17-sft-dev-3     1.7B   sft      2026-11-04 20:43   [ Remove ]                     |
```

<!-- Text fallback: while runs wait, a Queued runs list shows each waiting run's position, run id, model, method and when it was added, with a Remove button per row. -->

- Runs start in this order when the GPU is free; positions move up as runs start or are removed.
- Remove asks nothing extra (a waiting run has used no GPU time) and the row disappears; focus moves to the next row's Remove button, or to the Start button when the list empties.
- If a terminal run holds the GPU, the first row adds "Waiting for terminal run <run id>".

### Failure panel (AC3.5.1–AC3.5.3)

Opened from "Show log" on a FAILED run: the exit reason as a heading, then the last 20 log lines in a monospace block that scrolls, and a Copy button. If the log cannot be read: "Run log could not be read: outputs/q06-base-dev-1/run.log".

## Dialog: Confirm Run (AC4.6.2, AC4.6.3, AC4.6.5, AC4.6.6)

```
+----------------------------------------------------------------------+
| Confirm run                                                      [×] |
|----------------------------------------------------------------------|
| Run id        q06-sft-dev-3                                          |
| Model         Qwen3-0.6B-Base                                        |
| Method        SFT (LoRA rank 16)                                     |
| Changes       learning rate 1e-4 → 2e-4                              |
| Estimated     ~41 min (cap 3 h)                                      |
| Command       python -m gsm8k.train --config outputs/q06-sft-dev-3/  |
|               config.yaml --run-id q06-sft-dev-3          [Copy]     |
|                                                                      |
|                                      [ Cancel ]   [ Start run ]      |
+----------------------------------------------------------------------+
```

<!-- Text fallback: the Confirm run dialog lists the run id, model, method, what changed since the last run, the estimated time against the 3-hour cap, and the exact command with a Copy button, followed by Cancel and Start run buttons. -->

| State | What shows |
|---|---|
| Valid | As drawn |
| No earlier run | Changes reads "First run of this kind" |
| No estimate | Estimated reads "No estimate yet" |
| Over the cap | A warning line with an icon: "Estimated time is above the 3-hour cap." Start run becomes "Start anyway" and asks once more: "Start a run estimated at 3 h 40 min?" with Cancel and Start anyway (AC4.6.3) |
| Launching | Start run shows a spinner and "Starting…"; both buttons disabled |
| A run is active | An extra line: "Queued behind q17-sft-dev-1 · position 2"; the button reads "Add to queue" (AC4.6.2) |
| Error on launch | The dialog stays open with the reason under the summary, e.g. "The queue is full (10 waiting)" (AC4.6.5) |

The command shown is illustrative; the real entry points are set in later stages.

## Dialog: Stop Run (US3.4)

```
+------------------------------------------------------------+
| Stop q06-sft-dev-3?                                        |
| The run ends now. Its curves so far are kept; no score is  |
| recorded.                                                  |
|                              [ Keep running ]  [ Stop run ] |
+------------------------------------------------------------+
```

<!-- Text fallback: the Stop dialog names the run, says the run ends now, its curves are kept and no score is recorded, with Keep running and Stop run buttons. -->

If the run already ended when Stop is pressed: "This run has already ended." with a Close button (user-flow.md, Stop a Run).

## Dialog: Score a Finalist on Test (US3.6)

```
+----------------------------------------------------------------------+
| Score q17-sft-dev-2 on the test split                                |
|----------------------------------------------------------------------|
| The test split (1,319 problems) is held out. Scoring on it is for    |
| finalists only, and the result must never steer tuning.              |
| Estimated     ~1 h 52 min                                            |
| Command       python -m gsm8k.evaluate --adapter checkpoints/        |
|               q17-sft-dev-2 --split test --run-id q17-best-test-1    |
|                                                                      |
| [ ] I understand this uses the held-out test split.                  |
|                                      [ Cancel ]   [ Score on test ]  |
+----------------------------------------------------------------------+
```

<!-- Text fallback: the test-split dialog for a finalist explains that the test split is held out and for finalists only, shows the estimate and the command, and has a checkbox "I understand this uses the held-out test split". Score on test stays disabled until the box is ticked. -->

Score on test stays disabled until the checkbox is ticked; ticking it is the second confirmation (AC3.6.3).

## Story Coverage

| Story | Where |
|---|---|
| US4.1 | Top Bar; every screen |
| US4.2 | Screen 1 |
| US4.3 | Screen 2 table, filters, finalist menu |
| US4.4 | Screen 2 compare panel |
| US4.5 | Screen 3 hourglass band, live curves, past runs |
| US4.6 | Screen 3 dials panel; Confirm Run dialog |
| US4.7 | Screen 3 fine-tuning view |
| US3.4 | Stop Run dialog |
| US3.5 | Screen 3 failure panel |
| US3.6 | Screen 2 finalist menu; Score a Finalist on Test dialog |

## Assumptions & Open Questions

- [assumption] The service listens on `127.0.0.1:8000` and starts with `make serve`; both are placeholders until Functional Design names them.
- [assumption] The landing headline uses the pasted component with link columns and back-to-top turned off and `crop` 0; any change to its source stays inside `components/ui/`.
- [assumption] Brighter "spark" dots in the hourglass are decoration only and carry no data.
