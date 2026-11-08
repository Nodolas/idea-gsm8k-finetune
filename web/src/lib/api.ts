/**
 * The website's only door to data: the run service's HTTP API (contract C6, `/api/v1`) and its live
 * event stream (contract C7). Pages and components reach it through `useApi()` (ADR-008), never
 * through `fetch` or `EventSource` directly. Field names follow what `src/gsm8k/service/app.py`
 * returns.
 */

export type RunStatusWord = "finished" | "failed" | "stopped" | "running" | "queued";

/** One run of the run list (C6 Run; the run log joined with the run folders). */
export interface Run {
  run_id: string;
  model: string | null;
  method: string | null;
  /** The data of the run's last row (C1), e.g. `gsm8k-dev`. */
  data: string | null;
  /** For an evaluation of an adapter: the run id whose adapter it scored. */
  adapter_run: string | null;
  dev_accuracy: number | null;
  /** The run's own test row, else the joined one (C6, changed 2026-11-07). */
  test_accuracy: number | null;
  /** Dev accuracy minus the dev accuracy of the model's baseline; null for the baseline itself. */
  gain: number | null;
  minutes: number | null;
  date: string | null;
  started_at: string | null;
  status: RunStatusWord | null;
  finalist: boolean;
}

export interface RunList {
  runs: Run[];
  /** Run log rows that could not be read and were left out. */
  skipped_rows: number;
}

/** C2 config.json. Every field is optional here: an old or partial folder may lack some. */
export interface RunConfig {
  v?: number;
  run_id?: string;
  model?: string;
  method?: string;
  split?: string;
  adapter_path?: string | null;
  learning_rate?: number;
  epochs?: number;
  lora_rank?: number;
  lora_alpha?: number;
  max_seq_len?: number;
  train_examples?: number | "all";
  batch_size?: number;
  warmup_ratio?: number;
  seed?: number;
  split_seed?: number;
  model_revision?: string | null;
  dataset_revision?: string;
  answer_format?: string;
  limit?: number | null;
  vote_samples?: number;
  calculator?: boolean;
  max_new_tokens?: number;
  evaluator?: string;
  grpo_steps?: number | null;
  grpo_generations?: number | null;
  [field: string]: unknown;
}

/** One run's folder files (C6 RunDetail). `status` is status.json, `{status: "running"}` for the
 * active run, or `{}` while nothing has been written. */
export interface RunDetail {
  run_id: string;
  config: RunConfig;
  status: Record<string, unknown>;
  timings: Record<string, unknown>;
}

/** One C2 metrics.jsonl line; stream lines also carry `run_id` (C7). */
export interface MetricsLine {
  v: number;
  step: number;
  total_steps: number;
  loss: number | null;
  learning_rate: number | null;
  elapsed_s: number;
  eta_s: number | null;
  dev_accuracy?: number | null;
  reward?: number | null;
  kl?: number | null;
  answer_length?: number | null;
  /** The trainer's gradient norm; lines written before 2026-11-08 lack it (AC2.2.6). */
  grad_norm?: number | null;
  /** The fractional epoch of the step; lines written before 2026-11-08 lack it (AC2.2.6). */
  epoch?: number | null;
  run_id?: string;
}

/** C6 Gpu: the NVIDIA GPU's live figures from `GET /gpu`; every figure is null when unknown. */
export interface Gpu {
  available: boolean;
  /** Why it is not available; null when available. */
  reason: string | null;
  name: string | null;
  utilization_pct: number | null;
  /** MiB, as nvidia-smi prints it. */
  memory_used_mb: number | null;
  memory_total_mb: number | null;
  temperature_c: number | null;
  power_w: number | null;
  power_limit_w: number | null;
  sm_clock_mhz: number | null;
  sm_clock_max_mhz: number | null;
}

export interface MetricsPage {
  lines: MetricsLine[];
  /** The number of complete lines read; pass it as `after` to read only newer lines. */
  next: number;
}

export type ServiceState = "IDLE" | "RUNNING" | "STOPPED" | "FAILED" | "FINISHED";

/** C6 Status: the active run, or the last one with its reason and log tail. */
export interface Status {
  status: ServiceState;
  run_id: string | null;
  reason: string | null;
  log_tail: string[];
  started_at: string | null;
  last_run: Status | null;
}

/** One dial of the Training Dials table, as `GET /dials` serves it. */
export interface DialSpec {
  name: string;
  label: string;
  kind: "select" | "number" | "integer";
  options: Array<string | number> | null;
  min: number | null;
  max: number | null;
  /** The dial also takes the word `all` (training examples). */
  allow_all: boolean;
  default: string | number;
  /** The allowed range in words, e.g. "1e-5 to 5e-4". */
  help: string;
}

