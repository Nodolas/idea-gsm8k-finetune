import type { DialSpec } from "@/lib/api";

/** Labels of the Training Dials table (stories.md) and the other run fields the pages name. */
const LABELS: Record<string, string> = {
  model: "Model",
  learning_rate: "Learning rate",
  epochs: "Epochs",
  lora_rank: "LoRA rank",
  lora_alpha: "LoRA alpha",
  max_seq_len: "Max sequence length",
  train_examples: "Training examples",
  batch_size: "Batch size",
  warmup_ratio: "Warmup ratio",
  seed: "Random seed",
  answer_format: "Answer format",
  method: "Method",
  split: "Split",
  adapter_path: "Adapter",
  limit: "Problem limit",
  vote_samples: "Vote samples",
  calculator: "Calculator",
  max_new_tokens: "Max new tokens",
  evaluator: "Evaluator",
  grpo_steps: "GRPO steps",
  grpo_generations: "GRPO generations",
};

/** The human label of a dial or run field: "lora_rank" -> "LoRA rank". */
export function labelFor(name: string): string {
  const known = LABELS[name];
  if (known) return known;
  const words = name.replace(/_/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** A bound as people write it: 0.00001 -> "1e-5", 0.2 -> "0.2". */
export function formatBound(value: number): string {
  if (value !== 0 && Math.abs(value) < 0.001) {
    return value.toExponential().replace("e+", "e").replace(/\.0+e/, "e");
  }
  return String(value);
}

export type DialCheck = { ok: true; value: string | number } | { ok: false; message: string };

const WHOLE = /^[+-]?\d+$/;

/** Checks one typed dial value against its spec (run on blur; the service checks again). */
export function checkDial(spec: DialSpec, raw: string): DialCheck {
  const text = raw.trim();
  const label = spec.label || labelFor(spec.name);

  if (spec.kind === "select") {
    const options = spec.options ?? [];
    const found = options.find((option) => String(option) === text);
    if (found !== undefined) return { ok: true, value: found };
    return { ok: false, message: `${label} must be one of ${options.map(String).join(", ")}` };
  }

  if (spec.allow_all && text.toLowerCase() === "all") return { ok: true, value: "all" };

  const range =
    spec.min !== null && spec.max !== null
      ? `${label} must be between ${formatBound(spec.min)} and ${formatBound(spec.max)}`
      : `${label} must be a number`;

  if (spec.kind === "integer" && !WHOLE.test(text)) {
    return { ok: false, message: `${label} must be a whole number` };
  }
  if (text === "") return { ok: false, message: range };
  const value = Number(text);
  if (!Number.isFinite(value)) return { ok: false, message: range };
  if ((spec.min !== null && value < spec.min) || (spec.max !== null && value > spec.max)) {
    return { ok: false, message: range };
  }
  return { ok: true, value };
}
