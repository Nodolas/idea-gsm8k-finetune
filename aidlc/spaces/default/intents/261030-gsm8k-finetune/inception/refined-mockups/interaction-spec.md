# Interaction Specification

How each website component behaves, in the format of the design agent's component template. Screens are in `mockups.md`; the rough structure comes from `ideation/rough-mockups/wireframes.md` and the flows from `ideation/rough-mockups/user-flow.md`. Behaviour traces to `inception/user-stories/stories.md` (US4.1–US4.6, US3.4–US3.6) and `inception/requirements-analysis/requirements.md` (FR3, FR4, NFR9, NFR10). Each behaviour named by an AC ID is checked by a Vitest test named after it (`inception/practices-discovery/team-practices.md`, Testing Posture; user-stories Q6).

## Shared Rules

- **Breakpoints:** desktop only (rough-mockups Q5). Designed for widths of 1024 px and up; at 1280 px and up the content is centred at 1280 px. Below 1024 px panels stack in one column with no further design. No mobile or tablet layout.
- **Data source:** every component reads from the local run service only (US3.1). Run list and status are fetched on page load and after any action; metrics arrive on a stream (US4.5).
- **Feedback timing:** an action that takes longer than 300 ms shows a spinner on its own button; after 5 s the button's label adds "Still working…".
- **Motion:** 150–300 ms, ease-out on enter, ease-in on exit. With `prefers-reduced-motion: reduce`, transitions are instant and canvases draw still frames.
- **Errors:** always text near the cause, with an icon, saying what happened and what to do; never a raw status code.
- **Focus:** a 2 px accent (`#e9762b`) outline with 2 px offset on every focusable element; never removed.

## TopBar

| Field | Value |
|---|---|
| Component | TopBar |
| Description | Site-wide header with the wordmark, page links and the active-run tag |
| Category | navigation |

### States

| State | Description | Trigger |
|---|---|---|
| default | Wordmark left; Scores, Training right; current page underlined and `aria-current="page"` | page load |
| run active | Tag `● RUNNING <run id>` before the links, linking to Training | status RUNNING |
| focus | Skip link becomes visible as the first stop | Tab from page top |

### Props / Inputs

| Prop | Type | Required | Default | Description |
|---|---|---|---|---|
| currentPage | `"landing" \| "scores" \| "training"` | yes | — | Marks the current link |
| activeRunId | string \| null | no | null | Shows the running tag when set |

### Responsive Behaviour

| Breakpoint | Behaviour |
|---|---|
| desktop (≥1024px) | As above, 56 px tall, sticky |

### Accessibility

| Requirement | Implementation |
|---|---|
| ARIA role | `<header>` with `<nav aria-label="Main">` |
| Keyboard interaction | Tab order: skip link, wordmark, run tag (if shown), Scores, Training (AC4.1.2) |
| Label / aria-label | Wordmark link `aria-label="gsm8k home"` |
| Contrast ratio | Text 15:1, accent 5.9:1 on `#0c0c0b` |
| Screen reader | Current page announced via `aria-current` |
| Focus management | Skip link moves focus to `<main id="main">` |

## HalftoneHeadline

| Field | Value |
|---|---|
| Component | HalftoneHeadline |
| Description | The pasted Halftone Wordmark Footer used as the landing hero, spelling `gsm8k` |
| Category | display |

### States

| State | Description | Trigger |
|---|---|---|
| default | Dots at rest forming the word | page load |
| pointer over | Dots within 80 px part on springs and warm toward `#e9762b` | pointer move |
| click | A shock ring runs through the word | click |
| reduced motion | Still dots; pointer and click do nothing (AC4.2.4) | `prefers-reduced-motion: reduce` |

### Props / Inputs

