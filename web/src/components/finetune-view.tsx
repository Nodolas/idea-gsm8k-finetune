/**
 * The fine-tuning view of the training page (US4.7; refined-mockups "The fine-tuning view"): how a
 * model gets fine-tuned. A row of frozen decoder layers, a small LoRA adapter on each that is
 * trained, and the five stages of one training step (read, guess, score, blame, nudge), with the
 * newest step line's figures and the weight counts worked out from the model's shape and the run's
 * LoRA rank. A run that does not change the model (answer generation, evaluation) says so. A run
 * that is not live can be replayed step by step.
 *
 * The numbers are measured (step, loss, gradient norm, learning rate); the drawing is an
 * illustration, hidden from assistive technology, and the panel says so (AC4.7.8). Data comes only
 * through `useApi()` (ADR-008): the run's settings, and the stored lines of a run that is not live.
 */
import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";

import { Button } from "@/components/ui/button";
import type { MetricsLine, RunConfig } from "@/lib/api";
import { useApi } from "@/lib/api-context";
import {
  DEFAULT_LAYERS,
  describeChange,
  figuresAt,
  formatChance,
  formatCount,
  formatGrad,
  formatLoss,
  formatRate,
  kindOf,
  loraCounts,
  queryProjection,
  shapeOf,
  stepLines,
  type ModelShape,
  type StepFigures,
  type ViewKind,
} from "@/lib/finetune-model";
import { modelName } from "@/lib/format";
import { useAsync } from "@/lib/queries";
import { usePrefersReducedMotion } from "@/lib/reduced-motion";
import "@/styles/finetune.css";

export interface FinetuneViewProps {
  /** The run the panel is about; null when there is none. */
  runId: string | null;
  method: string | null;
  /** Model as the run list names it, e.g. "Qwen/Qwen3-1.7B-Base". */
  model: string | null;
  /** The lines the stream delivered for the live run; ignored unless `live`. */
  liveLines: readonly MetricsLine[];
  /** The run is the active one and the panel follows it. */
  live: boolean;
  /** The service status is not known yet. */
  loading?: boolean;
}

/** Replay: one tick per 150 ms, and a replay of a long run takes about 20 s (about 130 ticks). */
const REPLAY_TICK_MS = 150;
const REPLAY_TICKS = 130;

const STAGES: ReadonlyArray<{ key: string; name: string; meaning: string }> = [
  {
    key: "read",
    name: "Read",
    meaning: "A few training examples, each a problem and its answer, go into the model.",
  },
  {
    key: "guess",
    name: "Guess",
    meaning: "The model predicts every next word of the answer, layer after layer.",
  },
  {
    key: "score",
    name: "Score",
    meaning:
      "The guess is compared with the real word. Loss is the penalty: the lower, the more chance it gave the right word.",
  },
  {
    key: "blame",
    name: "Blame",
    meaning:
      "The gradient runs backwards through the layers and says how much each adapter weight added to the error.",
  },
  {
    key: "nudge",
    name: "Nudge",
    meaning:
      "Only the adapter weights move, a small step set by the learning rate. The frozen weights never change.",
  },
];

const READING_NOTES: Record<string, string> = {
  cotgen:
    "It writes step-by-step solutions to training problems with the model as it is. The solutions it gets right become the training text of the next fine-tune.",
};
const READING_NOTE_DEFAULT =
  "It only measures how many problems the model solves: it reads each problem, writes an answer and the answer is scored.";

