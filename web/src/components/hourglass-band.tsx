/**
 * The hourglass band at the top of the training page (refined mockups, Screen 3; interaction-spec
 * HourglassBand). Dotted lines fan from the top and bottom edges into a narrow waist, after the
 * Gateway Flow look (inputs/design, recreated from scratch). The top half holds the steps still to
 * come, the bottom half the steps done: the share of lit dots below the waist is `step / total`.
 * The canvas is decorative (`aria-hidden`); the same facts are text over the band, with a
 * progressbar named "Run progress". While a run is RUNNING one frame loop keeps grains flowing
 * down through the waist (`data-flow="on"`, AC4.5.11); under reduced motion the dots jump with no
 * fall and nothing flows. While a run scores problems the band shows that progress in place of
 * the step counter (AC4.5.12).
 */
import { useEffect, useRef, type ReactNode } from "react";
import { WifiOff } from "lucide-react";

import type { EvaluationProgress } from "@/lib/api";
import { formatClock } from "@/lib/format";
import { usePrefersReducedMotion } from "@/lib/reduced-motion";

export type BandStatus = "IDLE" | "RUNNING" | "STOPPED" | "FAILED";

export interface HourglassBandProps {
  /** The status word over the band; null while the status is not known. */
  status: BandStatus | null;
  /** Steps done, or problems scored for an evaluation. */
  step: number;
  /** Total steps or problems; 0 when not known yet. */
  totalSteps: number;
  runId: string | null;
  /** Method as shown, e.g. "SFT". */
  method: string | null;
  /** Model as shown, e.g. "Qwen3-0.6B-Base". */
  model: string | null;
  elapsedS: number | null;
  etaS: number | null;
  /** When the last live update arrived, for the paused banner. */
  lastUpdate: Date | null;
  /** The live stream dropped and is reconnecting. */
  paused: boolean;
  /** Overrides `step / totalSteps` (a finished run drains fully). */
  fraction?: number;
  /** The line under the status, e.g. "Waiting for first step...". */
  message?: ReactNode;
  /** A control beside the message, e.g. Show log for a failed run. */
  action?: ReactNode;
  /** While the run scores problems (C6 `Status.evaluation`): shown in place of the step counter. */
  evaluation?: EvaluationProgress | null;
}

const LINES = 48;
const DOTS_PER_HALF = 22;
const SPARKS = 44;
const FALL_MS = 260;

const clamp01 = (value: number) => (Number.isFinite(value) ? Math.min(1, Math.max(0, value)) : 0);

/** Seconds -> "0:19" (hours:minutes, as the mockup draws elapsed and remaining time). */
function clockSpan(seconds: number): string {
  const minutes = Math.max(0, Math.floor(seconds / 60));
  return `${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, "0")}`;
}

/** Remaining seconds rounded to the nearest minute, as "~0:44". */
function remainingSpan(seconds: number): string {
  return `~${clockSpan(Math.round(seconds / 60) * 60)}`;
}

