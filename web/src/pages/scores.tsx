import { CircleAlertIcon, RotateCwIcon } from "lucide-react";
import { useId, useMemo, useState } from "react";
import { Link } from "react-router";

import { CompareView } from "@/components/compare-view";
import { ScoresTable } from "@/components/scores-table";
import { TestSplitDialog } from "@/components/test-split-dialog";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { toApiError, type ApiError, type ConfirmResult, type Run } from "@/lib/api";
import { useApi } from "@/lib/api-context";
import { shortModel } from "@/lib/format";
import { useFinalists, useRuns } from "@/lib/queries";
import { isScored, rankRuns } from "@/lib/ranking";

const LABEL = "font-mono text-[10.5px] uppercase tracking-[0.18em] text-muted-foreground";
const SELECT =
  "h-8 rounded-sm border border-hairline bg-panel px-2 font-mono text-sm text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange";

/** An error said in words, naming the file when the service names one (AC4.3.4). */
function errorText(error: ApiError): string {
  if (error.file && !error.message.includes(error.file)) return `${error.message}: ${error.file}`;
  return error.message;
}

function ErrorLine({ children }: { children: string }) {
  return (
    <p role="alert" className="flex items-start gap-2 text-sm text-danger">
      <CircleAlertIcon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      <span>{children}</span>
    </p>
  );
}

function LoadingRows() {
  return (
    <div className="flex flex-col gap-2" aria-busy="true">
      <span className="sr-only">Loading runs…</span>
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} className="h-8 w-full bg-panel" />
      ))}
    </div>
  );
}

const NO_RUNS: Run[] = [];

function distinct(values: Array<string | null>): string[] {
  return [...new Set(values.filter((v): v is string => v !== null && v !== ""))].sort();
}

/** "1 malformed row in results/runs.csv was skipped" (AC3.1.3). */
function skippedText(count: number): string {
  return count === 1
    ? "1 malformed row in results/runs.csv was skipped"
    : `${count} malformed rows in results/runs.csv were skipped`;
}

/**
 * The scores page (mockups.md Screen 2; US4.3, US4.4, US3.6): runs ranked by dev accuracy with
 * each model's baseline first, filters, finalist marks, the test-split dialog for finalists and
 * the compare panel for two picked runs.
 */
