import { CircleAlertIcon, DiamondIcon, XIcon } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { MetricChart, type MetricSeries } from "@/components/metric-chart";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  toApiError,
  type ApiError,
  type MetricsLine,
  type MetricsPage,
  type Run,
  type RunConfig,
  type RunDetail,
} from "@/lib/api";
import { useApi } from "@/lib/api-context";
import { formatBound, labelFor } from "@/lib/dials";
import { METRICS, formatGain, formatPct, modelName, type MetricKey } from "@/lib/format";
import { useAsync } from "@/lib/queries";

export interface CompareViewProps {
  /** The first picked run: solid line in the accent colour. */
  runA: Run;
  /** The second picked run: dashed line in the text colour. */
  runB: Run;
  onClose?(): void;
}

type Settled<T> = { ok: true; value: T } | { ok: false; error: ApiError };

function settle<T>(promise: Promise<T>): Promise<Settled<T>> {
  return promise.then(
    (value) => ({ ok: true as const, value }),
    (error: unknown) => ({ ok: false as const, error: toApiError(error) }),
  );
}

/** Settings shown first, in the Training Dials order, then the other run fields. */
const SETTING_ORDER = [
  "model",
  "method",
  "split",
  "learning_rate",
  "epochs",
  "lora_rank",
  "lora_alpha",
  "max_seq_len",
  "train_examples",
  "batch_size",
  "warmup_ratio",
  "seed",
  "answer_format",
  "adapter_path",
  "limit",
  "vote_samples",
  "calculator",
  "max_new_tokens",
  "evaluator",
  "grpo_steps",
  "grpo_generations",
];
const HIDDEN_FIELDS = new Set(["v", "run_id"]);

