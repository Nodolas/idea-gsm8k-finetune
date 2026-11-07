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
  type DialSpec,
  type MetricsLine,
  type QueueEntry,
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

/** A C6 Status; defaults to IDLE with no run. */
export function serviceStatus(partial: Partial<Status> = {}): Status {
  return {
    status: "IDLE",
    run_id: null,
    reason: null,
    log_tail: [],
    started_at: null,
    last_run: null,
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
