import { Link } from "react-router";

import type { LabLessonInfo, LabState } from "@/lib/api";
import { cn } from "@/lib/utils";

export const STATE_WORDS: Record<LabState, string> = {
  "not-run": "Not run",
  running: "Running",
  finished: "Done",
  failed: "Failed",
  stopped: "Stopped",
};

/** The twelve lessons in order, each linking to `?lesson=<id>`, with its state in words. */
export function LessonList({ lessons, shownId }: { lessons: LabLessonInfo[]; shownId: string }) {
  return (
    <nav aria-label="Lab lessons">
      <ul className="flex flex-col">
        {lessons.map((lesson) => (
          <li
            key={lesson.id}
            className="flex items-baseline justify-between gap-3 border-b-[0.5px] border-hairline py-2 text-sm"
          >
            <Link
              to={{ search: `?lesson=${lesson.id}` }}
              aria-current={lesson.id === shownId ? "true" : undefined}
              className={cn(
                "rounded-sm text-ink-muted hover:text-ink",
                lesson.id === shownId &&
                  "text-ink underline decoration-orange decoration-1 underline-offset-[6px]",
              )}
            >
              {`Lesson ${lesson.number} · ${lesson.title}`}
            </Link>
            <span
              className={cn(
                "num shrink-0 text-xs text-ink-muted",
                lesson.state === "running" && "text-orange",
                lesson.state === "failed" && "text-danger",
              )}
            >
              {STATE_WORDS[lesson.state]}
            </span>
          </li>
        ))}
      </ul>
    </nav>
  );
}
