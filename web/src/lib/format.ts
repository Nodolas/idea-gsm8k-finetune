/** Display formats shared by every page (numbers in words, never colour alone; NFR9). */

const MINUS = "−";

/** 0.681 -> "68.1%"; null -> "--". */
export function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "--";
  return `${(value * 100).toFixed(1)}%`;
}

/** 0.094 -> "+9.4 pts"; -0.02 -> "−2.0 pts" (U+2212); 0 -> "±0.0 pts"; null -> "—". */
export function formatGain(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  const points = Math.round(Math.abs(value) * 1000) / 10;
  if (points === 0) return "±0.0 pts"; // AC4.3.2: every gain carries a sign
  return `${value > 0 ? "+" : MINUS}${points.toFixed(1)} pts`;
}

/** 52.4 -> "52"; null -> "--". */
export function formatMinutes(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "--";
  return String(Math.round(value));
}

const pad = (n: number) => String(n).padStart(2, "0");

/** ISO time -> "2026-11-04 20:10" in local time (tests run with TZ=UTC); null or bad -> "--". */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "--";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "--";
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
    `${pad(date.getHours())}:${pad(date.getMinutes())}`
  );
}

/** ISO time -> "20:10:05" in local time; null or bad -> "--". */
export function formatClock(iso: string | Date | null | undefined): string {
  if (!iso) return "--";
  const date = iso instanceof Date ? iso : new Date(iso);
  if (Number.isNaN(date.getTime())) return "--";
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

/** Seconds -> "~41 min" under an hour, "3 h 40 min" (or "3 h") above; null -> "No estimate yet". */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) {
    return "No estimate yet";
  }
  const minutes = Math.max(1, Math.round(seconds / 60));
  if (minutes < 60) return `~${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0 ? `${hours} h` : `${hours} h ${rest} min`;
}

/** "Qwen/Qwen3-1.7B-Base" -> "1.7B"; null -> "--". */
export function shortModel(model: string | null | undefined): string {
  if (!model) return "--";
  const match = /(\d+(?:\.\d+)?B)\b/.exec(model);
  return match ? match[1] : model;
}

/** "Qwen/Qwen3-1.7B-Base" -> "Qwen3-1.7B-Base"; null -> "--". */
export function modelName(model: string | null | undefined): string {
  if (!model) return "--";
  const slash = model.lastIndexOf("/");
  return slash >= 0 ? model.slice(slash + 1) : model;
}

export type MetricKey =
  "loss" | "learning_rate" | "dev_accuracy" | "reward" | "kl" | "answer_length";

/** Curve labels, in display order (supervised first, then the reinforcement-learning extras). */
export const METRICS: Record<MetricKey, string> = {
  loss: "Loss",
  learning_rate: "Learning rate",
  dev_accuracy: "Dev accuracy",
  reward: "Reward",
  kl: "KL",
  answer_length: "Answer length",
};
