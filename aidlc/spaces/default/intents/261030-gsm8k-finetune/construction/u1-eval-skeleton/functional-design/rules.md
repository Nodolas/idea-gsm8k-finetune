# Business Rules: u1-eval-skeleton

Rules for US1.1–US1.4 in `inception/user-stories/stories.md`, sourced from `inception/requirements-analysis/requirements.md` (FR1.1–FR1.7, NFR5, NFR7, NFR8). They hold to the contracts in `inception/contract-design/contract-summary.md`, inside the blocks of `inception/domain-design/components.md`, for the unit scope in `inception/units-generation/unit-of-work.md` and `inception/units-generation/unit-of-work-story-map.md`. Entities are in `entities.md`.

## Rules

```yaml
rules:
  - id: BR1.1
    statement: Every cache, download and run file stays inside the project folder.
    category: constraint
    applies_to: every command
    trigger: process start, before any other import
    logic: SET HF_HOME, PIP_CACHE_DIR, XDG_CACHE_HOME, TRITON_CACHE_DIR, TORCHINDUCTOR_CACHE_DIR, TORCH_HOME to absolute paths under the project root (.cache/huggingface, .cache/pip, .cache, .cache/triton, .cache/torchinductor, .cache/torch)
    violation: not possible by construction; a test inspects the environment of a started command
    source: NFR5, FR1.1
  - id: BR1.2
    statement: GSM8K loads with no login or token.
    category: policy
    applies_to: Problem loading
    trigger: first use of the dataset
    logic: IF the dataset is not cached THEN download openai/gsm8k config main anonymously into the project cache
    violation: a failed download stops the run with exit code 1 and names the dataset
    source: FR1.1
  - id: BR1.3
    statement: The dev/train split is a pure function of the fixed split seed, never of the training seed.
    category: calculation
    applies_to: DataSplit
    trigger: split build
    logic: sort all 7,473 training ids by numeric index; shuffle the sorted list with the standard library's seeded pseudo-random generator (Mersenne Twister) seeded with split_seed (42); the first 500 are dev; the rest are train; store both lists sorted by numeric index
    violation: none
    source: FR1.2, NFR7
  - id: BR1.4
    statement: Dev and train are disjoint and together cover every training problem.
    category: constraint
    applies_to: DataSplit
    trigger: split build and split load
    logic: IF the two lists overlap OR their union is not all 7,473 training ids THEN the split is invalid
    violation: an invalid loaded split is treated as unreadable (BR1.6)
    source: FR1.2
  - id: BR1.5
    statement: No test problem is ever in the dev or train lists.
    category: constraint
    applies_to: DataSplit
    trigger: split build and split load
    logic: IF any id starts with gsm8k-test- THEN the split is invalid
    violation: as BR1.4
    source: FR1.2, NFR8
  - id: BR1.6
    statement: A missing split file is rebuilt; an unreadable one stops the run.
    category: policy
    applies_to: DataSplit file outputs/splits/gsm8k-split<split_seed>.json
    trigger: a run needs the split
    logic: IF the file is missing THEN rebuild it from the split seed (BR1.3) and save it atomically; IF it exists but cannot be parsed or fails BR1.4/BR1.5 THEN stop
    violation: exit code 1 with "Split file could not be read: <path>"
    source: FR1.2
  - id: BR2.1
    statement: The four exemplars are chosen deterministically from the dev split.
    category: calculation
    applies_to: FewShotPrompt
    trigger: prompt build
    logic: take a sample of 4 ids from the dev ids sorted by numeric index, using a fresh seeded pseudo-random generator (as in BR1.3) seeded with split_seed; keep the sampled order
    violation: none
    source: FR1.3
  - id: BR2.2
    statement: A model is never scored on its own exemplars.
    category: constraint
    applies_to: dev evaluation
    trigger: choosing the problems to score
    logic: dev problems to score = dev ids minus the 4 exemplar ids (496); test problems to score = all 1,319 test ids; a limit takes the first N of these sorted by numeric index
    violation: none
    source: FR1.3
  - id: BR2.3
    statement: The prompt text is fixed and contains no calculator notes.
    category: calculation
    applies_to: FewShotPrompt
    trigger: prompt build
    logic: for each exemplar write 'Question: <question>', a newline, 'Answer: <worked answer with every <<...>> note removed>'; join examples with a blank line; append a blank line, 'Question: <target>', a newline and 'Answer:'
    violation: none
    source: FR1.3, functional-design Q2
  - id: BR3.1
    statement: The predicted answer is the number after the first '####'.
    category: calculation
    applies_to: Prediction
    trigger: scoring an output
    logic: IF the output has a '####' followed by a number THEN that number, with commas, '$' and '%' removed, is the prediction
    violation: none
    source: FR1.4
  - id: BR3.2
    statement: Without a '####' number, the last number in the output is the prediction.
    category: calculation
    applies_to: Prediction
    trigger: scoring an output with no '####' number
    logic: take the last number (optional minus sign, digits with optional commas, optional decimal part) in the scored text
    violation: none
    source: FR1.4
  - id: BR3.3
    statement: An output with no number is wrong, not an error.
    category: policy
    applies_to: Prediction
    trigger: scoring an output with no number
    logic: predicted = none; correct = false; scoring continues with the next problem
    violation: none
    source: FR1.4
  - id: BR3.4
    statement: Prediction and gold are compared as numbers.
    category: calculation
    applies_to: Prediction
    trigger: after extraction
    logic: correct = |predicted - gold| < 1e-6, both read as decimals after removing commas, '$' and '%'
    violation: none
    source: FR1.4
  - id: BR3.5
    statement: Only the text up to the stop point is scored.
    category: policy
    applies_to: generation
    trigger: generating an answer
    logic: greedy decoding; stop at the end of the first line containing '#### <number>', or when the model begins a new 'Question:', or after 512 new tokens, whichever is first; cut the output at that point
    violation: none
    source: FR1.5, functional-design Q3
  - id: BR4.1
    statement: An evaluation reports accuracy, the number scored and minutes, and saves every prediction.
    category: policy
    applies_to: gsm8k evaluate
    trigger: end of an evaluation
    logic: accuracy = correct / scored; print accuracy, scored and minutes; write one Prediction per scored problem to outputs/<run_id>/predictions.jsonl
    violation: none
    source: FR1.5
  - id: BR4.2
    statement: Rows go to results/runs.csv only for runs started with a run id.
    category: policy
    applies_to: RunRow destination
    trigger: end of a finished evaluation
    logic: IF --run-id was given THEN append to --results (default results/runs.csv) ELSE append to a new temporary file whose path is printed
    violation: none
    source: FR1.6
  - id: BR4.3
    statement: A finished evaluation appends exactly one row in the C1 column order, with the given run id.
    category: validation
    applies_to: RunRow
    trigger: end of a finished evaluation
    logic: write date, run_id, model, method, data, metric, value, minutes, config_hash, adapter_run as one whole line; run_id is the --run-id value unchanged
    violation: a failed or stopped run writes no row
    source: FR1.6
  - id: BR4.4
    statement: Each run records its seconds per problem and peak GPU memory.
    category: policy
    applies_to: RunFolder
    trigger: end of an evaluation (also on failure, when known)
    logic: seconds_per_problem = generation time / problems scored; peak_gpu_memory_gb = the GPU's peak allocated memory; write both to outputs/<run_id>/timings.json
    violation: none
    source: FR1.7, NFR1
  - id: BR4.5
    statement: The same configuration always gives the same hash; any change gives a different one.
    category: calculation
    applies_to: RunConfig
    trigger: before the run starts
    logic: config_hash = sha256 of the canonical JSON of {model, method} plus every other field whose value differs from its documented default, keys sorted, run_id and v removed (C2 as changed 2026-10-31); so a field added later with a default leaves this hash unchanged
    violation: none
    source: FR1.6, NFR7
  - id: BR4.6
    statement: A missing adapter stops the evaluation before any work.
    category: validation
    applies_to: gsm8k evaluate
    trigger: start, when adapter_path is set
    logic: IF adapter_path does not exist THEN stop
    violation: exit code 2 with "Adapter not found: <path>"; nothing written
    source: FR1.5
  - id: BR4.7
    statement: An adapter evaluation is labelled with the adapter's own run.
    category: calculation
    applies_to: RunConfig and RunRow when adapter_path is set
    trigger: start, after BR4.6
    logic: adapter run id = the adapter folder's name; method = the method in outputs/<adapter run id>/config.json; the row's adapter_run = the adapter run id. With no adapter, method = base and adapter_run is empty
    violation: IF the adapter run's config.json cannot be read THEN exit code 2 with "Adapter run unknown: <run id>"; nothing written
    source: FR1.5, FR1.6, contract C1 (adapter_run)
  - id: BR4.8
    statement: A launched run reads its configuration from the file its launcher wrote; a terminal run may give it as flags.
    category: policy
    applies_to: gsm8k evaluate
    trigger: start
    logic: IF --config is given THEN read it, require its run_id to equal --run-id, and use it unchanged ELSE build the configuration from the flags and their defaults; --started-by (worker or terminal, default terminal) is recorded only in the lock content
    violation: exit code 2 naming the file or the mismatched run id; nothing written
    source: contract C5 (as changed 2026-10-31)
  - id: BR5.1
    statement: Only the process holding the OS lock on outputs/run.lock may use the GPU.
    category: constraint
    applies_to: every GPU command
    trigger: before loading the model
    logic: try the exclusive non-blocking lock; IF taken THEN write run_id, pid, started_at, started_by into the file ELSE refuse
    violation: exit code 3 with "A run is already active: <run_id>"; nothing written
    source: FR3.4, contract C3
  - id: BR5.2
    statement: Every command ends with a fixed exit code and a status file.
    category: policy
    applies_to: gsm8k evaluate
    trigger: process end
    logic: 0 finished, 1 failed, 2 invalid configuration, 3 lock held, 130 stopped; for 0, 1 and 130 write outputs/<run_id>/status.json with status, exit_code, reason, ended_at; exits 2 and 3 happen before the run starts and write nothing
    violation: none
    source: FR3.7, contract C5
  - id: BR5.3
    statement: A run id is used only once.
    category: validation
    applies_to: --run-id
    trigger: start
    logic: IF the run id already has a row in the results file OR its folder under outputs/ holds a status.json or predictions.jsonl (a run already happened there) THEN refuse; a folder holding only the config.json its launcher wrote (BR4.8) is not a used run id
    violation: exit code 2 with "Run id already used: <run_id>"
    source: contract C1 (run_id unique)
  - id: BR5.4
    statement: Run files are never left half written.
    category: constraint
    applies_to: split file, config.json, status.json, timings.json
    trigger: every write
    logic: write to a temporary name in the same folder, then rename; appends to runs.csv and predictions.jsonl write one whole line at a time
    violation: none
    source: contract Common Rules
```

