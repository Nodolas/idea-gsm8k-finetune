import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { CourseComparisonRow, CourseMemoryRow } from "@/lib/api";
import { formatGb, formatPoints } from "@/lib/course";
import { formatMinutes, formatPct } from "@/lib/format";

function MemoryCell({ gb, fits }: { gb: number | null; fits: boolean | null }) {
  return (
    <TableCell>
      <div className="flex flex-col">
        <span className="num text-ink">{gb === null ? "--" : `${formatGb(gb)} GB`}</span>
        {fits === null ? null : (
          <span className={fits ? "text-xs text-ok" : "text-xs text-danger"}>
            {fits ? "Fits in 8 GB" : "Does not fit"}
          </span>
        )}
      </div>
    </TableCell>
  );
}

/** c19: the memory table, each cell with its figure and "Fits in 8 GB" or "Does not fit". */
export function MemoryTable({ rows }: { rows: CourseMemoryRow[] }) {
  const empty = rows.every((r) => r.full_gb === null && r.lora_gb === null && r.qlora_gb === null);
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead scope="col">Model</TableHead>
            <TableHead scope="col">Full fine-tuning</TableHead>
            <TableHead scope="col">LoRA</TableHead>
            <TableHead scope="col">QLoRA</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.model}>
              <TableCell className="num">{row.model}</TableCell>
              <MemoryCell gb={row.full_gb} fits={row.full_fits} />
              <MemoryCell gb={row.lora_gb} fits={row.lora_fits} />
              <MemoryCell gb={row.qlora_gb} fits={row.qlora_fits} />
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {empty ? (
        <p className="max-w-[75ch] text-sm text-ink-muted">
          The figures appear after the model designs have been read (steps 2 to 4).
        </p>
      ) : null}
    </div>
  );
}

/** One interval drawn on a 0 to 100 % track, with a tick at the accuracy. */
function IntervalBar({ row }: { row: CourseComparisonRow }) {
  const low = Math.max(0, Math.min(1, row.interval_low)) * 100;
  const high = Math.max(low, Math.min(1, row.interval_high) * 100);
  const at = Math.max(0, Math.min(1, row.accuracy)) * 100;
  return (
    <span
      data-interval-bar=""
      role="img"
      aria-label={`${formatPct(row.accuracy)}, interval ${formatPct(row.interval_low)} to ${formatPct(row.interval_high)}`}
      className="relative block h-3 w-40 rounded-sm bg-hairline"
    >
      <span
        className="absolute inset-y-0 rounded-sm bg-ink-muted"
        style={{ left: `${low}%`, width: `${high - low}%` }}
      />
      <span className="absolute inset-y-0 w-0.5 bg-orange" style={{ left: `${at}%` }} />
    </span>
  );
}

/** c24: every finished course run with its interval drawn as a bar and its numbers in a row. */
export function ComparisonTable({ rows }: { rows: CourseComparisonRow[] }) {
  if (rows.length === 0) {
    return (
      <p className="max-w-[75ch] text-ink-muted">
        No course run has finished yet, so there is nothing to compare.
      </p>
    );
  }
  return (
    <Table className="num">
      <TableHeader>
        <TableRow>
          <TableHead scope="col">Step</TableHead>
          <TableHead scope="col">Run</TableHead>
          <TableHead scope="col">Method</TableHead>
          <TableHead scope="col" className="text-right">
            Accuracy
          </TableHead>
          <TableHead scope="col">Interval</TableHead>
          <TableHead scope="col" className="text-right">
            Gain
          </TableHead>
          <TableHead scope="col">Against noise</TableHead>
          <TableHead scope="col" className="text-right">
            Min
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.attempt_id}>
            <TableCell>{row.step} </TableCell>
            <TableCell>
              <div className="flex flex-col">
                <span>{row.attempt_id} </span>
                <span className="text-xs text-ink-muted">{row.model} </span>
              </div>
            </TableCell>
            <TableCell>{row.method} </TableCell>
            <TableCell className="text-right">{formatPct(row.accuracy)} </TableCell>
            <TableCell>
              <div className="flex flex-col gap-1">
                <IntervalBar row={row} />
                <span className="text-xs text-ink-muted">
                  {`${formatPct(row.interval_low)} to ${formatPct(row.interval_high)}`}
                </span>
              </div>{" "}
            </TableCell>
            <TableCell className="text-right">{formatPoints(row.gain_pts)} </TableCell>
            <TableCell>{row.noise ?? "--"} </TableCell>
            <TableCell className="text-right">{formatMinutes(row.minutes)} </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
