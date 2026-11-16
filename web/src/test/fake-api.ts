/**
 * A fake run service for the website tests: every Api method is a Vitest mock with a sensible
 * default (no runs, IDLE, the Training Dials, empty queue and finalists), any of which a test can
 * override, plus a FakeStream that pushes C7 events into the open stream inside `act()`.
 */
import { act } from "@testing-library/react";
import { vi, type Mock } from "vitest";

import {
  ApiError,
  type Api,
  type CheckedRun,
  type ConfirmResult,
  type CourseArchitecture,
  type CourseArchitectures,
  type CourseKind,
  type CourseOverview,
  type CourseRun,
  type CourseStep,
  type CourseStepSummary,
  type DialSpec,
  type Gpu,
  type LabLesson,
  type LabLessonInfo,
  type LabList,
  type LabSummary,
  type MetricsLine,
  type QueueEntry,
  type Reasoning,
  type ReasoningRole,
  type Run,
  type RunRequest,
  type Status,
  type StreamHandlers,
} from "@/lib/api";

export const Q06 = "Qwen/Qwen3-0.6B-Base";
export const Q17 = "Qwen/Qwen3-1.7B-Base";

/** The eleven dials of the Training Dials table (stories.md), in table order, as `GET /dials`. */
export const DIALS: DialSpec[] = [
  {
    name: "model",
    label: "Model",
    kind: "select",
    options: [Q06, Q17],
    min: null,
    max: null,
    allow_all: false,
    default: Q06,
    help: "Qwen/Qwen3-0.6B-Base or Qwen/Qwen3-1.7B-Base",
  },
  {
    name: "learning_rate",
    label: "Learning rate",
    kind: "number",
    options: null,
    min: 1e-5,
    max: 5e-4,
    allow_all: false,
    default: 2e-4,
    help: "1e-5 to 5e-4",
  },
  {
    name: "epochs",
    label: "Epochs",
    kind: "integer",
    options: null,
    min: 1,
    max: 3,
    allow_all: false,
    default: 1,
    help: "1 to 3 (whole number)",
  },
  {
    name: "lora_rank",
    label: "LoRA rank",
    kind: "select",
    options: [4, 8, 16, 32, 64],
    min: null,
    max: null,
    allow_all: false,
    default: 16,
    help: "4, 8, 16, 32 or 64",
  },
  {
    name: "lora_alpha",
    label: "LoRA alpha",
    kind: "integer",
    options: null,
    min: 1,
    max: 128,
    allow_all: false,
    default: 32,
    help: "1 to 128 (whole number)",
  },
  {
    name: "max_seq_len",
    label: "Max sequence length",
    kind: "integer",
    options: null,
    min: 256,
    max: 1024,
    allow_all: false,
    default: 512,
    help: "256 to 1024 tokens (whole number)",
  },
  {
    name: "train_examples",
    label: "Training examples",
    kind: "integer",
    options: null,
    min: 50,
    max: 6973,
    allow_all: true,
    default: "all",
    help: "50 to 6973, or all",
  },
  {
    name: "batch_size",
    label: "Batch size",
    kind: "integer",
    options: null,
    min: 1,
    max: 16,
    allow_all: false,
    default: 4,
    help: "1 to 16 (whole number)",
  },
  {
    name: "warmup_ratio",
    label: "Warmup ratio",
    kind: "number",
    options: null,
    min: 0,
    max: 0.2,
    allow_all: false,
    default: 0.03,
    help: "0 to 0.2",
  },
  {
    name: "seed",
    label: "Random seed",
    kind: "integer",
    options: null,
    min: 0,
    max: 2147483647,
    allow_all: false,
    default: 42,
    help: "0 to 2147483647 (whole number)",
  },
  {
    name: "answer_format",
    label: "Answer format",
    kind: "select",
    options: ["step-by-step", "terse"],
    min: null,
    max: null,
    allow_all: false,
    default: "step-by-step",
    help: "step-by-step or terse",
  },
];

/** One empty role of the reasoning comparison (no run). */
export function reasoningRole(
  role: ReasoningRole["role"],
  partial: Partial<ReasoningRole> = {},
): ReasoningRole {
  return {
    role,
    run_id: null,
    accuracy: null,
    correct: null,
    scored: null,
    interval_low: null,
    interval_high: null,
    trained_on: null,
    gain_pts: null,
    noise: null,
    mean_lines: null,
    mean_words: null,
    error: null,
    ...partial,
  };
}

