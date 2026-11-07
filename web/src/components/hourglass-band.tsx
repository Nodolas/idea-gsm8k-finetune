/**
 * The hourglass band at the top of the training page (refined mockups, Screen 3; interaction-spec
 * HourglassBand). Dotted lines fan from the top and bottom edges into a narrow waist, after the
 * Gateway Flow look (inputs/design, recreated from scratch). The top half holds the steps still to
 * come, the bottom half the steps done: the share of lit dots below the waist is `step / total`.
 * The canvas is decorative (`aria-hidden`); the same facts are text over the band, with a
 * progressbar named "Run progress". Under reduced motion the dots jump with no fall.
 */
import { useEffect, useRef, type ReactNode } from "react";
import { WifiOff } from "lucide-react";

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
}: HourglassBandProps) {
  const known = totalSteps > 0;
  const shareDone = clamp01(fraction ?? (known ? step / totalSteps : 0));
  const percent = Math.round(shareDone * 100);
  const dim = status === "STOPPED" || status === "FAILED";
  const detail = [method, model].filter((part): part is string => Boolean(part)).join(" · ");

  return (
    <section
      aria-label="Run progress band"
      data-fraction={String(shareDone)}
      data-status={status ?? "LOADING"}
      className="relative h-[280px] w-full overflow-hidden rounded-lg border border-hairline bg-bg"
    >
      <HourglassCanvas fraction={shareDone} dim={dim} accent={status === "RUNNING"} />

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
              aria-valuemax={totalSteps}
              aria-valuenow={step}
              aria-valuetext={`step ${step} of ${totalSteps}`}
              className="num text-[20px]"
            >
              <span>
                step {step} / {totalSteps}
              </span>{" "}
              <span className="ml-4">{percent}%</span>
            </div>
            {status === "RUNNING" ? (
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

interface Dot {
  x: number;
  y: number;
}

/** Points along a quadratic curve from the waist (t = 0) to an edge (t = 1). */
function curveDots(waist: Dot, control: Dot, edge: Dot): Dot[] {
  const dots: Dot[] = [];
  for (let k = 0; k < DOTS_PER_HALF; k += 1) {
    // Denser near the waist, as the lines bunch there.
    const t = ((k + 0.5) / DOTS_PER_HALF) ** 1.15;
    const a = (1 - t) * (1 - t);
    const b = 2 * (1 - t) * t;
    const c = t * t;
    dots.push({
      x: a * waist.x + b * control.x + c * edge.x,
      y: a * waist.y + b * control.y + c * edge.y,
    });
  }
  return dots;
}

/** Stable pseudo-random numbers, so the bright "spark" dots stay put between frames. */
function sparkPicks(): Array<{ line: number; dot: number; top: boolean }> {
  let seed = 7;
  const next = () => {
    seed = (seed * 16807) % 2147483647;
    return seed / 2147483647;
  };
  return Array.from({ length: SPARKS }, () => ({
    line: Math.floor(next() * LINES),
    dot: Math.floor(next() * DOTS_PER_HALF),
    top: next() < 0.5,
  }));
}

const SPARK_PICKS = sparkPicks();

function cssToken(el: HTMLElement, name: string, fallback: string): string {
  const value = getComputedStyle(el).getPropertyValue(name).trim();
  return value || fallback;
}

function draw(canvas: HTMLCanvasElement, fraction: number, dim: boolean, accent: boolean): void {
  const ctx = canvas.getContext("2d");
  if (!ctx) return; // no canvas (tests): the text over the band carries every fact
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  if (width === 0 || height === 0) return;
  const ratio = window.devicePixelRatio || 1;
  if (canvas.width !== Math.round(width * ratio) || canvas.height !== Math.round(height * ratio)) {
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
  }
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height);

  const ink = cssToken(canvas, "--ink", getComputedStyle(canvas).color);
  const orange = cssToken(canvas, "--accent-orange", ink);
  const cx = width / 2;
  const cy = height / 2;
  const waistHalf = Math.max(4, width * 0.006);
  const remainingDots = Math.round((1 - fraction) * DOTS_PER_HALF);
  const doneDots = Math.round(fraction * DOTS_PER_HALF);

  ctx.globalAlpha = 1;
  const base = dim ? 0.5 : 1;
  const sparkSet = new Set(SPARK_PICKS.map((s) => `${s.line}:${s.dot}:${s.top ? 1 : 0}`));

  for (let i = 0; i < LINES; i += 1) {
    const share = (i + 0.5) / LINES;
    const edgeX = share * width;
    const waistX = cx + (share - 0.5) * 2 * waistHalf;
    for (const top of [true, false]) {
      const edgeY = top ? 0 : height;
      const controlY = top ? cy * 0.55 : height - cy * 0.55;
      const dots = curveDots(
        { x: waistX, y: cy },
        { x: edgeX, y: controlY },
        { x: edgeX, y: edgeY },
      );
      dots.forEach((dot, k) => {
        // Top: the sand left sits nearest the waist; bottom: the sand done piles from the edge.
        const lit = top ? k < remainingDots : k >= DOTS_PER_HALF - doneDots;
        const front = !top && accent && doneDots > 0 && k === DOTS_PER_HALF - doneDots;
        const spark = sparkSet.has(`${i}:${k}:${top ? 1 : 0}`);
        const size = spark ? 2.2 : 1.3;
        ctx.fillStyle = front ? orange : ink;
        ctx.globalAlpha = base * (lit ? (spark ? 1 : 0.78) : spark ? 0.3 : 0.13);
        ctx.fillRect(dot.x - size / 2, dot.y - size / 2, size, size);
      });
    }
  }
  ctx.globalAlpha = 1;
}

function HourglassCanvas({
  fraction,
  dim,
  accent,
}: {
  fraction: number;
  dim: boolean;
  accent: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const shown = useRef(fraction);
  const reduced = usePrefersReducedMotion();

  // A short eased fall from the drawn fraction to the new one; none under reduced motion.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const from = shown.current;
    if (reduced || from === fraction || typeof requestAnimationFrame !== "function") {
      shown.current = fraction;
      draw(canvas, fraction, dim, accent);
      return;
    }
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / FALL_MS);
      const eased = 1 - (1 - t) ** 3;
      shown.current = from + (fraction - from) * eased;
      draw(canvas, shown.current, dim, accent);
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(frame);
      shown.current = fraction;
    };
  }, [fraction, dim, accent, reduced]);

  // Redraw at the new size when the band is resized.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || typeof ResizeObserver !== "function") return;
    const observer = new ResizeObserver(() => draw(canvas, shown.current, dim, accent));
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
