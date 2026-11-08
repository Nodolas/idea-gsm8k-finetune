import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { LabVariantResult } from "@/lib/api";

const STROKES = ["var(--ink)", "var(--accent-orange)", "var(--ink-muted)"];
const DASHES = [undefined, "5 4", "1 3"];

function strokeFor(i: number): { stroke: string; dash: string | undefined } {
  return {
    stroke: STROKES[i % STROKES.length],
    dash: DASHES[Math.floor(i / STROKES.length) % DASHES.length],
  };
}

export interface LabChartProps {
  kind: "train-loss" | "dev-loss";
  title: string;
  results: LabVariantResult[];
}

function pointsOf(result: LabVariantResult, kind: LabChartProps["kind"]) {
  const points: Array<{ step: number; value: number }> = [];
  for (const line of result.lines) {
    const value = kind === "train-loss" ? line.loss : line.dev_loss;
    if (value !== null) points.push({ step: line.step, value });
  }
  return points;
}

/**
 * One overlay of every variant's loss curve. Hidden from assistive technology: the results table
 * holds the same facts (AC11.4.8). Each variant leaves a `data-series`/`data-points` marker.
 */
export function LabChart({ kind, title, results }: LabChartProps) {
  const series = results
    .map((r, i) => ({ result: r, index: i, points: pointsOf(r, kind) }))
    .filter((s) => s.points.length > 0);
  return (
    <div className="min-w-0">
      <h3 className="mb-2 text-sm font-semibold">{title}</h3>
      <div data-chart={kind} aria-hidden="true">
        {series.map((s) => (
          <span
            key={s.result.name}
            hidden
            data-series={s.result.name}
            data-points={s.points.length}
          />
        ))}
        <div style={{ width: "100%", height: 220 }}>
          <ResponsiveContainer
            width="100%"
            height="100%"
            initialDimension={{ width: 480, height: 220 }}
          >
            <LineChart margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
              <CartesianGrid stroke="var(--grid)" strokeDasharray="1 3" />
              <XAxis
                dataKey="step"
                type="number"
                domain={["dataMin", "dataMax"]}
                allowDuplicatedCategory={false}
                stroke="var(--ink-muted)"
                tick={{ fill: "var(--ink-muted)", fontSize: 11 }}
                tickLine={false}
              />
              <YAxis
                dataKey="value"
                stroke="var(--ink-muted)"
                tick={{ fill: "var(--ink-muted)", fontSize: 11 }}
                tickLine={false}
                width={48}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--panel)",
                  border: "0.5px solid var(--hairline)",
                  borderRadius: 4,
                  color: "var(--ink)",
                }}
                labelFormatter={(step) => `Step ${String(step)}`}
              />
              {series.map((s) => {
                const { stroke, dash } = strokeFor(s.index);
                return (
                  <Line
                    key={s.result.name}
                    data={s.points}
                    dataKey="value"
                    name={s.result.label}
                    type="linear"
                    stroke={stroke}
                    strokeWidth={1.5}
                    strokeDasharray={dash}
                    dot={false}
                    isAnimationActive={false}
                  />
                );
              })}
            </LineChart>
          </ResponsiveContainer>
        </div>
        <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-muted">
          {series.map((s) => {
            const { stroke, dash } = strokeFor(s.index);
            return (
              <li key={s.result.name} className="flex items-center gap-2">
                <svg width="22" height="6" aria-hidden="true">
                  <line
                    x1="0"
                    y1="3"
                    x2="22"
                    y2="3"
                    stroke={stroke}
                    strokeWidth="1.5"
                    strokeDasharray={dash}
                  />
                </svg>
                <span>{s.result.label}</span>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
