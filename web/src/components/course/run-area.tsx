import { useState } from "react";
import { Link } from "react-router";

import { Button } from "@/components/ui/button";
import { toApiError, type CourseRun, type Status } from "@/lib/api";
import { useApi } from "@/lib/api-context";
import { RUN_STATE_WORDS } from "@/lib/course";
import { formatMinutes, formatPct } from "@/lib/format";
import { cn } from "@/lib/utils";

/** "about N min on the GPU" with "(estimate, not measured yet)" when unmeasured (AC12.5.4). */
function estimateText(run: CourseRun): string {
  const base = `about ${run.estimate_minutes} min on the GPU`;
  return run.estimate_measured ? base : `${base} (estimate, not measured yet)`;
}

function resultText(run: CourseRun): string | null {
  if (run.state !== "finished") return null;
  const minutes = run.minutes === null ? "" : `, ${formatMinutes(run.minutes)} min`;
  if (run.accuracy !== null) {
    const interval =
      run.interval_low !== null && run.interval_high !== null
        ? ` (interval ${formatPct(run.interval_low)} to ${formatPct(run.interval_high)})`
        : "";
    return `${formatPct(run.accuracy)} right on 100 problems${interval}${minutes}`;
  }
  if (run.value !== null) return `${run.metric ?? "result"} ${run.value}${minutes}`;
  return `Finished${minutes}`;
}

function RunRow({ run }: { run: CourseRun }) {
  const result = resultText(run);
  return (
    <li
      data-run={run.run}
      className="flex min-w-0 flex-col gap-1 rounded-sm border-[0.5px] border-hairline bg-panel p-3 text-sm"
    >
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="num break-all text-ink">{run.model}</span>
        <span
          className={cn(
            "num text-xs",
            run.state === "running" && "text-orange",
            run.state === "failed" && "text-danger",
            run.state === "finished" && "text-ok",
            (run.state === "not-run" || run.state === "queued" || run.state === "stopped") &&
              "text-ink-muted",
          )}
        >
          {RUN_STATE_WORDS[run.state]}
        </span>
      </div>
      <p className="text-ink-muted">{run.changes}</p>
      <p className="num text-xs text-ink-muted">{estimateText(run)}</p>
      {result ? <p className="num text-ink">{result}</p> : null}
      {run.state === "running" ? (
        <Link to="/training" className="self-start rounded-sm text-orange underline">
          Watch it on the Training page
        </Link>
      ) : null}
    </li>
  );
}

export interface GpuRunsProps {
  stepId: string;
  runs: CourseRun[];
  status: Status | null;
  notice: string | null;
  /** Called after the run request answered, so the step is read again. */
  onChanged(): void;
}

/** The run area of a gpu step: each run, the GPU holder, "Run this step" and its refusals. */
export function GpuRuns({ stepId, runs, status, notice, onChanged }: GpuRunsProps) {
  const api = useApi();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const active = runs.some((r) => r.state === "queued" || r.state === "running");
  const own = new Set(runs.map((r) => r.attempt_id).filter((id): id is string => id !== null));
  const holder =
    status !== null &&
    status.status === "RUNNING" &&
    status.run_id !== null &&
    !own.has(status.run_id)
      ? status.run_id
      : null;

  const start = async () => {
    setError(null);
    setBusy(true);
    try {
      await api.runCourseStep(stepId);
    } catch (e) {
      setError(toApiError(e).message);
    } finally {
      setBusy(false);
      onChanged();
    }
  };

  return (
    <div className="flex min-w-0 flex-col gap-3">
      {holder !== null ? (
        <p role="status" className="max-w-[75ch] text-sm text-ink-muted">
          <span>A run holds the GPU now: </span>
          <span className="num text-ink">{holder}</span>
          <span>. The runs of this step wait in the queue until it ends.</span>
        </p>
      ) : null}
      <ul className="flex list-none flex-col gap-2">
        {runs.map((run) => (
          <RunRow key={run.run} run={run} />
        ))}
      </ul>
      {notice ? (
        <p role="status" className="max-w-[75ch] text-sm text-ink">
          {notice}
        </p>
      ) : null}
      <div className="flex flex-col items-start gap-2">
        <Button disabled={busy || active} onClick={() => void start()}>
          Run this step
        </Button>
        {active ? (
          <p className="text-sm text-ink-muted">
            This step has runs queued or running; they are shown above.
          </p>
        ) : null}
        {error ? (
          <p role="alert" className="max-w-[75ch] text-sm text-danger">
            {error}
          </p>
        ) : null}
      </div>
    </div>
  );
}
