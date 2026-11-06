# Entities: u1-eval-skeleton

The data the walking skeleton defines and owns. The entity set comes from `inception/domain-design/components.md` (DatasetsAndPrompts, RunConfiguration, RunRecords) and the shapes on disk from `inception/contract-design/contract-summary.md` (C1, C2, C3 as changed 2026-10-31). Unit scope: `inception/units-generation/unit-of-work.md` (U1) and `inception/units-generation/unit-of-work-story-map.md` (US1.1–US1.4). Answers: `functional-design-questions.md`.

## Entity Model

```yaml
entities:
  - name: Problem
    description: One math word problem with its gold answer.
    attributes:
      - { name: problem_id, type: string, required: true, unique: true, constraints: "gsm8k-train-<index> or gsm8k-test-<index>, index = row order in the dataset" }
      - { name: source_set, type: enum, required: true, allowed: [gsm8k] }
      - { name: split, type: enum, required: true, allowed: [train, test] }
      - { name: question, type: text, required: true }
      - { name: worked_answer, type: text, required: true, constraints: "dataset solution text ending with a '#### <number>' line" }
      - { name: gold_answer, type: decimal, required: true, constraints: "the number after '####', commas removed" }
    constraints:
      - every problem_id is unique across train and test
    relationships: []

  - name: DataSplit
    description: The fixed partition of the 7,473 training problems into dev and train, plus the four prompt exemplars.
    attributes:
      - { name: split_seed, type: integer, required: true, unique: true, default: 42, constraints: "a fixed data constant, never the training seed dial (C2)" }
      - { name: dev_ids, type: list<problem_id>, required: true, constraints: "exactly 500 ids, sorted by numeric index" }
      - { name: train_ids, type: list<problem_id>, required: true, constraints: "exactly 6,973 ids, sorted by numeric index" }
      - { name: exemplar_ids, type: list<problem_id>, required: true, constraints: "exactly 4 ids, each in dev_ids" }
    constraints:
      - dev_ids and train_ids do not overlap and together are all 7,473 training problem ids
      - no id from the test split appears anywhere in the split
      - the same split_seed always gives the same three lists; changing the training seed never changes them
    relationships:
      - { to: Problem, cardinality: "one split references many problems", direction: "DataSplit -> Problem" }

  - name: FewShotPrompt
    description: The fixed 4-shot prompt template filled with one target question.
    attributes:
      - { name: prompt_version, type: string, required: true, unique: true, default: "v1" }
      - { name: exemplar_ids, type: list<problem_id>, required: true, constraints: "the DataSplit's four exemplars, in seeded order" }
      - { name: template, type: text, required: true, constraints: "'Question: <q>' newline 'Answer: <worked answer without calculator notes>' per exemplar, a blank line between examples, then 'Question: <target>' newline 'Answer:'" }
    relationships:
      - { to: DataSplit, cardinality: "one prompt uses one split's exemplars", direction: "FewShotPrompt -> DataSplit" }

  - name: RunConfig
    description: Every option that changes an evaluation's result (contract C2 config.json); the skeleton uses the evaluation subset.
    attributes:
      - { name: v, type: integer, required: true, default: 1 }
      - { name: run_id, type: string, required: true, constraints: "'<base id>-<n>' when given, else 'adhoc-<UTC timestamp>'" }
      - { name: model, type: enum, required: true, allowed: [Qwen/Qwen3-0.6B-Base, Qwen/Qwen3-1.7B-Base], default: Qwen/Qwen3-0.6B-Base }
      - { name: method, type: enum, required: true, allowed: "C1 method values", default: base, constraints: "base without an adapter; with an adapter, the method recorded in the adapter run's config.json" }
      - { name: split, type: enum, required: true, allowed: [dev, test], default: dev }
      - { name: adapter_path, type: path, required: false, default: null, constraints: "checkpoints/<run_id>/; its folder name is the adapter run id" }
      - { name: limit, type: integer, required: false, min: 1, default: null, constraints: "null = whole split" }
      - { name: seed, type: integer, required: true, min: 0, max: 2147483647, default: 42, constraints: "training and sampling seed; does not move the split" }
      - { name: split_seed, type: integer, required: true, default: 42, constraints: "fixed; the DataSplit to use" }
      - { name: vote_samples, type: integer, required: true, default: 1 }
      - { name: calculator, type: boolean, required: true, default: false }
    constraints:
      - "config_hash = sha256 of the canonical JSON of {model, method} plus every other field whose value differs from its default, keys sorted, without run_id and v (C2 as changed 2026-10-31)"
      - the training dials of C2 are not used by an evaluation; they are absent from the hash input while they hold their defaults
    relationships: []

  - name: RunRow
    description: One line of the run log (contract C1).
    attributes:
      - { name: date, type: timestamp, required: true }
      - { name: run_id, type: string, required: true, unique: true }
      - { name: model, type: enum, required: true }
      - { name: method, type: enum, required: true }
      - { name: data, type: enum, required: true, allowed: [gsm8k-dev, gsm8k-test] }
      - { name: metric, type: enum, required: true, allowed: [accuracy] }
      - { name: value, type: decimal, required: true, min: 0, max: 1, constraints: "4 decimals" }
      - { name: minutes, type: decimal, required: true, min: 0, constraints: "1 decimal" }
      - { name: config_hash, type: string, required: true }
      - { name: adapter_run, type: string, required: false, default: "", constraints: "the adapter's run id when an adapter was evaluated; empty for a base model" }
    relationships:
      - { to: RunConfig, cardinality: "each row names one config by hash", direction: "RunRow -> RunConfig" }
      - { to: RunRow, cardinality: "an adapter row points at the row of the run that trained the adapter", direction: "RunRow -> RunRow (adapter_run)" }

  - name: Prediction
    description: One scored problem of an evaluation (C2 predictions.jsonl).
    attributes:
      - { name: problem_id, type: string, required: true }
      - { name: output, type: text, required: true, constraints: "the generated text up to the stop point" }
      - { name: predicted, type: decimal, required: false, constraints: "null when no number was found" }
      - { name: gold, type: decimal, required: true }
      - { name: correct, type: boolean, required: true }
    relationships:
      - { to: Problem, cardinality: "each prediction scores one problem", direction: "Prediction -> Problem" }

  - name: RunFolder
    description: Everything one run leaves under outputs/<run_id>/ (C2).
    attributes:
      - { name: run_id, type: string, required: true, unique: true }
      - { name: config, type: RunConfig, required: true }
      - { name: predictions, type: list<Prediction>, required: false }
      - { name: status, type: enum, required: true, allowed: [finished, failed, stopped] }
      - { name: exit_code, type: integer, required: true, allowed: [0, 1, 2, 3, 130] }
      - { name: reason, type: text, required: false }
      - { name: seconds_per_problem, type: decimal, required: false }
      - { name: peak_gpu_memory_gb, type: decimal, required: false }
    relationships:
      - { to: RunRow, cardinality: "a finished run folder has at most one row", direction: "RunFolder -> RunRow" }

  - name: RunLock
    description: The single GPU lock on outputs/run.lock (C3 as changed 2026-10-31).
    attributes:
      - { name: run_id, type: string, required: false }
      - { name: pid, type: integer, required: false }
      - { name: started_at, type: timestamp, required: false }
      - { name: started_by, type: enum, required: false, allowed: [terminal, worker] }
    constraints:
      - at most one process holds the OS lock at any moment
      - the content is display only; holding the OS lock, not the content, decides who owns the GPU
    relationships: []
```

## Summary

| Entity | Owned by (component) | Persisted as | Notes |
|---|---|---|---|
| Problem | DatasetsAndPrompts | Hugging Face cache under `.cache/` | Ids from dataset row order |
| DataSplit | DatasetsAndPrompts | `outputs/splits/gsm8k-split<split_seed>.json` | Rebuilt from the fixed split seed if missing |
| FewShotPrompt | DatasetsAndPrompts | not stored; rebuilt from the split | Calculator notes stripped (Q2) |
| RunConfig | RunConfiguration | `outputs/<run_id>/config.json` | Its hash is in every row |
| RunRow | RunRecords | `results/runs.csv` or a temporary file | One per finished run |
| Prediction | RunRecords | `outputs/<run_id>/predictions.jsonl` | One per scored problem |
| RunFolder | RunRecords | `outputs/<run_id>/` | Status, timings, peak memory |
| RunLock | RunRecords | `outputs/run.lock` plus an OS lock | `flock` held for the run's life (Q1) |
