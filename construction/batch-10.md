# batch-10: full-width pages and a moving hourglass band with evaluation progress (u4-run-service, u5-website)

Branch `wip/batch-10`, built in the main working tree (no other session builds here; `wip/batch-9`, the interrupted lab batch, lives in `.cache/worktrees/batch-9` and is not touched). `S` = `aidlc/spaces/default/intents/261030-gsm8k-finetune/inception`. Criteria: `S/user-stories/stories.md`; the Status field: contract C6 `Status.evaluation` and C7 `status` in `S/contract-design/contract-summary.md`; the reason: the last line of `inception/changes.md`.

`test_command`: `scripts/check.sh` (CPU, through `scripts/in-env.sh`). Single files: `scripts/in-env.sh .venv/bin/python -m pytest -q tests/<file>`; website: `scripts/in-env.sh npm run web:test -- <file>`, `scripts/in-env.sh npm run web:lint`, `scripts/in-env.sh npm run web:typecheck`.

Why now (Nico, 2026-11-08, while q17-selfcot-dev-2 scored its dev split after training): "I want the whole screen to be used not only the middle third. also make sure the top of the screen with the dots moves or shows the progress of the training." Every page is capped at 1280 px (`max-w-[1280px]`, `--content-width`), and the band redraws only when a metrics line arrives, so it reads 100% through a fine-tune's whole dev evaluation (about 25 minutes) and an evaluation run never leaves "Waiting for first step...".

Do not influence the live run: `q17-selfcot-dev-2` (pid 4857) runs from this tree. No part changes a module the training or evaluation commands import (`src/gsm8k/training/`, `evaluation.py`, `datasets_prompts/`, `scoring.py`, `run_config.py`, `run_records/`, `run_control/`, `cli.py`); the service code may import `run_control.launch.SPLIT_SIZES` and `run_records` helpers read-only. Tests run on the CPU. The running service and Vite pick up the change after the merge (service restart by the lead).

Teach:
- u4-run-service AC3.1.6–AC3.1.7: a run's progress has two phases, optimizer steps (metrics lines) and then scoring problems (predictions lines, one per problem as it is scored). The number that moves: `scored` of `total`, 500 for the dev split.
- u5-website AC4.5.11–AC4.5.12: an animation shows the process is alive between the measured updates; the measured share (steps or problems) stays the only number the band claims. AC4.1.4–AC4.1.5: layout only.

## Criteria

- u4-run-service: AC3.1.6, AC3.1.7 (part P).
- u5-website: AC4.5.11, AC4.5.12 (part B); AC4.1.4 (part W). AC4.1.5 is `[manual]` (Nico looks at each page full screen).

## Parts

### Part P: evaluation progress in the status (Python), u4-run-service

Owns: `src/gsm8k/service/progress.py` (new), and in `src/gsm8k/service/app.py` only `_status_payload` and the lines that call it (`get_status`, the stream's `_events`), so the payload gains `evaluation`.
Tests: `tests/test_u4_eval_progress.py` (AC3.1.6, AC3.1.7).

- `progress.evaluation_progress(outputs: Path, run_id: str) -> dict | None`: `{"split", "scored", "total"}` from `outputs/<run_id>/config.json` (`split`, `limit`) and `outputs/<run_id>/predictions.jsonl` (count only lines ending in `\n`, reading bytes; never parse JSON). `total` = `SPLIT_SIZES[split]` (`gsm8k.run_control.launch`), or `limit` when it is set and smaller; `scored` = min(count, total). None when there is no predictions file, the split has no size, or config.json is missing, unreadable or not an object. Every `OSError`/`ValueError` gives None, never an exception.
- `_status_payload(st, outputs)`: `evaluation` only when `st.state == "RUNNING"` and `st.run_id`, else null; `last_run` nested with `evaluation: null`. The stream compares payloads, so a new `scored` sends a new status event by itself (AC3.1.7); keep the poll as it is.
- Tests: `TestClient` with `tmp_project_dirs`, a RUNNING status (copy how `tests/test_u4_service.py` / `tests/test_u4_runs_status.py` make one: a held lock or a stubbed `status.current_status`), fixture run folders written by the test; the stream test reads events from `_events` (or the `/stream` route) until a second status event with the new `scored`.

### Part B: the moving band and evaluation progress (website), u5-website

Owns: `web/src/components/hourglass-band.tsx`, `web/src/pages/training.tsx` (including its page container: drop `mx-auto ... max-w-[1280px]` and use `px-[var(--gutter)]` in place of `px-6`, for AC4.1.4).
Tests: `tests/web/hourglass-flow.test.tsx` (AC4.5.11, AC4.5.12).

- Flow (AC4.5.11): while `status === "RUNNING"` and reduced motion is off, one `requestAnimationFrame` loop keeps drawing; grains (a few bright dots per line, phase from `performance.now()`) slide along the top curves toward the waist and down the bottom curves, after the Gateway Flow look; the lit share still follows `fraction`. The section carries `data-flow="on"` while it flows, else `"off"`. Under reduced motion or any other status: no loop (the existing eased fall stays, none under reduced motion), and the loop is cancelled on unmount and status change. Draw nothing when `getContext` gives null (jsdom), but keep requesting frames while flowing so the loop is testable with a stubbed `requestAnimationFrame`.
- Evaluation (AC4.5.12): new optional band props for evaluation progress (`evaluation: {split, scored, total} | null`); `training.tsx` passes `status.evaluation` for the running run and sets the message and fraction as the criterion says. `Status.evaluation` is already in `web/src/lib/api.ts` (lead).

### Part W: full-width pages (website), u5-website

Owns: `web/src/components/top-bar.tsx`, `web/src/pages/landing.tsx`, `web/src/pages/scores.tsx`, `web/src/pages/reasoning.tsx`, `web/src/styles/tokens.css` (`--content-width` goes; `--gutter` stays).
Tests: `tests/web/full-width.test.tsx` (AC4.1.4): render each page and the top bar (through the router helpers in `web/src/test/utils.tsx` and `fakeApi`) and check that no element carries a `max-w-[1280px]` or `max-w-[var(--content-width)]` class, that each page's outer container and the top bar's row carry the class `px-[var(--gutter)]` (the scores, reasoning and training containers swap `px-6` for it). Landing is the exception: its halftone headline stays full-bleed, so its outer container has no padding and no max-width cap, and its text block under the headline carries `px-[var(--gutter)]` (lead, 2026-11-08), and that `web/src/styles/tokens.css` no longer defines `--content-width`. The training page's container is part B's: this test checks it too.

- Prose blocks keep their line length (`max-w-[70ch]`, `max-w-[75ch]`, `max-w-xl` stay). Tables and charts stretch with the page.

## Lead (shared files, `feat(batch-10): shared setup`)

- `web/src/lib/api.ts`: `Status.evaluation: EvaluationProgress | null` (optional in the type for older payloads) and `export interface EvaluationProgress { split: string; scored: number; total: number }`.
- `web/src/test/fake-api.ts`: `serviceStatus()` defaults `evaluation: null`.

## Rules

Tests named by criterion ID; no existing test line changed or deleted; tests committed before the code; CPU only; Ruff clean (line length 110); website lint, Prettier and strict type check clean. Builders write only their owned files and use read-only git (status, diff, log).