/** A reasoning comparison (`GET /reasoning`); defaults to the empty one (no self-taught run). */
export function reasoning(partial: Partial<Reasoning> = {}): Reasoning {
  return {
    v: 1,
    model: Q17,
    available: false,
    roles: [reasoningRole("base"), reasoningRole("sft"), reasoningRole("selfcot")],
    flips: [],
    generation: null,
    generation_error: null,
    examples: [],
    summary: [],
    ...partial,
  };
}

/** A run-list row; defaults to a finished 0.6B SFT dev run. */
export function run(partial: Partial<Run> = {}): Run {
  return {
    run_id: "q06-sft-dev-1",
    model: Q06,
    method: "sft",
    data: "gsm8k-dev",
    adapter_run: null,
    dev_accuracy: 0.62,
    test_accuracy: null,
    gain: null,
    minutes: 41,
    date: "2026-11-04T20:10:00Z",
    started_at: null,
    status: "finished",
    finalist: false,
    ...partial,
  };
}

/** A C2 metrics line; defaults to step 1 of 100 of a supervised run. */
export function metricsLine(partial: Partial<MetricsLine> = {}): MetricsLine {
  return {
    v: 1,
    step: 1,
    total_steps: 100,
    loss: 1.2,
    learning_rate: 2e-4,
    elapsed_s: 10,
    eta_s: 990,
    ...partial,
  };
}

/** A C6 Gpu; defaults to an RTX 3060 Ti at 97% with 5.9 of 8 GiB used. */
export function gpu(partial: Partial<Gpu> = {}): Gpu {
  return {
    available: true,
    reason: null,
    name: "NVIDIA GeForce RTX 3060 Ti",
    utilization_pct: 97,
    memory_used_mb: 6048,
    memory_total_mb: 8192,
    temperature_c: 59,
    power_w: 161.7,
    power_limit_w: 200,
    sm_clock_mhz: 1920,
    sm_clock_max_mhz: 2100,
    ...partial,
  };
}

/** A C6 Status; defaults to IDLE with no run. */
export function serviceStatus(partial: Partial<Status> = {}): Status {
  return {
    status: "IDLE",
    run_id: null,
    reason: null,
    log_tail: [],
    started_at: null,
    last_run: null,
    evaluation: null,
    ...partial,
  };
}

/** A waiting run (C3 queue entry). */
export function queueEntry(partial: Partial<QueueEntry> = {}): QueueEntry {
  return {
    position: 1,
    attempt_id: "q17-sft-dev-1",
    config: { model: Q17, method: "sft", split: "dev" },
    added_at: "2026-11-04T20:10:00Z",
    kind: "train",
    ...partial,
  };
}

/** A `POST /runs/check` answer; defaults to a 0.6B SFT run that fits the 3-hour cap. */
export function checkedRun(partial: Partial<CheckedRun> = {}): CheckedRun {
  const model = partial.model ?? Q06;
  const method = partial.method ?? "sft";
  const attemptId = partial.attempt_id ?? "q06-sft-dev-1";
  const command = partial.command ?? [
    ".venv/bin/python",
    "-m",
    "gsm8k",
    method === "base" ? "evaluate" : "train",
    "--config",
    `outputs/${attemptId}/config.json`,
    "--run-id",
    attemptId,
  ];
  return {
    check_id: "check-1",
    attempt_id: attemptId,
    model,
    method,
    kind: method === "base" ? "evaluate" : "train",
    changes: [],
    estimate_s: 2460,
    estimate_text: "about 41 minutes",
    over_cap: false,
    command,
    command_text: command.join(" "),
    queue_position: 1,
    needs_second_confirmation: false,
    config: { model, method, split: "dev" },
    ...partial,
  };
}

const ERROR_STATUS: Record<string, number> = {
  invalid_dial: 422,
  queue_full: 409,
  not_finalist: 409,
  no_active_run: 409,
  lab_busy: 409,
  no_lab_run: 409,
  course_busy: 409,
  use_lab: 422,
  nothing_to_run: 422,
  invalid_answers: 422,
  invalid_text: 422,
  progress_unreadable: 500,
  confirmation_required: 409,
  not_found: 404,
  check_expired: 404,
  run_log_unreadable: 500,
  finalists_unreadable: 500,
  internal: 500,
  unreachable: 0,
};