export function HourglassBand({
  status,
  step,
  totalSteps,
  runId,
  method,
  model,
  elapsedS,
  etaS,
  lastUpdate,
  paused,
  fraction,
  message,
  action,
  evaluation,
}: HourglassBandProps) {
  const reduced = usePrefersReducedMotion();
  const scoring = evaluation ?? null;
  const done = scoring ? scoring.scored : step;
  const total = scoring ? scoring.total : totalSteps;
  const known = total > 0;
  const shareDone = clamp01(fraction ?? (known ? done / total : 0));
  const percent = Math.round(shareDone * 100);
  const dim = status === "STOPPED" || status === "FAILED";
  const flow = status === "RUNNING" && !reduced;
  const detail = [method, model].filter((part): part is string => Boolean(part)).join(" · ");

  return (
    <section
      aria-label="Run progress band"
      data-fraction={String(shareDone)}
      data-status={status ?? "LOADING"}
      data-flow={flow ? "on" : "off"}
      className="relative h-[280px] w-full overflow-hidden rounded-lg border border-hairline bg-bg"
    >
      <HourglassCanvas
        fraction={shareDone}
        dim={dim}
        accent={status === "RUNNING"}
        flow={flow}
        reduced={reduced}
      />

      {paused ? (
        <p className="absolute inset-x-0 top-0 z-10 flex items-center gap-2 border-b border-hairline bg-panel px-4 py-1.5 text-sm">
          <WifiOff aria-hidden="true" className="size-4 text-orange" />
          <span>
            Live updates paused, reconnecting
            {lastUpdate ? <> · last update {formatClock(lastUpdate)}</> : null}
          </span>
        </p>
      ) : null}

      <div className="absolute inset-0 flex items-center justify-between gap-6 px-6">
        <div className="max-w-[45%] rounded-md bg-scrim px-3 py-2">
          {status || runId ? (
            <p className="label-caps">
              {status}
              {runId ? (
                <>
                  {" "}
                  <span className="num ml-3 normal-case tracking-normal">{runId}</span>
                </>
              ) : null}
            </p>
          ) : null}
          {detail ? <p className="text-sm text-ink-muted">{detail}</p> : null}
          {message ? <p className="mt-1 text-sm">{message}</p> : null}
          {action ? <div className="mt-2">{action}</div> : null}
        </div>

        {known ? (
          <div className="rounded-md bg-scrim px-3 py-2 text-right">
            <div
              role="progressbar"
              aria-label="Run progress"
              aria-valuemin={0}
              aria-valuemax={total}
              aria-valuenow={done}
              aria-valuetext={
                scoring ? `scored ${done} of ${total} problems` : `step ${done} of ${total}`
              }
              className="num text-[20px]"
            >
              <span>
                {scoring
                  ? `scoring ${scoring.split} ${done} / ${total}`
                  : `step ${done} / ${total}`}
              </span>{" "}
              <span className="ml-4">{percent}%</span>
            </div>
            {status === "RUNNING" && !scoring ? (
              <p className="num text-sm text-ink-muted">
                {elapsedS !== null ? <span>elapsed {clockSpan(elapsedS)} </span> : null}
                <span className="ml-4">
                  {etaS !== null ? `left ${remainingSpan(etaS)}` : "No estimate yet"}
                </span>
              </p>
            ) : null}
          </div>
        ) : null}
      </div>
    </section>
  );
}

/** Point pairs per line: the top curve's dots, then the bottom curve's. */
const POINTS_PER_LINE = 2 * DOTS_PER_HALF;

/** Stable pseudo-random numbers, so sparks and grain offsets stay put between frames. */
function seeded(): () => number {
  let seed = 7;
  return () => {
    seed = (seed * 16807) % 2147483647;
    return seed / 2147483647;
  };
}

/** The bright "spark" dots: 1 at index `(line * 2 + half) * DOTS_PER_HALF + dot`, else 0. */
const SPARK_MASK: Uint8Array = (() => {
  const next = seeded();
  const mask = new Uint8Array(LINES * POINTS_PER_LINE);
  for (let s = 0; s < SPARKS; s += 1) {
    const line = Math.floor(next() * LINES);
    const dot = Math.floor(next() * DOTS_PER_HALF);
    const half = next() < 0.5 ? 0 : 1;
    mask[(line * 2 + half) * DOTS_PER_HALF + dot] = 1;
  }
  return mask;
})();

/** Each line's grain offset (0..1), so the grains do not march in step. */
const GRAIN_OFFSETS: Float32Array = (() => {
  const next = seeded();
  next(); // a different stream than the sparks
  const offsets = new Float32Array(LINES);
  for (let i = 0; i < LINES; i += 1) offsets[i] = next();
  return offsets;
})();

/** Grains per line; each runs down the top curve, through the waist, and down the bottom one. */
const GRAINS_PER_LINE = 2;
/** How long one grain takes from the top edge, through the waist, to the bottom edge. */
const GRAIN_MS = 5200;
/** How often the theme colours are read again while the band flows. */
const COLOR_MS = 1000;

/** What the canvas keeps between frames: the curve points for its size and the theme colours. */
interface Geometry {
  width: number;
  height: number;
  /** x, y of every dot: `((line * 2 + half) * DOTS_PER_HALF + k) * 2`, k = 0 at the waist. */
  points: Float32Array;
  ink: string;
  orange: string;
  colorsAt: number;
  /** The still dots (lit share, sparks, orange front), drawn once per change and blitted. */
  still: HTMLCanvasElement | null;
  /** What `still` was drawn for: dot counts, dim, accent, colours and pixel ratio. */
  stillKey: string;
}

function cssToken(el: HTMLElement, name: string, fallback: string): string {
  const value = getComputedStyle(el).getPropertyValue(name).trim();
  return value || fallback;
}

