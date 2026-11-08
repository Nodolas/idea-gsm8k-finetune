/**
 * The training page (refined mockups, Screen 3; US4.5, US3.5): the hourglass band, the curves
 * panel, W4's run controls, and past runs. It opens the C7 stream once (`useLiveStream`), holds
 * the status, the queue and every line per run, and reads data only through `useApi()` (ADR-008).
 */
import { useEffect, useState, type ReactNode } from "react";

import { CurvesPanel } from "@/components/curves-panel";
import { FailurePanel } from "@/components/failure-panel";
import { FinetuneView } from "@/components/finetune-view";
import { HourglassBand, type BandStatus } from "@/components/hourglass-band";
import { PastRunsList, statusWord } from "@/components/past-runs-list";
import { RunControls } from "@/components/run-controls";
import { toApiError, type MetricsLine, type Run, type Status } from "@/lib/api";
import { useApi } from "@/lib/api-context";
import { formatPct, modelName } from "@/lib/format";
import { useLiveStream } from "@/lib/live-stream";
import { useAsync } from "@/lib/queries";

const NO_LINES: readonly MetricsLine[] = [];

type Phase = "running" | "finished" | "stopped" | "failed" | "idle";

/** The run the band is about: the active run, else the last one (C6: `last_run`). */
function phaseOf(status: Status): { phase: Phase; run: Status | null } {
  switch (status.status) {
    case "RUNNING":
      return { phase: "running", run: status };
    case "STOPPED":
      return { phase: "stopped", run: status };
    case "FAILED":
      return { phase: "failed", run: status };
    case "FINISHED":
      return { phase: "finished", run: status };
    default: {
      const last = status.last_run;
      if (last?.status === "FINISHED") return { phase: "finished", run: last };
      if (last?.status === "STOPPED") return { phase: "stopped", run: last };
      if (last?.status === "FAILED") return { phase: "failed", run: last };
      return { phase: "idle", run: null };
    }
  }
}

const METHOD_NAMES: Record<string, string> = {
  sft: "SFT",
  grpo: "GRPO",
  terse: "SFT (terse)",
  optuna: "SFT (Optuna)",
  base: "Evaluation",
  best: "Finalist evaluation",
};

function methodName(method: string | null | undefined): string | null {
  if (!method) return null;
  return METHOD_NAMES[method] ?? method.toUpperCase();
}

/** The run list, read again whenever `key` changes; the last list stays on screen meanwhile. */
function useRunList(key: string): { runs: Run[] | null; error: string | null } {
  const api = useApi();
  const [state, setState] = useState<{ runs: Run[] | null; error: string | null }>({
    runs: null,
    error: null,
  });
  useEffect(() => {
    let alive = true;
    api.listRuns().then(
      (list) => {
        if (alive) setState({ runs: list.runs, error: null });
      },
      (error: unknown) => {
        if (alive) setState({ runs: null, error: toApiError(error).message });
      },
    );
    return () => {
      alive = false;
    };
  }, [api, key]);
  return state;
}

interface BandView {
  status: BandStatus | null;
  runId: string | null;
  fraction?: number;
  message?: ReactNode;
  action?: ReactNode;
}

