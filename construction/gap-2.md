# gap-2: Converge gap (u11-finetune-lab)

Converge on 2026-11-18 (main 35577a9, `scripts/check.sh` exit 0, 907 Python tests, 431 website tests, coverage 88.6%, trace PASS; four reviewers re-read every criterion of the 10 built units) found one gap. Every other unit PASS; AC7.1.5 is pending on the GPU (`q17-grpo-dev-3`), not a gap. Spec: `aidlc/spaces/default/intents/261030-gsm8k-finetune/inception/user-stories/stories.md` (AC11.4.6, Lab Lessons table), contract C8 in `contract-design/contract-summary.md`.

## Gap and finding

- **AC11.4.6** (u11): a finished lesson's "What happened" list must state "the variant with the lowest dev loss after training and its value" for every lesson except `l09` (which states the higher accuracy and the format rates instead). Finding 1: `web/src/lib/lab-verdicts.ts` `verdicts()` skips that sentence for `l12` (`else if (lessonId !== "l12")`), and the l12 test in `tests/web/lab.test.tsx` does not check for it. Finding 2: for `l11` the AC asks for the spread across seeds "and that smaller differences in the other lessons are noise"; `seedVerdict` says only "A difference this small between two runs is noise, not an effect.", and the l11 test only matches `/noise/i`. Fix: the lowest-dev-loss sentence for every lesson but `l09` (l12 too, in addition to its timing sentences); the l11 sentence says that differences smaller than this spread between variants in the other lessons are noise.

## Parts

| Part | Unit | Criteria | Owned files | Test files (new) |
|---|---|---|---|---|
| W | u11-finetune-lab | AC11.4.6 | `web/src/lib/lab-verdicts.ts` | `tests/web/lab-verdicts-gap2.test.tsx` |

One file, so one part (test writer, then builder). Lead: `construction/gap-2.md`, `STATE.md`. No spec change, no shared files, no dependency changes. No long run: the GPU run `q17-grpo-dev-3` imports no website file.
