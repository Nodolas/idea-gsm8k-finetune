/**
 * The failure panel (refined mockups, Failure panel; interaction-spec FailurePanel; US3.5): a
 * "Show log" button that opens a dialog titled "Why <run id> failed", with the exit reason first
 * and then the last log lines in a scrolling monospace block and a Copy button. Escape closes it
 * and focus returns to Show log (Radix Dialog).
 */
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

/** The service keeps the last 20 lines (AC3.5.1); show no more than that. */
const MAX_LINES = 20;

export interface FailurePanelProps {
  runId: string;
  /** The exit reason, e.g. "GPU out of memory", or "Run log could not be read: <file>". */
  reason: string;
  /** The last lines of the run's log. */
  lines: readonly string[];
}

export function FailurePanel({ runId, reason, lines }: FailurePanelProps) {
  const [copied, setCopied] = useState<"idle" | "done" | "failed">("idle");
  const tail = lines.slice(-MAX_LINES);

  const copy = () => {
    const text = tail.join("\n");
    if (typeof navigator === "undefined" || !navigator.clipboard) {
      setCopied("failed");
      return;
    }
    navigator.clipboard.writeText(text).then(
      () => setCopied("done"),
      () => setCopied("failed"),
    );
  };

  return (
    <Dialog onOpenChange={() => setCopied("idle")}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          Show log
        </Button>
      </DialogTrigger>
      <DialogContent className="top-0 right-0 left-auto flex h-full max-h-screen w-full max-w-[640px] translate-x-0 translate-y-0 flex-col rounded-none border-y-0 border-r-0 border-hairline bg-panel sm:max-w-[640px]">
        <DialogHeader>
          <DialogTitle>Why {runId} failed</DialogTitle>
          <DialogDescription asChild>
            <h3 className="text-base font-semibold text-ink">{reason}</h3>
          </DialogDescription>
        </DialogHeader>
        {tail.length > 0 ? (
          <>
            <pre
              aria-label={`Last ${tail.length} log lines of ${runId}`}
              tabIndex={0}
              className="num min-h-0 flex-1 overflow-auto rounded-md border border-hairline bg-bg p-3 text-xs whitespace-pre-wrap"
            >
              {tail.join("\n")}
            </pre>
            <div className="flex items-center gap-3">
              <Button variant="outline" size="sm" onClick={copy}>
                Copy log
              </Button>
              <span className="text-sm text-ink-muted">
                {copied === "done" ? "Copied" : copied === "failed" ? "Could not copy the log" : ""}
              </span>
            </div>
          </>
        ) : (
          <p className="text-sm text-ink-muted">No log lines were recorded.</p>
        )}
      </DialogContent>
    </Dialog>
  );
}