/** An ApiError as the service would send it (HTTP status from the C6 error mapping). */
export function apiError(code: string, message: string, file?: string): ApiError {
  return new ApiError(ERROR_STATUS[code] ?? 500, code, message, file);
}

/** Pushes C7 events into every stream the page has open, each inside `act()`. */
export interface FakeStream {
  metric(line: MetricsLine & { run_id?: string }, n: number): void;
  status(s: Status): void;
  queue(entries: QueueEntry[]): void;
  drop(): void;
  open(): void;
  /** How many times the page opened the stream. */
  readonly openCount: number;
  /** Whether a stream is open now. */
  readonly isOpen: boolean;
}

/** The twelve lab lessons of the Lab Lessons table (stories.md group 11, C8), all `not-run`. */
const LAB_TABLE: Array<[string, string, Array<[string, string, string]>]> = [
  ["l01", "What a fine-tune does", [["baseline", "Baseline", "no change (the starting point)"]]],
  [
    "l02",
    "Learning rate",
    [
      ["lr-1e-5", "Learning rate 1e-5", "learning rate 1e-5"],
      ["lr-1e-4", "Learning rate 1e-4", "learning rate 1e-4"],
      ["lr-1e-3", "Learning rate 1e-3", "learning rate 1e-3"],
      ["lr-1e-2", "Learning rate 1e-2", "learning rate 1e-2"],
    ],
  ],
  [
    "l03",
    "Epochs and overfitting",
    [
      ["few-many", "64 problems, 12 epochs", "training examples 64, epochs 12"],
      ["many-once", "768 problems, 1 epoch", "training examples 768, epochs 1"],
    ],
  ],
  [
    "l04",
    "How much data",
    [
      ["data-200", "200 problems", "training examples 200"],
      ["data-800", "800 problems", "training examples 800"],
      ["data-1600", "1,600 problems", "training examples 1600"],
    ],
  ],
  [
    "l05",
    "LoRA rank",
    [
      ["rank-1", "Rank 1", "LoRA rank 1, LoRA alpha 2"],
      ["rank-8", "Rank 8", "LoRA rank 8, LoRA alpha 16"],
      ["rank-64", "Rank 64", "LoRA rank 64, LoRA alpha 128"],
    ],
  ],
  [
    "l06",
    "LoRA or every weight",
    [
      ["lora", "LoRA adapters", "no change (the starting point)"],
      ["full", "Every weight", "method full, learning rate 1e-4"],
    ],
  ],
  [
    "l07",
    "Batch size",
    [
      ["batch-1", "Batch size 1", "batch size 1"],
      ["batch-8", "Batch size 8", "batch size 8"],
      ["batch-32", "Batch size 32", "batch size 32"],
    ],
  ],
  [
    "l08",
    "What the loss counts",
    [
      ["answer-only", "Answer tokens only", "no change (the starting point)"],
      ["whole-text", "Question and answer", "loss on all"],
    ],
  ],
  [
    "l09",
    "Answer format",
    [
      ["step-by-step", "Step by step", "no change (the starting point)"],
      ["terse", "Final number only", "answer format terse"],
    ],
  ],
  [
    "l10",
    "Warm-up and schedule",
    [
      ["warmup-decay", "Warm-up, then decay", "no change (the starting point)"],
      ["constant", "Constant", "schedule constant, warmup ratio 0"],
      ["hot-start", "Hot start", "learning rate 3e-3, warmup ratio 0"],
    ],
  ],
  [
    "l11",
    "Seed noise",
    [
      ["seed-1", "Seed 1", "seed 1"],
      ["seed-2", "Seed 2", "seed 2"],
      ["seed-3", "Seed 3", "seed 3"],
    ],
  ],
  [
    "l12",
    "Where the time goes",
    [
      ["tokenize-once", "Tokenize once", "no change (the starting point)"],
      ["by-length", "Length-grouped batches", "batching by-length"],
      ["retokenize", "Tokenize every step", "retokenize true"],
    ],
  ],
];