| Prop | Type | Required | Default | Description |
|---|---|---|---|---|
| wordmark | string | no | `"gsm8k"` | The word printed in dots |
| preset | string | no | `"night"` | Colour preset |
| columns | array | no | `[]` | Empty: no link columns in the hero |
| backToTop | boolean | no | false | Off in the hero |
| crop | number | no | 0 | Whole word visible |

### Responsive Behaviour

| Breakpoint | Behaviour |
|---|---|
| desktop (≥1024px) | Full content width, about 40% of viewport height; the canvas resizes with the window |

### Accessibility

| Requirement | Implementation |
|---|---|
| ARIA role | The canvas is `aria-hidden="true"`; the word is a real `<h1>` (visually hidden) (AC4.2.1) |
| Keyboard interaction | None; not focusable |
| Label / aria-label | `<h1>gsm8k</h1>` |
| Contrast ratio | Decorative; the h1 text is the accessible content |
| Screen reader | Announces "gsm8k, heading level 1" |
| Focus management | Not applicable |

## BestSoFar

| Field | Value |
|---|---|
| Component | BestSoFar |
| Description | One line on the landing page with the best run and its gain over its baseline |
| Category | display |

### States

| State | Description | Trigger |
|---|---|---|
| loading | 320 px skeleton bar | run list pending |
| populated | Model · method · dev accuracy · signed gain (AC4.2.1) | runs loaded |
| baselines only | Baseline dev accuracy and "no tuned run yet" | only base rows |
| empty | "No runs yet: start with a baseline on the training page" (AC4.2.2) | no rows |
| error | "Run log could not be read: <file>" (AC4.2.3) | service error |

### Props / Inputs

| Prop | Type | Required | Default | Description |
|---|---|---|---|---|
| runs | Run[] \| null | yes | — | From the run list |
| error | { file: string } \| null | no | null | Read failure |

### Responsive Behaviour

| Breakpoint | Behaviour |
|---|---|
| desktop (≥1024px) | One line; wraps after the method if narrower than 1024 px |

### Accessibility

| Requirement | Implementation |
|---|---|
| ARIA role | `<p>` with a visible label "Best so far" |
| Keyboard interaction | Not focusable |
| Label / aria-label | Label is visible text |
| Contrast ratio | 15:1 |
| Screen reader | Gain read as "plus 9.4 points" via `aria-label` on the number |
| Focus management | Not applicable |

## ScoresTable

| Field | Value |
|---|---|
| Component | ScoresTable |
| Description | Runs ranked by dev accuracy with baseline rows, filters, pick checkboxes and a row menu |
| Category | display |

### States

| State | Description | Trigger |
|---|---|---|
| loading | Three skeleton rows | run list pending |
| populated | Baseline rows first (BL), then runs by dev accuracy, ties by date (AC4.3.1) | runs loaded |
| filtered | Only matching rows; baseline rows stay (AC4.3.3) | filter change |
| filtered empty | "No runs match these filters." + Clear filters | filter change |
| empty | "No scored runs yet. Run a baseline from the training page." + link (AC4.3.4) | no rows |
| error | "Run log could not be read: <file>" + Retry (AC4.3.4) | service error |
| skipped rows | Muted note naming how many malformed rows were skipped | service reports skipped |
| two picked | Further pick checkboxes refuse with "Two runs are already picked. Unpick one first." (AC4.4.2) | 2 picks |

### Props / Inputs

| Prop | Type | Required | Default | Description |
|---|---|---|---|---|
| runs | Run[] | yes | — | Rows to show |
| finalists | string[] | yes | — | Run ids marked as finalists |
| picked | string[] | yes | `[]` | Up to two run ids |
| onPick | (runId) => void | yes | — | Toggle a pick |
| onToggleFinalist | (runId) => void | yes | — | Mark or unmark (AC4.3.5) |
| onScoreOnTest | (runId) => void | yes | — | Opens the test-split dialog for a finalist |

### Responsive Behaviour

| Breakpoint | Behaviour |
|---|---|
| desktop (≥1024px) | Full table; below 1024 px the table scrolls sideways inside its panel |

