/**
 * Past runs on the training page (refined mockups, PAST RUNS; interaction-spec PastRunsList):
 * every run with its run id, status word and icon, start time, minutes and dev accuracy, each
 * openable into the curves panel (AC4.5.5). Status is always a word; icons are `aria-hidden`
 * (NFR9). With no runs at all it reads "None yet" (AC4.5.4).
 */
import { useState } from "react";
import { Check, CircleDot, Clock, Square, X, type LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Run, RunStatusWord } from "@/lib/api";
import { formatDateTime, formatMinutes, formatPct } from "@/lib/format";

const SHOWN_AT_FIRST = 10;

const ICONS: Record<RunStatusWord, { icon: LucideIcon; className: string }> = {
  finished: { icon: Check, className: "text-ok" },
  failed: { icon: X, className: "text-danger" },
  stopped: { icon: Square, className: "text-ink-muted" },
  running: { icon: CircleDot, className: "text-orange" },
  queued: { icon: Clock, className: "text-ink-muted" },
};

/** The C6 status word in capitals, as the page shows it (FINISHED, FAILED, ...). */
export function statusWord(status: RunStatusWord | null): string {
  return status ? status.toUpperCase() : "--";
}

/** A course run (AC12.3.8): its run id starts with `course-`; it shows its status only. */
function isCourseRun(run: Run): boolean {
  return run.run_id.startsWith("course-");
}

const RANK: Record<string, number> = { running: 0, queued: 1 };

/** Active and waiting runs first, then the newest start (or end) first. */
function ordered(runs: readonly Run[]): Run[] {
  return [...runs].sort((a, b) => {
    const rank = (RANK[a.status ?? ""] ?? 2) - (RANK[b.status ?? ""] ?? 2);
    if (rank !== 0) return rank;
    const at = (run: Run) => Date.parse(run.started_at ?? run.date ?? "") || 0;
    return at(b) - at(a);
  });
}

export interface PastRunsListProps {
  /** The runs; null while they load. */
  runs: readonly Run[] | null;
  /** Why the runs could not be read. */
  error?: string | null;
  onOpen(runId: string): void;
}

export function PastRunsList({ runs, error = null, onOpen }: PastRunsListProps) {
  const [showAll, setShowAll] = useState(false);

  let body;
  if (error) {
    body = <p className="text-danger">{error}</p>;
  } else if (runs === null) {
    body = (
      <div>
        <p className="sr-only">Loading past runs</p>
        <Skeleton className="h-24 w-full" />
      </div>
    );
  } else if (runs.length === 0) {
    body = <p className="text-ink-muted">None yet</p>;
  } else {
    const all = ordered(runs);
    const shown = showAll ? all : all.slice(0, SHOWN_AT_FIRST);
    body = (
      <>
        <Table className="num">
          <TableHeader>
            <TableRow>
              <TableHead scope="col">Run id</TableHead>
              <TableHead scope="col">Status</TableHead>
              <TableHead scope="col">Started</TableHead>
              <TableHead scope="col" className="text-right">
                Min
              </TableHead>
              <TableHead scope="col" className="text-right">
                Dev
              </TableHead>
              <TableHead scope="col">
                <span className="sr-only">Open</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {shown.map((run) => {
              const look = run.status ? ICONS[run.status] : null;
              const Icon = look?.icon;
              const course = isCourseRun(run);
              return (
                <TableRow key={run.run_id}>
                  <TableCell>
                    <span>{run.run_id}</span>
                    {course ? (
                      <Badge variant="outline" className="ml-2">
                        Course
                      </Badge>
                    ) : null}
                  </TableCell>
                  <TableCell>
                    <span className="inline-flex items-center gap-1.5">
                      <span>{statusWord(run.status)}</span>
                      {Icon ? (
                        <Icon aria-hidden="true" className={`size-3.5 ${look.className}`} />
                      ) : null}
                    </span>
                  </TableCell>
                  <TableCell>{formatDateTime(run.started_at)}</TableCell>
                  <TableCell className="text-right">
                    {course ? "--" : formatMinutes(run.minutes)}
                  </TableCell>
                  <TableCell className="text-right">
                    {course ? "--" : formatPct(run.dev_accuracy)}
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="link"
                      size="sm"
                      aria-label={`Open ${run.run_id}`}
                      data-open-run={run.run_id}
                      onClick={() => onOpen(run.run_id)}
                    >
                      Open <span aria-hidden="true">›</span>
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
        {all.length > SHOWN_AT_FIRST ? (
          <Button
            variant="outline"
            size="sm"
            className="self-start"
            onClick={() => setShowAll((v) => !v)}
          >
            {showAll ? "Show fewer" : `Show all (${all.length})`}
          </Button>
        ) : null}
      </>
    );
  }

  return (
    <section aria-labelledby="past-runs-heading" className="flex flex-col gap-3">
      <h2 id="past-runs-heading" className="label-caps">
        Past runs
      </h2>
      {body}
    </section>
  );
}
