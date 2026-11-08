# batch-9: token-by-token walkthrough (u5-website) and the fine-tuning lab (u11-finetune-lab)

Branch `wip/batch-9`, built in the git worktree `.cache/worktrees/batch-9` (Nico's website runs from the main tree's Vite; a half-written file there crashes his open page, so website batches build in a worktree). Rebased onto main 2026-11-08 after batches 8, 10 and 11. Spec: approved commit 37fb5a4 plus the `spec(` commits since, the last being `spec(u5-website, u11-finetune-lab): ...` (`inception/changes.md`, last line). `S` = `aidlc/spaces/default/intents/261030-gsm8k-finetune/inception`.

`test_command`: `scripts/check.sh`, on the CPU through `scripts/in-env.sh`. The gate runs in the main folder at the branch's commit (`git switch --detach wip/batch-9` there, then back to main): in a worktree three env tests in `tests/test_u1_env.py` fail because the shared `.venv` points the caches at the main folder. In this worktree, Python must import this tree's `src` (the venv's editable install points at the main tree): run `PYTHONPATH=$PWD/src scripts/check.sh`, and single test files as `PYTHONPATH=$PWD/src scripts/in-env.sh .venv/bin/python -m pytest -q tests/<file>`. Website: `scripts/in-env.sh npm run web:test -- <file>`, `npm run web:lint`, `npm run web:typecheck` (through `scripts/in-env.sh`). `node_modules`, `.venv` and `.tools` are symlinks to the main tree: never install anything.

Why now (Nico, 2026-11-08): "add more animation to the live training view that shows how it works also for training"; "are we always embedding the text every batch? this should be done once" (it is tokenized once, `tokenize_examples` in `src/gsm8k/training/sft.py`; the walkthrough says so and lesson l12 measures it); "set up a training pipeline where I fine tune ... a way smaller model that trains in minutes, and then build a learning pipeline step by step to learn all about fine tuning, mainly what affects what and how ... don't influence the current run".

Do not influence a GPU run: none runs now, but the worker can launch queued runs from the main tree's code at any time. Nothing in this batch uses the GPU (tests run through `scripts/in-env.sh`, which hides it; the lab is CPU only), and no part changes a module the training or evaluation commands import (`src/gsm8k/training/`, `evaluation.py`, `datasets_prompts/`, `scoring.py`, `run_config.py`, `run_records/`, `run_control/`). The lab imports them read-only.

Teach (what each unit teaches, which number should move):
- u5-website US4.8: what really happens inside one optimizer step (tokens, padding, embeddings, forward, next-token loss on answer tokens, backward into LoRA A and B, AdamW update), and the difference between training and generation. Nothing numeric moves; the live loss, gradient norm and learning rate appear inside the phases they belong to.
- u11-finetune-lab: a curriculum of twelve 3–15 minute CPU experiments on `EleutherAI/pythia-31m`, each changing one dial. Numbers that move: dev loss (falls with a good learning rate, rises again when overfitting), trainable weights (LoRA rank, full), seconds per step (batch size, padding, re-tokenizing) and format rate (the model learns the `#### <number>` ending long before it gets answers right).

## Criteria

- u5-website: AC4.8.1–AC4.8.7 (US4.8), part T.
- u11-finetune-lab: AC11.1.1–AC11.1.3 and AC11.2.1–AC11.2.9 (part L), AC11.3.1–AC11.3.4 (part S), AC11.4.1–AC11.4.8 (part W). AC11.2.10 is `[manual]` (Nico runs l01 from the Lab page after the merge and the service restart).

All in `S/user-stories/stories.md`; the lab's interfaces are contract C8 in `S/contract-design/contract-summary.md`.

## Parts

### Part L: lab core (Python), u11-finetune-lab, US11.1 and US11.2

Owns: `src/gsm8k/lab/__init__.py`, `src/gsm8k/lab/config.py`, `src/gsm8k/lab/lessons.py`, `src/gsm8k/lab/trainer.py`, `src/gsm8k/lab/runner.py`, `src/gsm8k/lab_cmd.py`, and one entry `"gsm8k.lab_cmd"` appended to `COMMAND_MODULES` in `src/gsm8k/cli.py` (nothing else in that file).
Tests: `tests/test_u11_lab_lessons.py` (AC11.1.x), `tests/test_u11_lab_run.py` (AC11.2.1–AC11.2.9).

- `config.py`: `LabConfig` (frozen dataclass, the Lab Defaults table plus `model`, `model_revision`), `validate()`, `config_for(lesson_id, variant)`, `estimate_minutes(lesson)`, `changes_text(variant)` (C8).
- `lessons.py`: `Lesson`, `Variant`, `LESSONS` with the table's ids, titles and variants; labels in plain words (for example `lr-1e-5` "Learning rate 1e-5", `few-many` "64 problems, 12 epochs", `full` "Every weight", `retokenize` "Tokenize every step"). Write the texts (question, watch, guess, why, big_run, check) carefully: they are the teaching. `why` explains the mechanism in 3–6 sentences and points at the numbers to look at; `big_run` names the matching Training Dials dial or method and what to try on the 1.7B runs; options are plausible and only one is what usually happens.
- `trainer.py`: seams `load_lab_model(cfg)` (pinned model on the CPU, float32; pad token = eos when missing) and `load_lab_problems(cfg) -> (train, dev)` (GSM8K at the run_config default dataset revision, the fixed split, `split.sort_by_index`, `guard.check_training_problems`; the test split's problems are only used to refuse leaks). A plain PyTorch loop: tokenize once (`gsm8k.training.targets.training_text` for prompt and target; prompt masked unless `loss_on` is `all`; eos appended; cut at `max_seq_len`), batches (`random` or `by-length`, AC11.2.8), AdamW, clip 1.0, schedule (linear or constant, with warm-up steps `ceil(warmup_ratio × total_steps)`), LoRA through peft with `target_modules="all-linear"` (peft leaves the output head out) or full; dev loss at the AC11.2.6 steps (0 and each distinct max(1, ceil(k × total/10))), over answer tokens whatever `loss_on` is; before and after scoring with `gsm8k.evaluation.evaluate(model, tokenizer, dev, lambda p: training_prompt(p.question), batch_size=16, max_new_tokens=cfg.max_new_tokens)` plus the format rate; peak memory from `resource.getrusage(RUSAGE_SELF).ru_maxrss / 1024` MB.
- `runner.py` and `lab_cmd.py`: `gsm8k lab list|run` (C8). `lab_cmd` and `gsm8k/lab/__init__.py`, `config.py`, `lessons.py` import no torch, transformers or peft at module level and set no environment variable on import (`cli.py` imports every command module, so GPU runs import `lab_cmd` too). The `run` handler sets `CUDA_VISIBLE_DEVICES=""` before CUDA is first used, `torch.set_num_threads`, `os.nice(10)`; the lab lock is an exclusive non-blocking `flock` on `outputs/lab/lab.lock` held for the process's life (copy the pattern of `src/gsm8k/run_records/lock.py`); status file written atomically (temp file and rename), SIGTERM ends after the current step (exit 130), errors end `failed` (exit 1), lock released in `finally`. Outputs root: `--outputs`, else the `GSM8K_OUTPUTS_DIR` environment variable the other commands honour (see `run_records/paths.py`), else `outputs/`.
- Tests: patch `trainer.load_lab_model` with a deep copy of the session `tiny_model` fixture (never train the shared object; peft injects layers in place) and `trainer.load_lab_problems` with a handful of fixture `Problem`s; keep configs tiny through `--variant` and by patching `config_for` or the defaults where needed (train_examples 16, batch 4, dev_problems 8, max_new_tokens 16, sample_problems 1). Whole file under a minute.

### Part S: lab service routes, u11-finetune-lab, US11.3

Owns: `src/gsm8k/service/lab_routes.py`, and in `src/gsm8k/service/app.py` only the lines that register the routes and add `lab_busy` and `no_lab_run` to the error codes.
Tests: `tests/test_u11_lab_service.py` (AC11.3.1–AC11.3.4), with FastAPI's `TestClient`, `tmp_project_dirs`, fixture lab files written by the test (C8 shapes), and a stubbed launcher (a module attribute read at call time, for example `lab_routes.launch(argv, log_path) -> pid`) so no real process starts; the stop test stubs the signal sender (`lab_routes.send_signal(pid, sig)`).
- `active` (C8): the lesson in `lab.lock` while its flock is held (try a non-blocking flock, release at once), else the lesson of the process this service launched while `Popen.poll()` is None; while `active` is a lesson, that lesson's state is answered `running`. The launch passes `CUDA_VISIBLE_DEVICES=""` in the child's environment.
- Reads lessons from `gsm8k.lab.lessons` / `gsm8k.lab.config` (part L) at call time. Until part L lands, build against the C8 interface; the lead runs the tests after both parts.
- Launch: `subprocess.Popen(argv, cwd=ROOT, start_new_session=True, stdout=<log, append>, stderr=STDOUT)`; `argv = [sys.executable, "-m", "gsm8k", "lab", "run", lesson]`. No GPU lock, no queue, no `scripts/run-detached.sh` (the lab is CPU only).

### Part W: Lab page (website), u11-finetune-lab, US11.4

Owns: `web/src/pages/lab.tsx`, `web/src/components/lab/` (new folder, any files), `web/src/lib/lab-verdicts.ts`, the `/lab` route in `web/src/router.tsx`, and the "Lab" link in `web/src/components/top-bar.tsx`.
Tests: `tests/web/lab.test.tsx` (AC11.4.1–AC11.4.8), with `fakeApi` and the lab helpers `LAB_LESSONS`, `labList`, `labLesson`, `labSummary` (lead-owned, `web/src/test/fake-api.ts`, already there); fake timers for the 2-second refresh.
- Uses `api.getLab`, `getLabLesson`, `runLabLesson`, `stopLab` and the `Lab*` types in `web/src/lib/api.ts` (lead-owned, already there). Reuse the existing chart component (`web/src/components/metric-chart.tsx`) if it takes several series; else draw the overlay with the same look. Guess storage: `localStorage` key `gsm8k-lab-guess-<lesson id>`, every read and write in try/catch.
- Verdicts (AC11.4.6) as pure functions in `lab-verdicts.ts` so they are easy to test.
- Full width (AC4.1.4, batch-10): the Lab page's outer container is `flex w-full flex-col ... px-[var(--gutter)]` with no `mx-auto`/max-width cap; prose keeps `max-w-[75ch]`. Part W's test file also checks this (titles `AC4.1.4 ...`).

### Part T: step walkthrough (website), u5-website, US4.8

Owns: `web/src/components/step-walkthrough.tsx`, `web/src/lib/walkthrough.ts`, `web/src/styles/walkthrough.css`, and in `web/src/pages/training.tsx` only the lines that render `<StepWalkthrough>` right after `<FinetuneView>` with the same run (method, config via `api.getRun`, live lines, live flag).
Tests: `tests/web/step-walkthrough.test.tsx` (AC4.8.1–AC4.8.7), rendering the component directly and through the training page, with fake timers (1.8 s per phase) and the reduce-motion hook (`web/src/lib/reduced-motion.ts`).
- Size: the walkthrough's drawings stay readable on a 3,840 px window and never fill it (like AC4.7.10: at most two-thirds of the window, `max-w-[66vw]`, centred); prose `max-w-[75ch]`.
- Look: the Gateway Flow look of the existing panel (`web/src/styles/finetune.css`, tokens in `web/src/styles/tokens.css`): token chips, the vectors as small dot columns, layers as the existing dotted blocks with an orange LoRA strip, arrows for the shift-by-one targets, a right-to-left orange sweep for the gradient. CSS animations keyed per phase; nothing moves under `data-motion="still"`.
- Sample text: a short built-in GSM8K-style problem and its step-by-step answer, pre-split into word-piece chips (an illustration, labelled so).

## Lead (shared files, done in `feat(batch-9): shared setup`)

- `web/src/lib/api.ts`: the C8 `Lab*` types and the four client methods.
- `web/src/test/fake-api.ts`: lab defaults and the helpers `LAB_LESSONS`, `labList`, `labSummary`, `labLesson`.

## Rules

Tests named by criterion ID; no existing test line changed or deleted; tests committed before the code; CPU only; Ruff clean (line length 110); website lint, Prettier and strict type check clean. Builders write only their owned files and use read-only git (status, diff, log).