### Accessibility

| Requirement | Implementation |
|---|---|
| ARIA role | Native `<table>` with `<th scope="col">`; caption "Highest scores, ranked by dev accuracy" |
| Keyboard interaction | Tab to filters, each pick checkbox, each row menu; Space toggles a checkbox; menu opens with Enter, arrows move, Escape closes |
| Label / aria-label | Each checkbox `aria-label="Pick <run id>"`; menu button `aria-label="Actions for <run id>"` |
| Contrast ratio | 15:1 text, muted 5.5:1 |
| Screen reader | BL announced as "baseline"; star announced as "finalist"; `--` announced as "not scored"; gain with its sign (AC4.3.2) |
| Focus management | After marking a finalist, focus returns to the row's menu button |

## CompareView

| Field | Value |
|---|---|
| Component | CompareView |
| Description | Two picked runs: settings side by side, accuracy difference, overlaid curves |
| Category | display |

### States

| State | Description | Trigger |
|---|---|---|
| disabled | Compare button disabled with "Pick two runs to compare" (AC4.4.2) | fewer than 2 picks |
| open | Settings table, signed dev difference, overlaid curves (AC4.4.1) | Compare pressed |
| missing curve | "No curve recorded for <run id>"; the other curve shows (AC4.4.3) | no metrics file |

### Props / Inputs

| Prop | Type | Required | Default | Description |
|---|---|---|---|---|
| runA | Run | yes | — | First picked run (solid line, accent) |
| runB | Run | yes | — | Second picked run (dashed line, text colour) |

### Responsive Behaviour

| Breakpoint | Behaviour |
|---|---|
| desktop (≥1024px) | Settings left (40%), curves right (60%) |

### Accessibility

| Requirement | Implementation |
|---|---|
| ARIA role | `<section aria-labelledby>` titled "Compare <a> vs <b>" |
| Keyboard interaction | Curve tabs: arrows switch, Tab leaves |
| Label / aria-label | Changed dials marked with a ◆ and visually hidden text "changed" |
| Contrast ratio | Lines 3:1 or better against the panel |
| Screen reader | Text summary under the chart: final value of each run per curve |
| Focus management | Focus moves to the section heading when opened |

## HourglassBand

| Field | Value |
|---|---|
| Component | HourglassBand |
| Description | Full-width 280 px canvas band at the top of Training; dots drain through the waist as a run progresses (Q3, Q4) |
| Category | feedback |

### States

| State | Description | Trigger |
|---|---|---|
| empty | Full top half; "No run yet. Set the dials and press Start run." (AC4.5.4) | no run ever |
| waiting | Full top half; "Waiting for first step..." (AC4.5.4) | run started, no line yet |
| running | Share of dots below the waist = step / total steps (eval: scored / total); new dots fall on each metrics line | metrics line |
| finished | All dots below; IDLE text with last run and dev accuracy | run ended |
| stopped | Frozen at stopped fraction, dimmed 50%, STOPPED text | Stop |
| failed | Frozen, dimmed, FAILED text with reason and "Show log" | process failed |
| paused | Banner "Live updates paused, reconnecting · last update <time>" (AC4.5.3) | stream drop |
| reduced motion | No fall animation; dots jump to the new fraction | `prefers-reduced-motion: reduce` |

### Props / Inputs

| Prop | Type | Required | Default | Description |
|---|---|---|---|---|
| status | `"IDLE" \| "RUNNING" \| "STOPPED" \| "FAILED"` | yes | — | Run status (FR3.7) |
| step | number | no | 0 | Current step or problems scored |
| totalSteps | number | no | 0 | Total steps or problems |
| runId | string \| null | no | null | Shown over the band |
| elapsedS / etaS | number \| null | no | null | Elapsed and remaining seconds; null ETA shows "No estimate yet" |
| lastUpdate | Date \| null | no | null | For the paused banner |

