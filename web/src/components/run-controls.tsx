/**
 * The training page's run controls (US4.6): the dials panel (h2 "Dials"), Start ("Start run", or
 * "Add to queue" while a run is active) and Stop, the Confirm run and Stop run dialogs, the
 * "Queued runs" list and the page's only polite status line. Dials come from `GET /dials` and are
 * checked on blur with `checkDial`; the service checks them again in its check step (US3.2).
 */
import { CircleAlert } from "lucide-react";
import { useCallback, useId, useRef, useState } from "react";

import { ConfirmRunDialog } from "@/components/confirm-run-dialog";
import { DialsPanel, dialUsed, rawOf, type RunMethod } from "@/components/dials-panel";
import { QueuedRuns } from "@/components/queued-runs";
import { StopRunDialog } from "@/components/stop-run-dialog";
import { Button } from "@/components/ui/button";
import {
  toApiError,
  type CheckedRun,
  type DialSpec,
  type QueueEntry,
  type RunRequest,
  type Status,
} from "@/lib/api";
import { useApi } from "@/lib/api-context";
import { checkDial } from "@/lib/dials";
import { useDials } from "@/lib/queries";

/** The most runs that may wait in the queue (C3, AC3.7.3). */
export const QUEUE_LIMIT = 10;

export interface RunControlsProps {
  status: Status | null;
  queue: QueueEntry[];
  /** Called after a run was started, queued, stopped or removed, so the page reads again. */
  onChanged(): void;
}

/** The polite status line: "Run q06-sft-dev-3 is running", "stopped", "failed: <reason>". */
export function statusLine(status: Status | null): string {
  if (status === null) return "Reading the run status…";
  const reason = status.reason ? `: ${status.reason}` : "";
  switch (status.status) {
    case "RUNNING":
      return status.run_id ? `Run ${status.run_id} is running` : "A run is running";
    case "STOPPED":
      return status.run_id ? `Run ${status.run_id} stopped` : "The last run stopped";
    case "FAILED":
      return status.run_id
        ? `Run ${status.run_id} failed${reason}`
        : `The last run failed${reason}`;
    case "FINISHED":
      return status.run_id ? `Run ${status.run_id} finished` : "The last run finished";
    case "IDLE": {
      const last = status.last_run;
      if (last?.run_id) {
        const word =
          last.status === "FAILED"
            ? `failed${last.reason ? `: ${last.reason}` : ""}`
            : last.status === "STOPPED"
              ? "stopped"
              : "finished";
        return `No run is active · last run ${last.run_id} ${word}`;
      }
      return "No run is active";
    }
    default:
      return "Run status unknown";
  }
}

type Values = Record<string, string>;
type Errors = Record<string, string>;

/** The C2 request for the chosen method, or the message of each dial that fails its check. */
function buildRequest(
  dials: DialSpec[],
  method: RunMethod,
  values: Values,
): { ok: true; request: RunRequest } | { ok: false; errors: Errors } {
  const request: Record<string, string | number> = { method, split: "dev" };
  const errors: Errors = {};
  for (const spec of dials) {
    if (!dialUsed(method, spec.name)) continue;
    const result = checkDial(spec, values[spec.name] ?? rawOf(spec.default));
    if (result.ok) request[spec.name] = result.value;
    else errors[spec.name] = result.message;
  }
  if (Object.keys(errors).length > 0) return { ok: false, errors };
  return { ok: true, request: request as RunRequest };
}

