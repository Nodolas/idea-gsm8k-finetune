/**
 * What the step walkthrough of the training page (US4.8) works out: which walkthrough a run gets,
 * its phases and their order, the built-in sample problem as word-piece tokens, the targets of the
 * shift-by-one, and the newest measured figures of a run. Pure data and functions.
 *
 * The training phases follow `src/gsm8k/training/sft.py`: the training set is tokenized once
 * (`tokenize_examples`, prompt tokens masked from the loss, end-of-text appended), each batch is
 * right-padded to its longest example (`PadCollator`), and only the LoRA matrices are trained.
 * The answer phases follow `src/gsm8k/evaluation.py` (greedy) and answer generation (sampling at
 * `cot_temperature`).
 */
import type { MetricsLine } from "@/lib/api";
import { stepLines } from "@/lib/finetune-model";

/** One phase of the clock: 1.8 seconds (AC4.8.4). */
export const PHASE_MS = 1800;

/** Answer generation samples at this temperature when the run's config names none (run_config). */
export const DEFAULT_COT_TEMPERATURE = 0.7;

/** The token a training target ends with, so the model learns to stop. */
export const EOS_TOKEN = "<|endoftext|>";

export interface WalkthroughSample {
  /** The question in the training frame (`Question: ...` newline `Answer:`), as word pieces. */
  prompt: readonly string[];
  /** The worked answer ending with its `#### <number>` line, as word pieces. */
  answer: readonly string[];
  /** The gold answer the final number is checked against. */
  gold: string;
}

/**
 * A short GSM8K-style problem, split by hand into word pieces the way a byte-pair tokenizer splits
 * text: a word carries its leading space, and every digit is a token of its own. An illustration.
 */
export const WALKTHROUGH_SAMPLE: WalkthroughSample = {
  prompt: [
    "Question",
    ":",
    " Tom",
    " has",
    " ",
    "5",
    " pens",
    " and",
    " buys",
    " ",
    "3",
    " more",
    ".",
    " How",
    " many",
    " pens",
    " does",
    " he",
    " have",
    "?\n",
    "Answer",
    ":",
  ],
  answer: [
    " He",
    " has",
    " ",
    "5",
    " +",
    " ",
    "3",
    " =",
    " ",
    "8",
    " pens",
    ".\n",
    "####",
    " ",
    "8",
  ],
  gold: "8",
};

/** A token as a chip shows it: a leading space as a dot, a newline as a return arrow. */
export function displayToken(token: string): string {
  return token.replace(/\n/g, "↵").replace(/^ /, "·");
}

export type WalkthroughKind = "training" | "generation";

const TRAINING_METHODS = new Set(["sft", "terse", "optuna", "selfcot"]);
const GENERATION_METHODS = new Set(["cotgen", "base", "best"]);

/** The walkthrough a run's method gets; null when it has none (AC4.8.7). */
export function walkthroughKind(method: string | null | undefined): WalkthroughKind | null {
  if (!method) return null;
  if (TRAINING_METHODS.has(method)) return "training";
  if (GENERATION_METHODS.has(method)) return "generation";
  return null;
}

/** Whether the answer walkthrough samples (answer generation) instead of taking the top token. */
export function samples(method: string | null | undefined): boolean {
  return method === "cotgen";
}

export interface PhaseInfo {
  key: string;
  name: string;
  /** One plain-language line. */
  meaning: string;
}

export const TRAINING_PHASES: readonly PhaseInfo[] = [
  {
    key: "tokenize",
    name: "Tokenize",
    meaning: "Text became token ids once, before training started.",
  },
  {
    key: "batch",
    name: "Batch",
    meaning: "A few tokenized examples are padded into one rectangle.",
  },
  {
    key: "embed",
    name: "Embed",
    meaning: "Each token id picks its vector from the embedding table.",
  },
  {
    key: "forward",
    name: "Forward",
    meaning: "The vectors pass through every layer: frozen weights plus LoRA.",
  },
  {
    key: "predict",
    name: "Predict",
    meaning: "At every answer token the model scores each possible next token.",
  },
  {
    key: "loss",
    name: "Loss",
    meaning: "One number: how little chance the right next tokens got.",
  },
  {
    key: "backward",
    name: "Backward",
    meaning: "The gradient flows back from the loss to the LoRA weights.",
  },
  {
    key: "update",
    name: "Update",
    meaning: "AdamW nudges only LoRA A and B, by the learning rate.",
  },
];

