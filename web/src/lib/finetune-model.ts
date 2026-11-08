/**
 * What the fine-tuning view (US4.7) works out from a run: the weights of the two Qwen3 models and
 * of the LoRA adapters on them, the sizes of one adapted matrix, the step lines of a run and the
 * figures at one of them. Pure functions; the numbers follow `src/gsm8k/training/sft.py`, which
 * puts a LoRA adapter on the q, k, v, o, gate, up and down projections of every decoder layer.
 */
import type { MetricsLine } from "@/lib/api";
import { modelName } from "@/lib/format";

/** The shape of a decoder-only model, as far as the adapters care. */
export interface ModelShape {
  layers: number;
  hidden: number;
  intermediate: number;
  /** Width of the query projection and the input of the output projection (heads x head size). */
  attention: number;
  /** Width of the key and value projections (key-value heads x head size). */
  keyValue: number;
  /** Every weight of the model before an adapter is added (peft's "all params" minus trainable). */
  weights: number;
}

// Read from the pinned models' config.json; the weight counts match peft's
// `print_trainable_parameters` lines in the run logs (10,092,544 and 17,432,576 trainable).
const SHAPES: Record<string, ModelShape> = {
  "Qwen3-0.6B-Base": {
    layers: 28,
    hidden: 1024,
    intermediate: 3072,
    attention: 2048,
    keyValue: 1024,
    weights: 596_049_920,
  },
  "Qwen3-1.7B-Base": {
    layers: 28,
    hidden: 2048,
    intermediate: 6144,
    attention: 2048,
    keyValue: 1024,
    weights: 1_720_574_976,
  },
};

/** The drawing's layer count when the model is not one of the two above. */
export const DEFAULT_LAYERS = 28;

export function shapeOf(model: string | null | undefined): ModelShape | null {
  if (!model) return null;
  return SHAPES[modelName(model)] ?? null;
}

export type ViewKind = "finetune" | "reading";

const FINETUNE_METHODS = new Set(["sft", "terse", "optuna", "selfcot", "grpo"]);
// Answer generation and the evaluations (vote and calc score an adapter that is already trained).
const READING_METHODS = new Set(["cotgen", "base", "best", "vote", "calc"]);

/** Whether a run's method changes the model's weights; null when the method is not known yet. */
export function kindOf(method: string | null | undefined): ViewKind | null {
  if (!method) return null;
  if (FINETUNE_METHODS.has(method)) return "finetune";
  if (READING_METHODS.has(method)) return "reading";
  return null;
}

/** (input, output) widths of the seven matrices that get an adapter in one layer. */
function adaptedMatrices(shape: ModelShape): Array<[number, number]> {
  return [
    [shape.hidden, shape.attention], // q_proj
    [shape.hidden, shape.keyValue], // k_proj
    [shape.hidden, shape.keyValue], // v_proj
    [shape.attention, shape.hidden], // o_proj
    [shape.hidden, shape.intermediate], // gate_proj
    [shape.hidden, shape.intermediate], // up_proj
    [shape.intermediate, shape.hidden], // down_proj
  ];
}

export interface LoraCounts {
  trained: number;
  frozen: number;
  /** Frozen plus trained, as peft prints "all params". */
  total: number;
  /** Trained weights as a share of all of them, in percent. */
  percent: number;
}

export function loraCounts(shape: ModelShape, rank: number): LoraCounts {
  const perLayer = adaptedMatrices(shape).reduce((sum, [i, o]) => sum + rank * (i + o), 0);
  const trained = perLayer * shape.layers;
  const total = shape.weights + trained;
  return { trained, frozen: shape.weights, total, percent: (trained / total) * 100 };
}

export interface QueryProjection {
  inWidth: number;
  outWidth: number;
  /** Weights of the frozen matrix. */
  frozen: number;
  /** Weights of A (rank x in) plus B (out x rank). */
  adapter: number;
}

export function queryProjection(shape: ModelShape, rank: number): QueryProjection {
  const inWidth = shape.hidden;
  const outWidth = shape.attention;
  return {
    inWidth,
    outWidth,
    frozen: inWidth * outWidth,
    adapter: rank * (inWidth + outWidth),
  };
}

/** 17432576 -> "17,432,576". */
export function formatCount(value: number): string {
  return String(Math.round(value)).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/** The lines of a run that are training steps: a line with a loss (dev accuracy lines have none). */
export function stepLines(lines: readonly MetricsLine[]): MetricsLine[] {
  return lines.filter((line) => typeof line.loss === "number" && Number.isFinite(line.loss));
}

function finite(value: number | null | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export interface StepFigures {
  step: number;
  totalSteps: number;
  loss: number;
  /**
   * The typical chance the model gave the right next word: e to the power of minus the loss, which
   * is the geometric mean of the per-word chances over the scored answer words.
   */
  chance: number;
  /** Change of the loss since the first step line; null on the first one. */
  change: { percent: number; sinceStep: number } | null;
  gradNorm: number | null;
  learningRate: number | null;
  /** Step times batch size; null without a batch size. */
  examplesSeen: number | null;
}

/** The figures at `steps[index]` (step lines only), or null when there is no such line. */
export function figuresAt(
  steps: readonly MetricsLine[],
  index: number,
  batchSize: number | null,
): StepFigures | null {
  const line = steps[index];
  if (!line || line.loss === null) return null;
  const first = steps[0];
  const firstLoss = first.loss;
  const change =
    index > 0 && firstLoss !== null && firstLoss !== 0
      ? { percent: ((line.loss - firstLoss) / firstLoss) * 100, sinceStep: first.step }
      : null;
  return {
    step: line.step,
    totalSteps: line.total_steps,
    loss: line.loss,
    chance: Math.exp(-line.loss),
    change,
    gradNorm: finite(line.grad_norm),
    learningRate: finite(line.learning_rate),
    examplesSeen: batchSize === null ? null : line.step * batchSize,
  };
}

/** 0.94 -> "0.94", 1.8 -> "1.8". */
export function formatLoss(value: number): string {
  return String(Number(value.toPrecision(3)));
}

/** 0.4213 -> "0.42"; null -> "—". */
export function formatGrad(value: number | null): string {
  return value === null ? "—" : String(Number(value.toPrecision(2)));
}

/** 1.8e-4 -> "1.8e-4", 2e-4 -> "2e-4" (the curves panel's format); null -> "—". */
export function formatRate(value: number | null): string {
  return value === null ? "—" : value.toExponential(1).replace(".0e", "e");
}

/** "47.8% lower than at step 40", "the same as at step 40", or "first logged step". */
export function describeChange(change: StepFigures["change"]): string {
  if (change === null) return "first logged step";
  const size = Math.abs(change.percent).toFixed(1);
  if (size === "0.0") return `the same as at step ${change.sinceStep}`;
  return `${size}% ${change.percent < 0 ? "lower" : "higher"} than at step ${change.sinceStep}`;
}

/** 39.06 -> "39%" for a chance of 0.3906. */
export function formatChance(chance: number): string {
  return `${Math.round(chance * 100)}%`;
}
