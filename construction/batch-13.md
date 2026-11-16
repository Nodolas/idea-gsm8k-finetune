# batch-13: the learning course (u12-learning-course)

Branch `wip/batch-13`, built in the git worktree `.cache/worktrees/batch-13` (Nico's website runs from the main tree's Vite; a half-written file there crashes his open page). Spec: approved commit 37fb5a4 plus the `spec(` commits since; u12 is the `inception/changes.md` lines of 2026-11-08 "u12-learning-course (with u7-grpo)" and "u12-learning-course, u7-grpo (spec review before merge)". `S` = `aidlc/spaces/default/intents/261030-gsm8k-finetune/inception`. Criteria: `S/user-stories/stories.md` section "12. Learning Course" (the Course Steps, Course Runs, Course Timing and Course Models tables are part of the spec); interfaces: contract C9 (and C1, C2 `quantize`, C3 `results`/`after`) in `S/contract-design/contract-summary.md`; components LearningCourse and CourseProgress in `S/domain-design/components.md`.

`test_command`: `scripts/check.sh`, on the CPU through `scripts/in-env.sh`. In this worktree Python must import this tree's `src` (the venv's editable install points at the main tree): run single test files as `PYTHONPATH=$PWD/src scripts/in-env.sh .venv/bin/python -m pytest -q tests/<file>`, the suite as `PYTHONPATH=$PWD/src scripts/check.sh` (three env tests in `tests/test_u1_env.py` fail in a worktree because the shared `.venv` points the caches at the main folder; the lead's gate runs in the main folder at the branch's commit). Website: `scripts/in-env.sh npm run web:test -- <file>`, `npm run web:lint`, `npm run web:typecheck` (through `scripts/in-env.sh`). `node_modules`, `.venv` and `.tools` are symlinks to the main tree: never install anything.

Do not influence a GPU run: none is running or queued. Tests never use the GPU (`scripts/in-env.sh` hides it) and never download weights: the quantized load, the course models and the inspection's config and tokenizer reads go through seams the tests patch.