function numberOf(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function figureText(stage: string, figures: StepFigures, batchSize: number | null): string {
  switch (stage) {
    case "read":
      return batchSize === null ? "—" : `${batchSize} examples per step`;
    case "guess":
      return "scored on answer words only";
    case "score":
      return [
        `loss ${formatLoss(figures.loss)}`,
        `${formatChance(figures.chance)} chance on the right word`,
        describeChange(figures.change),
      ].join(" · ");
    case "blame":
      return `gradient norm ${formatGrad(figures.gradNorm)}`;
    default:
      return `learning rate ${formatRate(figures.learningRate)}`;
  }
}

export function FinetuneView(props: FinetuneViewProps) {
  // A new run starts the panel afresh: the replay position and the replay itself are per run.
  return <FinetuneBody key={props.runId ?? "none"} {...props} />;
}

function FinetuneBody({
  runId,
  method,
  model,
  liveLines,
  live,
  loading = false,
}: FinetuneViewProps) {
  const api = useApi();
  const headingId = useId();
  const reduced = usePrefersReducedMotion();

  const settings = useAsync(
    () => (runId === null ? Promise.resolve(null) : api.getRun(runId)),
    [api, runId],
  );
  const stored = useAsync(
    () => (runId === null || live ? Promise.resolve(null) : api.getMetrics(runId)),
    [api, runId, live],
  );

  const config: RunConfig | null =
    settings.state === "ready" && settings.data ? settings.data.config : null;
  const storedLines = stored.state === "ready" && stored.data ? stored.data.lines : null;
  const lines = live ? liveLines : (storedLines ?? liveLines);
  const steps = useMemo(() => stepLines(lines), [lines]);
  const lastLine = lines.length > 0 ? lines[lines.length - 1] : null;

  const resolvedMethod = method ?? (typeof config?.method === "string" ? config.method : null);
  const kind: ViewKind | null = kindOf(resolvedMethod);
  const shape: ModelShape | null = shapeOf(
    model ?? (typeof config?.model === "string" ? config.model : null),
  );
  const rank = numberOf(config?.lora_rank);
  const alpha = numberOf(config?.lora_alpha);
  const batchSize = numberOf(config?.batch_size);

  // Replay: `cursor` is the shown line while the user is stepping or playing; null means the last.
  const [cursor, setCursor] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const last = steps.length - 1;
  const index = live || cursor === null ? last : Math.min(cursor, last);
  const canReplay = !live && kind === "finetune" && steps.length >= 2;
  const stride = Math.max(1, Math.ceil(steps.length / REPLAY_TICKS));

  const indexRef = useRef(index);
  useEffect(() => {
    indexRef.current = index;
  }, [index]);
  useEffect(() => {
    if (!playing) return;
    const timer = setInterval(() => {
      const next = Math.min(last, indexRef.current + stride);
      indexRef.current = next;
      setCursor(next);
      if (next >= last) setPlaying(false);
    }, REPLAY_TICK_MS);
    return () => clearInterval(timer);
  }, [playing, last, stride]);

  const play = () => {
    if (playing) {
      setPlaying(false);
      return;
    }
    if (index >= last) {
      indexRef.current = 0;
      setCursor(0);
    }
    setPlaying(true);
  };

  const figures = kind === "finetune" ? figuresAt(steps, index, batchSize) : null;
  const waiting = kind === "finetune" && live && figures === null;
  const showStages = kind === "finetune" && (figures !== null || waiting);
  const counts = kind === "finetune" && shape && rank !== null ? loraCounts(shape, rank) : null;
  const projection = shape && rank !== null ? queryProjection(shape, rank) : null;

  let empty: string | null = null;
  if (runId === null) {
    empty = loading
      ? "Reading the run…"
      : "Nothing to show yet: start a fine-tune to watch the model change.";
  } else if (kind === null) {
    if (resolvedMethod !== null) empty = `No picture for the method ${resolvedMethod}.`;
    else if (settings.state === "error") empty = settings.error.message;
    else if (settings.state === "ready") empty = "The method of this run is not recorded.";
    else empty = "Reading the run…";
  } else if (kind === "reading") {
    if (!live && stored.state === "error") empty = stored.error.message;
  } else if (figures === null) {
    if (live) empty = "Waiting for the first logged step";
    else if (stored.state === "loading") empty = "Reading the run…";
    else if (stored.state === "error") empty = stored.error.message;
    else empty = "No step lines were recorded for this run.";
  }

  let viewState: string | null = null;
  if (live) viewState = "Following the live run";
  else if (figures !== null) {
    viewState = canReplay
      ? `Replaying step ${figures.step} of ${figures.totalSteps}`
      : "Showing the last logged step";
  }

  let progress: string | null = null;
  if (figures !== null) {
    progress = `Step ${figures.step} of ${figures.totalSteps}`;
    if (figures.examplesSeen !== null)
      progress += ` · ${formatCount(figures.examplesSeen)} examples seen`;
  } else if (kind === "reading" && lastLine !== null) {
    progress = `${lastLine.step} of ${lastLine.total_steps} problems ${
      resolvedMethod === "cotgen" ? "written" : "scored"
    }`;
  }

  const shownStep = figures?.step ?? (kind === "reading" ? (lastLine?.step ?? null) : null);
  const subject = [runId, resolvedMethod, model ?? config?.model]
    .filter((part): part is string => typeof part === "string" && part.length > 0)
    .map((part) => (part.includes("/") ? modelName(part) : part))
    .join(" · ");

  return (
    <section
      aria-labelledby={headingId}
      data-mode={kind ?? "none"}
      data-view={live ? "live" : "replay"}
      data-step={shownStep === null ? "" : String(shownStep)}
      data-motion={reduced ? "still" : "live"}
      data-playing={playing ? "true" : "false"}
      className="flex min-w-0 flex-col gap-4 rounded-lg border border-hairline bg-panel p-4"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <h2 id={headingId} className="label-caps">
            How the model is fine-tuned
          </h2>
          {runId !== null && subject ? (
            <p data-part="subject" className="num text-sm text-ink-muted">
              {subject}
            </p>
          ) : null}
        </div>
        {viewState ? (
          <p data-part="view-state" className="num text-sm text-ink-muted">
            {viewState}
          </p>
        ) : null}
      </div>

      <div className="overflow-x-auto">
        <Drawing
          layers={shape?.layers ?? DEFAULT_LAYERS}
          trained={kind === "finetune" && runId !== null}
          reading={kind === "reading"}
          pass={shownStep}
          chance={figures?.chance ?? null}
          batchSize={batchSize}
          nudged={figures?.step ?? null}
        />
      </div>

      <div
        className={
          projection && kind === "finetune"
            ? "grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]"
            : "flex flex-col gap-4"
        }
      >
        <div className="flex min-w-0 flex-col gap-3">
          {empty ? (
            <p data-part="empty" className="text-ink-muted">
              {empty}
            </p>
          ) : null}

          {kind === "reading" ? (
            <p data-part="reading-note" className="max-w-[75ch]">
              This run does not change the model.{" "}
              <span className="text-ink-muted">
                {READING_NOTES[resolvedMethod ?? ""] ?? READING_NOTE_DEFAULT}
              </span>
            </p>
          ) : null}

          {settings.state === "error" && kind !== null ? (
            <p data-part="settings-error" className="max-w-[75ch] text-sm text-danger">
              The run's settings could not be read ({settings.error.message}); the weight counts and
              the examples per step are left out.
            </p>
          ) : null}

          {showStages ? (
            <ol
              key={figures?.step ?? "waiting"}
              role="list"
              data-part="stages"
              className="grid list-none grid-cols-1 gap-3 p-0 sm:grid-cols-2 lg:grid-cols-5"
            >
              {STAGES.map((stage, k) => (
                <li
                  key={stage.key}
                  data-stage={stage.key}
                  style={{ "--k": k } as CSSProperties}
                  className="ft-stage-card flex flex-col gap-1 rounded-md p-3"
                >
                  <div className="flex items-baseline gap-1.5">
                    <span aria-hidden="true" className="num text-ink-muted">
                      {k + 1}
                    </span>
                    <h3 className="label-caps">{stage.name}</h3>
                  </div>
                  <p data-part="meaning" className="text-sm text-ink-muted">
                    {stage.meaning}
                  </p>
                  {figures ? (
                    <p data-part="figure" className="num text-sm">
                      {figureText(stage.key, figures, batchSize)}
                    </p>
                  ) : null}
                </li>
              ))}
            </ol>
          ) : null}

          {progress ? (
            <p data-part="progress" className="num text-sm">
              {progress}
            </p>
          ) : null}

          {counts ? (
            <p data-part="weights" className="num text-sm">
              {formatCount(counts.trained)} trained of {formatCount(counts.total)} weights (
              {counts.percent.toFixed(1)}%) · {formatCount(counts.frozen)} frozen
            </p>
          ) : null}
          {kind === "reading" && shape ? (
            <p data-part="weights" className="num text-sm">
              None of the {formatCount(shape.weights)} weights changes
            </p>
          ) : null}

          {canReplay ? (
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="outline" size="sm" onClick={play}>
                {playing ? "Pause replay" : "Play replay"}
              </Button>
              <input
                type="range"
                aria-label="Replay step"
                aria-valuetext={
                  figures ? `step ${figures.step} of ${figures.totalSteps}` : undefined
                }
                min={1}
                max={steps.length}
                value={index + 1}
                onChange={(event) => {
                  setPlaying(false);
                  setCursor(Number(event.target.value) - 1);
                }}
                className="min-w-[200px] flex-1 accent-orange"
              />
            </div>
          ) : null}
        </div>

        {projection && kind === "finetune" ? (
          <CloseUp projection={projection} rank={rank} alpha={alpha} />
        ) : null}
      </div>

      <p data-part="note" className="max-w-[75ch] text-sm text-ink-muted">
        <strong className="font-medium text-ink">Measured</strong> from the run: step, loss,
        gradient norm and learning rate.{" "}
        <strong className="font-medium text-ink">Drawn for illustration</strong>: the layers, the
        moving dots, the blocks of training text and the bars for the other words. Every adapter is
        updated on every step; per-layer sizes are not recorded.
      </p>
    </section>
  );
}

function CloseUp({
  projection,
  rank,
  alpha,
}: {
  projection: ReturnType<typeof queryProjection>;
  rank: number | null;
  alpha: number | null;
}) {
  const captionId = useId();
  const dotsId = useId();
  const scale = rank !== null && rank > 0 && alpha !== null ? alpha / rank : null;
  const r = rank ?? 0;
  return (
    <figure
      aria-labelledby={captionId}
      data-part="closeup"
      className="m-0 flex flex-col gap-2 rounded-md border border-hairline p-3"
    >
      <figcaption id={captionId} className="label-caps">
        One layer up close
      </figcaption>
      <svg
        aria-hidden="true"
        viewBox="0 0 300 140"
        className="ft-drawing h-auto w-full max-w-[280px]"
      >
        <defs>
          <pattern id={dotsId} width="4" height="4" patternUnits="userSpaceOnUse">
            <circle cx="2" cy="2" r="0.7" fill="currentColor" opacity="0.7" />
          </pattern>
        </defs>
        <rect x="8" y="14" width="90" height="90" fill={`url(#${dotsId})`} className="ft-layer" />
        <text x="53" y="124" textAnchor="middle" className="ft-label">
          W frozen
        </text>
        <text x="118" y="64" textAnchor="middle" className="ft-value">
          +
        </text>
        <rect x="134" y="14" width="14" height="90" className="ft-solid" />
        <text x="141" y="124" textAnchor="middle" className="ft-label ft-label-orange">
          B
        </text>
        <text x="163" y="64" textAnchor="middle" className="ft-value">
          ×
        </text>
        <rect x="178" y="52" width="90" height="14" className="ft-solid" />
        <text x="223" y="124" textAnchor="middle" className="ft-label ft-label-orange">
          A
        </text>
      </svg>
      <dl className="num m-0 grid gap-1 text-sm">
        <Stat name="frozen-matrix" label="Frozen matrix W (query projection)">
          {projection.inWidth} × {projection.outWidth} = {formatCount(projection.frozen)} weights
        </Stat>
        <Stat name="adapter-a" label="Adapter A">
          {r} × {projection.inWidth}
        </Stat>
        <Stat name="adapter-b" label="Adapter B">
          {projection.outWidth} × {r}
        </Stat>
        <Stat name="adapter-total" label="Trained in this matrix">
          {formatCount(projection.adapter)} weights
        </Stat>
        <Stat name="scale" label="Scale of the adapter's output">
          {scale === null || rank === null || alpha === null
            ? "—"
            : `${Number(scale.toPrecision(3))} (alpha ${alpha} / rank ${rank})`}
        </Stat>
      </dl>
    </figure>
  );
}

function Stat({ name, label, children }: { name: string; label: string; children: ReactNode }) {
  return (
    <div data-stat={name} className="flex flex-col">
      <dt className="text-ink-muted">{label}</dt>
      <dd className="m-0">{children}</dd>
    </div>
  );
}

// --- the drawing ----------------------------------------------------------------------------

const VIEW_W = 1000;
const VIEW_Y = 30;
const VIEW_H = 206;
const LAYER_X0 = 212;
const LAYER_SPAN = 560;
const LAYER_Y = 84;
const LAYER_H = 92;
const CHIP_Y = 58;
const CHIP_H = 12;
const OUT_X = 842;
const OUT_W = 148;

const QUESTION_ROWS: number[][] = [
  [14, 22, 10, 18, 12],
  [20, 12, 16, 9],
  [11, 17, 21, 12],
  [18, 10, 14, 20],
];
const ANSWER_ROWS: number[][] = [
  [16, 11, 19, 8],
  [12, 18, 10],
];
const OTHER_SHARES = [0.5, 0.3, 0.12, 0.08];
const READING_WORDS = [100, 70, 45, 30, 20];

interface DrawingProps {
  layers: number;
  /** The adapters are trained (a fine-tune). */
  trained: boolean;
  /** The run only reads (answer generation, evaluation): the sweep runs forward only. */
  reading: boolean;
  /** The step line shown; a new value starts the passes again. Null: the drawing rests. */
  pass: number | null;
  /** The average chance the model gave the right word, 0 to 1; null before the first step. */
  chance: number | null;
  batchSize: number | null;
  /** Steps taken so far. */
  nudged: number | null;
}

function rowsOfTokens(rows: number[][], y0: number, className: string) {
  return rows.flatMap((widths, r) => {
    let x = 12;
    return widths.map((w, c) => {
      const rect = (
        <rect
          key={`${y0}-${r}-${c}`}
          x={x}
          y={y0 + r * 14}
          width={w}
          height={7}
          rx={1}
          className={className}
        />
      );
      x += w + 4;
      return rect;
    });
  });
}

function Drawing({ layers, trained, reading, pass, chance, batchSize, nudged }: DrawingProps) {
  const dotsId = useId();
  const pitch = LAYER_SPAN / layers;
  const colW = pitch * 0.68;
  const indices = Array.from({ length: layers }, (_, i) => i);
  const layerX = (i: number) => LAYER_X0 + i * pitch + (pitch - colW) / 2;
  const middle = LAYER_X0 + LAYER_SPAN / 2;
  const right = chance ?? 0;
  const style = { "--n": layers } as CSSProperties;
  const adapterState = trained ? "trained" : "none";
  const dotsFill = `url(#${dotsId})`;

  return (
    <svg
      data-part="drawing"
      aria-hidden="true"
      viewBox={`0 ${VIEW_Y} ${VIEW_W} ${VIEW_H}`}
      className="ft-drawing mx-auto block h-auto w-full min-w-[860px] max-w-[66vw]"
      style={style}
    >
      <defs>
        <pattern id={dotsId} width="4" height="4" patternUnits="userSpaceOnUse">
          <circle cx="2" cy="2" r="0.7" fill="currentColor" opacity="0.7" />
        </pattern>
      </defs>

      {/* The training text: a problem (grey) and its worked answer (orange). */}
      <text x="12" y="46" className="ft-label">
        {reading ? "Problems" : "Training text"}
      </text>
      {rowsOfTokens(QUESTION_ROWS, 64, "ft-token")}
      {rowsOfTokens(ANSWER_ROWS, 128, "ft-token-answer")}
      {reading ? null : (
        <>
          <text x="12" y="182" className="ft-label">
            {batchSize === null ? "a few examples" : `${batchSize} examples`} per step
          </text>
          <text x="12" y="196" className="ft-label ft-label-orange">
            answer: scored
          </text>
        </>
      )}
      <line x1="124" y1="130" x2="148" y2="130" className="ft-flow" />

      {/* The model: embedding, one frozen column per decoder layer, output head. */}
      <rect x="150" y={LAYER_Y} width="26" height={LAYER_H} fill={dotsFill} className="ft-layer" />
      <text x="163" y="196" textAnchor="middle" className="ft-label">
        embed
      </text>
      <line x1="180" y1="130" x2={LAYER_X0 - 4} y2="130" className="ft-flow" />
      {indices.map((i) => (
        <rect
          key={i}
          data-layer={i}
          data-state="frozen"
          x={layerX(i)}
          y={LAYER_Y}
          width={colW}
          height={LAYER_H}
          fill={dotsFill}
          className="ft-layer"
        />
      ))}
      <line x1={LAYER_X0 + LAYER_SPAN + 4} y1="130" x2="783" y2="130" className="ft-flow" />
      <rect x="785" y={LAYER_Y} width="26" height={LAYER_H} fill={dotsFill} className="ft-layer" />
      <text x="798" y="196" textAnchor="middle" className="ft-label">
        head
      </text>
      <line x1="815" y1="130" x2={OUT_X - 4} y2="130" className="ft-flow" />

      <text x={middle} y="46" textAnchor="middle" className="ft-label ft-label-orange">
        {trained ? "LoRA adapters: small, trained" : "no adapter is trained in this run"}
      </text>
      <text x={middle} y="196" textAnchor="middle" className="ft-label">
        {layers} decoder layers: frozen
      </text>
      {reading && pass !== null ? (
        <text x={middle} y="222" textAnchor="middle" className="ft-label">
          forward only: nothing flows back
        </text>
      ) : null}
      {nudged !== null ? (
        <text x={middle} y="222" textAnchor="middle" className="ft-label">
          adapters nudged {nudged} {nudged === 1 ? "time" : "times"}
        </text>
      ) : null}

      {/* The output: the chance the model gave the right word, against the other words. */}
      <text x={OUT_X} y="46" className="ft-label">
        {reading ? "Output" : "Guess"}
      </text>
      {reading ? (
        <>
          <text x={OUT_X} y="74" className="ft-label">
            words written
          </text>
          {READING_WORDS.map((w, k) => (
            <rect
              key={k}
              x={OUT_X}
              y={82 + k * 14}
              width={(w / 100) * OUT_W}
              height={6}
              className="ft-other"
            />
          ))}
        </>
      ) : (
        <>
          <text x={OUT_X} y="74" className="ft-label">
            right word
          </text>
          <text x={OUT_X + OUT_W} y="74" textAnchor="end" className="ft-value">
            {chance === null ? "" : formatChance(chance)}
          </text>
          <rect x={OUT_X} y="80" width={OUT_W} height="12" className="ft-track" />
          <rect x={OUT_X} y="80" width={OUT_W * right} height="12" className="ft-right" />
          <text x={OUT_X} y="114" className="ft-label">
            other words
          </text>
          {OTHER_SHARES.map((share, k) => (
            <rect
              key={k}
              x={OUT_X}
              y={120 + k * 12}
              width={Math.max(3, (1 - right) * share * OUT_W)}
              height={6}
              className="ft-other"
            />
          ))}
        </>
      )}

      {/* The passes of one step: they start again for every step line. */}
      <g key={pass ?? "rest"} data-part="pass" data-pass={pass === null ? "" : String(pass)}>
        <rect
          x="150"
          y={LAYER_Y}
          width="26"
          height={LAYER_H}
          className="ft-sweep-forward"
          style={{ "--i": -2 } as CSSProperties}
        />
        {indices.map((i) => (
          <g key={i} style={{ "--i": i } as CSSProperties}>
            <rect
              x={layerX(i)}
              y={LAYER_Y}
              width={colW}
              height={LAYER_H}
              className="ft-sweep-forward"
            />
            {trained ? (
              <rect
                x={layerX(i)}
                y={LAYER_Y}
                width={colW}
                height={LAYER_H}
                className="ft-sweep-back"
              />
            ) : null}
            <line
              x1={layerX(i) + colW / 2}
              y1={CHIP_Y + CHIP_H}
              x2={layerX(i) + colW / 2}
              y2={LAYER_Y}
              className="ft-link"
            />
            <rect
              data-adapter={i}
              data-state={adapterState}
              x={layerX(i)}
              y={CHIP_Y}
              width={colW}
              height={CHIP_H}
              className="ft-chip"
            />
          </g>
        ))}
        <rect
          x="785"
          y={LAYER_Y}
          width="26"
          height={LAYER_H}
          className="ft-sweep-forward"
          style={{ "--i": layers + 1 } as CSSProperties}
        />
      </g>
    </svg>
  );
}