/** Points along each line's two quadratic curves, waist (k = 0) to edge, for one canvas size. */
function curvePoints(width: number, height: number): Float32Array {
  const points = new Float32Array(LINES * POINTS_PER_LINE * 2);
  const cx = width / 2;
  const cy = height / 2;
  const waistHalf = Math.max(4, width * 0.006);
  for (let i = 0; i < LINES; i += 1) {
    const share = (i + 0.5) / LINES;
    const edgeX = share * width;
    const waistX = cx + (share - 0.5) * 2 * waistHalf;
    for (let half = 0; half < 2; half += 1) {
      const edgeY = half === 0 ? 0 : height;
      const controlY = half === 0 ? cy * 0.55 : height - cy * 0.55;
      for (let k = 0; k < DOTS_PER_HALF; k += 1) {
        // Denser near the waist, as the lines bunch there.
        const t = ((k + 0.5) / DOTS_PER_HALF) ** 1.15;
        const a = (1 - t) * (1 - t);
        const b = 2 * (1 - t) * t;
        const c = t * t;
        const at = ((i * 2 + half) * DOTS_PER_HALF + k) * 2;
        points[at] = a * waistX + b * edgeX + c * edgeX;
        points[at + 1] = a * cy + b * controlY + c * edgeY;
      }
    }
  }
  return points;
}

/** Draws every still dot: the lit share on both halves, the sparks and the orange front. */
function drawStill(
  ctx: CanvasRenderingContext2D,
  points: Float32Array,
  remainingDots: number,
  doneDots: number,
  base: number,
  accent: boolean,
  ink: string,
  orange: string,
): void {
  for (let i = 0; i < LINES; i += 1) {
    for (let half = 0; half < 2; half += 1) {
      const top = half === 0;
      const row = (i * 2 + half) * DOTS_PER_HALF;
      for (let k = 0; k < DOTS_PER_HALF; k += 1) {
        // Top: the sand left sits nearest the waist; bottom: the sand done piles from the edge.
        const lit = top ? k < remainingDots : k >= DOTS_PER_HALF - doneDots;
        const front = !top && accent && doneDots > 0 && k === DOTS_PER_HALF - doneDots;
        const spark = SPARK_MASK[row + k] === 1;
        const size = spark ? 2.2 : 1.3;
        ctx.fillStyle = front ? orange : ink;
        ctx.globalAlpha = base * (lit ? (spark ? 1 : 0.78) : spark ? 0.3 : 0.13);
        const at = (row + k) * 2;
        ctx.fillRect(points[at] - size / 2, points[at + 1] - size / 2, size, size);
      }
    }
  }
  ctx.globalAlpha = 1;
}

/**
 * Grains: a few bright dots per line slide down the top curve to the waist, then down the
 * bottom curve away from it. One phase per line and grain, so the flow runs through the waist.
 */
function drawGrains(
  ctx: CanvasRenderingContext2D,
  points: Float32Array,
  flowAt: number,
  base: number,
  ink: string,
): void {
  ctx.fillStyle = ink;
  const last = DOTS_PER_HALF - 1;
  const size = 2.4;
  for (let i = 0; i < LINES; i += 1) {
    for (let g = 0; g < GRAINS_PER_LINE; g += 1) {
      const cycle = flowAt / GRAIN_MS + GRAIN_OFFSETS[i] + g / GRAINS_PER_LINE;
      // 0..2: the first unit on the top curve (edge to waist), the second on the bottom one.
      const run = (cycle % 1) * 2;
      for (let half = 0; half < 2; half += 1) {
        const s = half === 0 ? run : run - 1;
        if (s < 0 || s >= 1) continue;
        const u = half === 0 ? (1 - s) * last : s * last; // k along the curve, 0 at the waist
        const k0 = Math.floor(u);
        const k1 = Math.min(last, k0 + 1);
        const f = u - k0;
        const row = (i * 2 + half) * DOTS_PER_HALF;
        const a = (row + k0) * 2;
        const b = (row + k1) * 2;
        const x = points[a] + (points[b] - points[a]) * f;
        const y = points[a + 1] + (points[b + 1] - points[a + 1]) * f;
        // Fade in at the top edge and out at the bottom edge.
        const fade = half === 0 ? Math.min(1, s * 4) : Math.min(1, (1 - s) * 4);
        ctx.globalAlpha = base * 0.95 * fade;
        ctx.fillRect(x - size / 2, y - size / 2, size, size);
      }
    }
  }
  ctx.globalAlpha = 1;
}

/**
 * Draws the band. `flowAt` is the clock (performance.now()) of a flowing frame, or null when
 * nothing flows; it places the grains. The still dots live on an offscreen canvas that is drawn
 * again only when the dot counts, size, colours, dim or accent change; a flowing frame blits it
 * and draws only the grains over it.
 */
