import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { METRICS, type MetricKey } from "@/lib/format";

export interface MetricPoint {
  step: number;
  value: number;
}

export interface MetricSeries {
  id: string;
  label: string;
  points: MetricPoint[];
  /** Drawn dashed (compare: run B). */
  dashed?: boolean;
  /** Drawn in the accent colour (the run being watched live). */
  accent?: boolean;
}

export interface MetricChartProps {
  metric: MetricKey;
  series: MetricSeries[];
  /** Chart height in px. */
  height?: number;
}

const INK = "var(--ink)";
const ACCENT = "var(--accent-orange)";
const MUTED = "var(--ink-muted)";
const GRID = "var(--grid)";

/**
 * One metric's curves over steps: 1.5 px lines on a dotted grid (design-system-mapping.md,
 * CurvesPanel). The figure is named "<Label> curve: <series labels>", and each series leaves a
 * hidden `data-series`/`data-points` marker, so tests read state rather than SVG paths.
 */
export function MetricChart({ metric, series, height = 240 }: MetricChartProps) {
  const label = METRICS[metric];
  const name = `${label} curve: ${series.map((s) => s.label).join(", ")}`;
  return (
    <figure aria-label={name} className="m-0 w-full" data-metric={metric}>
      {series.map((s) => (
        <span key={s.id} hidden data-series={s.id} data-points={s.points.length} />
      ))}
      <div style={{ width: "100%", height }}>
        <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 640, height }}>
          <LineChart margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
            <CartesianGrid stroke={GRID} strokeDasharray="1 3" />
            <XAxis
              dataKey="step"
              type="number"
              domain={["dataMin", "dataMax"]}
              allowDuplicatedCategory={false}
              stroke={MUTED}
              tick={{ fill: MUTED, fontSize: 11 }}
              tickLine={false}
            />
            <YAxis
              dataKey="value"
              stroke={MUTED}
              tick={{ fill: MUTED, fontSize: 11 }}
              tickLine={false}
              width={56}
            />
            <Tooltip
              contentStyle={{
                background: "var(--panel)",
                border: "0.5px solid var(--hairline)",
                borderRadius: 4,
                color: INK,
              }}
              labelFormatter={(step) => `Step ${String(step)}`}
            />
            {series.map((s) => (
              <Line
                key={s.id}
                data={s.points}
                dataKey="value"
                name={s.label}
                type="linear"
                stroke={s.accent ? ACCENT : INK}
                strokeWidth={1.5}
                strokeDasharray={s.dashed ? "5 4" : undefined}
                dot={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="sr-only">{name}</figcaption>
    </figure>
  );
}