## Summary

| Rule | Statement | Source |
|---|---|---|
| BR1.1 | Caches and run files stay in the project folder | NFR5, FR1.1 |
| BR1.2 | GSM8K loads with no token | FR1.1 |
| BR1.3 | Split is a pure function of the fixed split seed | FR1.2, NFR7 |
| BR1.4 | Dev and train disjoint and complete | FR1.2 |
| BR1.5 | No test problem in dev or train | FR1.2, NFR8 |
| BR1.6 | Missing split rebuilt, unreadable split stops the run | FR1.2 |
| BR2.1 | Exemplars are a seeded sample of dev | FR1.3 |
| BR2.2 | Exemplars excluded from dev scoring (496) | FR1.3 |
| BR2.3 | Fixed prompt text, calculator notes stripped | FR1.3 |
| BR3.1 | Prediction from the first `####` number | FR1.4 |
| BR3.2 | Else the last number | FR1.4 |
| BR3.3 | No number means wrong | FR1.4 |
| BR3.4 | Numeric comparison | FR1.4 |
| BR3.5 | Stop at the answer line or a new question, 512-token cap | FR1.5 |
| BR4.1 | Report accuracy, scored, minutes; save predictions | FR1.5 |
| BR4.2 | Rows to `results/runs.csv` only with a run id | FR1.6 |
| BR4.3 | One row per finished run, C1 order | FR1.6 |
| BR4.4 | Seconds per problem and peak GPU memory recorded | FR1.7, NFR1 |
| BR4.5 | Stable configuration hash | FR1.6, NFR7 |
| BR4.6 | Missing adapter stops before any work | FR1.5 |
| BR4.7 | Adapter evaluations take the adapter run's method and record `adapter_run` | FR1.5, FR1.6, C1 |
| BR4.8 | `--config` from the launcher, or flags from the terminal; `--started-by` | C5 |
| BR5.1 | OS lock guards the GPU | FR3.4, C3 |
| BR5.2 | Fixed exit codes and status file | FR3.7, C5 |
| BR5.3 | Run ids are never reused | C1 |
| BR5.4 | No half-written files | Contract common rules |
