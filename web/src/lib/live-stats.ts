/**
 * The numbers of the training page's live panels (AC4.5.7, AC4.5.8, AC4.5.10): pure functions from
 * metrics lines (C2) or a GPU reading (C6) to the label, value and plain-language meaning of each
 * number. A number nobody has yet reads "—", and it keeps its meaning. No React here.
 */
import type { Gpu, MetricsLine } from "@/lib/api";
import { formatClock, formatDuration, formatPct } from "@/lib/format";

export const DASH = "—";
const MINUS = "−";
const SEPARATOR = " · ";

/** Step lines the speed is measured over. */
const SPEED_WINDOW = 11;
/** Losses the running average covers. */
const AVERAGE_WINDOW = 10;
/** Step lines the Recent steps table shows. */
export const RECENT_STEPS = 10;

/** One number of a panel: `key` is the stable id the markup carries as `data-stat`. */
export interface Stat {
  key: string;
  label: string;
  value: string;
  meaning: string;
}

type Field =
  | "loss"
  | "learning_rate"
  | "grad_norm"
  | "epoch"
  | "dev_accuracy"
  | "reward"
  | "kl"
  | "answer_length";

function finite(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

/** The finite values of one field, oldest first. */
function column(lines: readonly MetricsLine[], field: Field): number[] {
  const values: number[] = [];
  for (const line of lines) {
    const value = line[field];
    if (finite(value)) values.push(value);
  }
  return values;
}

function min(values: readonly number[]): number {
  return values.reduce((a, b) => Math.min(a, b));
}

function max(values: readonly number[]): number {
  return values.reduce((a, b) => Math.max(a, b));
}

function average(values: readonly number[]): number {
  return values.reduce((total, value) => total + value, 0) / values.length;
}

/** A line of a logging step; a dev-accuracy line carries no step figures (AC2.2.6). */
export function isStepLine(line: MetricsLine): boolean {
  return !finite(line.dev_accuracy);
}

/** The newest `count` step lines, newest first. */
export function recentStepLines(
  lines: readonly MetricsLine[],
  count = RECENT_STEPS,
): MetricsLine[] {
  return lines.filter(isStepLine).slice(-count).reverse();
}

/** 0.4213 -> "0.421", 0.5 -> "0.5", 0 -> "0"; null -> "—". */
export function fmt3(value: number | null | undefined): string {
  return finite(value) ? String(Number(value.toPrecision(3))) : DASH;
}

/** Two significant digits: 0.4213 -> "0.42", 1.34 -> "1.3"; null -> "—". */
export function fmt2(value: number | null | undefined): string {
  return finite(value) ? String(Number(value.toPrecision(2))) : DASH;
}

/** The learning-rate format of the curves panel: 0.00017 -> "1.7e-4", 0.0002 -> "2e-4". */
export function formatRate(value: number | null | undefined): string {
  return finite(value) ? value.toExponential(1).replace(".0e", "e") : DASH;
}

/** 309 -> "0:05:09", 3725 -> "1:02:05"; null -> "—". */
export function formatElapsed(seconds: number | null | undefined): string {
  if (!finite(seconds)) return DASH;
  const whole = Math.max(0, Math.round(seconds));
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  return `${hours}:${String(minutes).padStart(2, "0")}:${String(whole % 60).padStart(2, "0")}`;
}

function progress(line: MetricsLine | undefined): string {
  if (!line || !finite(line.step) || !finite(line.total_steps) || line.total_steps <= 0) {
    return DASH;
  }
  const percent = ((line.step / line.total_steps) * 100).toFixed(1);
  return `${line.step} / ${line.total_steps} (${percent}%)`;
}

/** Seconds per step and steps per minute over the last step lines; "—" when they cannot say. */
function speed(lines: readonly MetricsLine[]): string {
  const recent = lines.filter(isStepLine).slice(-SPEED_WINDOW);
  const first = recent.at(0);
  const last = recent.at(-1);
  if (recent.length < 2 || !first || !last) return DASH;
  const secondsPerStep = (last.elapsed_s - first.elapsed_s) / (last.step - first.step);
  // A step difference of 0 divides to Infinity or NaN; a clock that did not move gives 0.
  if (!Number.isFinite(secondsPerStep) || secondsPerStep <= 0) return DASH;
  return `${secondsPerStep.toFixed(2)} s/step${SEPARATOR}${(60 / secondsPerStep).toFixed(1)} steps/min`;
}

function formatChange(percent: number): string {
  const rounded = Math.round(Math.abs(percent) * 10) / 10;
  if (rounded === 0) return "±0.0%";
  return `${percent > 0 ? "+" : MINUS}${rounded.toFixed(1)}%`;
}

/** The learning rate and, from the newest two rates, whether it is warming up, decaying or steady. */
function learningRate(rates: readonly number[]): string {
  const newest = rates.at(-1);
  if (newest === undefined) return DASH;
  const before = rates.at(-2);
  if (before === undefined) return formatRate(newest);
  const phase = newest > before ? "warming up" : newest < before ? "decaying" : "steady";
  return `${formatRate(newest)}${SEPARATOR}${phase}`;
}

function finishClock(eta: number | null | undefined, asOf: Date | null): string {
  if (!asOf || !finite(eta) || eta <= 0) return DASH;
  return formatClock(new Date(asOf.getTime() + eta * 1000));
}

/**
 * The Live numbers of a run (AC4.5.7). `asOf` is when the newest line arrived, so the clock time
 * the run should end can be worked out; null for a past run, whose finish time is meaningless.
 */
export function liveStats(lines: readonly MetricsLine[], asOf: Date | null): Stat[] {
  const newest = lines.at(-1);
  const eta = newest?.eta_s;
  const losses = column(lines, "loss");
  const firstLoss = losses.at(0);
  const newestLoss = losses.at(-1);
  const gradNorms = column(lines, "grad_norm");
  const devs = column(lines, "dev_accuracy");
  const newestEpoch = column(lines, "epoch").at(-1);

  const stats: Stat[] = [
    {
      key: "progress",
      label: "Progress",
      value: progress(newest),
      meaning: "How far through its training steps the run is.",
    },
    {
      key: "epoch",
      label: "Epoch",
      value: newestEpoch === undefined ? DASH : newestEpoch.toFixed(2),
      meaning: "How many times the model has read the whole training set; 0.50 is halfway through.",
    },
    {
      key: "speed",
      label: "Speed",
      value: speed(lines),
      meaning: "How fast training goes, measured over the last 10 steps.",
    },
    {
      key: "elapsed",
      label: "Elapsed",
      value: formatElapsed(newest?.elapsed_s),
      meaning: "How long the run has been going (hours:minutes:seconds).",
    },
    {
      key: "remaining",
      label: "Remaining",
      value: !finite(eta) ? DASH : eta <= 0 ? "Done" : formatDuration(eta),
      meaning: "A guess at the time left, from the current speed.",
    },
    {
      key: "finish",
      label: "Should end at",
      value: finishClock(eta, asOf),
      meaning: "The clock time the run should be done, if the speed stays the same.",
    },
    {
      key: "loss",
      label: "Loss",
      value: fmt3(newestLoss),
      meaning: "How wrong the model's next-word guesses are; it should fall.",
    },
    {
      key: "lowest-loss",
      label: "Lowest loss",
      value: losses.length > 0 ? fmt3(min(losses)) : DASH,
      meaning: "The best (smallest) loss seen so far in this run.",
    },
    {
      key: "average-loss",
      label: "Average of last 10 steps",
      value: losses.length > 0 ? fmt3(average(losses.slice(-AVERAGE_WINDOW))) : DASH,
      meaning: "The loss averaged over the last 10 steps, which smooths out the noise.",
    },
    {
      key: "loss-change",
      label: "Change since first step",
      value:
        losses.length >= 2 && firstLoss !== undefined && firstLoss !== 0 && newestLoss !== undefined
          ? formatChange(((newestLoss - firstLoss) / firstLoss) * 100)
          : DASH,
      meaning: "How far the loss has moved since the first step; a minus sign means it improved.",
    },
    {
      key: "learning-rate",
      label: "Learning rate",
      value: learningRate(column(lines, "learning_rate")),
      meaning: "How big a step the model takes when it learns; it warms up, then decays.",
    },
    {
      key: "grad-norm",
      label: "Gradient norm",
      value:
        gradNorms.length > 0 ? `${fmt2(gradNorms.at(-1))} (highest ${fmt2(max(gradNorms))})` : DASH,
      meaning: "How big the correction signal is; a sudden spike means an unstable step.",
    },
    {
      key: "dev-accuracy",
      label: "Dev accuracy",
      value: devs.length > 0 ? `${formatPct(devs.at(-1))} (best ${formatPct(max(devs))})` : DASH,
      meaning: "The share of held-out practice problems the model answers right; higher is better.",
    },
  ];

  // Reinforcement-learning runs also write these; a supervised run's lines never do.
  const extras: { key: string; label: string; field: Field; meaning: string }[] = [
    {
      key: "reward",
      label: "Reward",
      field: "reward",
      meaning:
        "The average score the model's answers earn while it learns by trial; it should rise.",
    },
    {
      key: "kl",
      label: "KL",
      field: "kl",
      meaning: "How far the model has drifted from where it started; large means it changes a lot.",
    },
    {
      key: "answer-length",
      label: "Answer length",
      field: "answer_length",
      meaning: "The average length of the model's answers, in tokens (word pieces).",
    },
  ];
  for (const extra of extras) {
    const latest = column(lines, extra.field).at(-1);
    if (latest === undefined) continue;
    stats.push({
      key: extra.key,
      label: extra.label,
      value: extra.field === "answer_length" ? String(Math.round(latest)) : fmt3(latest),
      meaning: extra.meaning,
    });
  }
  return stats;
}

/** MiB -> "5.9" (GiB, one decimal); null -> "—". */
function gib(mebibytes: number | null): string {
  return finite(mebibytes) ? (mebibytes / 1024).toFixed(1) : DASH;
}

function whole(value: number | null): string {
  return finite(value) ? String(Math.round(value)) : DASH;
}

/** "used / total unit"; both unknown reads a single "—", one unknown keeps its half as "—". */
function pair(
  used: number | null,
  total: number | null,
  unit: string,
  format: (value: number | null) => string,
): string {
  if (!finite(used) && !finite(total)) return DASH;
  return `${format(used)} / ${format(total)} ${unit}`;
}

/** The GPU panel's numbers (AC4.5.10) for a reading that says it is available. */
export function gpuStats(gpu: Gpu): Stat[] {
  return [
    {
      key: "utilization",
      label: "Utilisation",
      value: finite(gpu.utilization_pct) ? `${Math.round(gpu.utilization_pct)}%` : DASH,
      meaning: "How busy the graphics card is; during training it should stay high.",
    },
    {
      key: "memory",
      label: "Memory",
      value: pair(gpu.memory_used_mb, gpu.memory_total_mb, "GB", gib),
      meaning: "Video memory in use out of the total; if it runs out, the run stops.",
    },
    {
      key: "temperature",
      label: "Temperature",
      value: finite(gpu.temperature_c) ? `${Math.round(gpu.temperature_c)} °C` : DASH,
      meaning: "How hot the card is; it slows itself down when it gets too hot.",
    },
    {
      key: "power",
      label: "Power",
      value: pair(gpu.power_w, gpu.power_limit_w, "W", whole),
      meaning: "The electric power the card is drawing, out of the most it is allowed.",
    },
    {
      key: "clock",
      label: "Clock",
      value: pair(gpu.sm_clock_mhz, gpu.sm_clock_max_mhz, "MHz", whole),
      meaning: "How fast the card's compute cores run now, out of their top speed.",
    },
  ];
}
