# batch-11: landing wordmark centred and fast, fine-tuning drawing at its designed size (u5-website)

Branch `wip/batch-11`, built in the git worktree `.cache/worktrees/batch-11` (the main tree's Vite serves Nico's open page; a batch-10 builder's half-written file crashed it, so website batches build apart). `node_modules`, `.venv` and `.tools` are symlinks to the main tree: never install anything. `S` = `aidlc/spaces/default/intents/261030-gsm8k-finetune/inception`. Criteria: `S/user-stories/stories.md`; the reason: the last line of `inception/changes.md`.

`test_command`: `PYTHONPATH=$PWD/src scripts/check.sh` in this worktree (the venv's editable install points at the main tree). Website: `scripts/in-env.sh npm run web:test -- <file>`, `scripts/in-env.sh npm run web:lint`, `scripts/in-env.sh npm run web:typecheck`.

Why now (Nico, 2026-11-08): "place the gsm8k in the middle of the landing page not at the top and make sure that the dots move properly and smoothly" (relayed by the self-taught course session); "the landing page is buggy the gsm8k is super slow and not performant, maybe due to its size and it is not in the middle of the screen, it is still all the way at the top"; and on the training page's fine-tuning panel, "make this smaller ... that is way too big". Batch-10's full width made the halftone canvas about 2,400 × 520 px at a 6 px dot gap (about 35,000 dots, each its own `beginPath`/`arc`/`fill` with a colour string, and a new grain pattern every frame), and stretched the fine-tuning drawing (viewBox 1000 × 206) to 2,303 × 474 px.

Teach: rendering cost grows with the number of draw calls, not just the number of shapes; batching every dot of one colour into one path, and stepping physics by elapsed time instead of by frame, keeps an animation smooth at any size and refresh rate. Nothing numeric about the model moves.

## Criteria

- u5-website: AC4.2.5, AC4.2.7, AC4.2.8 (part L); AC4.7.10 (part F). AC4.2.6 is `[manual]` (Nico opens the landing page full screen).

## Parts

### Part L: landing page and halftone (website), u5-website

Owns: `web/src/pages/landing.tsx`, `web/src/components/halftone-headline.tsx`, `web/src/components/ui/halftone-wordmark-footer.tsx`.
Tests: `tests/web/landing-halftone.test.tsx` (AC4.2.5, AC4.2.7, AC4.2.8).

- Centre (AC4.2.5): the landing root fills the window height below the top bar (the top bar is `h-14`, 56 px: `min-h-[calc(100svh-3.5rem)]`, flex column); the headline section grows into the free height above the text block (`flex-1`, its content centred) and carries `data-align="center"`; the halftone component gains `align?: "bottom" | "center"` (default `"bottom"`, the old look) and draws the word in the middle of its canvas when `"center"`. The canvas keeps a definite height (40vh, as now); the text block stays at the bottom.
- Fast (AC4.2.7): export `hwfGap(width, height, dotGap, maxDots = 16000)`: the gap used for layout, `dotGap` unless the canvas would hold more than `maxDots`, then the smallest gap that keeps it at or under. Per frame: at-rest ink dots in one path and one `fill()`, warm (displaced) dots bucketed into a few colour steps, each one path; the grain pattern created once per layout. Keep the sleep rule (no frames while nothing moves).
- Smooth (AC4.2.8): `hwfStep(..., dtMs = 1000 / 60)` scales the spring, damping and push to elapsed time (exact for the default, so the old result is unchanged), dt clamped to at most 50 ms; the loop passes the real elapsed time.
- Tests: the pure functions directly (`hwfGap`, `hwfStep` paths at 60 and 144 Hz over 1 s within 5%); a stub canvas 2D context (count `fill()`/`createPattern` calls over a few stubbed animation frames with a pointer move) for the draw rules; the landing page through the router helpers for the centring hooks.

### Part F: the fine-tuning drawing's size (website), u5-website

Owns: `web/src/components/finetune-view.tsx`, `web/src/styles/finetune.css`.
Tests: `tests/web/finetune-size.test.tsx` (AC4.7.10).

- The main drawing (`svg.ft-drawing`, viewBox 1000 wide) gets `max-w-[1100px]` and sits centred in its column (`mx-auto`); keep `min-w-[860px]` and the horizontal scroll at narrow widths as now. The "One layer up close" figure keeps `max-w-[280px]`.

## Lead

No shared files.

## Rules

Tests named by criterion ID; no existing test line changed or deleted; tests committed before the code; CPU only; website lint, Prettier and strict type check clean. Builders write only their owned files and use read-only git (status, diff, log).
