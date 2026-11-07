/**
 * The curves panel of the training page (refined mockups, Live curves; interaction-spec
 * CurvesPanel): one curve per tab, Loss, Learning rate and Dev accuracy, plus Reward, KL and
 * Answer length when the run's lines carry them (AC4.5.1). Live, the accent line grows with each
 * stream line (AC4.5.2); for a past run the heading reads "Viewing <run id> (<status>)", takes
 * focus, and "Back to live" returns (AC4.5.5).
 */
import { useEffect, useRef, useState } from "react";

import { MetricChart } from "@/components/metric-chart";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { MetricsLine } from "@/lib/api";
import { formatPct, METRICS, type MetricKey } from "@/lib/format";

const ALWAYS: MetricKey[] = ["loss", "learning_rate", "dev_accuracy"];
const WHEN_PRESENT: MetricKey[] = ["reward", "kl", "answer_length"];

export interface CurvesPanelProps {
  /** The run whose curves are shown; null when there is none. */
  runId: string | null;
  lines: readonly MetricsLine[];
  /** "live": the active or last run of this visit; "past": a run opened from Past runs. */
  mode: "live" | "past";
  /** The past run's status word, e.g. "STOPPED". */
  statusWord?: string | null;
  loading?: boolean;
  error?: string | null;
  /** Shown in live mode when there are no lines. */
  emptyText?: string;
  onBack?: () => void;
}

function valueOf(line: MetricsLine, key: MetricKey): number | null {
  const value = line[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function pointsFor(lines: readonly MetricsLine[], key: MetricKey) {
  const points: { step: number; value: number }[] = [];
  for (const line of lines) {
    const value = valueOf(line, key);
    if (value !== null) points.push({ step: line.step, value });
  }
  return points;
}

function latestOf(lines: readonly MetricsLine[], key: MetricKey): number | null {
  for (let i = lines.length - 1; i >= 0; i -= 1) {
    const value = valueOf(lines[i], key);
    if (value !== null) return value;
  }
  return null;
}

const SHORT: Record<MetricKey, string> = {
  loss: "loss",
  learning_rate: "lr",
  dev_accuracy: "dev",
  reward: "reward",
  kl: "KL",
  answer_length: "length",
};

function formatValue(key: MetricKey, value: number | null): string {
  if (value === null) return "—";
  switch (key) {
    case "learning_rate":
      return value.toExponential(1).replace(".0e", "e");
    case "dev_accuracy":
      return formatPct(value);
    case "answer_length":
      return String(Math.round(value));
    default:
      return String(Number(value.toPrecision(3)));
  }
}

export function CurvesPanel({
  runId,
  lines,
  mode,
  statusWord,
  loading = false,
  error = null,
  emptyText = "No curves yet.",
  onBack,
}: CurvesPanelProps) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const [chosen, setChosen] = useState<MetricKey>("loss");

  const keys = [
    ...ALWAYS,
    ...WHEN_PRESENT.filter((key) => lines.some((line) => valueOf(line, key) !== null)),
  ];
  const tab = keys.includes(chosen) ? chosen : "loss";

  // Opening a past run moves focus to this heading (interaction-spec PastRunsList).
  useEffect(() => {
    if (mode === "past") headingRef.current?.focus();
  }, [mode, runId]);

  const heading =
    mode === "past" && runId
      ? `Viewing ${runId}${statusWord ? ` (${statusWord})` : ""}`
      : "Live curves";

  let body;
  if (loading) {
    body = (
      <div>
        <p className="sr-only">Loading curves</p>
        <Skeleton className="h-[360px] w-full" />
      </div>
    );
  } else if (error) {
    body = <p className="text-danger">{error}</p>;
  } else if (lines.length === 0 || runId === null) {
    body = (
      <p className="text-ink-muted">
        {mode === "past" && runId ? `No curve recorded for ${runId}` : emptyText}
      </p>
    );
  } else {
    const latest = keys
      .map((key) => `${SHORT[key]} ${formatValue(key, latestOf(lines, key))}`)
      .join(" · ");
    body = (
      <Tabs value={tab} onValueChange={(value) => setChosen(value as MetricKey)}>
        <TabsList variant="line" aria-label="Curves">
          {keys.map((key) => (
            <TabsTrigger key={key} value={key}>
              {METRICS[key]}
            </TabsTrigger>
          ))}
        </TabsList>
        {keys.map((key) => (
          <TabsContent key={key} value={key}>
            <MetricChart
              metric={key}
              height={360}
              series={[
                { id: runId, label: runId, points: pointsFor(lines, key), accent: mode === "live" },
              ]}
            />
          </TabsContent>
        ))}
        <p className="num text-sm text-ink-muted">Latest: {latest}</p>
      </Tabs>
    );
  }

  return (
    <section
      aria-labelledby="curves-heading"
      className="flex min-w-0 flex-col gap-3 rounded-lg border border-hairline bg-panel p-4"
    >
      <div className="flex items-center justify-between gap-4">
        <h2
          id="curves-heading"
          ref={headingRef}
          tabIndex={-1}
          className={mode === "past" ? "num text-base font-semibold" : "label-caps"}
        >
          {heading}
        </h2>
        {mode === "past" && onBack ? (
          <Button variant="outline" size="sm" onClick={onBack}>
            Back to live
          </Button>
        ) : null}
      </div>
      {body}
    </section>
  );
}
