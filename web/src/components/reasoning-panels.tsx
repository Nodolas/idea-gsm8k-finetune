import { CircleAlertIcon } from "lucide-react";
import { useId, type ReactNode } from "react";

import type {
  ReasoningExample,
  ReasoningFlip,
  ReasoningGeneration,
  ReasoningRole,
} from "@/lib/api";
import { formatGain, formatPct } from "@/lib/format";
import { cn } from "@/lib/utils";

/** The words each role goes by on the page (base first, it is the reference point). */
export const ROLE_LABEL: Record<ReasoningRole["role"], string> = {
  base: "Base",
  sft: "Reference fine-tune",
  selfcot: "Self-taught",
};

export const LABEL = "font-mono text-[10.5px] uppercase tracking-[0.18em] text-muted-foreground";
const HEAD = cn("px-2 py-2 font-normal", LABEL);
const NUMBER = "px-2 py-2 text-right font-mono tabular-nums whitespace-nowrap";

/** 6973 -> "6,973". */
function count(value: number): string {
  return value.toLocaleString("en-US");
}

/** 5.94 -> "5.9". */
function mean(value: number): string {
  return value.toFixed(1);
}

/** A missing figure: a dash for the eye, words for a screen reader (never a blank cell). */
function Missing({ why = "no figure" }: { why?: string }) {
  return (
    <>
      <span aria-hidden="true">—</span>
      <span className="sr-only">{why}</span>
    </>
  );
}

/** A number, or the dash when it is missing. */
function Figure({ value, format }: { value: number | null; format(value: number): string }) {
  return value === null || !Number.isFinite(value) ? <Missing /> : <>{format(value)}</>;
}

/** "54.5–63.1%" from the interval ends (fractions), or the dash. */
function Interval({ low, high }: { low: number | null; high: number | null }) {
  if (low === null || high === null) return <Missing />;
  return (
    <>
      {(low * 100).toFixed(1)}
      <span aria-hidden="true">–</span>
      <span className="sr-only"> to </span>
      {(high * 100).toFixed(1)}%
    </>
  );
}

/** A note said in words with an icon, for a figure the service could not read. */
export function NoteLine({ children, alert = false }: { children: ReactNode; alert?: boolean }) {
  return (
    <p role={alert ? "alert" : undefined} className="flex items-start gap-2 text-sm text-danger">
      <CircleAlertIcon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      <span>{children}</span>
    </p>
  );
}

/** A titled panel: a section with its own h2. */
export function Panel({
  title,
  children,
  className,
}: {
  title: string;
  children: ReactNode;
  className?: string;
}) {
  const id = useId();
  return (
    <section
      aria-labelledby={id}
      className={cn("flex flex-col gap-3 border-t-[0.5px] border-hairline pt-5", className)}
    >
      <h2 id={id} className={LABEL}>
        {title}
      </h2>
      {children}
    </section>
  );
}

/** Notes for roles whose run could not be read in full (e.g. unreadable predictions). */
function RoleErrors({ roles }: { roles: ReasoningRole[] }) {
  const failed = roles.filter((r) => r.error !== null);
  if (failed.length === 0) return null;
  return (
    <div className="flex flex-col gap-1">
      {failed.map((r) => (
        <NoteLine key={r.role}>{`${ROLE_LABEL[r.role]}: ${r.error ?? ""}`}</NoteLine>
      ))}
    </div>
  );
}

function ScoreRow({ role }: { role: ReasoningRole }) {
  const isBase = role.role === "base";
  return (
    <tr className="border-b border-hairline last:border-0" data-role={role.role}>
      <th scope="row" className="px-2 py-2 text-left font-normal whitespace-nowrap text-ink">
        {ROLE_LABEL[role.role]}
      </th>
      <td className="px-2 py-2 font-mono whitespace-nowrap text-ink-muted">
        {role.run_id ?? <Missing why="no run yet" />}
      </td>
      <td className={NUMBER}>
        {role.accuracy === null ? <Missing /> : formatPct(role.accuracy)}
        {role.correct !== null && role.scored !== null && (
          <span className="text-ink-muted">
            {" "}
            ({count(role.correct)} of {count(role.scored)})
          </span>
        )}
      </td>
      <td className={NUMBER}>
        <Interval low={role.interval_low} high={role.interval_high} />
      </td>
      <td className={NUMBER}>
        {isBase ? (
          <Missing why="not fine-tuned" />
        ) : (
          <Figure value={role.trained_on} format={count} />
        )}
      </td>
      <td className={NUMBER}>
        {isBase ? (
          <Missing why="the reference point" />
        ) : role.gain_pts === null ? (
          <Missing />
        ) : (
          formatGain(role.gain_pts / 100)
        )}
      </td>
      <td className="px-2 py-2 whitespace-nowrap">
        {isBase ? <Missing why="the reference point" /> : (role.noise ?? <Missing />)}
      </td>
    </tr>
  );
}

