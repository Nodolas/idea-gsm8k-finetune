import type { CourseOverview } from "@/lib/api";

/** "Your progress: N of 24 steps done (P %)" (AC12.5.1). */
export function ProgressLine({ progress }: { progress: CourseOverview["progress"] }) {
  return (
    <p className="num text-ink">{`Your progress: ${progress.done} of ${progress.total} steps done (${progress.percent} %)`}</p>
  );
}

/** "First-try answers right: R of Q". */
export function FirstTryLine({ progress }: { progress: CourseOverview["progress"] }) {
  return (
    <p className="num text-sm text-ink-muted">{`First-try answers right: ${progress.first_try_right} of ${progress.questions_answered}`}</p>
  );
}

/** One bar per part with its done count as text, so colour is never the only carrier (NFR9). */
export function PartBars({ parts }: { parts: CourseOverview["parts"] }) {
  return (
    <ul className="grid list-none gap-3 sm:grid-cols-2 lg:grid-cols-5">
      {parts.map((part) => {
        const percent = part.total === 0 ? 0 : Math.round((part.done * 100) / part.total);
        return (
          <li
            key={part.number}
            data-part-progress={part.number}
            className="flex min-w-0 flex-col gap-1"
          >
            <span className="text-sm text-ink">{part.title}</span>
            <span className="num text-xs text-ink-muted">{`${part.done} of ${part.total} done`}</span>
            <span
              role="progressbar"
              aria-label={`${part.title} progress`}
              aria-valuemin={0}
              aria-valuemax={part.total}
              aria-valuenow={part.done}
              className="block h-1.5 w-full overflow-hidden rounded-sm bg-hairline"
            >
              <span className="block h-full bg-orange" style={{ width: `${percent}%` }} />
            </span>
          </li>
        );
      })}
    </ul>
  );
}