### Responsive Behaviour

| Breakpoint | Behaviour |
|---|---|
| desktop (≥1024px) | Full content width, 280 px tall; about 48 lines; dot gap scales with width |

### Accessibility

| Requirement | Implementation |
|---|---|
| ARIA role | Canvas `aria-hidden="true"`; overlay text holds a `role="progressbar"` with `aria-valuenow`, `aria-valuemin=0`, `aria-valuemax=total`, `aria-valuetext="step 120 of 400"` |
| Keyboard interaction | "Show log" link reachable by Tab in the failed state |
| Label / aria-label | Progressbar `aria-label="Run progress"` |
| Contrast ratio | Overlay text sits on a 70% background scrim so it keeps 4.5:1 over the dots |
| Screen reader | Status changes announced by the page's polite live region (see DialsPanel), not by the band, so nothing is announced twice |
| Focus management | Not focusable except the link |

## CurvesPanel

| Field | Value |
|---|---|
| Component | CurvesPanel |
| Description | The largest panel on Training: one curve per tab, live for the current run, or a past run's curves (Q5) |
| Category | display |

### States

| State | Description | Trigger |
|---|---|---|
| loading | Chart skeleton | run selected, no data yet |
| live | Accent line grows as metrics lines arrive, no reload (AC4.5.2) | stream line |
| past run | Heading "Viewing <run id> (<status>)" and a "Back to live" button (AC4.5.5) | Open on a past run |
| RL tabs | Reward, KL, Answer length tabs added (AC4.5.1) | method `grpo` |
| no data | "No curve recorded for <run id>" | empty metrics |

### Props / Inputs

| Prop | Type | Required | Default | Description |
|---|---|---|---|---|
| lines | MetricsLine[] | yes | — | Parsed `metrics.jsonl` lines |
| method | `"sft" \| "grpo" \| "eval"` | yes | — | Chooses the tabs |
| live | boolean | yes | — | Accent colour and "Latest" updates |

### Responsive Behaviour

| Breakpoint | Behaviour |
|---|---|
| desktop (≥1024px) | About 64% of content width, 360 px chart height |

### Accessibility

| Requirement | Implementation |
|---|---|
| ARIA role | Tabs use `role="tablist"`; the chart is `role="img"` with `aria-label` naming the curve |
| Keyboard interaction | Arrow keys switch tabs; inside the chart, Left and Right move the read-out point by one step |
| Label / aria-label | Each tab labelled by its curve name |
| Contrast ratio | Line 15:1 (text colour) or 5.9:1 (accent); gridlines decorative |
| Screen reader | "Latest: loss 0.94 · lr 1.9e-4 · dev —" text under the chart |
| Focus management | "Back to live" returns focus to the past-runs row it came from |

## DialsPanel

| Field | Value |
|---|---|
| Component | DialsPanel |
| Description | The eleven dials with Start and Stop, and the page's status live region |
| Category | input |

### States

| State | Description | Trigger |
|---|---|---|
| default | All dials at their defaults; Start enabled; Stop disabled | page load, IDLE |
| invalid | Field message names the allowed range; Start disabled (AC4.6.1) | blur with bad value |
| running | The Start button reads "Add to queue"; Stop enabled (AC4.6.4; changed 2026-10-31, inception/changes.md) | status RUNNING |
| queue full | "Add to queue" disabled with "The queue is full (10 waiting)" (AC3.7.3) | 10 runs waiting |
| service down | Start disabled with how to start the service | service unreachable |

### Props / Inputs

| Prop | Type | Required | Default | Description |
|---|---|---|---|---|
| config | RunConfig | yes | defaults table | Current dial values |
| status | RunStatus | yes | — | Drives Start and Stop |
| onStart | (config) => void | yes | — | Opens the Confirm Run dialog |
| onStop | () => void | yes | — | Opens the Stop Run dialog |

