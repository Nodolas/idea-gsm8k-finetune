# batch-7: the fine-tuning view (u5-website)

Branch `wip/batch-7`, built in its own git worktree (`.cache/worktrees/batch-7`, outside the main working tree, because another session was building batch-6 in the main tree at the same time). Cut from `main` 81ac9e9. Spec: approved commit 37fb5a4 plus the `spec(` commits since, the last being `spec(u5-website): fine-tuning view on the training page (US4.7)` (`inception/changes.md`, last line). `test_command`: `scripts/check.sh`.

Why now: Nico, 2026-11-08: "this visualisation on the front end is not visualizing the training ... make sure this visualization shows me how a neural model gets fine tuned." The band and the curves show progress; nothing shows what a fine-tune does to the model. His screenshot was the `cotgen` run `q17-cotgen-train-1`, which changes no weights.

## Criteria

AC4.7.1-AC4.7.8 (AC4.7.9 is `[manual]`), all in `S/inception/user-stories/stories.md` (`S` = `aidlc/spaces/default/intents/261030-gsm8k-finetune`), with FR4.7 in `requirements.md` and the panel's design in `mockups.md` ("The fine-tuning view").

## Scope

Website only. No change to the training loop, the service, the contracts or any dial: the panel reads the run's metrics lines and `config.json` through `useApi()` (ADR-008). Per-layer adapter sizes are not recorded, so the picture says it is an illustration (AC4.7.8). Files this batch owns: `web/src/lib/finetune-model.ts`, `web/src/components/finetune-view.tsx`, `web/src/styles/finetune.css` (all new), `tests/web/finetune-view.test.tsx` (new), and two small edits to shared files: `MetricsLine` gains optional `grad_norm` and `epoch` in `web/src/lib/api.ts` (the same two fields, with the same comments, as batch-6's shared setup), and `web/src/pages/training.tsx` mounts the panel under the band.

## Interfaces

`web/src/lib/finetune-model.ts` (pure): model shapes of `Qwen/Qwen3-0.6B-Base` and `Qwen/Qwen3-1.7B-Base` (28 layers; hidden 1024 or 2048; MLP 3072 or 6144; query projection 2048 wide; key and value projections 1024 wide; 596,049,920 or 1,720,574,976 base weights, checked against peft's `print_trainable_parameters` lines in `outputs/*/run.log`); LoRA counts for a rank over the seven adapted matrices of a layer; the query projection's sizes; the step lines of a run (a line with a numeric loss); the figures at one step (loss, `exp(-loss)` as the chance on the right word, change since the first step line, gradient norm, learning rate, examples seen = step x batch size).

`FinetuneView` (`web/src/components/finetune-view.tsx`), props `runId: string | null`, `method: string | null`, `model: string | null`, `liveLines: readonly MetricsLine[]`, `live: boolean`, `loading?: boolean`. It reads the run's `config` with `getRun(runId)` and, when not live, the stored lines with `getMetrics(runId)`; live, it shows `liveLines`.

Markup the tests rely on (every number is text too; the drawing is `aria-hidden`):

- `<section aria-labelledby>` with `<h2>` "How the model is fine-tuned" (role region); attributes `data-mode` (`finetune`, `reading` or `none`), `data-view` (`live` or `replay`), `data-step` (the shown step line's step, `""` when none), `data-motion` (`live` or `still`).
- Drawing: `<svg aria-hidden="true" data-part="drawing">` holding one `[data-layer="<i>"][data-state="frozen"]` per layer and one `[data-adapter="<i>"]` per layer with `data-state="trained"` (fine-tune) or `"none"` (not a fine-tune), and a `<g data-part="pass" data-pass="<step>">` that is created anew for each shown step line (it holds the moving parts, so a new step starts the passes again).
- `<p data-part="weights">`: "17,432,576 trained of 1,738,007,552 weights (1.0%) · 1,720,574,976 frozen" (fine-tune, rank known); "None of the 1,720,574,976 weights changes" (not a fine-tune).
- `<ol data-part="stages">` with `<li data-stage="read|guess|score|blame|nudge">`: an `<h3>` with the stage name, `<p data-part="meaning">`, `<p data-part="figure">`. Figures: read "4 examples per step" ("—" without a batch size); guess "scored on answer words only"; score "loss 0.94 · 39% chance on the right word · 47.8% lower than at step 40" (first step line: "first logged step"; "higher than" or "the same as" when so); blame "gradient norm 0.42" or "gradient norm —"; nudge "learning rate 1.8e-4".
- `<p data-part="progress">`: "Step 120 of 400 · 480 examples seen" (no examples without a batch size); not a fine-tune: "90 of 1500 problems written" (`cotgen`) or "scored" (others).
- `<p data-part="view-state">`: "Following the live run", "Replaying step 80 of 400" (80 is the line's step, 400 its total steps), or "Showing the last logged step" (not live, fewer than two step lines).
- Replay (not live, two or more step lines): `<input type="range" aria-label="Replay step">` with `min` 1, `max` the number of step lines, `value` the shown line's 1-based position, and a button "Play replay" (reads "Pause replay" while playing; one tick every 150 ms, several lines per tick on long runs so a replay takes about 20 s; it stops on the last line, and pressing Play there starts again).
- `<figure aria-labelledby>` with figcaption "One layer up close" and `<dl>` of `<div data-stat="frozen-matrix|adapter-a|adapter-b|adapter-total|scale">`: "2048 × 2048 = 4,194,304 weights", "16 × 2048", "2048 × 16", "65,536 weights", "2 (alpha 32 / rank 16)". Only for a fine-tune whose rank is known.
- Not a fine-tune: `<p data-part="reading-note">` starting "This run does not change the model", then one line on what the run does.
- `<p data-part="empty">`: "Nothing to show yet: start a fine-tune to watch the model change." (no run); "Waiting for the first logged step" (fine-tune, no step line, live); "No step lines were recorded for this run." (not live, none stored); "Reading the run…" while loading.
- `<p data-part="note">`: says "Measured" (step, loss, gradient norm, learning rate) and "Drawn for illustration" (the layers and the moving dots; every adapter is updated on every step; per-layer sizes are not recorded).

Existing tests must keep passing unchanged: the panel avoids the strings and roles they query ("Waiting for first step...", "No run yet. Set the dials and press Start run.", "Live updates paused", role `progressbar` "Run progress", figures named "... curve", the run id as the only text node of a table cell).

## Order

1. Lead: this plan.
2. Lead: tests in `tests/web/finetune-view.test.tsx` from the criteria; run them, see them fail; commit `test(u5-website)`.
3. Lead: implementation; `scripts/check.sh` and `scripts/trace-check.sh`; a reviewer checks the batch against the spec; commit `feat(u5-website)`, `chore(state): batch-7 done`; rebase on `main` if it moved; fast-forward `main`.
