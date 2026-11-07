/**
 * The Stop run dialog (US3.4, AC4.6.4): names the run and says what stopping means before anything
 * is stopped. It opens on "Keep running" (the safe default); "Stop run" calls the service. If the
 * run already ended (`no_active_run`) it says so with one Close button; any other failure stays in
 * the dialog as an alert. Focus goes back to `returnFocus` on close.
 */
import { LoaderCircle, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState, type RefObject } from "react";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { toApiError } from "@/lib/api";

export interface StopRunDialogProps {
  open: boolean;
  /** The run the dialog stops, fixed when it opened. */
  runId: string;
  /** Asks the service to stop the active run; rejects with the reason when it cannot. */
  onConfirm(): Promise<void>;
  /** Closes the dialog. `ended` is true when the run had already ended. */
  onClose(ended: boolean): void;
  /** Gets focus back when the dialog closes (the Stop button). */
  returnFocus: RefObject<HTMLButtonElement | null>;
}

export function StopRunDialog({
  open,
  runId,
  onConfirm,
  onClose,
  returnFocus,
}: StopRunDialogProps) {
  const [stopping, setStopping] = useState(false);
  const [ended, setEnded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (ended) closeRef.current?.focus();
  }, [ended]);

  const stop = async () => {
    setStopping(true);
    setError(null);
    try {
      await onConfirm();
    } catch (failure: unknown) {
      const apiError = toApiError(failure);
      if (apiError.code === "no_active_run") setEnded(true);
      else setError(apiError.message);
    } finally {
      setStopping(false);
    }
  };

  return (
    <AlertDialog
      open={open}
      onOpenChange={(next) => {
        if (!next && !stopping) onClose(ended);
      }}
    >
      <AlertDialogContent
        className="border-[0.5px] bg-panel sm:max-w-[480px]"
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          returnFocus.current?.focus();
        }}
      >
        <AlertDialogHeader>
          <AlertDialogTitle>Stop {runId}?</AlertDialogTitle>
          <AlertDialogDescription className="text-foreground">
            {ended
              ? "This run has already ended."
              : "The run ends now. Its curves so far are kept; no score is recorded."}
          </AlertDialogDescription>
        </AlertDialogHeader>

        {error !== null && (
          <p role="alert" className="flex items-center gap-2 text-sm text-danger">
            <TriangleAlert aria-hidden="true" className="size-4 shrink-0" />
            <span>{error}</span>
          </p>
        )}

        <AlertDialogFooter>
          {ended ? (
            <AlertDialogCancel ref={closeRef}>Close</AlertDialogCancel>
          ) : (
            <>
              <AlertDialogCancel disabled={stopping}>Keep running</AlertDialogCancel>
              <Button
                type="button"
                variant="destructive"
                disabled={stopping}
                aria-busy={stopping}
                onClick={() => void stop()}
              >
                {stopping && (
                  <LoaderCircle aria-hidden="true" className="motion-safe:animate-spin" />
                )}
                {stopping ? "Stopping…" : "Stop run"}
              </Button>
            </>
          )}
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
