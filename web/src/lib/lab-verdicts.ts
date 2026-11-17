import type { LabSummary, LabVariantResult } from "@/lib/api";

/** A last dev loss more than this above the best one counts as overfitting (AC11.4.6). */
export const OVERFIT_MARGIN = 0.05;

/** A loss to three decimals, or a dash when the run did not produce one. */
export function loss3(value: number | null | undefined): string {
  return value === null || value === undefined ? "–" : value.toFixed(3);
}

/** A fraction as a whole percent. */
export function pct0(value: number | null | undefined): string {
  return value === null || value === undefined ? "–" : `${Math.round(value * 100)}%`;
}

export interface Ended {
  name: string;
  label: string;
  summary: LabSummary;
}

/** The variants that have a summary, in lesson order. */
export function endedVariants(results: LabVariantResult[]): Ended[] {
  const ended: Ended[] = [];
  for (const r of results) {
    if (r.summary) ended.push({ name: r.name, label: r.label, summary: r.summary });
  }
  return ended;
}

/** Last dev loss more than 0.05 above the best one. */
export function overfitted(s: LabSummary): boolean {
  if (s.dev_loss_after === null || s.dev_loss_best === null) return false;
  return s.dev_loss_after - s.dev_loss_best > OVERFIT_MARGIN;
}

/** Last training loss above the first, or missing (not a finite number). */
export function diverged(s: LabSummary): boolean {
  if (s.train_loss_last === null) return true;
  return s.train_loss_first !== null && s.train_loss_last > s.train_loss_first;
}

/** The variant with the lowest dev loss after training, or null when none has one. */
export function lowestDevLoss(ended: Ended[]): Ended | null {
  let best: Ended | null = null;
  for (const e of ended) {
    const v = e.summary.dev_loss_after;
    if (v === null) continue;
    if (best === null || v < (best.summary.dev_loss_after ?? Infinity)) best = e;
  }
  return best;
}

/** Variants ordered for the answers select: best first (dev loss, or accuracy for l09). */
export function orderVariants(lessonId: string, ended: Ended[]): Ended[] {
  const sorted = [...ended];
  if (lessonId === "l09") {
    return sorted.sort((a, b) => b.summary.accuracy_after - a.summary.accuracy_after);
  }
  return sorted.sort(
    (a, b) => (a.summary.dev_loss_after ?? Infinity) - (b.summary.dev_loss_after ?? Infinity),
  );
}

function seconds2(value: number): string {
  return value.toFixed(2);
}

function formatVerdict(ended: Ended[]): string[] {
  const best = [...ended].sort((a, b) => b.summary.accuracy_after - a.summary.accuracy_after)[0];
  if (ended.length < 2) return [];
  const others = ended.filter((e) => e !== best);
  const against = others.map((o) => `${pct0(o.summary.accuracy_after)} for ${o.label}`).join(", ");
  return [
    `${best.label} has the higher accuracy after training: ${pct0(best.summary.accuracy_after)} against ${against}.`,
    `Share of answers in the right format after training: ${ended
      .map((e) => `${e.label} ${pct0(e.summary.format_rate_after)}`)
      .join("; ")}.`,
    "Their dev losses are not compared: they are measured over different answer texts.",
  ];
}

function seedVerdict(ended: Ended[]): string[] {
  const lasts = ended.map((e) => e.summary.dev_loss_after).filter((v): v is number => v !== null);
  if (lasts.length < 2) return [];
  const max = Math.max(...lasts);
  const min = Math.min(...lasts);
  return [
    `The last dev loss spans ${loss3(max - min)} across the seeds (${loss3(min)} to ${loss3(max)}). A difference this small between two runs is noise, not an effect.`,
  ];
}

function timeVerdict(ended: Ended[]): string[] {
  const out: string[] = [];
  const once = ended.find((e) => e.name === "tokenize-once") ?? ended[0];
  const every = ended.find((e) => e.name === "retokenize");
  const grouped = ended.find((e) => e.name === "by-length");
  if (once)
    out.push(
      `Tokenizing every problem once took ${seconds2(once.summary.tokenize_seconds)} seconds.`,
    );
  const perStep = every?.summary.retokenize_seconds_per_step ?? null;
  if (every && perStep !== null && every.summary.seconds_per_step > 0) {
    out.push(
      `Tokenizing again at every step added ${seconds2(perStep)} seconds per step, ${Math.round(
        (perStep / every.summary.seconds_per_step) * 100,
      )}% of that variant's ${seconds2(every.summary.seconds_per_step)} second step.`,
    );
  }
  if (once && grouped) {
    out.push(
      `Padding wasted ${pct0(once.summary.padding_fraction)} of the tokens with random batches and ${pct0(
        grouped.summary.padding_fraction,
      )} with length-grouped batches.`,
    );
  }
  return out;
}

/** The "What happened" sentences for a lesson, worked out from its summaries (AC11.4.6). */
export function verdicts(lessonId: string, results: LabVariantResult[]): string[] {
  const ended = endedVariants(results);
  if (ended.length === 0) return [];
  const out: string[] = [];
  if (lessonId === "l09") {
    out.push(...formatVerdict(ended));
  } else if (lessonId !== "l12") {
    const low = lowestDevLoss(ended);
    if (low) {
      out.push(
        `${low.label} has the lowest dev loss after training: ${loss3(low.summary.dev_loss_after)}.`,
      );
    }
  }
  for (const e of ended) {
    const s = e.summary;
    if (overfitted(s)) {
      out.push(
        `${e.label} overfitted: its dev loss was best at step ${s.dev_loss_best_step ?? 0} (${loss3(
          s.dev_loss_best,
        )}) and ended higher at ${loss3(s.dev_loss_after)}.`,
      );
    }
  }
  for (const e of ended) {
    const s = e.summary;
    if (!diverged(s)) continue;
    out.push(
      s.train_loss_last === null
        ? `${e.label} diverged: its training loss stopped being a number.`
        : `${e.label} diverged: its training loss ended at ${loss3(s.train_loss_last)}, above the ${loss3(
            s.train_loss_first,
          )} it started at.`,
    );
  }
  if (lessonId === "l11") out.push(...seedVerdict(ended));
  else if (lessonId === "l12") out.push(...timeVerdict(ended));
  else if (lessonId !== "l09" && ended.length > 1) {
    out.push(
      "Differences of a few hundredths in dev loss between variants are noise; Lesson 11 measures how large the spread between seeds is.",
    );
  }
  return out;
}