/** C2 config.json fields without `run_id`; omitted dials take their defaults. */
export type RunRequest = Partial<{
  model: string;
  method: string;
  split: string;
  adapter_path: string | null;
  learning_rate: number;
  epochs: number;
  lora_rank: number;
  lora_alpha: number;
  max_seq_len: number;
  train_examples: number | "all";
  batch_size: number;
  warmup_ratio: number;
  seed: number;
  split_seed: number;
  model_revision: string;
  dataset_revision: string;
  answer_format: string;
  limit: number | null;
  vote_samples: number;
  calculator: boolean;
  max_new_tokens: number;
  evaluator: string;
  grpo_steps: number | null;
  grpo_generations: number | null;
}>;

/** The answer of `POST /runs/check`: what would run, launched nothing yet. */
export interface CheckedRun {
  check_id: string;
  attempt_id: string;
  model: string;
  method: string;
  kind: "train" | "evaluate";
  /** One line per dial that differs from the last run: "<dial>: <old> -> <new>". */
  changes: string[];
  estimate_s: number | null;
  estimate_text: string;
  over_cap: boolean;
  command: string[];
  command_text: string;
  /** 1 when the GPU is free; otherwise the place it would take in the queue. */
  queue_position: number;
  needs_second_confirmation: boolean;
  config: RunConfig;
}

export interface ConfirmResult {
  attempt_id: string;
  state: "started" | "queued";
  position: number | null;
}

/** One waiting run (C3 queue entry). */
export interface QueueEntry {
  position: number;
  attempt_id: string;
  config: RunConfig;
  added_at: string;
  kind?: string | null;
}

/** C6 Error codes, plus `unreachable` for a service that does not answer. */
export type ApiErrorCode =
  | "invalid_dial"
  | "queue_full"
  | "not_finalist"
  | "no_active_run"
  | "not_found"
  | "run_log_unreadable"
  | "finalists_unreadable"
  | "check_expired"
  | "confirmation_required"
  | "internal"
  | "lab_busy"
  | "no_lab_run"
  | "unreachable";

export const UNREACHABLE_MESSAGE =
  "The run service is not reachable at 127.0.0.1:8000. Start it with `make serve`.";

/** A refusal or failure of the run service (C6 Error), or `status 0` when it is unreachable. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly file?: string;
  readonly field?: string;

  constructor(status: number, code: string, message: string, file?: string, field?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    if (file !== undefined) this.file = file;
    if (field !== undefined) this.field = field;
  }
}

/** Any thrown value as an ApiError (a non-ApiError becomes `internal`). */
export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  const message = error instanceof Error ? error.message : String(error);
  return new ApiError(0, "internal", message);
}

/** One role of the reasoning comparison (C6 Reasoning, added 2026-11-08). */
export interface ReasoningRole {
  role: "base" | "sft" | "selfcot";
  run_id: string | null;
  accuracy: number | null;
  correct: number | null;
  scored: number | null;
  interval_low: number | null;
  interval_high: number | null;
  trained_on: number | null;
  gain_pts: number | null;
  noise: "within noise" | "outside noise" | null;
  mean_lines: number | null;
  mean_words: number | null;
  error: string | null;
}

/** Problems fixed and broken by a fine-tune against the base run. */
export interface ReasoningFlip {
  role: "sft" | "selfcot";
  run_id: string;
  against: string;
  fixed: number;
  broken: number;
  both_right: number;
  both_wrong: number;
}

/** The generation run's `cot_stats.json` figures plus its run id (C2). */
export interface ReasoningGeneration {
  run_id: string;
  problems: number;
  samples_per_problem: number;
  solved: number;
  kept: number;
  kept_fraction: number;
  mean_lines_kept: number | null;
  mean_words_kept: number | null;
  mean_lines_reference: number | null;
  mean_words_reference: number | null;
}

export interface ReasoningExample {
  problem_id: string;
  gold: string;
  base_output: string;
  selfcot_output: string;
}

/** `GET /reasoning`: self-taught chain of thought against base and the reference fine-tune. */
export interface Reasoning {
  v: number;
  model: string;
  available: boolean;
  roles: ReasoningRole[];
  flips: ReasoningFlip[];
  generation: ReasoningGeneration | null;
  generation_error: string | null;
  examples: ReasoningExample[];
  summary: string[];
}

/** C8: the lab model of `GET /lab`. */
export interface LabModel {
  name: string;
  weights: number;
  layers: number;
  device: "cpu";
}

export interface LabVariant {
  name: string;
  label: string;
  /** In words, e.g. "learning rate 1e-5"; "no change (the starting point)" when empty. */
  changes: string;
}

export type LabState = "not-run" | "running" | "finished" | "failed" | "stopped";

