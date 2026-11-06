# Accessibility Checklist

Target: practical basics (rough-mockups Q6), held to WCAG 2.1 AA for contrast, keyboard use and names, as required by NFR9 in `inception/requirements-analysis/requirements.md`. Screens are in `mockups.md`, behaviour in `interaction-spec.md`; the rough annotations come from `ideation/rough-mockups/wireframes.md` and the flows from `ideation/rough-mockups/user-flow.md`. Each row names the story criterion in `inception/user-stories/stories.md` that tests it, or how it is checked by hand. Automated checks run as Vitest tests (`inception/practices-discovery/team-practices.md`; user-stories Q6).

## Perceivable

| Check | Where | How it is verified |
|---|---|---|
| Text contrast at least 4.5:1: `ink` 15.4:1, `ink-muted` 5.5:1, `accent` 5.9:1, `danger` 7.0:1 on `#0c0c0b` | All pages | Token values in `design-system-mapping.md`; Nico checks by hand at the website unit's checkpoint (AC4.1.3) |
| UI component edges at least 3:1 (field borders, focus ring) | Dials, dialogs | Same check by hand |
| Text over the hourglass dots keeps 4.5:1 via a 70% scrim | HourglassBand | Same check by hand |
| Status never shown by colour alone: words RUNNING, IDLE, STOPPED, FAILED; ✓ and ✕ icons beside words; gain with a + or − sign; BL and ★ announced as words | Scores, Training, TopBar | AC4.3.2, AC4.6.4 |
| Compared runs told apart by line style (solid and dashed) and name, not only colour | CompareView | AC4.4.1 |
| Charts have a text alternative: a "Latest" line under the chart and an `aria-label` per curve | CurvesPanel, CompareView | AC4.5.1 |
| Decorative canvases hidden from assistive technology; the wordmark is a real `h1` | HalftoneHeadline, HourglassBand | AC4.2.1 |
| No flashing more than 3 times per second; the click shock ring is a single pulse | HalftoneHeadline | By hand |

## Operable

| Check | Where | How it is verified |
|---|---|---|
| Skip link is the first focus stop and jumps to `<main>` | Every page | AC4.1.2 |
| Every function works by keyboard: links, filters, picks, row menu, tabs, dials, Start, Stop, dialogs | Every page | AC4.1.2, AC4.6.6 |
| Visible focus ring on every focusable element (2 px accent, 2 px offset) | Every page | By hand |
| Tab order follows the visual order (top bar, main content left to right, then below) | Every page | AC4.1.2 |
| Dialogs trap focus, close on Escape, and return focus to the button that opened them | Confirm Run, Stop Run, Test Split, Failure panel | AC4.6.6 |
| Chart read-out reachable by keyboard (arrow keys move the point) | CurvesPanel | By hand |
| Motion stops under `prefers-reduced-motion: reduce`: still halftone dots, no hourglass fall, instant transitions | Landing, Training | AC4.2.4 |
| Live updates never move focus or the page; the run status is announced politely only | Training | AC4.6.4 |

## Understandable

| Check | Where | How it is verified |
|---|---|---|
| `<html lang="en">` | Every page | By hand |
| Same top bar, same labels and same positions on every page | Every page | AC4.1.1 |
| Every dial has a visible label above it and its allowed range as helper text | DialsPanel | AC4.6.1 |
| Invalid input named in text under the field with the allowed range; the value typed is kept | DialsPanel | AC4.6.1 |
| No action without an explicit button press: starting, stopping and scoring on test all ask first | Dialogs | AC4.6.2, AC3.6.3 |
| Error messages say what happened and what to do, naming the file or run id | Landing, Scores, Training | AC4.2.3, AC4.3.4, AC3.5.3 |

## Robust

| Check | Where | How it is verified |
|---|---|---|
| Native elements first: `<button>`, `<a>`, `<table>`, `<label>`, `<input>` | Every page | Code review at Code Generation |
| Landmarks: `<header>`, `<nav aria-label="Main">`, `<main id="main">` | Every page | AC4.1.2 |
| Live regions: one `role="status"` per page for run status; `role="alert"` only inside dialogs for launch errors | Training, dialogs | AC4.6.4, AC4.6.5 |
| Heading order: one `h1` per page, then `h2` per panel, no skipped levels | Every page | By hand |
| Unique ids for every label and description pair | Dials, dialogs | Vitest tests query by label |

## Out of Scope

- Screen reader testing on phones and tablets, and zoom beyond 200%: the site is desktop-only for one user on this PC (rough-mockups Q5).
- Formal WCAG certification: practical basics were chosen (rough-mockups Q6).