### Responsive Behaviour

| Breakpoint | Behaviour |
|---|---|
| desktop (≥1024px) | About 36% of content width, right of the curves |

### Accessibility

| Requirement | Implementation |
|---|---|
| ARIA role | `<form>` with `<fieldset>` "Run settings"; status in `<div role="status" aria-live="polite">` |
| Keyboard interaction | Tab through dials in reading order, then Start, then Stop |
| Label / aria-label | `<label>` above each field; range helper linked with `aria-describedby`; error linked with `aria-describedby` and `aria-invalid="true"` |
| Contrast ratio | Field borders 3:1; text 15:1 |
| Screen reader | Status changes announced politely: "Run q06-sft-dev-3 is running", "stopped", "failed: GPU out of memory" |
| Focus management | After an invalid blur, focus stays in the field |

## ConfirmRunDialog

| Field | Value |
|---|---|
| Component | ConfirmRunDialog |
| Description | Two-step start: summary, estimate and exact command, launch only on confirm (FR3.2) |
| Category | feedback |

### States

| State | Description | Trigger |
|---|---|---|
| valid | Run id, model, method, changes, estimate, command (AC4.6.2) | Start run |
| over cap | Warning line; "Start anyway" asks once more (AC4.6.3) | estimate > 3 h |
| launching | Spinner on Start; buttons disabled | confirm |
| error | Dialog stays open with the reason (AC4.6.5) | launch refused or failed |

### Props / Inputs

| Prop | Type | Required | Default | Description |
|---|---|---|---|---|
| summary | CheckedRun | yes | — | From the service's check step (US3.2) |
| onConfirm | () => Promise | yes | — | Launches the run |
| onCancel | () => void | yes | — | Closes, launches nothing |

### Responsive Behaviour

| Breakpoint | Behaviour |
|---|---|
| desktop (≥1024px) | Centred, 560 px wide |

### Accessibility

| Requirement | Implementation |
|---|---|
| ARIA role | `role="dialog"` `aria-modal="true"`, titled "Confirm run" |
| Keyboard interaction | Focus trapped; Escape cancels; Enter on Start confirms (AC4.6.6) |
| Label / aria-label | `aria-labelledby` the title; `aria-describedby` the summary |
| Contrast ratio | 15:1 text; warning icon plus text, never colour alone |
| Screen reader | Errors announced with `role="alert"` inside the dialog |
| Focus management | Opens on Cancel (safe default); returns to Start run on close (AC4.6.6) |

## StopRunDialog

| Field | Value |
|---|---|
| Component | StopRunDialog |
| Description | Confirmation naming the run before stopping it (user-flow.md, Stop a Run) |
| Category | feedback |

### States

| State | Description | Trigger |
|---|---|---|
| confirm | "Stop <run id>?" with what is kept and that no score is recorded | Stop |
| already ended | "This run has already ended." + Close | run ended meanwhile |

### Props / Inputs

| Prop | Type | Required | Default | Description |
|---|---|---|---|---|
| runId | string | yes | — | Run to stop |
| onConfirm | () => Promise | yes | — | Calls the service stop (US3.4) |

### Responsive Behaviour

| Breakpoint | Behaviour |
|---|---|
| desktop (≥1024px) | Centred, 480 px wide |

### Accessibility

| Requirement | Implementation |
|---|---|
| ARIA role | `role="alertdialog"` |
| Keyboard interaction | Focus trapped; Escape keeps running |
| Label / aria-label | Title names the run |
| Contrast ratio | 15:1 |
| Screen reader | Title and body read on open |
| Focus management | Opens on "Keep running"; returns to Stop on close |

## TestSplitDialog

| Field | Value |
|---|---|
| Component | TestSplitDialog |
| Description | Test-split evaluation for a finalist with a second confirmation (FR3.6, US3.6) |
| Category | feedback |

### States

