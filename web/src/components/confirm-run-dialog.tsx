/**
 * The Confirm run dialog (AC4.6.2, AC4.6.3, AC4.6.5, AC4.6.6): what the service's check step says
 * would run (attempt id, model, method, changes against the last run, the estimate and the exact
 * command), launched only on confirm. Above the 3-hour cap the start button reads "Start anyway"
 * and asks once more. A failed launch keeps the dialog open with the reason in an alert. It opens
 * with focus on Cancel and gives focus back to `returnFocus` on close.
 */
import { Check, Copy, LoaderCircle, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState, type RefObject } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toApiError, type CheckedRun } from "@/lib/api";
import { formatDuration, modelName } from "@/lib/format";

/** "sft" -> "SFT", "base" -> "Base model (no adapter)". */
export function methodText(method: string | null | undefined): string {
  switch (method) {
    case "sft":
      return "SFT";
    case "grpo":
      return "GRPO";
    case "base":
      return "Base model (no adapter)";
    case "best":
      return "Best checkpoint";
    case null:
    case undefined:
    case "":
      return "--";
    default:
      return method.toUpperCase();
  }
}

export interface ConfirmRunDialogProps {
  open: boolean;
  checked: CheckedRun | null;
  /** The run holding the GPU; the confirmed run waits in the queue behind it. */
  activeRunId: string | null;
  /** Launches (or queues) the checked run; rejects with the reason when the service refuses. */
  onConfirm(): Promise<void>;
  /** Closes the dialog; nothing is launched or queued. */
  onCancel(): void;
  /** Gets focus back when the dialog closes (the Start button). */
  returnFocus: RefObject<HTMLButtonElement | null>;
}

export function ConfirmRunDialog({
  open,
  checked,
  activeRunId,
  onConfirm,
  onCancel,
  returnFocus,
}: ConfirmRunDialogProps) {
  const [asking, setAsking] = useState(false);
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const askRef = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    if (asking) askRef.current?.focus();
  }, [asking]);

  if (checked === null) return null;

  const overCap = checked.over_cap;
  const queued = activeRunId !== null;
  const estimate = formatDuration(checked.estimate_s);
  const loraRank = checked.method === "sft" ? checked.config.lora_rank : undefined;
  const startLabel = overCap ? "Start anyway" : queued ? "Add to queue" : "Start run";

  const launch = async () => {
    setLaunching(true);
    setError(null);
    try {
      await onConfirm();
    } catch (failure: unknown) {
      setError(toApiError(failure).message);
    } finally {
      setLaunching(false);
    }
  };

  const onStart = () => {
    if (launching) return;
    if (overCap && !asking) {
      setAsking(true);
      return;
    }
    void launch();
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(checked.command_text);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next && !launching) onCancel();
      }}
    >
      <DialogContent
        className="border-[0.5px] bg-panel sm:max-w-[560px]"
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          cancelRef.current?.focus();
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          returnFocus.current?.focus();
        }}
      >
        <DialogHeader>
          <DialogTitle>Confirm run</DialogTitle>
        </DialogHeader>

        <DialogDescription asChild>
          <dl className="grid grid-cols-[7rem_1fr] gap-x-4 gap-y-2 text-sm text-foreground">
            <dt className="text-muted-foreground">Run id</dt>
            <dd className="font-mono tabular-nums">{checked.attempt_id}</dd>

            <dt className="text-muted-foreground">Model</dt>
            <dd className="font-mono">{modelName(checked.model)}</dd>

            <dt className="text-muted-foreground">Method</dt>
            <dd>
              {methodText(checked.method)}
              {typeof loraRank === "number" ? ` (LoRA rank ${loraRank})` : ""}
            </dd>

            <dt className="text-muted-foreground">Changes</dt>
            <dd className="font-mono">
              {checked.changes.length === 0 ? (
                <span className="font-sans">First run of this kind</span>
              ) : (
                <ul className="grid gap-0.5">
                  {checked.changes.map((change) => (
                    <li key={change}>{change}</li>
                  ))}
                </ul>
              )}
            </dd>

            <dt className="text-muted-foreground">Estimated</dt>
            <dd className="font-mono tabular-nums">
              {estimate}
              {checked.estimate_s === null ? "" : " (cap 3 h)"}
            </dd>

            <dt className="text-muted-foreground">Command</dt>
            <dd className="grid gap-2">
              <code className="block rounded-sm border-[0.5px] border-hairline bg-bg px-2 py-1.5 font-mono text-xs break-all whitespace-pre-wrap">
                {checked.command_text}
              </code>
              <Button
                type="button"
                variant="outline"
                size="xs"
                className="justify-self-start"
                onClick={() => void copy()}
              >
                {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
                {copied ? "Copied" : "Copy"}
              </Button>
            </dd>
          </dl>
        </DialogDescription>

        {queued && (
          <p className="font-mono text-sm tabular-nums">
            Queued behind {activeRunId} · position {checked.queue_position}
          </p>
        )}

        {overCap && (
          <p className="flex items-center gap-2 text-sm text-danger">
            <TriangleAlert aria-hidden="true" className="size-4 shrink-0" />
            <span>Estimated time is above the 3-hour cap.</span>
          </p>
        )}

        {error !== null && (
          <p role="alert" className="flex items-center gap-2 text-sm text-danger">
            <TriangleAlert aria-hidden="true" className="size-4 shrink-0" />
            <span>{error}</span>
          </p>
        )}

        {asking && (
          <p ref={askRef} tabIndex={-1} className="text-sm font-medium outline-none">
            Start a run estimated at {estimate}?
          </p>
        )}

        <DialogFooter>
          <Button
            ref={cancelRef}
            type="button"
            variant="outline"
            disabled={launching}
            onClick={onCancel}
          >
            Cancel
          </Button>
          <Button type="button" disabled={launching} aria-busy={launching} onClick={onStart}>
            {launching && <LoaderCircle aria-hidden="true" className="motion-safe:animate-spin" />}
            {launching ? "Starting…" : startLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