export const LAB_LESSONS: LabLessonInfo[] = LAB_TABLE.map(([id, title, variants], i) => ({
  id,
  number: i + 1,
  title,
  question: `Question of ${title}?`,
  watch: `What to watch in ${title}.`,
  guess_prompt: `What do you expect in ${title}?`,
  guess_options: [`${title} option A`, `${title} option B`, `${title} option C`],
  variants: variants.map(([name, label, changes]) => ({ name, label, changes })),
  why: `Why ${title} behaves this way.`,
  big_run: `For the big runs: the learning rate dial (${title}).`,
  check: `Check question of ${title}?`,
  estimate_minutes: 4 * variants.length,
  state: "not-run",
}));

/** `GET /lab` with every lesson `not-run` and no active lesson, with overrides. */
export function labList(overrides: Partial<LabList> = {}): LabList {
  return {
    model: { name: "EleutherAI/pythia-31m", weights: 30494720, layers: 6, device: "cpu" },
    lessons: LAB_LESSONS.map((lesson) => ({ ...lesson, variants: [...lesson.variants] })),
    active: null,
    ...overrides,
  };
}

/** A C8 summary for a variant, with overrides. */
export function labSummary(overrides: Partial<LabSummary> = {}): LabSummary {
  return {
    v: 1,
    lesson: "l01",
    variant: "baseline",
    label: "Baseline",
    config: { learning_rate: 1e-3, batch_size: 8, method: "lora" },
    trainable_params: 196608,
    total_params: 30691328,
    steps: 100,
    seconds: 180,
    seconds_per_step: 1.5,
    tokenize_seconds: 0.8,
    retokenize_seconds_per_step: null,
    padding_fraction: 0.31,
    peak_memory_mb: 900,
    train_loss_first: 2.9,
    train_loss_last: 1.4,
    dev_loss_before: 2.8,
    dev_loss_after: 1.5,
    dev_loss_best: 1.5,
    dev_loss_best_step: 100,
    accuracy_before: 0,
    accuracy_after: 0.0156,
    format_rate_before: 0,
    format_rate_after: 0.875,
    samples: [
      {
        question: "Tom has 3 apples and buys 2 more. How many?",
        gold: "5",
        before: "Tom Tom Tom",
        after: "3 + 2 = 5\n#### 5",
      },
    ],
    ...overrides,
  };
}

/** `GET /lab/{lesson}` for a lesson that has never run (no lines, no summaries), with overrides. */
export function labLesson(lessonId = "l01", overrides: Partial<LabLesson> = {}): LabLesson {
  const lesson = LAB_LESSONS.find((l) => l.id === lessonId) ?? LAB_LESSONS[0];
  return {
    lesson: { ...lesson },
    status: {
      state: "not-run",
      variant: null,
      done: [],
      started_at: null,
      ended_at: null,
      message: null,
    },
    results: lesson.variants.map((variant) => ({
      name: variant.name,
      label: variant.label,
      lines: [],
      summary: null,
    })),
    ...overrides,
  };
}

/** The five course parts (stories.md group 12, Course Steps). */
export const COURSE_PARTS: string[] = [
  "1. Scoring a base model",
  "2. Model designs",
  "3. How fine-tuning works (lab, CPU)",
  "4. Fine-tuning approaches",
  "5. The training pipeline",
];

/** The 24 steps of the Course Steps table: id, part number, title, kind, gpu runs or lab lesson. */
const COURSE_TABLE: Array<[string, number, string, CourseKind, string[] | string | null]> = [
  ["c01", 1, "How a base model is scored", "gpu", ["base-06"]],
  ["c02", 2, "Tokens and the prompt", "inspect", null],
  ["c03", 2, "Inside a decoder-only transformer", "inspect", null],
  ["c04", 2, "Five designs side by side", "inspect", null],
  ["c05", 2, "Same test, five designs", "gpu", ["pythia", "smollm2", "qwen25", "qwen3-17"]],
  ["c06", 2, "Why Qwen3-1.7B, and why not the others", "read", null],
  ["c07", 3, "What a fine-tune does", "lab", "l01"],
  ["c08", 3, "Learning rate", "lab", "l02"],
  ["c09", 3, "Epochs and overfitting", "lab", "l03"],
  ["c10", 3, "How much data", "lab", "l04"],
  ["c11", 3, "LoRA rank", "lab", "l05"],
  ["c12", 3, "LoRA or every weight", "lab", "l06"],
  ["c13", 3, "Batch size", "lab", "l07"],
  ["c14", 3, "What the loss counts", "lab", "l08"],
  ["c15", 3, "Answer format", "lab", "l09"],
  ["c16", 3, "Warm-up and schedule", "lab", "l10"],
  ["c17", 3, "Seed noise", "lab", "l11"],
  ["c18", 3, "Where the time goes", "lab", "l12"],
  ["c19", 4, "Memory budget: prompting, full, LoRA, QLoRA", "read", null],
  ["c20", 4, "LoRA or QLoRA on the GPU", "gpu", ["lora", "qlora"]],
  ["c21", 5, "Supervised fine-tune", "gpu", ["sft"]],
  ["c22", 5, "Self-taught reasoning", "gpu", ["cotgen", "selfcot"]],
  ["c23", 5, "Reinforcement learning with GRPO", "gpu", ["grpo"]],
  ["c24", 5, "What moved the score, and noise", "read", null],
];

