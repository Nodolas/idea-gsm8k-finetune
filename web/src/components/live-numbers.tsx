/**
 * The "Live numbers" panel of the training page (AC4.5.7, US4.5): the run's progress, pace, loss,
 * learning rate, gradient norm and dev accuracy, each with a plain-language line on what it means.
 * It is built from the viewed run's metrics lines only, so it updates with every stream line and
 * serves a run opened from Past runs the same way. `StatList` is shared with the GPU panel.
 */
import type { MetricsLine } from "@/lib/api";
import { liveStats, type Stat } from "@/lib/live-stats";

export interface StatListProps {
  stats: readonly Stat[];
}

/** One label, value and meaning per number, as a description list. */
export function StatList({ stats }: StatListProps) {
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
      {stats.map((stat) => (
        <div
          key={stat.key}
          data-stat={stat.key}
          className="flex min-w-0 flex-col gap-0.5 border-t border-hairline pt-2"
        >
          <dt className="label-caps text-ink-muted">{stat.label}</dt>
          <dd data-part="value" className="num text-base font-semibold">
            {stat.value}
          </dd>
          <dd data-part="meaning" className="text-sm text-ink-muted">
            {stat.meaning}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export interface LiveNumbersProps {
  /** The viewed run's lines, oldest first; the panel is only shown with at least one. */
  lines: readonly MetricsLine[];
  /** When the newest line arrived (the stream's last update); null for a past run. */
  asOf: Date | null;
}

export function LiveNumbers({ lines, asOf }: LiveNumbersProps) {
  return (
    <section
      aria-labelledby="live-numbers-heading"
      className="flex min-w-0 flex-col gap-3 rounded-lg border border-hairline bg-panel p-4"
    >
      <h2 id="live-numbers-heading" className="label-caps">
        Live numbers
      </h2>
      <StatList stats={liveStats(lines, asOf)} />
    </section>
  );
}