export function TrainingPage() {
  const api = useApi();
  const live = useLiveStream();
  const [changes, setChanges] = useState(0);
  const [viewing, setViewing] = useState<string | null>(null);
  const [returnTo, setReturnTo] = useState<{ runId: string; n: number } | null>(null);

  const status = live.status;
  const { phase, run: current } = status ? phaseOf(status) : { phase: null, run: null };
  const currentId = current?.run_id ?? null;

  // A run starting or ending changes the list (and a confirm or removal changes the queue).
  const statusKey = status
    ? `${status.status}:${status.run_id ?? ""}:${status.last_run?.status ?? ""}:${status.last_run?.run_id ?? ""}`
    : "";
  const list = useRunList(`${statusKey}|${changes}`);
  const runs = list.runs;
  const runOf = (runId: string | null) =>
    runId === null ? undefined : runs?.find((r) => r.run_id === runId);

  const lines = currentId ? (live.linesByRun[currentId] ?? NO_LINES) : NO_LINES;
  const last = lines.length > 0 ? lines[lines.length - 1] : null;
  const currentRun = runOf(currentId);
  const stepText = last ? `at step ${last.step} / ${last.total_steps}` : null;

  let band: BandView;
  if (status === null) {
    band = {
      status: null,
      runId: null,
      message: live.statusError ? live.statusError.message : "Reading the run status…",
    };
  } else if (phase === "running") {
    band = {
      status: "RUNNING",
      runId: currentId,
      message: last ? null : "Waiting for first step...",
    };
  } else if (phase === "finished") {
    const dev = currentRun?.dev_accuracy;
    band = {
      status: "IDLE",
      runId: null,
      fraction: 1,
      message: `last run ${currentId ?? ""} finished${
        dev !== null && dev !== undefined ? ` · dev ${formatPct(dev)}` : ""
      }`,
    };
  } else if (phase === "stopped") {
    band = {
      status: "STOPPED",
      runId: currentId,
      message: [stepText, "no score recorded"].filter(Boolean).join(" · "),
    };
  } else if (phase === "failed") {
    const reason = current?.reason ?? "The run failed without a reason";
    band = {
      status: "FAILED",
      runId: currentId,
      message: [stepText, reason].filter(Boolean).join(" · "),
      action: currentId ? (
        <FailurePanel runId={currentId} reason={reason} lines={current?.log_tail ?? []} />
      ) : null,
    };
  } else {
    band = {
      status: "IDLE",
      runId: null,
      message:
        runs === null
          ? null
          : runs.length === 0
            ? "No run yet. Set the dials and press Start run."
            : "No run is active.",
    };
  }

  // The run opened from Past runs: its lines, or the live ones when it is the active run.
  const viewingLive = viewing !== null && viewing === currentId && phase === "running";
  const past = useAsync(
    () => (viewing === null || viewingLive ? Promise.resolve(null) : api.getMetrics(viewing)),
    [api, viewing, viewingLive],
  );

  // "Back to live" returns focus to the Open control it came from (interaction-spec).
  useEffect(() => {
    if (returnTo === null) return;
    document
      .querySelector<HTMLElement>(`[data-open-run=${JSON.stringify(returnTo.runId)}]`)
      ?.focus();
  }, [returnTo]);

  const onChanged = () => {
    live.refresh();
    setChanges((n) => n + 1);
  };

  let curves: ReactNode;
  if (viewing !== null) {
    const pastLines = viewingLive
      ? lines
      : past.state === "ready" && past.data
        ? past.data.lines
        : NO_LINES;
    curves = (
      <CurvesPanel
        mode="past"
        runId={viewing}
        statusWord={statusWord(runOf(viewing)?.status ?? null)}
        lines={pastLines}
        loading={!viewingLive && past.state === "loading"}
        error={!viewingLive && past.state === "error" ? past.error.message : null}
        onBack={() => {
          setReturnTo((prev) => ({ runId: viewing, n: (prev?.n ?? 0) + 1 }));
          setViewing(null);
        }}
      />
    );
  } else {
    curves = (
      <CurvesPanel
        mode="live"
        runId={currentId}
        lines={lines}
        emptyText={
          phase === "running"
            ? "The curves appear with the first metrics line."
            : currentId
              ? "Open a past run below to see its curves."
              : "No curves yet."
        }
      />
    );
  }

  // The fine-tuning view follows the run the page shows: the one opened from Past runs, else the
  // active or last run. It reads the live run's lines here and any other run's from the service.
  const shownId = viewing ?? currentId;
  const shownRun = runOf(shownId);
  const shownLive = viewing === null ? phase === "running" : viewingLive;

  return (
    <div className="mx-auto flex w-full max-w-[1280px] flex-col gap-6 px-6 py-6">
      <h1>Training</h1>

      <HourglassBand
        status={band.status}
        step={last?.step ?? 0}
        totalSteps={last?.total_steps ?? 0}
        runId={band.runId}
        method={phase === "running" ? methodName(currentRun?.method) : null}
        model={phase === "running" && currentRun?.model ? modelName(currentRun.model) : null}
        elapsedS={last?.elapsed_s ?? null}
        etaS={last?.eta_s ?? null}
        lastUpdate={live.lastUpdate}
        paused={live.paused}
        fraction={band.fraction}
        message={band.message}
        action={band.action}
      />

      <FinetuneView
        runId={shownId}
        method={shownRun?.method ?? null}
        model={shownRun?.model ?? null}
        liveLines={shownId === currentId ? lines : NO_LINES}
        live={shownLive}
        loading={status === null}
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1.8fr)_minmax(0,1fr)]">
        {curves}
        <RunControls status={status} queue={live.queue} onChanged={onChanged} />
      </div>

      <PastRunsList runs={runs} error={list.error} onOpen={setViewing} />
    </div>
  );
}