export function RunControls({ status, queue, onChanged }: RunControlsProps) {
  const api = useApi();
  const dials = useDials();
  const headingId = useId();

  const [method, setMethod] = useState<RunMethod>("sft");
  const [values, setValues] = useState<Values>({});
  const [errors, setErrors] = useState<Errors>({});
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [checked, setChecked] = useState<CheckedRun | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmKey, setConfirmKey] = useState(0);

  const [stopTarget, setStopTarget] = useState<string | null>(null);
  const [stopOpen, setStopOpen] = useState(false);
  const [stopKey, setStopKey] = useState(0);

  const startRef = useRef<HTMLButtonElement>(null);
  const stopRef = useRef<HTMLButtonElement>(null);

  const active = status?.status === "RUNNING";
  const activeRunId = active ? (status?.run_id ?? null) : null;
  const queueFull = queue.length >= QUEUE_LIMIT;
  const specs = dials.state === "ready" ? dials.data : [];
  const invalid = specs.some((spec) => dialUsed(method, spec.name) && errors[spec.name]);
  const startDisabled = dials.state !== "ready" || invalid || queueFull;
  const startLabel = active ? "Add to queue" : "Start run";

  const setError = (name: string, message: string | null) =>
    setErrors((current) => {
      const next = { ...current };
      if (message === null) delete next[name];
      else next[name] = message;
      return next;
    });

  const onChange = (name: string, raw: string) => {
    setValues((current) => ({ ...current, [name]: raw }));
    setCheckError(null);
    const spec = specs.find((s) => s.name === name);
    // A select can only hold an allowed value: check it at once.
    if (spec?.kind === "select") {
      const result = checkDial(spec, raw);
      setError(name, result.ok ? null : result.message);
    }
  };

  const onBlur = (name: string) => {
    const spec = specs.find((s) => s.name === name);
    if (!spec) return;
    const result = checkDial(spec, values[name] ?? rawOf(spec.default));
    setError(name, result.ok ? null : result.message);
  };

  const start = async () => {
    if (startDisabled || checking) return;
    const built = buildRequest(specs, method, values);
    if (!built.ok) {
      setErrors((current) => ({ ...current, ...built.errors }));
      return;
    }
    setChecking(true);
    setCheckError(null);
    try {
      const answer = await api.checkRun(built.request);
      setChecked(answer);
      setConfirmKey((key) => key + 1);
      setConfirmOpen(true);
    } catch (failure: unknown) {
      const error = toApiError(failure);
      if (
        error.code === "invalid_dial" &&
        error.field &&
        specs.some((s) => s.name === error.field)
      ) {
        setError(error.field, error.message);
      } else {
        setCheckError(error.message);
      }
    } finally {
      setChecking(false);
    }
  };

  const confirm = async () => {
    if (checked === null) return;
    const result = await api.confirmRun(checked.check_id);
    setConfirmOpen(false);
    setNotice(
      result.state === "queued"
        ? `${result.attempt_id} added to the queue${
            result.position === null ? "" : ` at position ${result.position}`
          }`
        : `${result.attempt_id} started`,
    );
    onChanged();
  };

  const openStop = () => {
    if (!activeRunId) return;
    setStopTarget(activeRunId);
    setStopKey((key) => key + 1);
    setStopOpen(true);
  };

  const stop = async () => {
    await api.stop();
    setStopOpen(false);
    setNotice(stopTarget ? `Stop requested for ${stopTarget}` : null);
    onChanged();
  };

  const closeStop = (ended: boolean) => {
    setStopOpen(false);
    if (ended) onChanged();
  };

  const removeQueued = async (attemptId: string) => {
    await api.removeQueued(attemptId);
    setNotice(`${attemptId} removed from the queue`);
    onChanged();
  };

  const focusStart = useCallback(() => startRef.current?.focus(), []);

  let blockedReason: string | null = null;
  if (dials.state === "error") blockedReason = dials.error.message;
  else if (queueFull) blockedReason = `The queue is full (${QUEUE_LIMIT} waiting)`;
  else if (invalid) blockedReason = "Fix the highlighted dial to start";

  return (
    <>
      <section aria-labelledby={headingId} className="grid gap-4">
        <h2
          id={headingId}
          className="font-mono text-[10.5px] tracking-[0.18em] text-muted-foreground uppercase"
        >
          Dials
        </h2>

        <form
          noValidate
          className="grid gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            void start();
          }}
        >
          {dials.state === "loading" && (
            <p className="text-sm text-muted-foreground">Loading the dials…</p>
          )}
          {dials.state === "ready" && (
            <DialsPanel
              dials={specs}
              method={method}
              values={values}
              errors={errors}
              onMethodChange={(next) => {
                setMethod(next);
                setCheckError(null);
              }}
              onChange={onChange}
              onBlur={onBlur}
            />
          )}

          <div className="flex flex-wrap gap-2">
            <Button ref={startRef} type="submit" disabled={startDisabled} aria-busy={checking}>
              {startLabel}
            </Button>
            <Button
              ref={stopRef}
              type="button"
              variant="outline"
              disabled={!active}
              onClick={openStop}
            >
              Stop
            </Button>
          </div>
        </form>

        {activeRunId && (
          <p className="font-mono text-xs text-muted-foreground">Runs after {activeRunId}.</p>
        )}

        {blockedReason !== null && (
          <p className="flex items-center gap-2 text-sm text-danger">
            <CircleAlert aria-hidden="true" className="size-4 shrink-0" />
            <span>{blockedReason}</span>
          </p>
        )}
        {checkError !== null && (
          <p className="flex items-center gap-2 text-sm text-danger">
            <CircleAlert aria-hidden="true" className="size-4 shrink-0" />
            <span>{checkError}</span>
          </p>
        )}

        <div role="status" aria-live="polite" className="font-mono text-xs text-muted-foreground">
          <span>{statusLine(status)}</span>
          {notice !== null && <span> · {notice}</span>}
        </div>
      </section>

      <QueuedRuns entries={queue} onRemove={removeQueued} onEmptied={focusStart} />

      <ConfirmRunDialog
        key={confirmKey}
        open={confirmOpen}
        checked={checked}
        activeRunId={activeRunId}
        onConfirm={confirm}
        onCancel={() => setConfirmOpen(false)}
        returnFocus={startRef}
      />

      {stopTarget !== null && (
        <StopRunDialog
          key={stopKey}
          open={stopOpen}
          runId={stopTarget}
          onConfirm={stop}
          onClose={closeStop}
          returnFocus={stopRef}
        />
      )}
    </>
  );
}
