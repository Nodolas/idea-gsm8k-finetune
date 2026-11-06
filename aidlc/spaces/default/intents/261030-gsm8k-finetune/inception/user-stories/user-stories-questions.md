# User Stories: Story Plan Questions

The plan: one persona (Nico, already settled in Ideation), stories in "As Nico, I want …, so that …" form meeting INVEST, MoSCoW priority from `scope-document.md` (FR1–FR6 Must, FR7–FR9 Could), and Given/When/Then acceptance criteria with `AC{n}.{m}.{k}` IDs. Every criterion whose run takes over about 10 minutes carries `[manual]` and `Verify: results/runs.csv row <base id>`. The questions below settle what the requirements leave open.

## Q1. [Product] How should the stories be broken down?

This sets how many stories there are and how big each one is; each acceptance criterion becomes at least one test.

A. By learning-path step (data and evaluation, fine-tuning, run service, website pages, generalisation, write-up, then the could-haves). One story per outcome Nico can see, 3–6 criteria each, about 20–25 stories
B. One large story per requirement group (FR1–FR9), about 9 stories with many criteria each
C. By component (Python training and evaluation, service, website), about 3 large epics split into stories
X. Other (please specify)

[Answer]: A. By learning-path step, one story per outcome Nico can see, 3–6 criteria each

## Q2. [Product] How much detail should the could-have stories get now?

Reinforcement learning with GRPO (FR7), the Optuna and agent tuning loop (FR8) and the ablations (FR9) are could-haves, built only after everything else works.

A. Full stories with acceptance criteria now, marked Could, ready if there is time
B. One short placeholder story each, marked Could, detailed later only if built
X. Other (please specify)

[Answer]: A. Full stories with acceptance criteria now, marked Could

## Q3. [Product] What do "best run" and "finalist" mean?

The requirements keep only the baseline's and the best run's weights (FR2.5), and allow a test-split evaluation from the website only for a run marked as a finalist (FR3.6), but neither term is defined yet.

A. "Best run" is the run with the highest dev accuracy for its model (ties go to the earlier run). A "finalist" is a run Nico marks himself on the scores page; the mark is saved in a small committed file, `results/finalists.json`
B. "Best run" as in A, and the best run is automatically the only finalist (no marking)
X. Other (please specify)

[Answer]: A. Best run = highest dev accuracy for its model; finalists marked by Nico on the scores page, saved in `results/finalists.json`

## Q4. [Developer] Should the stories fix the allowed range and default of each training dial now?

The run check rejects a value outside its allowed range (FR2.2), but no range is written yet, so no test can check it, and the 8 GB memory limit (NFR1) depends on the defaults. Proposed: model 0.6B or 1.7B (default 0.6B); learning rate 1e-5 to 5e-4 (default 2e-4); epochs 1–3 (default 1); LoRA rank 4, 8, 16, 32 or 64 (default 16); LoRA alpha 1–128 (default 32); max sequence length 256–1024 (default 512); training examples 50 to all (default all); batch size 1–16 (default 4); warmup ratio 0–0.2 (default 0.03); seed 0 to 2³¹−1 (default 42); answer format step-by-step or terse (default step-by-step).

A. Use these proposed ranges and defaults in the stories now; the first unit's measurements confirm the defaults fit 8 GB and 3 hours, and any change goes through `inception/changes.md`
B. Leave the numbers to Functional Design; the stories only check that an out-of-range value is rejected with the dial's name
X. Other (please specify)

[Answer]: A. Use the proposed ranges and defaults now

## Q5. [Developer] How should "one run at a time" work when a run is started from the terminal?

Only one GPU run may be active at once (FR3.4), but long runs can be started from the terminal as well as the website. A terminal run started while a website run is active, or the service restarting while a run is still alive, could crash the GPU or show the wrong status.

A. A lock file under `outputs/` that both the terminal command and the service honour; it holds the run id and process id, and on restart the service reads it and checks the process is still alive
B. Enforce it in the service only; Nico avoids starting terminal runs while a website run is active
X. Other (please specify)

[Answer]: A. A lock file under `outputs/` honoured by the terminal command and the service, holding run id and process id; the service checks the process on restart

## Q6. [Quality] How should the website's acceptance criteria be tested?

The Python side is tested with pytest; the website's test runner is still open (requirements, Open Questions). Each criterion needs a test named by its ID or a `[manual]` mark.

A. Component tests (Vitest with React Testing Library) for behaviour, named `AC…`; `[manual]` checks for the visual look against your screenshots and for the 5-second live update
B. Browser tests (Playwright with the headless Chromium already on this PC) against the running site for behaviour; `[manual]` for the visual look
C. Every website criterion `[manual]`, checked by you in the browser
X. Other (please specify)

[Answer]: A. Vitest with React Testing Library for behaviour; `[manual]` for the visual look and the 5-second live update

## Q7. [Quality] How should long runs be named?

Each long run is a `[manual]` criterion with `Verify: results/runs.csv row <base id>`, and you start it with `--run-id <base id>-<n>`, so every long run needs a base id written into its criterion.

A. `<model>-<method>-<split>`, for example `q06-base-test`, `q17-base-dev`, `q06-sft-dev`; attempts add `-1`, `-2`
B. Short numbered ids per story, for example `us1-baseline`, `us2-sft`
X. Other (please specify)

[Answer]: A. `<model>-<method>-<split>`, for example `q06-base-test`; attempts add `-1`, `-2`

## Consolidated Summary Confirmation

- Stories follow the learning path (data and evaluation, fine-tuning, run service, website pages, generalisation, write-up, then the could-haves): one story per outcome Nico can see, 3–6 acceptance criteria each, about 20–25 stories, one persona (Nico).
- The could-haves (GRPO reinforcement learning, the Optuna and agent tuning loop, the ablations) get full stories with acceptance criteria now, marked Could.
- "Best run" is the run with the highest dev accuracy for its model (ties go to the earlier run). A finalist is a run Nico marks on the scores page, saved in a committed `results/finalists.json`; only finalists can get a test-split evaluation from the website.
- The training dials use the proposed ranges and defaults (model 0.6B or 1.7B, default 0.6B; learning rate 1e-5 to 5e-4, default 2e-4; epochs 1–3, default 1; LoRA rank 4/8/16/32/64, default 16; LoRA alpha 1–128, default 32; max sequence length 256–1024, default 512; training examples 50 to all, default all; batch size 1–16, default 4; warmup ratio 0–0.2, default 0.03; seed 0 to 2³¹−1, default 42; answer format step-by-step or terse, default step-by-step). The first unit's measurements confirm they fit 8 GB and 3 hours; any change goes through `inception/changes.md`.
- One run at a time is enforced by a lock file under `outputs/` that both the terminal command and the service honour; it holds the run id and process id, and the service checks on restart whether that process is still alive.
- Website behaviour is tested with Vitest and React Testing Library, each test named by its criterion ID; the visual look against Nico's screenshots and the 5-second live update are `[manual]` checks.
- Long runs use base ids of the form `<model>-<method>-<split>` (for example `q06-base-test`), written in each long-run criterion as `Verify: results/runs.csv row <base id>`; Nico starts attempts with `--run-id <base id>-1`, `-2`, and so on.

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