function draw(
  canvas: HTMLCanvasElement,
  cache: { current: Geometry | null },
  fraction: number,
  dim: boolean,
  accent: boolean,
  flowAt: number | null,
): void {
  const ctx = canvas.getContext("2d");
  if (!ctx) return; // no canvas (tests): the text over the band carries every fact
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  if (width === 0 || height === 0) return;
  const ratio = window.devicePixelRatio || 1;
  const pixelW = Math.round(width * ratio);
  const pixelH = Math.round(height * ratio);
  if (canvas.width !== pixelW || canvas.height !== pixelH) {
    canvas.width = pixelW;
    canvas.height = pixelH;
  }

  const now = flowAt ?? performance.now();
  let geom = cache.current;
  if (!geom || geom.width !== width || geom.height !== height) {
    geom = {
      width,
      height,
      points: curvePoints(width, height),
      ink: "",
      orange: "",
      colorsAt: -1,
      still: geom?.still ?? null,
      stillKey: "",
    };
    cache.current = geom;
  }
  // Colours follow the theme: read on every still frame, at most once a second while flowing.
  if (flowAt === null || geom.colorsAt < 0 || now - geom.colorsAt > COLOR_MS) {
    geom.ink = cssToken(canvas, "--ink", getComputedStyle(canvas).color);
    geom.orange = cssToken(canvas, "--accent-orange", geom.ink);
    geom.colorsAt = now;
  }
  const { points, ink, orange } = geom;

  const remainingDots = Math.round((1 - fraction) * DOTS_PER_HALF);
  const doneDots = Math.round(fraction * DOTS_PER_HALF);
  const base = dim ? 0.5 : 1;

  // The still layer, redrawn only when what it shows changes.
  const key = `${remainingDots}:${doneDots}:${dim ? 1 : 0}:${accent ? 1 : 0}:${ink}:${orange}:${pixelW}x${pixelH}`;
  if (geom.stillKey !== key) {
    const still = geom.still ?? document.createElement("canvas");
    const stillCtx = still.getContext("2d");
    if (stillCtx) {
      if (still.width !== pixelW || still.height !== pixelH) {
        still.width = pixelW;
        still.height = pixelH;
      }
      stillCtx.setTransform(ratio, 0, 0, ratio, 0, 0);
      stillCtx.clearRect(0, 0, width, height);
      drawStill(stillCtx, points, remainingDots, doneDots, base, accent, ink, orange);
      geom.still = still;
      geom.stillKey = key;
    } else {
      geom.still = null;
      geom.stillKey = "";
    }
  }

  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, pixelW, pixelH);
  if (geom.still && geom.stillKey === key) {
    ctx.globalAlpha = 1;
    ctx.drawImage(geom.still, 0, 0);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  } else {
    // No offscreen context: draw the still dots straight onto the band.
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    drawStill(ctx, points, remainingDots, doneDots, base, accent, ink, orange);
  }
  if (flowAt !== null) drawGrains(ctx, points, flowAt, base, ink);
}

function HourglassCanvas({
  fraction,
  dim,
  accent,
  flow,
  reduced,
}: {
  fraction: number;
  dim: boolean;
  accent: boolean;
  /** RUNNING with reduced motion off: one frame loop keeps the grains moving. */
  flow: boolean;
  reduced: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const shown = useRef(fraction);
  const flowAt = useRef<number | null>(null);
  const geometry = useRef<Geometry | null>(null);

  // At most one frame loop: while flowing it never stops; otherwise a short eased fall from the
  // drawn fraction to the new one that settles (none under reduced motion). The cleanup cancels
  // the outstanding frame on every change and on unmount.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const target = fraction;
    const from = shown.current;
    const canLoop = typeof requestAnimationFrame === "function";
    if (!canLoop || (!flow && (reduced || from === target))) {
      shown.current = target;
      flowAt.current = null;
      draw(canvas, geometry, target, dim, accent, null);
      return;
    }
    let frame = 0;
    const start = performance.now();
    const tick = () => {
      const now = performance.now();
      const t = Math.min(1, (now - start) / FALL_MS);
      shown.current = from + (target - from) * (1 - (1 - t) ** 3);
      flowAt.current = flow ? now : null;
      draw(canvas, geometry, shown.current, dim, accent, flowAt.current);
      if (flow || t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [fraction, dim, accent, flow, reduced]);

  // Redraw at the new size when the band is resized.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || typeof ResizeObserver !== "function") return;
    const observer = new ResizeObserver(() =>
      draw(canvas, geometry, shown.current, dim, accent, flowAt.current),
    );
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [dim, accent]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="absolute inset-0 h-full w-full text-ink"
    />
  );
}
