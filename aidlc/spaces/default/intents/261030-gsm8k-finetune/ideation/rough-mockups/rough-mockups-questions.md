# Rough Mockups — Questions

Context: the scope (`ideation/scope-definition/scope-document.md`) makes the whole website must-have: a landing page with the halftone headline, a highest-scores page, and a training page with live curves, dials and a start button. It runs locally only, for you alone. Your 21st.dev design screenshots are not in `inputs/design/` yet; the pasted halftone component is in `inputs/`.

## Q1. [Design] How should the look be handled while the screenshots are not in yet?

These wireframes are structure only (boxes, layout, states); the visual look is settled later in Refined Mockups.

A. Proceed with structure now; the look comes from your screenshots, added to `inputs/design/` before the website is built
B. Wait: I will add screenshots now, before the wireframes are written
C. Use the halftone component's look (dark background, dotted wordmark) as the style anchor for all pages; no other screenshots needed
D. Not yet defined
X. Other (please specify)

[Answer]: A. Proceed with structure now; the look comes from your screenshots, added before the website is built

## Q2. [Design] How should the three pages be navigated?

A. A top bar on every page: wordmark at the left (links to the landing page), then "Scores" and "Training"
B. A side navigation on the left
C. The landing page has one call to action ("Go to training"); scores and training share a top bar
D. Not yet defined
X. Other (please specify)

[Answer]: A. A top bar on every page

## Q3. [Design] What should the training page put first?

A. Live curves large at the top; run status with start and stop next to them; the dials panel at the right; the list of past runs below
B. The dials panel first at the left, live curves at the right
C. Tabs: Live, Dials, Runs
D. Not yet defined
X. Other (please specify)

[Answer]: A. Live curves first; status with start and stop beside them; dials at the right; past runs below

## Q4. [Design] What should the highest-scores page show?

A. A ranked table of runs (model, method, accuracy on the dev and test splits, gain over baseline, minutes, date), the baseline marked, and a way to compare two runs
B. Cards for the top three runs, then the full table
C. A bar chart of the best run per method, then the full table
D. Not yet defined
X. Other (please specify)

[Answer]: A. Ranked table with the baseline marked and a way to compare two runs

## Q5. [Design] Which devices must it work on?

A. Desktop browser on this PC only
B. Desktop, plus a phone on your home network to check runs
C. Not yet defined
X. Other (please specify)

[Answer]: A. Desktop browser on this PC only

## Q6. [Design] What accessibility level?

A. Practical basics: everything works by keyboard, readable contrast, status never shown by colour alone, and the halftone animation respects the "reduce motion" setting
B. Full WCAG 2.1 AA
C. None
D. Not yet defined
X. Other (please specify)

[Answer]: A. Practical basics

## Q7. [Product] What should the start button do?

A. Check the dials, show a summary of the run and the exact command it runs, ask you to confirm, then launch; show the run as running, allow only one run at a time, and offer a stop button
B. Launch immediately with no confirmation step
C. Not yet defined
X. Other (please specify)

[Answer]: A. Check, show summary and command, confirm, launch; one run at a time; stop button

## Consolidated Summary Confirmation

- Look: structure only for now; the visual look comes from your screenshots in `inputs/design/`, added before the website is built (Q1).
- Navigation: a top bar on every page: wordmark at the left (to the landing page), then "Scores" and "Training" (Q2).
- Training page: live curves large at the top, run status with start and stop beside them, the dials panel at the right, past runs below (Q3).
- Highest-scores page: a ranked table of runs (model, method, dev and test accuracy, gain over baseline, minutes, date), the baseline marked, and a way to compare two runs (Q4).
- Devices: desktop browser on this PC only (Q5).
- Accessibility: practical basics: keyboard everywhere, readable contrast, status never by colour alone, halftone animation respects reduce-motion (Q6).
- Start button: checks the dials, shows a run summary and the exact command, asks you to confirm, then launches; one run at a time; a stop button (Q7).

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