const GENERATION_BASE: readonly PhaseInfo[] = [
  {
    key: "tokenize",
    name: "Tokenize",
    meaning: "The prompt becomes token ids once, before writing starts.",
  },
  {
    key: "forward",
    name: "Forward",
    meaning: "The prompt and the tokens written so far pass through the layers.",
  },
  {
    key: "choose",
    name: "Choose",
    meaning: "One next token is picked from the model's scores.",
  },
  {
    key: "append",
    name: "Append",
    meaning: "The picked token joins the answer: one token at a time.",
  },
  {
    key: "stop",
    name: "Stop",
    meaning: "Writing ends once the answer's #### line is complete.",
  },
];

const CHECK_PHASE: PhaseInfo = {
  key: "check",
  name: "Check",
  meaning: "The answer is kept only when its final number is right.",
};

/** The answer walkthrough's phases; answer generation adds Check (AC4.8.5). */
export function generationPhases(method: string | null | undefined): readonly PhaseInfo[] {
  return samples(method) ? [...GENERATION_BASE, CHECK_PHASE] : GENERATION_BASE;
}

export function phasesOf(kind: WalkthroughKind, method: string | null | undefined) {
  return kind === "training" ? TRAINING_PHASES : generationPhases(method);
}

/** One position of the clock: the phase shown and the answer tokens written so far. */
export interface WalkStep {
  key: string;
  written: number;
}

/**
 * The positions the clock walks through, in order, before it starts again at the first.
 * Training: the eight phases. Answer: Tokenize, then Forward, Choose and Append once per answer
 * token (Append writes it), then Stop (and Check for answer generation).
 */
export function walkSteps(
  kind: WalkthroughKind,
  method: string | null | undefined,
  answerLength: number = WALKTHROUGH_SAMPLE.answer.length,
): WalkStep[] {
  if (kind === "training") return TRAINING_PHASES.map((p) => ({ key: p.key, written: 0 }));
  const steps: WalkStep[] = [{ key: "tokenize", written: 0 }];
  for (let i = 0; i < answerLength; i += 1) {
    steps.push({ key: "forward", written: i });
    steps.push({ key: "choose", written: i });
    steps.push({ key: "append", written: i + 1 });
  }
  steps.push({ key: "stop", written: answerLength });
  if (samples(method)) steps.push({ key: "check", written: answerLength });
  return steps;
}

/** Every answer token with the token it must predict: the text shifted by one, then end-of-text. */
export function predictPairs(
  answer: readonly string[] = WALKTHROUGH_SAMPLE.answer,
): Array<{ input: string; target: string }> {
  return answer.map((input, i) => ({ input, target: answer[i + 1] ?? EOS_TOKEN }));
}

function finite(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export interface NewestFigures {
  step: number;
  totalSteps: number;
  loss: number;
  gradNorm: number | null;
  learningRate: number | null;
}

/** The newest step line's figures (a line with a loss); null before the first one. */
export function newestFigures(lines: readonly MetricsLine[]): NewestFigures | null {
  const steps = stepLines(lines);
  const line = steps[steps.length - 1];
  if (!line || line.loss === null) return null;
  return {
    step: line.step,
    totalSteps: line.total_steps,
    loss: line.loss,
    gradNorm: finite(line.grad_norm),
    learningRate: finite(line.learning_rate),
  };
}

/** The temperature answer generation samples at: the config's, else 0.7. */
export function temperatureOf(value: unknown): number {
  return finite(value) ?? DEFAULT_COT_TEMPERATURE;
}

/** 0.7 -> "0.7", 0.95 -> "0.95". */
export function formatTemperature(value: number): string {
  return String(Number(value.toPrecision(3)));
}