/**
 * The score table (AC10.4.2): dev accuracy with its 95% interval, the training problems each
 * fine-tune learned from, the gain against base and the noise label, all in words.
 */
export function ScoreTable({ roles }: { roles: ReasoningRole[] }) {
  return (
    <Panel title="Dev accuracy">
      <div className="relative w-full overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">
            Dev accuracy of the base model, the reference fine-tune and the self-taught fine-tune
          </caption>
          <thead>
            <tr className="border-b border-hairline">
              <th scope="col" className={cn(HEAD, "text-left")}>
                Run
              </th>
              <th scope="col" className={cn(HEAD, "text-left")}>
                Run id
              </th>
              <th scope="col" className={cn(HEAD, "text-right")}>
                Dev accuracy
              </th>
              <th scope="col" className={cn(HEAD, "text-right")}>
                95% interval
              </th>
              <th scope="col" className={cn(HEAD, "text-right")}>
                Problems learned from
              </th>
              <th scope="col" className={cn(HEAD, "text-right")}>
                Gain vs base
              </th>
              <th scope="col" className={cn(HEAD, "text-left")}>
                Noise
              </th>
            </tr>
          </thead>
          <tbody>
            {roles.map((role) => (
              <ScoreRow key={role.role} role={role} />
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted-foreground">
        A gain under 4 points is within noise: the dev split is too small to tell it from luck.
      </p>
      <RoleErrors roles={roles} />
    </Panel>
  );
}

/** The summary sentences under "How it affected the score" (AC10.4.2). */
export function SummaryPanel({ summary }: { summary: string[] }) {
  return (
    <Panel title="How it affected the score">
      {summary.length === 0 ? (
        <p className="text-sm text-ink-muted">No summary yet.</p>
      ) : (
        <div className="flex max-w-[70ch] flex-col gap-2 text-ink">
          {summary.map((sentence) => (
            <p key={sentence}>{sentence}</p>
          ))}
        </div>
      )}
    </Panel>
  );
}

/** Problems each fine-tune fixed and broke against the base run (AC10.4.2). */
export function FlipsPanel({ flips }: { flips: ReasoningFlip[] }) {
  return (
    <Panel title="Problems fixed and broken">
      <p className="text-sm text-ink-muted">
        Fixed: the base model got it wrong and the fine-tune got it right. Broken: the other way
        round.
      </p>
      {flips.length === 0 ? (
        <p className="text-sm text-ink-muted">
          No counts yet: they need a fine-tune and a base run whose answers can both be read.
        </p>
      ) : (
        <ul className="flex flex-col gap-2 text-sm text-ink">
          {flips.map((flip) => (
            <li key={flip.role}>
              <span className="font-semibold">{ROLE_LABEL[flip.role]}</span>{" "}
              <span className="font-mono text-ink-muted">({flip.run_id})</span> against base{" "}
              <span className="font-mono text-ink-muted">({flip.against})</span>:{" "}
              <span className="num">{count(flip.fixed)}</span> fixed,{" "}
              <span className="num">{count(flip.broken)}</span> broken,{" "}
              <span className="num">{count(flip.both_right)}</span> right in both,{" "}
              <span className="num">{count(flip.both_wrong)}</span> wrong in both.
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

/** Mean reasoning lines and words of each run's answers (AC10.4.2). */
export function AnswerLengthPanel({ roles }: { roles: ReasoningRole[] }) {
  return (
    <Panel title="Answer length">
      <p className="text-sm text-ink-muted">
        Reasoning lines are the non-empty lines before the final answer line; words are counted in
        those lines.
      </p>
      <div className="relative w-full overflow-x-auto">
        <table className="w-full max-w-xl border-collapse text-sm">
          <caption className="sr-only">Mean reasoning lines and words per answer, per run</caption>
          <thead>
            <tr className="border-b border-hairline">
              <th scope="col" className={cn(HEAD, "text-left")}>
                Run
              </th>
              <th scope="col" className={cn(HEAD, "text-right")}>
                Mean reasoning lines
              </th>
              <th scope="col" className={cn(HEAD, "text-right")}>
                Mean reasoning words
              </th>
            </tr>
          </thead>
          <tbody>
            {roles.map((role) => (
              <tr key={role.role} className="border-b border-hairline last:border-0">
                <th scope="row" className="px-2 py-2 text-left font-normal text-ink">
                  {ROLE_LABEL[role.role]}
                </th>
                <td className={NUMBER}>
                  <Figure value={role.mean_lines} format={mean} />
                </td>
                <td className={NUMBER}>
                  <Figure value={role.mean_words} format={mean} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function Fact({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className={LABEL}>{term}</dt>
      <dd className="font-mono text-sm text-ink tabular-nums">{children}</dd>
    </div>
  );
}

function meanOrMissing(value: number | null): ReactNode {
  return <Figure value={value} format={mean} />;
}

/** The generation run behind the self-taught training data (AC10.4.2). */
export function GenerationPanel({
  generation,
  error,
}: {
  generation: ReasoningGeneration | null;
  error: string | null;
}) {
  return (
    <Panel title="Self-taught training data">
      {error !== null && <NoteLine>{error}</NoteLine>}
      {generation === null ? (
        error === null && (
          <p className="text-sm text-ink-muted">No generation figures for this run.</p>
        )
      ) : (
        <>
          <p className="text-sm text-ink-muted">
            The model wrote {count(generation.samples_per_problem)} solutions per training problem;
            the first one with the right final number and at least one reasoning line was kept.
          </p>
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Fact term="Generation run">{generation.run_id}</Fact>
            <Fact term="Problems tried">{count(generation.problems)}</Fact>
            <Fact term="Solved">{count(generation.solved)}</Fact>
            <Fact term="Kept">
              {count(generation.kept)} ({formatPct(generation.kept_fraction)})
            </Fact>
            <Fact term="Lines, kept solutions">{meanOrMissing(generation.mean_lines_kept)}</Fact>
            <Fact term="Lines, reference solutions">
              {meanOrMissing(generation.mean_lines_reference)}
            </Fact>
            <Fact term="Words, kept solutions">{meanOrMissing(generation.mean_words_kept)}</Fact>
            <Fact term="Words, reference solutions">
              {meanOrMissing(generation.mean_words_reference)}
            </Fact>
          </dl>
        </>
      )}
    </Panel>
  );
}

function Output({ label, text }: { label: string; text: string }) {
  return (
    <figure className="flex min-w-0 flex-col gap-1">
      <figcaption className={LABEL}>{label}</figcaption>
      <pre className="rounded-sm border-[0.5px] border-hairline bg-panel p-3 font-mono text-xs break-words whitespace-pre-wrap text-ink">
        {text}
      </pre>
    </figure>
  );
}

/** Problems the self-taught model fixed, with both outputs verbatim side by side (AC10.4.3). */
export function ExamplesPanel({ examples }: { examples: ReasoningExample[] }) {
  return (
    <Panel title="Examples">
      <p className="text-sm text-ink-muted">
        Dev problems the base model got wrong and the self-taught model got right, outputs exactly
        as written.
      </p>
      {examples.length === 0 ? (
        <p className="text-sm text-ink-muted">No examples: no problem was fixed.</p>
      ) : (
        <ul className="flex flex-col gap-6">
          {examples.map((example) => (
            <li key={example.problem_id} className="flex flex-col gap-2">
              <p className="text-sm text-ink">
                Problem <span className="font-mono">{example.problem_id}</span>
                <span aria-hidden="true"> · </span>
                <span className="sr-only">, </span>
                gold answer <span className="font-mono">{example.gold}</span>
              </p>
              <div className="grid gap-3 md:grid-cols-2">
                <Output label={ROLE_LABEL.base} text={example.base_output} />
                <Output label={ROLE_LABEL.selfcot} text={example.selfcot_output} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