/** A setting as people write it: 0.0002 -> "2e-4", true -> "on", missing -> "--". */
function formatSetting(name: string, value: unknown): string {
  if (value === null || value === undefined || value === "") return "--";
  if (name === "model" && typeof value === "string") return modelName(value);
  if (typeof value === "number") return formatBound(value);
  if (typeof value === "boolean") return value ? "on" : "off";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

function settingNames(a: RunConfig, b: RunConfig): string[] {
  const present = new Set(
    [...Object.keys(a), ...Object.keys(b)].filter((name) => !HIDDEN_FIELDS.has(name)),
  );
  const known = SETTING_ORDER.filter((name) => present.has(name));
  const others = [...present].filter((name) => !SETTING_ORDER.includes(name)).sort();
  return [...known, ...others];
}

const CURVE_ORDER: MetricKey[] = [
  "loss",
  "dev_accuracy",
  "learning_rate",
  "reward",
  "kl",
  "answer_length",
];
/** Tabs shown whenever there is a curve (mockups.md); the RL ones only when recorded. */
const ALWAYS: MetricKey[] = ["loss", "dev_accuracy", "learning_rate"];

function points(lines: MetricsLine[], metric: MetricKey) {
  const out: { step: number; value: number }[] = [];
  for (const line of lines) {
    const value = line[metric];
    if (typeof value === "number" && Number.isFinite(value)) out.push({ step: line.step, value });
  }
  return out;
}

function lastValue(lines: MetricsLine[], metric: MetricKey): string {
  const pts = points(lines, metric);
  if (pts.length === 0) return "none";
  const value = pts[pts.length - 1].value;
  return Number.isInteger(value) ? String(value) : String(Number(value.toPrecision(4)));
}

/** Names a run whose settings could not be read, with the service's reason. */
function SettingsError({ run, detail }: { run: Run; detail: Settled<RunDetail> }) {
  if (detail.ok) return null;
  return (
    <p className="flex items-start gap-2 text-sm text-danger">
      <CircleAlertIcon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      <span>
        Settings of {run.run_id} could not be read: {detail.error.message}
      </span>
    </p>
  );
}

interface SettingsProps {
  runA: Run;
  runB: Run;
  details: [Settled<RunDetail>, Settled<RunDetail>] | null;
}

/** The two runs' settings side by side; a changed dial carries a ◆ and the word "changed". */
function SettingsTable({ runA, runB, details }: SettingsProps) {
  if (details === null) {
    return <p className="text-sm text-muted-foreground">Reading the settings…</p>;
  }
  const [a, b] = details;
  const configA = a.ok ? a.value.config : {};
  const configB = b.ok ? b.value.config : {};
  const names = settingNames(configA, configB);
  const head =
    "px-2 py-1.5 text-left font-mono text-[10.5px] font-normal uppercase tracking-[0.18em] text-muted-foreground";
  return (
    <div className="flex flex-col gap-2">
      <SettingsError run={runA} detail={a} />
      <SettingsError run={runB} detail={b} />
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">Settings of the two runs</caption>
        <thead>
          <tr className="border-b border-hairline">
            <th scope="col" className={head}>
              Dial
            </th>
            <th scope="col" className={head}>
              {runA.run_id}
            </th>
            <th scope="col" className={head}>
              {runB.run_id}
            </th>
            <th scope="col" className={head}>
              <span className="sr-only">Difference</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {names.map((name) => {
            const valueA = formatSetting(name, configA[name]);
            const valueB = formatSetting(name, configB[name]);
            const changed = valueA !== valueB;
            return (
              <tr
                key={name}
                className="border-b border-hairline last:border-0"
                data-changed={changed ? "true" : "false"}
              >
                <th scope="row" className="px-2 py-1.5 text-left font-normal text-muted-foreground">
                  {labelFor(name)}
                </th>
                <td className="px-2 py-1.5 font-mono tabular-nums">{valueA}</td>
                <td className="px-2 py-1.5 font-mono tabular-nums">{valueB}</td>
                <td className="px-2 py-1.5 text-orange">
                  {changed && (
                    <>
                      <DiamondIcon aria-hidden="true" className="inline size-3 fill-current" />
                      <span className="sr-only">changed</span>
                    </>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

interface CurvesProps {
  runA: Run;
  runB: Run;
  pages: [MetricsPage, MetricsPage] | null;
}

/** Both runs' curves overlaid, one tab per metric; a run without lines reads "No curve recorded". */
function Curves({ runA, runB, pages }: CurvesProps) {
  const [metric, setMetric] = useState<MetricKey>("loss");
  if (pages === null) {
    return <p className="text-sm text-muted-foreground">Reading the curves…</p>;
  }
  const runs: Array<{ run: Run; lines: MetricsLine[]; dashed: boolean }> = [
    { run: runA, lines: pages[0].lines, dashed: false },
    { run: runB, lines: pages[1].lines, dashed: true },
  ];
  const withLines = runs.filter((r) => r.lines.length > 0);
  const missing = runs.filter((r) => r.lines.length === 0);
  const metrics = CURVE_ORDER.filter(
    (key) => ALWAYS.includes(key) || withLines.some((r) => points(r.lines, key).length > 0),
  );
  const current = metrics.includes(metric) ? metric : "loss";

  return (
    <div className="flex flex-col gap-3">
      {missing.map(({ run }) => (
        <p key={run.run_id} className="text-sm text-muted-foreground">
          No curve recorded for {run.run_id}
        </p>
      ))}
      {withLines.length > 0 && (
        <Tabs value={current} onValueChange={(value) => setMetric(value as MetricKey)}>
          <TabsList variant="line" aria-label="Curve">
            {metrics.map((key) => (
              <TabsTrigger key={key} value={key}>
                {METRICS[key]}
              </TabsTrigger>
            ))}
          </TabsList>
          {metrics.map((key) => {
            const series: MetricSeries[] = withLines.map(({ run, lines, dashed }) => ({
              id: run.run_id,
              label: run.run_id,
              points: points(lines, key),
              dashed,
              accent: !dashed,
            }));
            return (
              <TabsContent key={key} value={key}>
                <MetricChart metric={key} series={series} />
                <p className="mt-1 font-mono text-xs text-muted-foreground">
                  Latest {METRICS[key].toLowerCase()}:{" "}
                  {withLines
                    .map(
                      ({ run, lines, dashed }) =>
                        `${run.run_id} (${dashed ? "dashed" : "solid"}) ${lastValue(lines, key)}`,
                    )
                    .join(" · ")}
                </p>
              </TabsContent>
            );
          })}
        </Tabs>
      )}
    </div>
  );
}

/**
 * Two picked runs side by side (interaction-spec CompareView, AC4.4.1-AC4.4.3): settings from
 * each run's config.json, the signed dev accuracy difference (first minus second) and both
 * training curves overlaid.
 */
export function CompareView({ runA, runB, onClose }: CompareViewProps) {
  const api = useApi();
  const idA = runA.run_id;
  const idB = runB.run_id;
  const headingId = useId();
  const headingRef = useRef<HTMLHeadingElement>(null);

  const details = useAsync(
    () => Promise.all([settle(api.getRun(idA)), settle(api.getRun(idB))]),
    [api, idA, idB],
  );
  const curves = useAsync(async (): Promise<[MetricsPage, MetricsPage]> => {
    const empty: MetricsPage = { lines: [], next: 0 };
    const [a, b] = await Promise.all([settle(api.getMetrics(idA)), settle(api.getMetrics(idB))]);
    return [a.ok ? a.value : empty, b.ok ? b.value : empty];
  }, [api, idA, idB]);

  useEffect(() => {
    headingRef.current?.focus();
  }, [idA, idB]);

  const difference =
    runA.dev_accuracy !== null && runB.dev_accuracy !== null
      ? runA.dev_accuracy - runB.dev_accuracy
      : null;

  return (
    <section
      aria-labelledby={headingId}
      className="mt-8 flex flex-col gap-4 border-t border-hairline pt-6"
    >
      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2">
        <h2
          id={headingId}
          ref={headingRef}
          tabIndex={-1}
          className="font-mono text-sm outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange"
        >
          <span className="mr-3 text-[10.5px] uppercase tracking-[0.18em] text-muted-foreground">
            Compare
          </span>{" "}
          {idA} <span className="text-muted-foreground">vs</span> {idB}
        </h2>
        <p className="font-mono text-sm tabular-nums">
          <span className="text-muted-foreground">dev </span>
          {formatPct(runA.dev_accuracy)} <span className="text-muted-foreground">vs</span>{" "}
          {formatPct(runB.dev_accuracy)}
          <span className="text-muted-foreground"> · difference </span>
          {formatGain(difference)}
        </p>
        {onClose && (
          <Button variant="ghost" size="sm" className="ml-auto" onClick={onClose}>
            <XIcon aria-hidden="true" />
            Close comparison
          </Button>
        )}
      </div>
      <div className="grid gap-6 lg:grid-cols-[2fr_3fr]">
        <div>
          <h3 className="mb-2 font-mono text-[10.5px] uppercase tracking-[0.18em] text-muted-foreground">
            Settings
          </h3>
          <SettingsTable
            runA={runA}
            runB={runB}
            details={details.state === "ready" ? details.data : null}
          />
        </div>
        <div>
          <h3 className="mb-2 font-mono text-[10.5px] uppercase tracking-[0.18em] text-muted-foreground">
            Curves
          </h3>
          <Curves runA={runA} runB={runB} pages={curves.state === "ready" ? curves.data : null} />
        </div>
      </div>
    </section>
  );
}
