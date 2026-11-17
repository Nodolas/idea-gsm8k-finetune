# gap-1: Converge gaps (u7-grpo, u12-learning-course, u11-finetune-lab, u5-website)

Converge on 2026-11-17 (main 8f190b6, `scripts/check.sh` exit 0, 870 Python tests, coverage 88.2%, trace PASS before the spec change) found these gaps. Spec: `aidlc/spaces/default/intents/261030-gsm8k-finetune/inception/user-stories/stories.md` (AC lines), `requirements-analysis/requirements.md` (FR7.1), `inception/changes.md` (2026-11-17 lines), contracts in `contract-design/contract-summary.md`.

## Gaps and findings

- **AC7.1.5** [manual] Verify: results/runs.csv row q17-grpo-dev. Finding: q17-grpo-dev-1 crashed in its first step: TRL 1.17.1's Triton log-prob kernel (`trl/kernels/chunked_logprob.py`, used whenever Triton is installed and the device is CUDA) compiles Triton's CUDA helper with `gcc ... -I/usr/include/python3.12`, and this PC has no `Python.h` (python3.12-dev not installed). The lead unpacked Ubuntu's `python3.12-dev` and `libpython3.12-dev` 3.12.3-1ubuntu0.17 (the installed python3.12's version) into `.tools/python-headers/` and checked that the helper compiles with `CPATH=<h>/usr/include/python3.12:<h>/usr/include` and that a Triton kernel runs on the GPU. The rerun (q17-grpo-dev-2) is submitted after the merge (3.4), after a short trial run.
- **AC7.1.6** (new, spec change 2026-11-17): `CPATH` in every `gsm8k` process; exit 2 before the model loads when no headers exist and the run is on the GPU.
- **AC7.1.4** (changed 2026-11-17): the 362 planned steps filled 3 hours with training alone; the closing dev score (496 problems) was not reserved, and `train_cmd._print_estimate` printed a GRPO estimate from supervised step times ("about 3 min"). Fix: `grpo.steps_for` passes `budget_s = CAP_SECONDS - closing-dev reserve` to `plan_grpo_steps` (whose own tests pin counts for a given budget and stay as they are); the reserve is 496 × `measured_seconds_per_problem(model)`, else a stated fallback constant; the printed estimate and over-cap flag come from the GRPO plan (`check_grpo_steps` for an explicit count) plus the reserve.
- **AC12.1.2** (u12): a course run estimated above 10 minutes must be shown with "over 10 minutes"; the Course page never shows it (`web/src/components/course/run-area.tsx` `estimateText`). Fix in the website from `estimate_minutes > 10` (no contract change).
- **AC11.4.6** (u11): a finished lesson's "What happened" list must state the variant with the lowest dev loss after training; `web/src/lib/lab-verdicts.ts` does so only when more than one variant ended, so a finished l01 (one variant) shows no list. Fix: drop that condition for the lowest-dev-loss sentence (keep it for the closing "noise" sentence).
- **AC4.2.4** (u5): code is right, but `tests/web/landing.test.tsx` only checks the `data-motion` marker. A real test: with reduced motion, pointer move and pointer down request no animation frame and move no dot (the AC4.2.7 harness in `landing-halftone.test.tsx` shows how). Test only; no code change expected.

## Parts

| Part | Unit | Criteria | Owned files | Test files (new) |
|---|---|---|---|---|
| P | u7-grpo | AC7.1.4, AC7.1.6 (AC7.1.5 is the long run) | `src/gsm8k/_env.py`, `src/gsm8k/training/grpo.py`, `src/gsm8k/training/grpo_plan.py`, `src/gsm8k/train_cmd.py`, `scripts/fetch-python-headers.sh` | `tests/test_u7_grpo_gap1.py` |
| W1 | u12-learning-course | AC12.1.2 | `web/src/components/course/run-area.tsx` | `tests/web/course-over-ten.test.tsx` |
| W2 | u11-finetune-lab | AC11.4.6 | `web/src/lib/lab-verdicts.ts` | `tests/web/lab-single-variant.test.tsx` |
| W3 | u5-website | AC4.2.4 | (none; test only) | `tests/web/landing-reduced-motion.test.tsx` |

The three website parts are small and run as one builder (W), each file still owned by its part. Lead: `construction/gap-1.md`, spec files, `STATE.md`. No dependency changes.

`scripts/fetch-python-headers.sh`: idempotent; downloads the two `.deb` files matching the installed `python3.12` version with `apt-get download` into `.cache/debs/` and unpacks them with `dpkg-deb -x` into `.tools/python-headers/` (both gitignored); no root, nothing written outside the folder; exits 0 when `.tools/python-headers/usr/include/python3.12/Python.h` already exists.

## Long runs (after the merge, 3.4)

1. Trial (Nico asked for a short training run, 2026-11-17): `q17-grpotrial-dev-1`, `gsm8k train --method grpo --model Qwen/Qwen3-1.7B-Base --grpo-steps 10 --limit 20 --results outputs/trial/runs.csv`. A few minutes; its row goes to `outputs/trial/runs.csv`, not `results/runs.csv`; it saves GRPO `seconds_per_step` for the step plan.
2. AC7.1.5: `q17-grpo-dev-2` with the default steps (from the plan, now measured; GRPO trains one problem per step with its 4 answers as the batch).
