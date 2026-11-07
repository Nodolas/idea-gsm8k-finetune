import { Skeleton } from "@/components/ui/skeleton";
import type { ApiError, Run } from "@/lib/api";
import { formatGain, formatPct, modelName } from "@/lib/format";

export interface BestSoFarProps {
  /** The run list; null while it loads. */
  runs: Run[] | null;
  /** Why the run list could not be read, if it could not. */
  error?: ApiError | null;
}

/** Highest dev accuracy first; a tie goes to the earlier run (US2.5), runs without a date last. */
function byDevThenDate(a: Run, b: Run): number {
  const dev = (b.dev_accuracy ?? 0) - (a.dev_accuracy ?? 0);
  if (dev !== 0) return dev;
  const at = a.date ? Date.parse(a.date) : Number.POSITIVE_INFINITY;
  const bt = b.date ? Date.parse(b.date) : Number.POSITIVE_INFINITY;
  if (at === bt) return 0;
  return at < bt ? -1 : 1;
}

/** The best run by dev accuracy among `runs`, or null. */
export function bestRun(runs: Run[]): Run | null {
  const sorted = [...runs].sort(byDevThenDate);
  return sorted[0] ?? null;
}

/** "plus 9.4 points" for a screen reader, beside the visible signed gain. */
function spokenGain(gain: number): string {
  const points = (Math.round(Math.abs(gain) * 1000) / 10).toFixed(1);
  if (Number(points) === 0) return "no change";
  return `${gain > 0 ? "plus" : "minus"} ${points} points`;
}

function Label() {
  return <span className="label-caps mr-4 text-ink-muted">Best so far</span>;
}

/**
 * The landing page's one line (US4.2): the best non-base run by dev accuracy across both
 * models with its gain over its own model's baseline; the best baseline when only baselines are
 * scored; "No runs yet" with no scored run; the file named when the run log cannot be read.
 */
export function BestSoFar({ runs, error = null }: BestSoFarProps) {
  if (error) {
    const reason = error.file ? `Run log could not be read: ${error.file}` : error.message;
    return (
      <p className="text-sm text-danger" data-state="error">
        <Label />
        <span aria-hidden="true">✕ </span>
        {reason}
      </p>
    );
  }

  if (runs === null) {
    return (
      <div className="flex items-center" data-state="loading">
        <Label />
        <Skeleton className="h-4 w-80" aria-label="Loading the best run" />
      </div>
    );
  }

  const scored = runs.filter((r) => r.dev_accuracy !== null && Number.isFinite(r.dev_accuracy));
  const tuned = bestRun(scored.filter((r) => r.method !== "base"));
  const baseline = bestRun(scored.filter((r) => r.method === "base"));

  if (tuned) {
    return (
      <p className="text-ink" data-state="populated" data-run-id={tuned.run_id}>
        <Label />
        <span>{modelName(tuned.model)}</span>
        <span aria-hidden="true"> · </span>
        <span>{(tuned.method ?? "--").toUpperCase()}</span>
        <span aria-hidden="true"> · </span>
        <span>
          dev <span className="num">{formatPct(tuned.dev_accuracy)}</span>
        </span>
        <span aria-hidden="true"> · </span>
        {tuned.gain === null ? (
          <span className="text-ink-muted">no baseline to compare yet</span>
        ) : (
          <span>
            <span className="num" aria-hidden="true">
              {formatGain(tuned.gain)}
            </span>
            <span className="sr-only">{spokenGain(tuned.gain)}</span> vs baseline
          </span>
        )}
      </p>
    );
  }

  if (baseline) {
    return (
      <p className="text-ink" data-state="baselines-only" data-run-id={baseline.run_id}>
        <Label />
        <span>{modelName(baseline.model)}</span>
        <span aria-hidden="true"> · </span>
        <span>baseline</span>
        <span aria-hidden="true"> · </span>
        <span>
          dev <span className="num">{formatPct(baseline.dev_accuracy)}</span>
        </span>
        <span aria-hidden="true"> · </span>
        <span className="text-ink-muted">no tuned run yet</span>
      </p>
    );
  }

  return (
    <p className="text-ink" data-state="empty">
      <Label />
      No runs yet: start with a baseline on the training page
    </p>
  );
}
