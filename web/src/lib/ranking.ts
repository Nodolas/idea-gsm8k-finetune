import type { Run } from "@/lib/api";

/** The scores page filters; null (or "") means every model or method. */
export interface RankFilter {
  model: string | null;
  method: string | null;
}

export interface Ranking {
  /** Each model's baseline (its latest `base` dev run), shown first under any filter. */
  baselines: Run[];
  /** Every other scored run that matches the filters, by dev accuracy (ties to the earlier date). */
  ranked: Run[];
}

/** A run is scored when it has a dev accuracy (batch-4 Settled details, Scores). */
export function isScored(run: Run): boolean {
  return typeof run.dev_accuracy === "number" && Number.isFinite(run.dev_accuracy);
}

function time(iso: string | null): number {
  if (!iso) return Number.NaN;
  return Date.parse(iso);
}

/** Earlier first; runs without a readable date go last. */
function byDate(a: Run, b: Run): number {
  const ta = time(a.date);
  const tb = time(b.date);
  if (Number.isNaN(ta) && Number.isNaN(tb)) return 0;
  if (Number.isNaN(ta)) return 1;
  if (Number.isNaN(tb)) return -1;
  return ta - tb;
}

/** Higher dev accuracy first; a tie goes to the earlier run (US2.5's tie rule). */
export function byDevAccuracy(a: Run, b: Run): number {
  const diff = (b.dev_accuracy ?? 0) - (a.dev_accuracy ?? 0);
  if (diff !== 0) return diff;
  return byDate(a, b);
}

function isBaselineCandidate(run: Run): boolean {
  return (
    run.method === "base" &&
    run.model !== null &&
    isScored(run) &&
    (run.data === null || run.data === "gsm8k-dev")
  );
}

/** Each model's latest `base` dev run, keyed by model. */
export function baselinesByModel(runs: Run[]): Map<string, Run> {
  const found = new Map<string, Run>();
  for (const run of runs) {
    if (!isBaselineCandidate(run) || run.model === null) continue;
    const known = found.get(run.model);
    if (!known || byDate(known, run) <= 0) found.set(run.model, run);
  }
  return found;
}

const active = (value: string | null): value is string => value !== null && value !== "";

/**
 * Ranks the scored runs for the scores page (AC4.3.1, AC4.3.3). A model filter keeps only that
 * model's baseline; a method filter keeps every baseline.
 */
export function rankRuns(runs: Run[], filter: RankFilter): Ranking {
  const scored = runs.filter(isScored);
  const baselineMap = baselinesByModel(scored);
  const baselineIds = new Set([...baselineMap.values()].map((run) => run.run_id));

  const baselines = [...baselineMap.values()]
    .filter((run) => !active(filter.model) || run.model === filter.model)
    .sort(byDevAccuracy);

  const ranked = scored
    .filter((run) => !baselineIds.has(run.run_id))
    .filter((run) => !active(filter.model) || run.model === filter.model)
    .filter((run) => !active(filter.method) || run.method === filter.method)
    .sort(byDevAccuracy);

  return { baselines, ranked };
}