/** Every course step summary, all `not-started`. */
export const COURSE_STEPS: CourseStepSummary[] = COURSE_TABLE.map(([id, part, title, kind], i) => ({
  id,
  number: i + 1,
  part,
  title,
  kind,
  state: "not-started",
  run_done: kind === "read",
  quiz_passed: false,
}));

/**
 * `GET /course` built from step summaries (defaults: every step `not-started`). Pass `steps` to
 * change states; parts, done counts, progress and next step are worked out from them.
 */
export function courseOverview(
  options: {
    steps?: Partial<CourseStepSummary>[];
    first_try_right?: number;
    questions_answered?: number;
  } = {},
): CourseOverview {
  const steps = COURSE_STEPS.map((step, i) => ({ ...step, ...(options.steps?.[i] ?? {}) }));
  const done = steps.filter((step) => step.state === "done").length;
  return {
    v: 1,
    parts: COURSE_PARTS.map((title, i) => {
      const inPart = steps.filter((step) => step.part === i + 1);
      return {
        number: i + 1,
        title,
        done: inPart.filter((step) => step.state === "done").length,
        total: inPart.length,
        steps: inPart,
      };
    }),
    progress: {
      done,
      total: 24,
      percent: Math.floor((done * 100) / 24),
      first_try_right: options.first_try_right ?? 0,
      questions_answered: options.questions_answered ?? 0,
    },
    next_step: steps.find((step) => step.state !== "done")?.id ?? null,
  };
}

const COURSE_RUN_MODELS: Record<string, string> = {
  pythia: "EleutherAI/pythia-31m",
  smollm2: "HuggingFaceTB/SmolLM2-360M",
  qwen25: "Qwen/Qwen2.5-0.5B",
  "qwen3-17": Q17,
};

/** A C9 course run that has not run, with overrides. */
export function courseRun(partial: Partial<CourseRun> = {}): CourseRun {
  const run = partial.run ?? "base-06";
  return {
    run,
    command: "evaluate",
    model: COURSE_RUN_MODELS[run] ?? Q06,
    changes: "method base",
    estimate_minutes: 3,
    estimate_measured: false,
    attempt_id: null,
    state: "not-run",
    accuracy: null,
    interval_low: null,
    interval_high: null,
    minutes: null,
    value: null,
    metric: null,
    ...partial,
  };
}

/** One architectures.json model entry, with overrides (figures shaped like Qwen3-0.6B-Base). */
export function courseArchitecture(partial: Partial<CourseArchitecture> = {}): CourseArchitecture {
  return {
    id: Q06,
    revision: "c1899de289a04d12100db370d81485cdf75e47ca",
    licence: "Apache-2.0",
    family: "qwen3",
    layers: 28,
    width: 1024,
    heads: 16,
    kv_heads: 8,
    attention: "grouped-query",
    head_size: 128,
    mlp_width: 3072,
    mlp_matrices: 3,
    vocab: 151936,
    context: 32768,
    tied_embeddings: true,
    position_encoding: "rotary",
    activation: "silu",
    weights_total: 596049920,
    weights_by_part: {
      embeddings: 155582464,
      attention: 176160768,
      mlp: 264241152,
      norms: 65536,
      head: 0,
    },
    bf16_gb: 1.19,
    int4_gb: 0.3,
    problem_tokens: 48,
    prompt_tokens: 702,
    first_tokens: ["Jan", "et", "’s", " ducks", " lay", " ", "1", "6"],
    ...partial,
  };
}