| State | Description | Trigger |
|---|---|---|
| unconfirmed | Score on test disabled until the checkbox is ticked (AC3.6.3) | open |
| confirmed | Score on test enabled | checkbox ticked |
| error | Reason shown, dialog stays open | refused or failed |

### Props / Inputs

| Prop | Type | Required | Default | Description |
|---|---|---|---|---|
| finalist | Run | yes | — | Only finalists can open it (AC3.6.2) |
| summary | CheckedRun | yes | — | Estimate and command |

### Responsive Behaviour

| Breakpoint | Behaviour |
|---|---|
| desktop (≥1024px) | Centred, 560 px wide |

### Accessibility

| Requirement | Implementation |
|---|---|
| ARIA role | `role="dialog"` `aria-modal="true"` |
| Keyboard interaction | Focus trapped; Space ticks the checkbox; Escape cancels |
| Label / aria-label | Checkbox has a visible label |
| Contrast ratio | 15:1 |
| Screen reader | Disabled button explains why via `aria-describedby` |
| Focus management | Opens on Cancel; returns to the row menu on close |

## PastRunsList

| Field | Value |
|---|---|
| Component | PastRunsList |
| Description | Every run with status, start time, minutes and dev accuracy, each openable (AC4.5.5) |
| Category | display |

### States

| State | Description | Trigger |
|---|---|---|
| empty | "None yet" (AC4.5.4) | no runs |
| populated | Rows newest first; status as text with an icon (✓ IDLE, ✕ FAILED) | runs loaded |

### Props / Inputs

| Prop | Type | Required | Default | Description |
|---|---|---|---|---|
| runs | Run[] | yes | — | All runs |
| onOpen | (runId) => void | yes | — | Loads the run into CurvesPanel |

### Responsive Behaviour

| Breakpoint | Behaviour |
|---|---|
| desktop (≥1024px) | Full width under the panels; shows 10 rows, then "Show all" |

### Accessibility

| Requirement | Implementation |
|---|---|
| ARIA role | Native `<table>` |
| Keyboard interaction | Tab to each "Open" link; Enter opens |
| Label / aria-label | "Open <run id>" |
| Contrast ratio | 15:1 |
| Screen reader | Status read as a word, icons `aria-hidden` |
| Focus management | Opening moves focus to the CurvesPanel heading |

## FailurePanel

| Field | Value |
|---|---|
| Component | FailurePanel |
| Description | Exit reason and the last 20 log lines of a failed run (AC3.5.1, AC3.5.2) |
| Category | feedback |

### States

| State | Description | Trigger |
|---|---|---|
| default | Reason heading, 20 log lines, Copy button | Show log |
| unreadable | "Run log could not be read: <file>" (AC3.5.3) | read error |

### Props / Inputs

| Prop | Type | Required | Default | Description |
|---|---|---|---|---|
| reason | string | yes | — | Exit reason, e.g. "GPU out of memory" |
| lines | string[] | yes | — | Last 20 log lines |

### Responsive Behaviour

| Breakpoint | Behaviour |
|---|---|
| desktop (≥1024px) | Opens as a sheet from the right, 640 px wide |

### Accessibility

| Requirement | Implementation |
|---|---|
| ARIA role | `role="dialog"` |
| Keyboard interaction | Escape closes; Copy reachable by Tab |
| Label / aria-label | Title "Why <run id> failed" |
| Contrast ratio | 15:1 monospace on `#141413` |
| Screen reader | Reason read first, then the log as preformatted text |
| Focus management | Returns to "Show log" on close |

## Usage Example

```
<TrainingPage>
  <HourglassBand status={status} step={step} totalSteps={total} runId={runId} etaS={eta} />
  <CurvesPanel lines={lines} method="sft" live />
  <DialsPanel config={config} status={status} onStart={openConfirm} onStop={openStop} />
  <PastRunsList runs={runs} onOpen={openRun} />
</TrainingPage>
```
