/**
 * The step walkthrough of the training page (US4.8): what happens inside one training step, token
 * by token (Tokenize, Batch, Embed, Forward, Predict, Loss, Backward, Update), or, for a run that
 * does not change the model, how the model writes an answer one token at a time (Tokenize,
 * Forward, Choose, Append, Stop, and Check for answer generation). A clock moves to the next phase
 * every 1.8 seconds; the reduce-motion setting starts it paused and stills the drawing.
 *
 * The sample problem and its tokens are an illustration; the batch size, temperature, loss,
 * gradient norm and learning rate are the run's own (its settings and its newest step line). The
 * drawing is hidden from assistive technology and every fact it shows is also text (AC4.8.6).
 * Data comes only through `useApi()` (ADR-008), like the fine-tuning view it sits under.
 */
import { useEffect, useId, useMemo, useState, type CSSProperties, type ReactNode } from "react";

import type { FinetuneViewProps } from "@/components/finetune-view";
import { Button } from "@/components/ui/button";
import type { RunConfig } from "@/lib/api";
import { useApi } from "@/lib/api-context";
import {
  DEFAULT_LAYERS,
  formatCount,
  formatGrad,
  formatLoss,
  formatRate,
  shapeOf,
  type ModelShape,
} from "@/lib/finetune-model";
import { modelName } from "@/lib/format";
import { useAsync } from "@/lib/queries";
import { usePrefersReducedMotion } from "@/lib/reduced-motion";
import {
  EOS_TOKEN,
  PHASE_MS,
  WALKTHROUGH_SAMPLE,
  displayToken,
  formatTemperature,
  newestFigures,
  phasesOf,
  predictPairs,
  samples,
  temperatureOf,
  walkSteps,
  walkthroughKind,
  type NewestFigures,
  type WalkthroughKind,
} from "@/lib/walkthrough";
import "@/styles/walkthrough.css";

export type StepWalkthroughProps = FinetuneViewProps;

const EMPTY_TEXT = "Start a run to see how a step works.";

const TITLES: Record<WalkthroughKind, string> = {
  training: "One training step, token by token",
  generation: "How the model writes an answer, token by token",
};

const DASH = "—";