/** C8 `LabLessonInfo`: one lesson as `GET /lab` lists it. */
export interface LabLessonInfo {
  id: string;
  number: number;
  title: string;
  question: string;
  watch: string;
  guess_prompt: string;
  guess_options: string[];
  variants: LabVariant[];
  why: string;
  big_run: string;
  check: string;
  estimate_minutes: number;
  state: LabState;
}

/** `GET /lab`. */
export interface LabList {
  model: LabModel;
  lessons: LabLessonInfo[];
  /** The lesson whose lab run is going, or null. */
  active: string | null;
}

export interface LabStatus {
  state: LabState;
  variant: string | null;
  done: string[];
  started_at: string | null;
  ended_at: string | null;
  message: string | null;
}

/** A C8 metrics line: a step line (loss set, dev_loss null) or a dev line (dev_loss set, loss null). */
export interface LabMetricsLine {
  v: number;
  step: number;
  total_steps: number;
  loss: number | null;
  learning_rate: number | null;
  grad_norm: number | null;
  elapsed_s: number;
  dev_loss: number | null;
}

export interface LabSample {
  question: string;
  gold: string;
  before: string;
  after: string;
}

/** The C8 `summary.json` of a variant that has ended. */
export interface LabSummary {
  v: number;
  lesson: string;
  variant: string;
  label: string;
  config: Record<string, unknown>;
  trainable_params: number;
  total_params: number;
  steps: number;
  seconds: number;
  seconds_per_step: number;
  tokenize_seconds: number;
  retokenize_seconds_per_step: number | null;
  padding_fraction: number;
  peak_memory_mb: number;
  train_loss_first: number | null;
  train_loss_last: number | null;
  dev_loss_before: number | null;
  dev_loss_after: number | null;
  dev_loss_best: number | null;
  dev_loss_best_step: number | null;
  accuracy_before: number;
  accuracy_after: number;
  format_rate_before: number;
  format_rate_after: number;
  samples: LabSample[];
}

export interface LabVariantResult {
  name: string;
  label: string;
  lines: LabMetricsLine[];
  summary: LabSummary | null;
}

/** `GET /lab/{lesson}`. */
export interface LabLesson {
  lesson: LabLessonInfo;
  status: LabStatus;
  results: LabVariantResult[];
}

export interface StreamHandlers {
  onMetric?(line: MetricsLine & { run_id: string }, lineNo: number): void;
  onStatus?(status: Status): void;
  onQueue?(entries: QueueEntry[]): void;
  onOpen?(): void;
  onDrop?(): void;
}

export interface Api {
  listRuns(): Promise<RunList>;
  getRun(id: string): Promise<RunDetail>;
  getMetrics(id: string, after?: number): Promise<MetricsPage>;
  getStatus(): Promise<Status>;
  getDials(): Promise<DialSpec[]>;
  /** The NVIDIA GPU's live figures (AC4.5.9); `available: false` with a reason, never an error. */
  getGpu(): Promise<Gpu>;
  checkRun(req: RunRequest): Promise<CheckedRun>;
  confirmRun(checkId: string, secondConfirmation?: boolean): Promise<ConfirmResult>;
  getQueue(): Promise<QueueEntry[]>;
  removeQueued(id: string): Promise<void>;
  stop(): Promise<Status>;
  getFinalists(): Promise<string[]>;
  /** Resolves to the new finalist list. */
  markFinalist(id: string): Promise<string[]>;
  /** Resolves to the new finalist list. */
  unmarkFinalist(id: string): Promise<string[]>;
  /** The reasoning comparison for one model (default: the service's, Qwen3-1.7B-Base). */
  getReasoning(model?: string): Promise<Reasoning>;
  /** The lab lessons (C8, AC11.3.1). */
  getLab(): Promise<LabList>;
  /** One lesson with its status, metrics lines and summaries (C8, AC11.3.2). */
  getLabLesson(lessonId: string): Promise<LabLesson>;
  /** Starts a lesson on the CPU (C8, AC11.3.3); 409 `lab_busy` while another runs. */
  runLabLesson(lessonId: string): Promise<{ lesson: string; state: "running" }>;
  /** Stops the lab run (C8, AC11.3.4); 409 `no_lab_run` when none is going. */
  stopLab(): Promise<{ lesson: string }>;
  /** Opens the C7 stream; the returned function closes it. */
  openStream(handlers: StreamHandlers): () => void;
}