/** architectures.json with the five Course Models (only id and family differ), with overrides. */
export function courseArchitectures(
  partial: Partial<CourseArchitectures> = {},
): CourseArchitectures {
  const models: Array<[string, string]> = [
    ["EleutherAI/pythia-31m", "gpt_neox"],
    ["HuggingFaceTB/SmolLM2-360M", "llama"],
    ["Qwen/Qwen2.5-0.5B", "qwen2"],
    [Q06, "qwen3"],
    [Q17, "qwen3"],
  ];
  return {
    v: 1,
    generated_at: "2026-11-16T20:00:00Z",
    sample_problem_id: "dev-0004",
    models: models.map(([id, family]) => courseArchitecture({ id, family })),
    ...partial,
  };
}

/**
 * `GET /course/{step}` for a step nobody has opened (no answers, no runs started), with
 * overrides; gpu steps list their runs, lab steps their lesson, c19 an all-null memory table and
 * c24 an empty comparison.
 */
export function courseStep(stepId = "c01", overrides: Partial<CourseStep> = {}): CourseStep {
  const index = COURSE_TABLE.findIndex(([id]) => id === stepId);
  const [, part, title, kind, extra] = COURSE_TABLE[index < 0 ? 0 : index];
  const summary = COURSE_STEPS[index < 0 ? 0 : index];
  const lessonNumber = typeof extra === "string" ? Number(extra.slice(1)) : 0;
  return {
    v: 1,
    step: { ...summary },
    part_title: COURSE_PARTS[part - 1],
    why: `Why ${title} comes now.`,
    body: `What ${title} is about.\n\nA second paragraph.`,
    questions: [
      {
        prompt: `First question of ${title}?`,
        options: ["Option one", "Option two", "Option three"],
        answered: false,
        right: null,
        explanation: null,
      },
      {
        prompt: `Second question of ${title}?`,
        options: ["Choice A", "Choice B", "Choice C", "Choice D"],
        answered: false,
        right: null,
        explanation: null,
      },
    ],
    own_words_prompt: `In your own words: what did ${title} show?`,
    own_words: null,
    model_answer: null,
    runs: Array.isArray(extra) ? extra.map((run) => courseRun({ run })) : [],
    architectures: null,
    lesson:
      kind === "lab" && typeof extra === "string"
        ? {
            id: extra,
            number: lessonNumber,
            title: LAB_LESSONS[lessonNumber - 1]?.title ?? title,
            question: LAB_LESSONS[lessonNumber - 1]?.question ?? `Question of ${title}?`,
            state: "not-run",
          }
        : null,
    memory:
      stepId === "c19"
        ? courseArchitectures().models.map((model) => ({
            model: model.id,
            full_gb: null,
            lora_gb: null,
            qlora_gb: null,
            full_fits: null,
            lora_fits: null,
            qlora_fits: null,
          }))
        : null,
    comparison: stepId === "c24" ? [] : null,
    notice: null,
    ...overrides,
  };
}

export type FakeApi = { [K in keyof Api]: Mock<Api[K]> } & { stream: FakeStream };

function createStream(): { stream: FakeStream; openStream: Api["openStream"] } {
  const subscribers = new Set<StreamHandlers>();
  let opened = 0;
  const each = (fn: (h: StreamHandlers) => void) => {
    act(() => {
      for (const handlers of [...subscribers]) fn(handlers);
    });
  };
  const stream: FakeStream = {
    metric: (line, n) =>
      each((h) => h.onMetric?.({ ...line, run_id: line.run_id ?? "q06-sft-dev-1" }, n)),
    status: (s) => each((h) => h.onStatus?.(s)),
    queue: (entries) => each((h) => h.onQueue?.(entries)),
    drop: () => each((h) => h.onDrop?.()),
    open: () => each((h) => h.onOpen?.()),
    get openCount() {
      return opened;
    },
    get isOpen() {
      return subscribers.size > 0;
    },
  };
  const openStream = (handlers: StreamHandlers) => {
    opened += 1;
    subscribers.add(handlers);
    return () => {
      subscribers.delete(handlers);
    };
  };
  return { stream, openStream };
}

