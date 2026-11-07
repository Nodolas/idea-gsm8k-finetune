/**
 * The "Queued runs" list (AC4.6.7, US3.7): each waiting run's position, attempt id, model, method
 * and when it was added, with a Remove button per row; hidden while nothing waits. Remove asks
 * nothing extra (a waiting run has used no GPU time). Once the removed row is gone, focus moves to
 * the next row's Remove button, or to `onEmptied` (the Start button) when the list empties.
 */
import { TriangleAlert } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { toApiError, type QueueEntry } from "@/lib/api";
import { formatDateTime, shortModel } from "@/lib/format";

export interface QueuedRunsProps {
  entries: QueueEntry[];
  /** Takes the run out of the queue; rejects with the reason when the service refuses. */
  onRemove(attemptId: string): Promise<void>;
  /** Called when the last waiting run was removed, to move focus elsewhere. */
  onEmptied(): void;
}

export function QueuedRuns({ entries, onRemove, onEmptied }: QueuedRunsProps) {
  const headingId = useId();
  const [error, setError] = useState<string | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);
  const buttons = useRef(new Map<string, HTMLButtonElement>());
  const pending = useRef<{ id: string; index: number } | null>(null);

  // After a removal, move focus once the removed row has left the list.
  useEffect(() => {
    const removed = pending.current;
    if (removed === null || entries.some((entry) => entry.attempt_id === removed.id)) return;
    pending.current = null;
    if (entries.length === 0) {
      onEmptied();
      return;
    }
    const next = entries[Math.min(removed.index, entries.length - 1)];
    if (next) buttons.current.get(next.attempt_id)?.focus();
  }, [entries, onEmptied]);

  const remove = async (attemptId: string, index: number) => {
    setError(null);
    setRemoving(attemptId);
    pending.current = { id: attemptId, index };
    try {
      await onRemove(attemptId);
    } catch (failure: unknown) {
      pending.current = null;
      setError(toApiError(failure).message);
    } finally {
      setRemoving(null);
    }
  };

  if (entries.length === 0) return null;

  return (
    <section aria-labelledby={headingId} className="grid gap-3">
      <h2
        id={headingId}
        className="font-mono text-[10.5px] tracking-[0.18em] text-muted-foreground uppercase"
      >
        Queued runs
      </h2>
      <Table className="font-mono tabular-nums">
        <TableHeader>
          <TableRow>
            <TableHead scope="col">#</TableHead>
            <TableHead scope="col">Run id</TableHead>
            <TableHead scope="col">Model</TableHead>
            <TableHead scope="col">Method</TableHead>
            <TableHead scope="col">Added</TableHead>
            <TableHead scope="col">
              <span className="sr-only">Remove</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {entries.map((entry, index) => (
            <TableRow key={entry.attempt_id}>
              <TableCell>{entry.position}</TableCell>
              <TableCell>{entry.attempt_id}</TableCell>
              <TableCell>{shortModel(entry.config.model)}</TableCell>
              <TableCell>{entry.config.method ?? "--"}</TableCell>
              <TableCell>{formatDateTime(entry.added_at)}</TableCell>
              <TableCell>
                <Button
                  ref={(element: HTMLButtonElement | null) => {
                    if (element) buttons.current.set(entry.attempt_id, element);
                    else buttons.current.delete(entry.attempt_id);
                  }}
                  type="button"
                  variant="outline"
                  size="sm"
                  aria-label={`Remove ${entry.attempt_id} from the queue`}
                  disabled={removing === entry.attempt_id}
                  onClick={() => void remove(entry.attempt_id, index)}
                >
                  Remove
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {error !== null && (
        <p className="flex items-center gap-2 text-sm text-danger">
          <TriangleAlert aria-hidden="true" className="size-4 shrink-0" />
          <span>{error}</span>
        </p>
      )}
    </section>
  );
}