const EVENT_ID = /^(.+):([0-9]+)$/;
const UNREACHABLE_STATUSES = new Set([500, 502, 503, 504]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

/** The ApiError for a non-2xx answer. A body without a C6 Error from a 5xx is the dev server's
 * proxy failing to reach the service, so it reads as unreachable. */
function errorFrom(response: Response, body: unknown): ApiError {
  if (isRecord(body) && typeof body.error === "string") {
    const message = typeof body.message === "string" ? body.message : body.error;
    const file = typeof body.file === "string" ? body.file : undefined;
    const field = typeof body.field === "string" ? body.field : undefined;
    return new ApiError(response.status, body.error, message, file, field);
  }
  if (UNREACHABLE_STATUSES.has(response.status)) {
    return new ApiError(0, "unreachable", UNREACHABLE_MESSAGE);
  }
  return new ApiError(
    response.status,
    response.status === 404 ? "not_found" : "internal",
    `The run service answered ${response.status} ${response.statusText}`.trim(),
  );
}

/** The real client. `base` is relative, so the Vite dev server proxies it (no CORS, NFR6). */
export function createApi(base = "/api/v1"): Api {
  async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
    let response: Response;
    try {
      response = await fetch(`${base}${path}`, {
        method,
        headers: body === undefined ? undefined : { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new ApiError(0, "unreachable", UNREACHABLE_MESSAGE);
    }
    const data = await readJson(response);
    if (!response.ok) throw errorFrom(response, data);
    return data as T;
  }

  const id = (value: string) => encodeURIComponent(value);

  return {
    listRuns: () => request<RunList>("GET", "/runs"),
    getRun: (runId) => request<RunDetail>("GET", `/runs/${id(runId)}`),
    getMetrics: (runId, after = 0) =>
      request<MetricsPage>("GET", `/runs/${id(runId)}/metrics?after=${after}`),
    getStatus: () => request<Status>("GET", "/status"),
    getGpu: () => request<Gpu>("GET", "/gpu"),
    getDials: async () => (await request<{ dials: DialSpec[] }>("GET", "/dials")).dials,
    getReasoning: (model) =>
      request<Reasoning>(
        "GET",
        model === undefined ? "/reasoning" : `/reasoning?model=${encodeURIComponent(model)}`,
      ),
    getLab: () => request<LabList>("GET", "/lab"),
    getLabLesson: (lessonId) => request<LabLesson>("GET", `/lab/${id(lessonId)}`),
    runLabLesson: (lessonId) =>
      request<{ lesson: string; state: "running" }>("POST", `/lab/${id(lessonId)}/run`),
    stopLab: () => request<{ lesson: string }>("POST", "/lab/stop"),
    checkRun: (req) => request<CheckedRun>("POST", "/runs/check", req),
    confirmRun: (checkId, secondConfirmation = false) =>
      request<ConfirmResult>("POST", "/runs/confirm", {
        check_id: checkId,
        second_confirmation: secondConfirmation,
      }),
    getQueue: async () => (await request<{ entries: QueueEntry[] }>("GET", "/queue")).entries,
    removeQueued: async (attemptId) => {
      await request<null>("DELETE", `/queue/${id(attemptId)}`);
    },
    stop: () => request<Status>("POST", "/stop"),
    getFinalists: async () =>
      (await request<{ finalists: string[] }>("GET", "/finalists")).finalists,
    markFinalist: async (runId) =>
      (await request<{ finalists: string[] }>("PUT", `/finalists/${id(runId)}`)).finalists,
    unmarkFinalist: async (runId) =>
      (await request<{ finalists: string[] }>("DELETE", `/finalists/${id(runId)}`)).finalists,
    openStream: (handlers) => openEventStream(`${base}/stream`, handlers),
  };
}

function parseData(event: MessageEvent): unknown {
  try {
    return JSON.parse(String(event.data)) as unknown;
  } catch {
    return null;
  }
}

function openEventStream(url: string, handlers: StreamHandlers): () => void {
  const source = new EventSource(url);
  source.addEventListener("metric", (event: MessageEvent) => {
    const data = parseData(event);
    const match = EVENT_ID.exec(event.lastEventId);
    if (!isRecord(data) || !match) return;
    const runId = typeof data.run_id === "string" ? data.run_id : match[1];
    handlers.onMetric?.({ ...(data as unknown as MetricsLine), run_id: runId }, Number(match[2]));
  });
  source.addEventListener("status", (event: MessageEvent) => {
    const data = parseData(event);
    if (isRecord(data)) handlers.onStatus?.(data as unknown as Status);
  });
  source.addEventListener("queue", (event: MessageEvent) => {
    const data = parseData(event);
    if (isRecord(data) && Array.isArray(data.entries)) {
      handlers.onQueue?.(data.entries as QueueEntry[]);
    }
  });
  source.addEventListener("open", () => handlers.onOpen?.());
  source.addEventListener("error", () => handlers.onDrop?.());
  return () => source.close();
}