/**
 * A fake Api. Defaults: no runs, IDLE, DIALS, empty queue and finalists; marking finalists and
 * removing queued runs change what the next read returns. `overrides` replace any method (a plain
 * function is wrapped in `vi.fn`, so every method has `.mock`).
 */
export function fakeApi(overrides: Partial<Api> = {}): FakeApi {
  let finalists: string[] = [];
  let queue: QueueEntry[] = [];
  const { stream, openStream } = createStream();

  const defaults: Api = {
    listRuns: async () => ({ runs: [], skipped_rows: 0 }),
    getRun: async (id) => ({ run_id: id, config: {}, status: {}, timings: {} }),
    getMetrics: async () => ({ lines: [], next: 0 }),
    getStatus: async () => serviceStatus(),
    getDials: async () => DIALS.map((dial) => ({ ...dial })),
    getGpu: async () =>
      gpu({
        available: false,
        reason: "No NVIDIA GPU in the tests",
        name: null,
        utilization_pct: null,
        memory_used_mb: null,
        memory_total_mb: null,
        temperature_c: null,
        power_w: null,
        power_limit_w: null,
        sm_clock_mhz: null,
        sm_clock_max_mhz: null,
      }),
    getReasoning: async (model?: string) => reasoning({ model: model ?? Q17 }),
    getLab: async () => labList(),
    getLabLesson: async (lessonId: string) => labLesson(lessonId),
    runLabLesson: async (lessonId: string) => ({ lesson: lessonId, state: "running" as const }),
    stopLab: async () => ({ lesson: "l01" }),
    getCourse: async () => courseOverview(),
    getCourseStep: async (stepId: string) => courseStep(stepId),
    runCourseStep: async (stepId: string) => ({ step: stepId, attempt_ids: [] }),
    submitCourseQuiz: async (_stepId: string, answers: number[]) => ({
      results: answers.map((answer) => ({
        right: answer === 0,
        right_option: 0,
        explanation: "Because.",
      })),
      passed: answers.every((answer) => answer === 0),
      attempts: 1,
    }),
    saveCourseOwnWords: async () => ({
      saved_at: "2026-11-16T20:00:00Z",
      model_answer: "One way to say it.",
    }),
    openCourseStep: async () => ({ opened_at: "2026-11-16T20:00:00Z" }),
    checkRun: async (req: RunRequest) =>
      checkedRun({
        model: req.model ?? Q06,
        method: req.method ?? "base",
        config: { ...req },
      }),
    confirmRun: async (): Promise<ConfirmResult> => ({
      attempt_id: "q06-sft-dev-1",
      state: "started",
      position: null,
    }),
    getQueue: async () => queue.map((entry) => ({ ...entry })),
    removeQueued: async (id) => {
      queue = queue
        .filter((entry) => entry.attempt_id !== id)
        .map((entry, i) => ({ ...entry, position: i + 1 }));
    },
    stop: async () => serviceStatus({ status: "STOPPED", reason: "Stopped by request" }),
    getFinalists: async () => [...finalists],
    markFinalist: async (id) => {
      if (!finalists.includes(id)) finalists = [...finalists, id];
      return [...finalists];
    },
    unmarkFinalist: async (id) => {
      finalists = finalists.filter((f) => f !== id);
      return [...finalists];
    },
    openStream,
  };

  const api = { stream } as FakeApi;
  for (const name of Object.keys(defaults) as Array<keyof Api>) {
    const chosen = overrides[name] ?? defaults[name];
    const mock = vi.isMockFunction(chosen) ? chosen : vi.fn(chosen);
    (api as Record<keyof Api, unknown>)[name] = mock;
  }
  return api;
}

/** Fills the default queue a fake api serves (for tests that remove queued runs). */
export function withQueue(api: FakeApi, entries: QueueEntry[]): FakeApi {
  let queue = entries.map((entry, i) => ({ ...entry, position: i + 1 }));
  api.getQueue.mockImplementation(async () => queue.map((entry) => ({ ...entry })));
  api.removeQueued.mockImplementation(async (id: string) => {
    queue = queue
      .filter((entry) => entry.attempt_id !== id)
      .map((entry, i) => ({ ...entry, position: i + 1 }));
  });
  return api;
}
