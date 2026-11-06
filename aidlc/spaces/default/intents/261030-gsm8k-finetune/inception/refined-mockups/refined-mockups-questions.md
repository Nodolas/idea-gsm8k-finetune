# Refined Mockups: Design Questions

Already settled earlier and not asked again: desktop browser on this PC only (rough-mockups Q5); a top bar on every page (Q2); training page with curves first and large, status with Start and Stop beside them, dials at the right, past runs below (Q3); a ranked scores table with the baseline marked and a compare view (Q4); practical accessibility basics (Q6); the two-step confirm before a run launches (Q7); shadcn/ui with charts on React, TypeScript, Vite and Tailwind (requirements.md Constraints); the halftone headline cleared for use (requirements Q6); website behaviour tested with Vitest, the look checked by hand (user-stories Q6).

Your design inputs: the pasted "Halftone Wordmark Footer" (`inputs/halftone-wordmark-footer.tsx.txt`, presets night, paper, ember, cobalt) and the "Gateway Flow" screenshot (`inputs/design/training-live-gateway-flow.png`: dotted lines on black converging to an hourglass waist, with brighter dots scattered along them), which you want as the training page's live view.

## Q1. [Design] Which colour theme should the whole site use?

The halftone headline and the Gateway Flow screenshot are both dark, dotted and monochrome; one theme across the three pages keeps them consistent.

A. Dark "night" everywhere: near-black background (`#0c0c0b`), warm off-white text and dots (`#e9e4da`), one orange accent (`#e9762b`) for the active run and highlights; system sans for text, monospace for numbers, run ids and commands
B. Dark with the "cobalt" accent: deep blue background (`#0d1b4d`), pale blue text, yellow accent (`#ffcd3c`)
C. Light "paper": warm off-white background (`#efebe3`), near-black text, red accent (`#c2361c`), with only the training view dark
X. Other (please specify)

[Answer]: A. Dark "night" everywhere with one orange accent; system sans text, monospace numbers, run ids and commands

## Q2. [Design] Which word should the halftone headline spell?

The headline prints one lowercase word in dots across the landing page, and the same word is the wordmark in the top bar.

A. `gsm8k`
B. `mathlab`
C. `finetune`
X. Other (please specify)

[Answer]: A. `gsm8k`

## Q3. [Design] What should the Gateway Flow view show while a run trains?

You want the training page's live view to look like the Gateway Flow screenshot plus a live picture of the training itself. The real numbers stay in the curves either way.

A. Data flowing through the model: dotted lines converge through the waist; bright dots travel along the lines, their speed set by steps per second and their brightness by how fast the loss is falling; when the run is idle the dots rest
B. An hourglass of progress: dots drain from the top half through the waist into the bottom half as steps complete, so the fill shows how much of the run is done
C. A still backdrop only: the dotted field is drawn once behind the curves and does not react to the run
X. Other (please specify)

[Answer]: B. An hourglass of progress: dots drain from the top half through the waist into the bottom half as steps complete

## Q4. [Design] Where should the Gateway Flow view sit on the training page?

The earlier answer put the live curves first and large (rough-mockups Q3).

A. A full-width band at the top of the page, about 280 px tall, with the run status, step and time left written over it; the curves panel stays the largest panel below it, dials at the right, past runs below
B. Behind the curves: the dotted field fills the curves panel and the curves are drawn on top of it
X. Other (please specify)

[Answer]: A. A full-width band at the top, about 280 px tall, with status, step and time left over it; curves stay the largest panel below

## Q5. [Design] How should the training curves be drawn?

The curves (loss, learning rate, dev accuracy, and reward, KL and answer length for reinforcement learning) are the source of truth for every run.

A. Clean thin lines in the text colour, the current run in the accent colour, faint dotted gridlines, and a hover read-out of the exact value at each step
B. Dotted point clouds that echo the halftone look, with the same hover read-out
X. Other (please specify)

[Answer]: A. Clean thin lines in the text colour, the current run in the accent colour, faint dotted gridlines, hover read-out

## Consolidated Summary Confirmation

- The whole site uses the dark "night" theme: near-black background `#0c0c0b`, warm off-white text and dots `#e9e4da`, one orange accent `#e9762b` for the active run and highlights; system sans for text, monospace for numbers, run ids and commands.
- The halftone headline on the landing page, and the wordmark in the top bar, spell `gsm8k`.
- The Gateway Flow view is an hourglass of progress: dots drain from the top half through the waist into the bottom half as a run's steps complete.
- It sits as a full-width band about 280 px tall at the top of the training page, with the run status, step and time left written over it; the curves panel stays the largest panel below it, with the dials at the right and past runs below.
- The curves are clean thin lines in the text colour, the current run in the accent colour, with faint dotted gridlines and a hover read-out of the exact value at each step.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