export function ScoresPage() {
  const api = useApi();
  const runs = useRuns();
  const finalistsQuery = useFinalists();
  const [model, setModel] = useState("");
  const [method, setMethod] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  const [pickRefused, setPickRefused] = useState(false);
  const [compared, setCompared] = useState<[string, string] | null>(null);
  const [finalistOverride, setFinalistOverride] = useState<string[] | null>(null);
  const [finalistError, setFinalistError] = useState<string | null>(null);
  const [testTarget, setTestTarget] = useState<Run | null>(null);
  const [started, setStarted] = useState<string | null>(null);
  const ids = useId();
  const hintId = `${ids}-compare-hint`;

  const allRuns = runs.state === "ready" ? runs.data.runs : NO_RUNS;
  const scored = useMemo(() => allRuns.filter(isScored), [allRuns]);
  const { baselines, ranked } = useMemo(
    () => rankRuns(allRuns, { model: model || null, method: method || null }),
    [allRuns, model, method],
  );

  let finalists: string[];
  if (finalistOverride !== null) finalists = finalistOverride;
  else if (finalistsQuery.state === "ready") finalists = finalistsQuery.data;
  else finalists = allRuns.filter((r) => r.finalist).map((r) => r.run_id);

  const togglePick = (runId: string) => {
    if (picked.includes(runId)) {
      setPicked(picked.filter((id) => id !== runId));
      setPickRefused(false);
    } else if (picked.length >= 2) {
      setPickRefused(true);
    } else {
      setPicked([...picked, runId]);
      setPickRefused(false);
    }
  };

  const toggleFinalist = async (runId: string) => {
    setFinalistError(null);
    try {
      const next = finalists.includes(runId)
        ? await api.unmarkFinalist(runId)
        : await api.markFinalist(runId);
      setFinalistOverride(next);
    } catch (thrown: unknown) {
      setFinalistError(errorText(toApiError(thrown)));
    }
  };

  const onStarted = (result: ConfirmResult) => {
    const where =
      result.state === "queued"
        ? `queued${result.position !== null ? ` at position ${result.position}` : ""}`
        : "started";
    setStarted(`Test-split evaluation ${result.attempt_id} ${where}.`);
    setTestTarget(null);
  };

  const clearFilters = () => {
    setModel("");
    setMethod("");
  };

  const runById = (id: string) => allRuns.find((r) => r.run_id === id);
  const compareA = compared ? runById(compared[0]) : undefined;
  const compareB = compared ? runById(compared[1]) : undefined;
  const filtered = model !== "" || method !== "";

  let hint = "";
  if (pickRefused) hint = "Two runs are already picked. Unpick one first.";
  else if (picked.length < 2) hint = "Pick two runs to compare";

  let body;
  if (runs.state === "loading") {
    body = <LoadingRows />;
  } else if (runs.state === "error") {
    body = (
      <div className="flex flex-col items-start gap-3">
        <ErrorLine>{errorText(runs.error)}</ErrorLine>
        <Button variant="outline" size="sm" onClick={runs.reload}>
          <RotateCwIcon aria-hidden="true" />
          Retry
        </Button>
      </div>
    );
  } else if (scored.length === 0) {
    body = (
      <p className="text-sm">
        No scored runs yet. Run a baseline from the{" "}
        <Link to="/training" className="underline underline-offset-4 hover:text-orange">
          training page
        </Link>
        .
      </p>
    );
  } else {
    body = (
      <>
        {runs.data.skipped_rows > 0 && (
          <p className="text-sm text-muted-foreground">{skippedText(runs.data.skipped_rows)}</p>
        )}
        {finalistError !== null && <ErrorLine>{finalistError}</ErrorLine>}
        {finalistsQuery.state === "error" && (
          <ErrorLine>{errorText(finalistsQuery.error)}</ErrorLine>
        )}
        <ScoresTable
          baselines={baselines}
          ranked={ranked}
          finalists={finalists}
          picked={picked}
          onPick={togglePick}
          onToggleFinalist={(runId) => void toggleFinalist(runId)}
          onScoreOnTest={(run) => {
            setStarted(null);
            setTestTarget(run);
          }}
        />
        {filtered && ranked.length === 0 && (
          <div className="flex items-center gap-3 text-sm">
            <p>No runs match these filters.</p>
            <Button variant="outline" size="sm" onClick={clearFilters}>
              Clear filters
            </Button>
          </div>
        )}
        <p className="font-mono text-xs text-muted-foreground">
          <span aria-hidden="true">★</span> = finalist
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="outline"
            disabled={picked.length !== 2}
            aria-describedby={hint ? hintId : undefined}
            onClick={() => {
              if (picked.length === 2) setCompared([picked[0], picked[1]]);
            }}
          >
            Compare selected ({picked.length})
          </Button>
          {hint && (
            <p id={hintId} className="text-sm text-muted-foreground">
              {hint}
            </p>
          )}
        </div>
        {started !== null && (
          <p role="status" className="text-sm">
            {started}
          </p>
        )}
        {compareA && compareB && (
          <CompareView runA={compareA} runB={compareB} onClose={() => setCompared(null)} />
        )}
        {testTarget !== null && (
          <TestSplitDialog
            key={testTarget.run_id}
            finalist={testTarget}
            onClose={() => setTestTarget(null)}
            onStarted={onStarted}
          />
        )}
      </>
    );
  }

  const models = distinct(scored.map((r) => r.model));
  const methods = distinct(scored.map((r) => r.method));

  return (
    <div className="mx-auto flex w-full max-w-[1280px] flex-col gap-6 px-6 py-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-[28px] font-semibold">Highest scores</h1>
          <p className="text-sm text-muted-foreground">
            Ranked by dev accuracy. Gain is against the same model&apos;s baseline.
          </p>
        </div>
        {runs.state === "ready" && scored.length > 0 && (
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2">
              <span className={LABEL}>Model</span>
              <select
                className={SELECT}
                value={model}
                onChange={(event) => setModel(event.target.value)}
              >
                <option value="">All</option>
                {models.map((m) => (
                  <option key={m} value={m}>
                    {shortModel(m)}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex items-center gap-2">
              <span className={LABEL}>Method</span>
              <select
                className={SELECT}
                value={method}
                onChange={(event) => setMethod(event.target.value)}
              >
                <option value="">All</option>
                {methods.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}
      </div>
      <section aria-labelledby={`${ids}-runs`} className="flex flex-col gap-4">
        <h2 id={`${ids}-runs`} className={LABEL}>
          Ranked runs
        </h2>
        {body}
      </section>
    </div>
  );
}
