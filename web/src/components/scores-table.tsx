import { EllipsisIcon, StarIcon } from "lucide-react";
import { DropdownMenu } from "radix-ui";

import type { Run } from "@/lib/api";
import { formatDateTime, formatGain, formatMinutes, formatPct, shortModel } from "@/lib/format";
import { cn } from "@/lib/utils";

export const SCORES_CAPTION = "Highest scores, ranked by dev accuracy";
export const NOT_FINALIST_REASON = "Only finalists can be scored on the test split";

export interface ScoresTableProps {
  baselines: Run[];
  ranked: Run[];
  finalists: string[];
  picked: string[];
  onPick(runId: string): void;
  onToggleFinalist(runId: string): void;
  onScoreOnTest(run: Run): void;
}

const NUMBER = "text-right font-mono tabular-nums";
const HEAD = "font-mono text-[10.5px] uppercase tracking-[0.18em] text-muted-foreground";

/** The date part of a run's date: "2026-11-05", or "--". */
function shortDate(iso: string | null): string {
  return formatDateTime(iso).split(" ")[0];
}

/** A test score, or "--" announced as "not scored" (AC4.3.2). */
function TestCell({ value }: { value: number | null }) {
  const text = formatPct(value);
  if (text !== "--") return <>{text}</>;
  return (
    <>
      <span aria-hidden="true">--</span>
      <span className="sr-only">not scored</span>
    </>
  );
}

interface RowMenuProps {
  run: Run;
  isFinalist: boolean;
  onToggleFinalist(runId: string): void;
  onScoreOnTest(run: Run): void;
}