function numberOf(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function StepWalkthrough(props: StepWalkthroughProps) {
  // A new run starts the walkthrough afresh at its first phase.
  return <WalkthroughBody key={props.runId ?? "none"} {...props} />;
}

function WalkthroughBody({
  runId,
  method,
  model,
  liveLines,
  live,
  loading = false,
}: StepWalkthroughProps) {
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
  const figures = useMemo(() => newestFigures(lines), [lines]);

  const resolvedMethod = method ?? (typeof config?.method === "string" ? config.method : null);
  const kind = walkthroughKind(resolvedMethod);

  if (kind === null) {
    let message = EMPTY_TEXT;
    if (runId === null && loading) message = "Reading the run…";
    else if (runId !== null && resolvedMethod === null && settings.state === "loading")
      message = "Reading the run…";
    return (
      <section
        aria-labelledby={headingId}
        data-walkthrough="none"
        data-phase=""
        data-motion={reduced ? "still" : "live"}
        className="flex min-w-0 flex-col gap-2 rounded-lg border border-hairline bg-panel p-4"
      >
        <h2 id={headingId} className="label-caps">
          How a step works
        </h2>
        <p data-part="empty" className="text-ink-muted">
          {message}
        </p>
      </section>
    );
  }

  return (
    <Walk
      key={`${kind}:${resolvedMethod ?? ""}`}
      headingId={headingId}
      kind={kind}
      method={resolvedMethod}
      reduced={reduced}
      figures={figures}
      batchSize={numberOf(config?.batch_size)}
      temperature={temperatureOf(config?.cot_temperature)}
      shape={shapeOf(model ?? (typeof config?.model === "string" ? config.model : null))}
      model={model ?? (typeof config?.model === "string" ? config.model : null)}
    />
  );
}

interface WalkProps {
  headingId: string;
  kind: WalkthroughKind;
  method: string | null;
  reduced: boolean;
  figures: NewestFigures | null;
  batchSize: number | null;
  temperature: number;
  shape: ModelShape | null;
  model: string | null;
}

function Walk({
  headingId,
  kind,
  method,
  reduced,
  figures,
  batchSize,
  temperature,
  shape,
  model,
}: WalkProps) {
  const steps = useMemo(() => walkSteps(kind, method), [kind, method]);
  const phases = phasesOf(kind, method);
  const [position, setPosition] = useState(0);
  const [playing, setPlaying] = useState(!reduced);
  // A manual move restarts the clock, so the phase it moved to stays a full 1.8 s.
  const [moves, setMoves] = useState(0);

  // Reduce-motion turned on while playing stops the clock (state adjusted during render).
  const [wasReduced, setWasReduced] = useState(reduced);
  if (wasReduced !== reduced) {
    setWasReduced(reduced);
    if (reduced) setPlaying(false);
  }

  useEffect(() => {
    if (!playing) return;
    const timer = setInterval(() => {
      setPosition((p) => (p + 1) % steps.length);
    }, PHASE_MS);
    return () => clearInterval(timer);
  }, [playing, steps.length, moves]);

  const step = steps[position] ?? steps[0];
  const phaseIndex = Math.max(
    0,
    phases.findIndex((p) => p.key === step.key),
  );

  const move = (by: number) => {
    setPosition((p) => (p + by + steps.length) % steps.length);
    setMoves((n) => n + 1);
  };

  const answerLength = WALKTHROUGH_SAMPLE.answer.length;
  let progress: string;
  if (kind === "training") progress = `Phase ${phaseIndex + 1} of ${phases.length}`;
  else if (step.key === "tokenize") progress = "Answer not started";
  else if (step.key === "forward" || step.key === "choose")
    progress = `Answer token ${step.written + 1} of ${answerLength}`;
  else if (step.key === "append") progress = `Answer token ${step.written} of ${answerLength}`;
  else progress = `Answer complete: ${answerLength} tokens`;

  const layers = shape?.layers ?? DEFAULT_LAYERS;
  const facts: Facts = {
    figures,
    batchSize,
    temperature,
    shape,
    layers,
    model,
    method,
    written: step.written,
  };

  return (
    <section
      aria-labelledby={headingId}
      data-walkthrough={kind}
      data-phase={step.key}
      data-motion={reduced ? "still" : "live"}
      data-playing={playing ? "true" : "false"}
      className="flex min-w-0 flex-col gap-4 rounded-lg border border-hairline bg-panel p-4"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 id={headingId} className="label-caps">
          {TITLES[kind]}
        </h2>
        <p data-part="progress" className="num text-sm text-ink-muted">
          {progress}
        </p>
      </div>

      {kind === "generation" ? (
        <p data-part="intro" className="max-w-[75ch]">
          The weights do not change.{" "}
          <span className="text-ink-muted">{generationIntro(method)}</span>
        </p>
      ) : (
        <p data-part="intro" className="max-w-[75ch] text-ink-muted">
          What every optimizer step of this run does, from token ids to the LoRA update. The text
          was tokenized once; these eight phases repeat on every step.
        </p>
      )}

      <ol
        role="list"
        data-part="phases"
        className={
          kind === "training"
            ? "grid list-none grid-cols-2 gap-2 p-0 sm:grid-cols-4 2xl:grid-cols-8"
            : "grid list-none grid-cols-2 gap-2 p-0 sm:grid-cols-3 xl:grid-cols-6"
        }
      >
        {phases.map((p, k) => (
          <li
            key={p.key}
            data-phase-key={p.key}
            aria-current={p.key === step.key ? "step" : undefined}
            className="wt-phase flex min-w-0 flex-col gap-0.5 rounded-md p-2"
          >
            <div className="flex items-baseline gap-1.5">
              <span aria-hidden="true" className="num text-xs text-ink-muted">
                {k + 1}
              </span>
              <h3 className="label-caps">{p.name}</h3>
            </div>
            <p data-part="meaning" className="text-sm text-ink-muted">
              {p.meaning}
            </p>
          </li>
        ))}
      </ol>

      <div className="min-w-0">
        {kind === "training" ? (
          <TrainingDrawing key={position} phase={step.key} facts={facts} />
        ) : (
          <GenerationDrawing key={position} phase={step.key} facts={facts} />
        )}
      </div>

      <div
        data-part="phase-detail"
        aria-live={playing ? "off" : "polite"}
        className="max-w-[75ch] text-sm"
      >
        {kind === "training" ? (
          <TrainingDetail phase={step.key} facts={facts} />
        ) : (
          <GenerationDetail phase={step.key} facts={facts} />
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" size="sm" onClick={() => move(-1)}>
          Previous phase
        </Button>
        <Button variant="outline" size="sm" onClick={() => setPlaying((p) => !p)}>
          {playing ? "Pause walkthrough" : "Play walkthrough"}
        </Button>
        <Button variant="outline" size="sm" onClick={() => move(1)}>
          Next phase
        </Button>
      </div>

      <p data-part="note" className="max-w-[75ch] text-sm text-ink-muted">
        {kind === "training" ? (
          <>
            <strong className="font-medium text-ink">Illustration</strong>: the sample problem and
            its tokens, split by hand into word pieces the way a tokenizer splits text, and the
            drawing. <strong className="font-medium text-ink">Measured</strong> from the run: the
            batch size (its settings) and the loss, gradient norm and learning rate of its newest
            step line
            {figures ? ` (step ${figures.step} of ${figures.totalSteps})` : " (none logged yet)"}.
          </>
        ) : (
          <>
            <strong className="font-medium text-ink">Illustration</strong>: the sample problem and
            its answer, split by hand into word pieces, and the scores drawn for the next token; the
            run writes its own answers to its own problems.
            {samples(method) ? " The temperature is the run's own setting." : null}
          </>
        )}
      </p>
    </section>
  );
}

function generationIntro(method: string | null): string {
  if (method === "cotgen")
    return "This run writes step-by-step solutions to training problems, sampling one token at a time; the solutions with the right final number become the training text of the next fine-tune.";
  if (method === "best")
    return "This run scores a finalist: the model with its trained adapter writes an answer one token at a time, always taking the most likely token, and the final number is scored.";
  return "This run scores the model: it writes an answer one token at a time, always taking the most likely token, and the final number is scored.";
}

// --- the facts as text ---------------------------------------------------------------------

interface Facts {
  figures: NewestFigures | null;
  batchSize: number | null;
  temperature: number;
  shape: ModelShape | null;
  layers: number;
  model: string | null;
  method: string | null;
  written: number;
}

function Figure({ name, children }: { name: string; children: ReactNode }) {
  return (
    <span data-figure={name} className="num font-medium text-ink">
      {children}
    </span>
  );
}

function Lead({ children }: { children: ReactNode }) {
  return <p className="m-0 mb-1 font-medium">{children}</p>;
}

function TrainingDetail({ phase, facts }: { phase: string; facts: Facts }) {
  const { figures, batchSize, shape, layers, model } = facts;
  const name = model ? modelName(model) : "the model";
  switch (phase) {
    case "tokenize":
      return (
        <>
          <Lead>Tokenized once, before step 1.</Lead>
          <p className="m-0">
            The whole training set was tokenized once, before step 1: each example's question and
            worked answer became token ids, the end-of-text token was put after the answer so the
            model learns to stop, and the question's tokens were marked "no loss". Each step only
            pads its batch of token ids into a rectangle; no text is tokenized again.
          </p>
        </>
      );
    case "batch":
      return (
        <>
          <Lead>
            Batch size:{" "}
            <Figure name="batch-size">{batchSize === null ? DASH : String(batchSize)}</Figure>
          </Lead>
          <p className="m-0">
            Each step takes that many tokenized examples. They differ in length, so the shorter ones
            are padded on the right with a pad token up to the longest, which makes a rectangle of
            token ids the GPU can work on at once. Pad positions are masked: the model does not look
            at them and they add nothing to the loss.
          </p>
        </>
      );
    case "embed":
      return (
        <>
          <Lead>
            Every token id becomes a vector of{" "}
            {shape ? `${formatCount(shape.hidden)} numbers` : "numbers"}.
          </Lead>
          <p className="m-0">
            The id picks one row of the embedding table, a list of{" "}
            {shape ? formatCount(shape.hidden) : "a few thousand"} numbers for {name}. The table is
            frozen, so the same token gets the same vector at every step; what the vector means next
            depends on the tokens around it.
          </p>
        </>
      );
    case "forward":
      return (
        <>
          <Lead>Forward through all {layers} layers at once.</Lead>
          <p className="m-0">
            The whole padded batch goes through every decoder layer in one pass. In each layer the
            frozen weight matrix W does its usual work and the LoRA adapter adds a small correction,
            B times A applied to the same input. A causal mask lets each token look only at the
            tokens before it, so every position can be predicted in the same pass.
          </p>
        </>
      );
    case "predict":
      return (
        <>
          <Lead>Every answer token must guess the next one.</Lead>
          <p className="m-0">
            The head turns each position's last vector into a score for every token of the
            vocabulary. Training compares those scores with the text shifted by one: at each answer
            position the right guess is the token that comes next, and the last answer token must
            guess the end-of-text token. All answer positions are scored in the same pass.
          </p>
        </>
      );
    case "loss":
      return (
        <>
          <Lead>
            Loss: <Figure name="loss">{figures ? formatLoss(figures.loss) : DASH}</Figure>
          </Lead>
          <p className="m-0">
            The loss is the average, over the scored tokens, of minus the log of the chance the
            model gave the right next token: 0 would mean certainty. Only answer tokens count: the
            question and the padding are masked out, so the model learns to write answers, not to
            repeat questions. This is the newest step line's loss, measured by the run.
          </p>
        </>
      );
    case "backward":
      return (
        <>
          <Lead>
            Gradient norm:{" "}
            <Figure name="grad-norm">{figures ? formatGrad(figures.gradNorm) : DASH}</Figure>
          </Lead>
          <p className="m-0">
            Backpropagation runs from the loss back through the head and every layer, working out
            how much each weight added to the loss. The gradient passes through the layers but stops
            at the frozen weights: they get none and stay as they are, and only the LoRA matrices A
            and B collect one. The gradient norm is its overall size, logged before it is clipped to
            1.
          </p>
        </>
      );
    default:
      return (
        <>
          <Lead>
            Learning rate:{" "}
            <Figure name="learning-rate">
              {figures ? formatRate(figures.learningRate) : DASH}
            </Figure>
          </Lead>
          <p className="m-0">
            AdamW turns each gradient into a small step whose size follows the learning rate on its
            warm-up and decay schedule. Only the LoRA matrices A and B change;{" "}
            {shape
              ? `the ${formatCount(shape.weights)} weights of ${name}`
              : "the model's own weights"}{" "}
            stay exactly as they were. Then the next batch comes, and the eight phases start again.
          </p>
        </>
      );
  }
}

function GenerationDetail({ phase, facts }: { phase: string; facts: Facts }) {
  const { method, temperature, layers, written } = facts;
  const total = WALKTHROUGH_SAMPLE.answer.length;
  switch (phase) {
    case "tokenize":
      return (
        <>
          <Lead>The prompt is tokenized once.</Lead>
          <p className="m-0">
            Before the first answer token, the prompt (the question, after any worked examples the
            run puts before it) is cut into token ids by the same tokenizer as in training. The
            answer starts empty.
          </p>
        </>
      );
    case "forward":
      return (
        <>
          <Lead>
            Forward for answer token {Math.min(written + 1, total)} of {total}.
          </Lead>
          <p className="m-0">
            The prompt and the {written} {written === 1 ? "token" : "tokens"} written so far go
            through all {layers} layers, and the head scores every token of the vocabulary as the
            next one. Earlier positions are not worked out again: their keys and values are kept
            (the KV cache), so each new token costs one more position. No loss and no gradient:
            nothing flows back.
          </p>
        </>
      );
    case "choose":
      return samples(method) ? (
        <>
          <Lead>
            Sampled at temperature{" "}
            <Figure name="temperature">{formatTemperature(temperature)}</Figure>
          </Lead>
          <p className="m-0">
            The scores are divided by the temperature and turned into chances, and the next token is
            drawn at random by those chances. A low temperature keeps close to the top token; a
            higher one tries more varied wording, so the same problem gets different solutions.
          </p>
        </>
      ) : (
        <>
          <Lead>The most likely token is taken.</Lead>
          <p className="m-0">
            The model takes the most likely token, the one with the top score (greedy decoding), so
            the same prompt always gets the same answer.
          </p>
        </>
      );
    case "append":
      return (
        <>
          <Lead>
            Written so far: {written} of {total} tokens.
          </Lead>
          <p className="m-0">
            The chosen token goes on the end of the answer, and the longer text is the input for the
            next token. The model writes one token at a time; it never sees its whole answer before
            it is written.
          </p>
        </>
      );
    case "stop":
      return (
        <>
          <Lead>The answer is complete.</Lead>
          <p className="m-0">
            Writing stops once the answer's "#### &lt;number&gt;" line is complete, or at a new
            "Question:", the end-of-text token or the token limit. The number after #### is the
            answer that is scored.
          </p>
        </>
      );
    default:
      return (
        <>
          <Lead>Kept only when the final number is right.</Lead>
          <p className="m-0">
            The final number is compared with the problem's gold answer. A solution with the right
            number is kept and becomes training text for the next fine-tune; a wrong one is dropped.
          </p>
        </>
      );
  }
}

// --- the drawings ----------------------------------------------------------------------------

const DRAWING_CLASS =
  "wt-drawing mx-auto flex w-full max-w-[66vw] min-w-0 flex-col items-center gap-3 py-2";

function indexStyle(i: number): CSSProperties {
  return { "--i": i } as CSSProperties;
}

function Chip({
  token,
  role,
  i = 0,
  pop = true,
  extra = "",
}: {
  token: string;
  role: "prompt" | "answer" | "pad";
  i?: number;
  /** The chip appears with a short pop when the phase starts. */
  pop?: boolean;
  extra?: string;
}) {
  const classes = ["wt-chip", `wt-chip-${role}`, pop ? "wt-pop" : "", extra].filter(Boolean);
  return (
    <span data-token={token} data-role={role} style={indexStyle(i)} className={classes.join(" ")}>
      {displayToken(token)}
    </span>
  );
}

/** A plain chip without a token marker (for chips that repeat a token already drawn). */
function Mark({ text, kind, i = 0 }: { text: string; kind: string; i?: number }) {
  return (
    <span style={indexStyle(i)} className={`wt-chip wt-chip-${kind}`}>
      {displayToken(text)}
    </span>
  );
}

function Label({ children, orange = false }: { children: ReactNode; orange?: boolean }) {
  return <span className={orange ? "wt-label wt-label-orange" : "wt-label"}>{children}</span>;
}

function Arrow({ dir = "→" }: { dir?: string }) {
  return <span className="wt-arrow">{dir}</span>;
}

function DotColumn({
  i,
  dots = 8,
  orange = false,
}: {
  i: number;
  dots?: number;
  orange?: boolean;
}) {
  return (
    <span className="wt-vec" style={indexStyle(i)}>
      {Array.from({ length: dots }, (_, d) => (
        <span
          key={d}
          className={orange ? "wt-dot wt-dot-orange" : "wt-dot"}
          style={indexStyle(i * 2 + d)}
        />
      ))}
    </span>
  );
}

const DRAWN_LAYERS = 10;

/** Dotted layer blocks, each with its orange LoRA strip; sweeps run over the row. */
function LayerRow({
  sweep,
  lora,
  layers,
  label,
}: {
  sweep: "forward" | "back" | "none";
  lora: "trained" | "glow" | "frozen";
  layers: number;
  label: string;
}) {
  return (
    <span className="flex flex-col items-center gap-1">
      <span className="wt-layers">
        <span className="wt-layer wt-layer-edge">
          <span className="wt-layer-name">embed</span>
        </span>
        {Array.from({ length: DRAWN_LAYERS }, (_, k) => (
          <span
            key={k}
            className="wt-layer"
            style={{ "--i": k, "--n": DRAWN_LAYERS } as CSSProperties}
          >
            <span className={`wt-lora wt-lora-${lora}`} />
          </span>
        ))}
        <span className="wt-layer wt-layer-edge">
          <span className="wt-layer-name">head</span>
        </span>
        {sweep === "forward" ? <span className="wt-sweep wt-sweep-forward" /> : null}
        {sweep === "back" ? <span className="wt-sweep wt-sweep-back" /> : null}
      </span>
      <Label orange={lora !== "frozen"}>{label.replace("{n}", String(layers))}</Label>
    </span>
  );
}

const OTHER_ROWS = [34, 41, 27, 38, 31, 44, 29];

function TrainingDrawing({ phase, facts }: { phase: string; facts: Facts }) {
  const { prompt, answer } = WALKTHROUGH_SAMPLE;
  const { batchSize, layers, figures } = facts;

  if (phase === "tokenize") {
    return (
      <div data-part="drawing" aria-hidden="true" className={DRAWING_CLASS}>
        <span className="wt-text">
          {prompt.join("").replace(/\n/g, " ")}
          <span className="wt-text-answer">{answer.join("").replace(/\n/g, " ")}</span>
        </span>
        <Arrow dir="↓ tokenizer, once" />
        <span className="flex flex-wrap items-start justify-center gap-2">
          <span data-group="prompt" aria-label="question: no loss" className="wt-group">
            <Label>question · no loss</Label>
            <span className="wt-row">
              {prompt.map((t, i) => (
                <Chip key={i} token={t} role="prompt" i={i} />
              ))}
            </span>
          </span>
          <span
            data-group="answer"
            aria-label="answer: scored"
            className="wt-group wt-group-answer"
          >
            <Label orange>answer · scored</Label>
            <span className="wt-row">
              {answer.map((t, i) => (
                <Chip key={i} token={t} role="answer" i={prompt.length + i} />
              ))}
              <Mark text="<eos>" kind="eos" />
            </span>
          </span>
        </span>
        <Label>· marks a leading space, ↵ a new line</Label>
      </div>
    );
  }

  if (phase === "batch") {
    const rows = Math.max(1, Math.min(batchSize ?? 4, 1 + OTHER_ROWS.length));
    const sampleLen = prompt.length + answer.length + 1;
    const lengths = [sampleLen, ...OTHER_ROWS.slice(0, rows - 1)];
    const width = Math.max(...lengths);
    const more = batchSize !== null && batchSize > rows ? batchSize - rows : 0;
    return (
      <div data-part="drawing" aria-hidden="true" className={DRAWING_CLASS}>
        <Label>
          {batchSize === null ? "a batch" : `batch of ${batchSize}`} · padded on the right to the
          longest
        </Label>
        <span className="wt-batch">
          {lengths.map((len, r) => {
            const promptLen = r === 0 ? prompt.length : Math.round(len * 0.55);
            return (
              <span key={r} className="wt-batch-row">
                {Array.from({ length: width }, (_, c) => {
                  if (c >= len)
                    return (
                      <span
                        key={c}
                        data-token="pad"
                        data-role="pad"
                        style={indexStyle(c - len + r)}
                        className="wt-id wt-id-pad wt-pop"
                      />
                    );
                  return (
                    <span key={c} className={c < promptLen ? "wt-id" : "wt-id wt-id-answer"} />
                  );
                })}
              </span>
            );
          })}
        </span>
        <span className="flex flex-wrap justify-center gap-3">
          <Label>■ question ids</Label>
          <Label orange>■ answer ids</Label>
          <Label>□ pad: masked</Label>
          {more > 0 ? <Label>+ {more} more rows</Label> : null}
        </span>
      </div>
    );
  }

  if (phase === "embed") {
    const shown = prompt.slice(2, 9);
    return (
      <div data-part="drawing" aria-hidden="true" className={DRAWING_CLASS}>
        <Label>embedding table · frozen · one row per token id</Label>
        <span className="flex flex-wrap items-start justify-center gap-3">
          {shown.map((t, i) => (
            <span key={i} className="flex flex-col items-center gap-1">
              <Mark text={t} kind="prompt" />
              <Arrow dir="↓" />
              <DotColumn i={i} />
            </span>
          ))}
        </span>
        <Label>one vector per token</Label>
      </div>
    );
  }

  if (phase === "forward") {
    return (
      <div data-part="drawing" aria-hidden="true" className={DRAWING_CLASS}>
        <span className="flex flex-wrap items-center justify-center gap-3">
          <span className="flex gap-1">
            {[0, 1, 2, 3].map((i) => (
              <DotColumn key={i} i={i} dots={7} />
            ))}
          </span>
          <Arrow />
          <LayerRow
            sweep="forward"
            lora="trained"
            layers={layers}
            label="{n} layers · frozen W, LoRA strip on each"
          />
          <Arrow />
          <Label>scores</Label>
        </span>
        <Label>every position at once · each token sees only the tokens before it</Label>
      </div>
    );
  }

  if (phase === "predict") {
    return (
      <div data-part="drawing" aria-hidden="true" className={DRAWING_CLASS}>
        <Label>input token → the next token it must guess (the text shifted by one)</Label>
        <span className="flex flex-wrap justify-center gap-1.5">
          {predictPairs(answer).map((pair, i) => (
            <span
              key={i}
              data-predict=""
              data-input={pair.input}
              data-target={pair.target}
              className="flex flex-col items-center gap-0.5"
            >
              <Mark text={pair.input} kind="answer" />
              <span className="wt-arrow wt-shift" style={indexStyle(i)}>
                ↓
              </span>
              <span className="wt-pop" style={indexStyle(i)}>
                <Mark text={pair.target === EOS_TOKEN ? "<eos>" : pair.target} kind="target" />
              </span>
            </span>
          ))}
        </span>
      </div>
    );
  }

  if (phase === "loss") {
    return (
      <div data-part="drawing" aria-hidden="true" className={DRAWING_CLASS}>
        <span className="flex flex-wrap items-end justify-center gap-2">
          <span className="wt-group wt-muted">
            <Label>question · no loss</Label>
            <span className="wt-row">
              {prompt.slice(-6).map((t, i) => (
                <Mark key={i} text={t} kind="prompt" />
              ))}
            </span>
          </span>
          <span className="wt-group wt-group-answer">
            <Label orange>answer · −log(chance of the right token)</Label>
            <span className="wt-bars">
              {answer.map((t, i) => (
                <span key={i} className="flex flex-col items-center gap-0.5">
                  <span className="wt-bar-track">
                    <span
                      className="wt-bar wt-grow"
                      style={{ ...indexStyle(i), height: `${barHeight(i)}%` }}
                    />
                  </span>
                  <Mark text={t} kind="answer" />
                </span>
              ))}
            </span>
          </span>
        </span>
        <Label orange>
          average over answer tokens = loss {figures ? formatLoss(figures.loss) : DASH}
        </Label>
      </div>
    );
  }

  if (phase === "backward") {
    return (
      <div data-part="drawing" aria-hidden="true" className={DRAWING_CLASS}>
        <span className="flex flex-wrap items-center justify-center gap-3">
          <Label>frozen W: no gradient</Label>
          <Arrow dir="←" />
          <LayerRow
            sweep="back"
            lora="glow"
            layers={layers}
            label="gradient reaches only LoRA A and B"
          />
          <Arrow dir="←" />
          <Label orange>loss</Label>
        </span>
        <Label>gradient norm {figures ? formatGrad(figures.gradNorm) : DASH} · clipped to 1</Label>
      </div>
    );
  }

  return (
    <div data-part="drawing" aria-hidden="true" className={DRAWING_CLASS}>
      <span className="flex flex-wrap items-center justify-center gap-4">
        <span className="flex flex-col items-center gap-1">
          <span className="wt-matrix" />
          <Label>W frozen</Label>
        </span>
        <span className="wt-op">+</span>
        <span className="flex flex-col items-center gap-1">
          <span className="wt-strip-b wt-nudge" />
          <Label orange>B</Label>
        </span>
        <span className="wt-op">×</span>
        <span className="flex flex-col items-center gap-1">
          <span className="wt-strip-a wt-nudge" />
          <Label orange>A</Label>
        </span>
      </span>
      <Label orange>
        A, B ← A, B − step × learning rate {figures ? formatRate(figures.learningRate) : DASH}
      </Label>
    </div>
  );
}

/** Illustrative per-token loss heights: the first words of a step are harder than the rest. */
function barHeight(i: number): number {
  const pattern = [70, 35, 15, 55, 25, 12, 40, 20, 10, 60, 30, 18, 8, 10, 45];
  return pattern[i % pattern.length];
}

const ALTERNATIVES = [" The", " So", "\n", " pens", " 1", " is"];

function GenerationDrawing({ phase, facts }: { phase: string; facts: Facts }) {
  const { prompt, answer, gold } = WALKTHROUGH_SAMPLE;
  const { written, method, temperature, layers } = facts;
  const sampled = samples(method);
  const next = answer[written];

  const textSoFar = (
    <span className="flex flex-wrap items-start justify-center gap-2">
      <span data-group="prompt" aria-label="prompt" className="wt-group">
        <Label>prompt</Label>
        <span className="wt-row">
          {prompt.map((t, i) => (
            <Chip key={i} token={t} role="prompt" i={i} pop={phase === "tokenize"} />
          ))}
        </span>
      </span>
      <span data-group="answer" aria-label="answer so far" className="wt-group wt-group-answer">
        <Label orange>answer so far</Label>
        <span className="wt-row">
          {answer.slice(0, written).map((t, i) => (
            <Chip
              key={i}
              token={t}
              role="answer"
              pop={phase === "append" && i === written - 1}
              extra={phase === "append" && i === written - 1 ? "wt-chip-new" : ""}
            />
          ))}
          {written === 0 ? <span className="wt-label">(empty)</span> : null}
        </span>
      </span>
    </span>
  );

  let part: ReactNode = null;
  if (phase === "tokenize") {
    part = <Label>tokenized once, before the first answer token</Label>;
  } else if (phase === "forward") {
    part = (
      <span className="flex flex-wrap items-center justify-center gap-3">
        <Arrow dir="↓" />
        <LayerRow
          sweep="forward"
          lora="frozen"
          layers={layers}
          label={
            method === "best"
              ? "{n} layers · adapter included · nothing trained"
              : "{n} layers · weights frozen"
          }
        />
        <Arrow />
        <Label>scores for the next token</Label>
      </span>
    );
  } else if (phase === "choose" && next !== undefined) {
    const others = ALTERNATIVES.filter((t) => t !== next).slice(0, 3);
    const shares = [62, 18, 12, 8];
    part = (
      <span className="flex flex-col items-center gap-1">
        <Label orange>
          {sampled
            ? `sampled at temperature ${formatTemperature(temperature)}`
            : "most likely token taken"}
        </Label>
        {[next, ...others].map((t, k) => (
          <span key={k} className="wt-candidate">
            <Mark text={t} kind={k === 0 ? "target" : "prompt"} />
            <span className="wt-cand-track">
              <span
                className={k === 0 ? "wt-cand wt-cand-top wt-grow-x" : "wt-cand wt-grow-x"}
                style={{ ...indexStyle(k), width: `${shares[k]}%` }}
              />
            </span>
            <span className="wt-label">{k === 0 ? "← chosen" : ""}</span>
          </span>
        ))}
      </span>
    );
  } else if (phase === "append") {
    part = <Label orange>+1 token · the longer text goes back in</Label>;
  } else if (phase === "stop") {
    part = <Label orange>■ stop: the #### line is complete</Label>;
  } else if (phase === "check") {
    part = (
      <span className="flex flex-wrap items-center justify-center gap-2">
        <Mark text="####" kind="answer" />
        <Mark text={answer[answer.length - 1]} kind="answer" />
        <span className="wt-op">=</span>
        <Label>gold {gold}</Label>
        <span className="wt-op wt-ok wt-pop">✓ kept</span>
      </span>
    );
  }

  return (
    <div data-part="drawing" aria-hidden="true" className={DRAWING_CLASS}>
      {textSoFar}
      {part}
    </div>
  );
}
