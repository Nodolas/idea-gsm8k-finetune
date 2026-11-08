import { CircleAlertIcon, RotateCwIcon } from "lucide-react";

import {
  AnswerLengthPanel,
  ExamplesPanel,
  FlipsPanel,
  GenerationPanel,
  ScoreTable,
  SummaryPanel,
} from "@/components/reasoning-panels";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { ApiError, Reasoning } from "@/lib/api";
import { modelName } from "@/lib/format";
import { useReasoning } from "@/lib/queries";

const EMPTY_TEXT = "No self-taught chain-of-thought run yet";

/** An error said in words, naming the file when the service names one (as on Scores). */
function errorText(error: ApiError): string {
  if (error.file && !error.message.includes(error.file)) return `${error.message}: ${error.file}`;
  return error.message;
}

function LoadingRows() {
  return (
    <div className="flex flex-col gap-2" aria-busy="true">
      <span className="sr-only">Loading the comparison…</span>
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} className="h-8 w-full bg-panel" />
      ))}
    </div>
  );
}

function ErrorState({ error, onRetry }: { error: ApiError; onRetry(): void }) {
  return (
    <div className="flex flex-col items-start gap-3">
      <p role="alert" className="flex items-start gap-2 text-sm text-danger">
        <CircleAlertIcon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
        <span>{errorText(error)}</span>
      </p>
      <Button variant="outline" size="sm" onClick={onRetry}>
        <RotateCwIcon aria-hidden="true" />
        Retry
      </Button>
    </div>
  );
}

/** No self-taught run yet: say so, then show the base and reference figures that exist. */
function EmptyState({ data }: { data: Reasoning }) {
  const existing = data.roles.filter((r) => r.role !== "selfcot" && r.run_id !== null);
  const withLengths = existing.filter((r) => r.mean_lines !== null || r.mean_words !== null);
  return (
    <>
      <div className="flex flex-col gap-1">
        <p className="text-ink">{EMPTY_TEXT}.</p>
        <p className="text-sm text-ink-muted">
          It takes two runs started from the command line: generating the model&apos;s own
          solutions, then training on them.
          {existing.length === 0 && " There is no base or reference fine-tune dev run yet either."}
        </p>
      </div>
      {existing.length > 0 && <ScoreTable roles={existing} />}
      {data.flips.length > 0 && <FlipsPanel flips={data.flips} />}
      {withLengths.length > 0 && <AnswerLengthPanel roles={withLengths} />}
    </>
  );
}

/** The full comparison: scores, the summary, flips, answer length, generation and examples. */
function Comparison({ data }: { data: Reasoning }) {
  return (
    <>
      <ScoreTable roles={data.roles} />
      <SummaryPanel summary={data.summary} />
      <FlipsPanel flips={data.flips} />
      <AnswerLengthPanel roles={data.roles} />
      <GenerationPanel generation={data.generation} error={data.generation_error} />
      <ExamplesPanel examples={data.examples} />
    </>
  );
}

/**
 * The Reasoning page (US10.4): how self-taught chain of thought moved the dev score against the
 * base model and the reference fine-tune, read from `GET /reasoning` only.
 */
export function ReasoningPage() {
  const query = useReasoning();

  let body;
  if (query.state === "loading") body = <LoadingRows />;
  else if (query.state === "error")
    body = <ErrorState error={query.error} onRetry={query.reload} />;
  else if (!query.data.available) body = <EmptyState data={query.data} />;
  else body = <Comparison data={query.data} />;

  return (
    <div className="flex w-full flex-col gap-6 px-[var(--gutter)] py-8">
      <div className="flex max-w-[75ch] flex-col gap-2">
        <h1 className="text-[28px] font-semibold">Reasoning</h1>
        <p className="text-ink">
          Self-taught chain of thought lets the model learn from its own reasoning. It writes
          several step-by-step solutions to each training problem, keeps one that reaches the right
          answer, and is then fine-tuned on those kept solutions. The reference fine-tune learns
          from the human-written GSM8K solutions instead. Both are scored on the same dev problems
          as the base model.
        </p>
        {query.state === "ready" && (
          <p className="font-mono text-xs text-muted-foreground">
            {modelName(query.data.model)} · dev split
          </p>
        )}
      </div>
      {body}
    </div>
  );
}