/** The row's overflow menu: mark or unmark as finalist, and Score on test for finalists only. */
function RowMenu({ run, isFinalist, onToggleFinalist, onScoreOnTest }: RowMenuProps) {
  const item =
    "flex cursor-default flex-col items-start gap-0.5 rounded-sm px-2 py-1.5 text-sm outline-none select-none data-[disabled]:cursor-not-allowed data-[disabled]:text-muted-foreground data-[highlighted]:bg-hairline";
  return (
    <DropdownMenu.Root modal={false}>
      <DropdownMenu.Trigger
        aria-label={`Actions for ${run.run_id}`}
        className="inline-flex size-7 items-center justify-center rounded-sm text-muted-foreground hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange"
      >
        <EllipsisIcon aria-hidden="true" className="size-4" />
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={4}
          className="z-50 min-w-56 rounded-md border border-hairline bg-panel p-1 text-foreground"
        >
          <DropdownMenu.Item className={item} onSelect={() => onToggleFinalist(run.run_id)}>
            {isFinalist ? "Unmark finalist" : "Mark as finalist"}
          </DropdownMenu.Item>
          <DropdownMenu.Item
            className={item}
            disabled={!isFinalist}
            onSelect={() => {
              if (isFinalist) onScoreOnTest(run);
            }}
          >
            <span>Score on test…</span>
            {!isFinalist && (
              <span className="text-xs text-muted-foreground">{NOT_FINALIST_REASON}</span>
            )}
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

interface RowProps extends Omit<ScoresTableProps, "baselines" | "ranked" | "finalists"> {
  run: Run;
  rank: number | null;
  isFinalist: boolean;
}

function ScoreRow({
  run,
  rank,
  isFinalist,
  picked,
  onPick,
  onToggleFinalist,
  onScoreOnTest,
}: RowProps) {
  const isPicked = picked.includes(run.run_id);
  return (
    <tr
      className="border-b border-hairline last:border-0"
      data-run-id={run.run_id}
      data-baseline={rank === null ? "true" : "false"}
      data-finalist={isFinalist ? "true" : "false"}
    >
      <th scope="row" className="px-2 py-2 text-left font-mono font-normal text-muted-foreground">
        {rank === null ? (
          <>
            <span aria-hidden="true">BL</span>
            <span className="sr-only">baseline</span>
          </>
        ) : (
          rank
        )}
      </th>
      <td className="px-2 py-2 font-mono whitespace-nowrap">
        {run.run_id}
        {isFinalist && (
          <>
            {" "}
            <StarIcon aria-hidden="true" className="inline size-3.5 fill-current text-orange" />
            <span className="sr-only">finalist</span>
          </>
        )}
      </td>
      <td className="px-2 py-2 font-mono">{shortModel(run.model)}</td>
      <td className="px-2 py-2 font-mono">{run.method ?? "--"}</td>
      <td className={cn("px-2 py-2", NUMBER)}>{formatPct(run.dev_accuracy)}</td>
      <td className={cn("px-2 py-2", NUMBER)}>
        <TestCell value={run.test_accuracy} />
      </td>
      <td className={cn("px-2 py-2 whitespace-nowrap", NUMBER)}>
        {rank === null ? "—" : formatGain(run.gain)}
      </td>
      <td className={cn("px-2 py-2", NUMBER)}>{formatMinutes(run.minutes)}</td>
      <td className={cn("px-2 py-2 whitespace-nowrap", NUMBER)}>
        {run.date ? <time dateTime={run.date}>{shortDate(run.date)}</time> : "--"}
      </td>
      <td className="px-2 py-2 text-center">
        <input
          type="checkbox"
          aria-label={`Pick ${run.run_id}`}
          checked={isPicked}
          onChange={() => onPick(run.run_id)}
          className="size-4 accent-[var(--accent-orange)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange"
        />
      </td>
      <td className="px-2 py-2 text-right">
        <RowMenu
          run={run}
          isFinalist={isFinalist}
          onToggleFinalist={onToggleFinalist}
          onScoreOnTest={onScoreOnTest}
        />
      </td>
    </tr>
  );
}

/**
 * The ranked runs (interaction-spec ScoresTable): each model's baseline first, marked BL, then
 * runs by dev accuracy, with pick checkboxes for compare and a row menu for finalists (AC4.3.1,
 * AC4.3.2, AC4.3.5, AC4.4.2).
 */
export function ScoresTable({ baselines, ranked, finalists, ...rest }: ScoresTableProps) {
  return (
    <div className="relative w-full overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">{SCORES_CAPTION}</caption>
        <thead>
          <tr className="border-b border-hairline">
            <th scope="col" className={cn("px-2 py-2 text-left font-normal", HEAD)}>
              #
            </th>
            <th scope="col" className={cn("px-2 py-2 text-left font-normal", HEAD)}>
              Run id
            </th>
            <th scope="col" className={cn("px-2 py-2 text-left font-normal", HEAD)}>
              Model
            </th>
            <th scope="col" className={cn("px-2 py-2 text-left font-normal", HEAD)}>
              Method
            </th>
            <th scope="col" className={cn("px-2 py-2 text-right font-normal", HEAD)}>
              Dev
            </th>
            <th scope="col" className={cn("px-2 py-2 text-right font-normal", HEAD)}>
              Test
            </th>
            <th scope="col" className={cn("px-2 py-2 text-right font-normal", HEAD)}>
              Gain
            </th>
            <th scope="col" className={cn("px-2 py-2 text-right font-normal", HEAD)}>
              Min
            </th>
            <th scope="col" className={cn("px-2 py-2 text-right font-normal", HEAD)}>
              Date
            </th>
            <th scope="col" className={cn("px-2 py-2 text-center font-normal", HEAD)}>
              Pick
            </th>
            <th scope="col" className={cn("px-2 py-2 text-right font-normal", HEAD)}>
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {baselines.map((run) => (
            <ScoreRow
              key={run.run_id}
              run={run}
              rank={null}
              isFinalist={finalists.includes(run.run_id)}
              {...rest}
            />
          ))}
          {ranked.map((run, i) => (
            <ScoreRow
              key={run.run_id}
              run={run}
              rank={i + 1}
              isFinalist={finalists.includes(run.run_id)}
              {...rest}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}