Teach (what the unit teaches, which number should move): the course is the guided path through the whole project in 24 steps. It teaches how a base model is scored (accuracy on 100 dev problems and its ±10-point interval), how five open model designs differ (layers, width, grouped-query attention, gated MLPs, tied embeddings, weights by part) and why Qwen3-1.7B-Base was chosen, the twelve lab lessons, what memory each fine-tuning approach needs (16 bytes a weight for full fine-tuning against about 0.55 for QLoRA's frozen base), and the pipeline sft, self-taught reasoning, GRPO on Qwen3-0.6B. Numbers that move: course accuracy per run (c05: pythia near 0 %, Qwen3-1.7B near 79 %), QLoRA's peak GPU memory below LoRA's (c20) at about 1.5 times the step time, and Nico's progress (steps done of 24, first-try right answers).

## Criteria

- Part D (course data): AC12.1.1, AC12.1.2, AC12.1.3, AC12.1.4, AC12.4.4.
- Part I (inspection): AC12.2.1, AC12.2.2.
- Part S (service routes and progress): AC12.3.1–AC12.3.7, AC12.3.8 (service side: run list, scores and best read `results/runs.csv` only; course runs listed from their folders with status only), AC12.4.6 (c23's missing c21 adapter).
- Part Q (queue, worker, prune): AC12.4.1 (queue entry `results`, worker passes `--results`), AC12.3.3 (worker side: the `after` rule), AC12.4.6 (prune leaves `course-*` alone).
- Part M (course models and QLoRA): AC12.4.1 (course attempt ids accepted by the commands, row appended to `--results`), AC12.4.2, AC12.4.3.
- Part W (website): AC12.5.1–AC12.5.11, AC12.5.13, AC12.3.8 (website side: Training page's past runs mark course runs "Course", status only).
- `[manual]`: AC12.4.5 (QLoRA and GRPO course runs on this PC) and AC12.5.12 (Nico runs c01 from the page), after the merge and a service and worker restart. Course runs are short (estimated 10 minutes or less) and go through the website's queue; there is no long-run script and no `results/runs.csv` row in this batch.

Tests may share an AC id across files (for example `test_AC12_3_3_...` in parts S and Q) as long as the function names differ.

## Interfaces between the parts (settled here; the contract decides anything not listed)

- `gsm8k.course.steps` (part D): `STEPS: tuple[Step, ...]` (C9 fields), `STEP_IDS`, `get_step(step_id) -> Step | None` (None for unknown), `PARTS: tuple[tuple[int, str], ...]` (number, title), `CourseRunSpec(step, run, command, model, changes: dict, changes_text: str)` and `COURSE_RUNS: tuple[CourseRunSpec, ...]` in table order with `runs_of(step_id)`, `CourseModel(id, revision, weights_label, why, licence="Apache-2.0")` and `COURSE_MODELS` in table order (project models take their revision from `gsm8k.datasets_prompts.hub.MODEL_REVISIONS`, the three course-only models from `hub.COURSE_MODEL_REVISIONS`, part M), `COURSE_RESULTS = "outputs/course/runs.csv"` (the queue-entry value), `course_dir(outputs: Path) -> Path` (`<outputs>/course`), `ATTEMPT_ID_PATTERN` (`^course-c[0-9]{2}-[a-z0-9-]+-[0-9]+$`).
- `gsm8k.course.configs` (part D): `course_config(step, run, attempt_id, outputs, *, cot_data_run=None, checkpoints=None) -> RunConfig` (C2-valid; c22 `selfcot` takes the `cotgen` attempt id queued with it through `cot_data_run`; c23 `grpo` sets `adapter` to `<checkpoints>/<latest finished course-c21-sft-n>` from `<outputs>/course/runs.csv`, or no adapter when there is none, and raises `CourseRunRefused("Run step c21 again: its adapter is missing")` when that row exists but its folder does not); `estimate_minutes(step, run, outputs) -> tuple[int, bool]` (Course Timing; measured timings from `gsm8k.estimates.measured_seconds_per_problem/step`); `next_attempt_id(step, run, outputs) -> str` (one more than the highest `n` among `<outputs>/course/runs.csv` rows, run folders `outputs/course-<step>-<run>-*` and queue entries); `class CourseRunRefused(Exception)`.
- `gsm8k.course.progress` (part S): `read_progress(outputs) -> dict` (missing file: `{"v":1,"steps":{}}`; unreadable: raises `ProgressUnreadable(path)`), `record_open`, `check_quiz(step, answers, outputs) -> dict` (C9 QuizResult; raises `InvalidAnswers`), `save_own_words(step, text, outputs) -> dict` (raises `InvalidText`), `first_try(progress) -> tuple[int, int]` (right on first try, questions answered); atomic writes (temp file and rename).
- `gsm8k.course.inspect` (part I): seams `load_config(model, revision)` and `load_tokenizer(model, revision)` read at call time; `inspect_models(outputs) -> dict` and `write_architectures(outputs)`.
- `gsm8k.run_control.queue` (part Q): `QueueEntry` gains `results: str | None` and `after: str | None`; `add(attempt_id, config, kind=None, outputs=None, *, results=None, after=None)`; `add_all(entries: list[dict], outputs=None) -> list[QueueEntry]` (each dict: `attempt_id`, `config`, `kind`, `results`, `after`), all or none: raises `QueueFull` and adds nothing when they do not all fit under `MAX_WAITING`; a `results` other than None or `"outputs/course/runs.csv"` raises `ValueError` and adds nothing; attempt ids accept the course pattern. The worker passes `--results <outputs root>/course/runs.csv` for that value (the entry's path is relative to the project's outputs root, so tests with a temporary outputs folder work), else its own default.
- `gsm8k.run_config` and the commands (part M): `RunConfig.quantize: str = "none"` (`none|4bit`; at its default out of `config_hash`); `MODELS` stays the two project models, `COURSE_ONLY_MODELS` the three course models, accepted only with method `base` and a course attempt id (`ConfigError` naming the model otherwise); course attempt ids accepted wherever a run id is checked (`run_records/paths.py RUN_ID_PATTERN`, `cli.py ATTEMPT_ID_PATTERN`); `gsm8k train --quantize none|4bit` and the config field; the quantized load is a seam in `train_cmd` (for example `train_cmd.load_quantized_model(model_id, revision)`) that tests replace.

## Parts

### Part D: course data, `gsm8k.course` steps and configs

Owns: `src/gsm8k/course/__init__.py`, `src/gsm8k/course/steps.py`, `src/gsm8k/course/configs.py`.
Tests: `tests/test_u12_course_steps.py` (AC12.1.1–AC12.1.4, AC12.4.4 config side: c23 is method grpo, grpo_steps 20, grpo_generations 4, limit 100, from the latest c21 adapter).
- Write the step texts carefully: they are the teaching. `why` says in 2–4 sentences why the step comes now; `body` explains the idea in Markdown paragraphs (no HTML) with the numbers to look at; questions are plausible with exactly one right option and an explanation; `model_answer` is 2–4 sentences. c03, c04, c06 and c19 must say what AC12.1.3 lists. Lab steps' texts point at the lab lesson (`gsm8k.lab.lessons`) and say what it shows for the big runs.
- None of these modules imports torch, transformers, peft or bitsandbytes at module level, nor sets an environment variable (AC12.1.4; the test also covers `gsm8k.course.progress` and `gsm8k.course_cmd`, owned by parts S and I).

### Part I: model-design inspection, `gsm8k course inspect`

Owns: `src/gsm8k/course/inspect.py`, `src/gsm8k/course_cmd.py` (the lead already added `"gsm8k.course_cmd"` to `COMMAND_MODULES` in `src/gsm8k/cli.py`).
Tests: `tests/test_u12_course_inspect.py` (AC12.2.1, AC12.2.2), with tiny fixture configurations (GPTNeoX, Llama, Qwen2, Qwen3 configs built in the test with a handful of layers and a small vocabulary) and a tiny tokenizer, patched into the seams; a temporary outputs folder; no download.
- The handler sets `CUDA_VISIBLE_DEVICES=""` first; weights are counted on a model built from the configuration on the `meta` device (`torch.device("meta")` / `init_empty_weights`), by part: embeddings (input embeddings, and learned position embeddings), attention (q, k, v, o and their biases and norms inside attention), MLP, norms (layer and final norms), `head` (output head; 0 when tied); the parts sum to the total. The sample problem is the first scored dev problem of the fixed split (`gsm8k.datasets_prompts`), its 4-shot prompt as FR1.2 builds it. Atomic write; any model that fails ends exit 1 with a message naming it and writes nothing.
- `course_cmd` imports nothing heavy at module level (AC12.1.4).

### Part S: service course routes and progress

Owns: `src/gsm8k/service/course_routes.py`, `src/gsm8k/course/progress.py`, and in `src/gsm8k/service/app.py` only the lines that register the routes (like `lab_routes.register(...)`) and add the C9 error codes.
Tests: `tests/test_u12_course_service.py` (AC12.3.1–AC12.3.8, AC12.4.6 c23 message), with FastAPI's `TestClient`, `tmp_project_dirs`, fixture course rows in `<outputs>/course/runs.csv` (C1 format), fixture `architectures.json` and lab files, and stubbed launchers (module attributes read at call time, as `lab_routes` does) so no process starts.
- States, the c19 memory table, the c24 comparison and the run states (`not-run|queued|running|finished|failed|stopped`, from the queue, the run folder's `status.json`, the lock and the course rows) live in `course_routes.py` (or a helper module under `src/gsm8k/course/` named in the report). Run steps queue through `queue.add_all` with `results="outputs/course/runs.csv"` and, for c22's `selfcot`, `after=<cotgen attempt id>`; `course_busy` while any run of the step is queued or running; `CourseRunRefused` answers 422 `nothing_to_run` with its message, and `GET /course/c23` then carries it as `notice` (an additive field; c22 also shows "Too few solutions were kept (<n>); run the step again" as `notice` when its latest `cotgen` kept fewer than 50).
- The inspection launch: `[sys.executable, "-m", "gsm8k", "course", "inspect"]` as an argument list, own session, `CUDA_VISIBLE_DEVICES=""` in the child's environment, output appended to `<outputs>/course/inspect.log`.

### Part Q: queue, worker and prune for course runs

Owns: `src/gsm8k/run_control/queue.py`, `src/gsm8k/run_control/worker.py`, `src/gsm8k/prune.py`, `src/gsm8k/run_control/runs.py` (only if a course id needs to list or resolve there).
Tests: `tests/test_u12_course_queue.py` (AC12.4.1 queue and worker side, AC12.3.3 worker `after` rule, AC12.4.6 prune), with `tmp_project_dirs`, a stubbed `launch.build_argv`/launcher and GPU check as the existing worker tests do (`tests/test_u4_queue_worker.py`).
- `after`: the entry and those behind it wait until the named attempt has a row in the entry's results file; when that attempt's `status.json` reads `failed` or `stopped`, or `finished` with no row, the entry is removed and the reason appended to `outputs/queue/queue.log`. A missing key reads as null; existing entries keep working.

### Part M: course models and QLoRA in the commands

Owns: `src/gsm8k/run_config.py`, `src/gsm8k/datasets_prompts/hub.py`, `src/gsm8k/run_records/paths.py`, `src/gsm8k/cli.py` (not the `COMMAND_MODULES` list), `src/gsm8k/evaluation.py`, `src/gsm8k/train_cmd.py`, `src/gsm8k/training/sft.py`, `src/gsm8k/training/grpo.py`, `src/gsm8k/training/loop.py`, `src/gsm8k/cot_cmd.py` (each only where needed).
Tests: `tests/test_u12_course_models.py` (AC12.4.1 command side, AC12.4.2, AC12.4.3), on the CPU with the `tiny_model` fixture, patched loaders and a temporary outputs folder and results file.
- `hub.COURSE_MODEL_REVISIONS` holds the three pinned revisions of the Course Models table; `evaluate` loads a course model at that revision (method `base`, course attempt id only). QLoRA: `BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16)`, then `peft.prepare_model_for_kbit_training` and the same LoRA as `none`; `quantize` `4bit` refused for methods other than `sft`, `selfcot`, `grpo`. bitsandbytes is imported only inside the quantized load.

### Part W: Course page and landing card (website)

Owns: `web/src/pages/course.tsx`, `web/src/components/course/` (new folder, any files), `web/src/lib/course.ts` (optional helpers), the `/course` route in `web/src/router.tsx`, the "Course" link after "Lab" in `web/src/components/top-bar.tsx`, the lines in `web/src/pages/landing.tsx` that render the "Your course" card, and the "Course" mark in `web/src/components/past-runs-list.tsx`.
Tests: `tests/web/course.test.tsx` (AC12.5.1–AC12.5.11, AC12.5.13, AC12.3.8 web side), with `fakeApi` and the lead's course helpers `COURSE_PARTS`, `COURSE_STEPS`, `courseOverview`, `courseStep`, `courseRun`, `courseArchitecture`, `courseArchitectures` in `web/src/test/fake-api.ts`.
- Uses `api.getCourse`, `getCourseStep`, `runCourseStep`, `submitCourseQuiz`, `saveCourseOwnWords`, `openCourseStep` and the `Course*` types in `web/src/lib/api.ts` (lead-owned, already there). Look: the existing pages' look (`web/src/pages/lab.tsx`, tokens in `web/src/styles/tokens.css`, shadcn parts in `web/src/components/ui/`). The page refreshes the shown step every 3 s while one of its runs is queued or running. Full width (AC4.1.4, AC12.5.13): `px-[var(--gutter)]`, no max-width cap, prose `max-w-[75ch]`. The landing card keeps AC4.2.5 (existing tests in `tests/web/landing*.test.tsx` and `full-width.test.tsx` must stay green).

## Lead (shared files, in `feat(batch-13): shared setup`)

- `requirements.txt`: `bitsandbytes==0.50.2` (installed in `.venv`).
- `src/gsm8k/cli.py`: `"gsm8k.course_cmd"` appended to `COMMAND_MODULES` (part M owns the rest of the file).
- `web/src/lib/api.ts`: the C9 `Course*` types (plus an additive `notice` on `CourseStep`), the six client methods and error codes.
- `web/src/test/fake-api.ts`: course defaults and helpers.

## Rules

Tests named by criterion ID; no existing test line changed or deleted; tests committed before the code; CPU only; Ruff clean (line length 110); website lint, Prettier and strict type check clean. Builders write only their owned files and use read-only git (status, diff, log).
