import { CircleAlertIcon, LoaderCircleIcon } from "lucide-react";
import { useId, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toApiError, type ConfirmResult, type Run, type RunRequest } from "@/lib/api";
import { useApi } from "@/lib/api-context";
import { formatDuration } from "@/lib/format";
import { useAsync } from "@/lib/queries";

export interface TestSplitDialogProps {
  /** The finalist to score (only finalists open this dialog; the service checks again). */
  finalist: Run;
  onClose(): void;
  onStarted(result: ConfirmResult): void;
}

/** The test-split request for a finalist's adapter (batch-4 Part W2, mockups.md). */
export function testSplitRequest(run: Run): RunRequest {
  const request: RunRequest = {
    method: "best",
    split: "test",
    adapter_path: `checkpoints/${run.run_id}`,
  };
  if (run.model) request.model = run.model;
  return request;
}

/** A refusal or failure, said in words with an icon (never a bare status code). */
function ErrorLine({ message }: { message: string }) {
  return (
    <p role="alert" className="flex items-start gap-2 text-sm text-danger">
      <CircleAlertIcon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      <span>{message}</span>
    </p>
  );
}

/**
 * Scores a finalist on the held-out test split after a second confirmation (US3.6, AC3.6.3):
 * the service checks the request first, and Score on test stays disabled until the checkbox is
 * ticked; ticking it sends `second_confirmation: true`.
 */
export function TestSplitDialog({ finalist, onClose, onStarted }: TestSplitDialogProps) {
  const api = useApi();
  const runId = finalist.run_id;
  const check = useAsync(() => api.checkRun(testSplitRequest(finalist)), [api, runId]);
  const [understood, setUnderstood] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const ids = useId();
  const reasonId = `${ids}-reason`;
  const boxId = `${ids}-understood`;

  const ready = check.state === "ready";
  const canScore = ready && understood && !submitting;

  const score = async () => {
    if (check.state !== "ready" || !understood || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await api.confirmRun(check.data.check_id, true);
      onStarted(result);
    } catch (thrown: unknown) {
      setError(toApiError(thrown).message);
      setSubmitting(false);
    }
  };

  let reason = "";
  if (check.state === "loading") reason = "Checking the run with the service…";
  else if (check.state === "error") reason = "The service refused this run; see the reason above.";
  else if (!understood) reason = "Tick the box to confirm the held-out test split.";

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !submitting) onClose();
      }}
    >
      <DialogContent
        className="border-hairline bg-panel sm:max-w-[560px]"
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          cancelRef.current?.focus();
        }}
      >
        <DialogHeader>
          <DialogTitle className="font-sans text-lg font-semibold">
            Score {runId} on the test split
          </DialogTitle>
          <DialogDescription>
            The test split (1,319 problems) is held out. Scoring on it is for finalists only, and
            the result must never steer tuning.
          </DialogDescription>
        </DialogHeader>

        {check.state === "loading" && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <LoaderCircleIcon aria-hidden="true" className="size-4 animate-spin" />
            Checking the run…
          </p>
        )}
        {check.state === "error" && <ErrorLine message={check.error.message} />}
        {check.state === "ready" && (
          <dl className="grid grid-cols-[8rem_1fr] gap-x-4 gap-y-2 text-sm">
            <dt className="text-muted-foreground">Run id</dt>
            <dd className="font-mono">{check.data.attempt_id}</dd>
            <dt className="text-muted-foreground">Estimated</dt>
            <dd className="font-mono">
              {check.data.estimate_text || formatDuration(check.data.estimate_s)}
            </dd>
            <dt className="text-muted-foreground">Command</dt>
            <dd className="font-mono break-all">{check.data.command_text}</dd>
            {check.data.queue_position > 1 && (
              <>
                <dt className="text-muted-foreground">Queue</dt>
                <dd>Waits in the queue at position {check.data.queue_position}</dd>
              </>
            )}
          </dl>
        )}

        <div className="flex items-center gap-2 text-sm">
          <input
            id={boxId}
            type="checkbox"
            checked={understood}
            disabled={submitting}
            onChange={(event) => setUnderstood(event.target.checked)}
            className="size-4 accent-[var(--accent-orange)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange"
          />
          <label htmlFor={boxId}>I understand this uses the held-out test split.</label>
        </div>

        {error !== null && <ErrorLine message={error} />}
        {submitting && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <LoaderCircleIcon aria-hidden="true" className="size-4 animate-spin" />
            Starting…
          </p>
        )}

        <DialogFooter>
          <Button ref={cancelRef} variant="outline" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button
            onClick={() => void score()}
            disabled={!canScore}
            aria-describedby={reason ? reasonId : undefined}
          >
            Score on test
          </Button>
        </DialogFooter>
        {reason && (
          <p id={reasonId} className="sr-only">
            {reason}
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}
