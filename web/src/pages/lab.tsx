import { useState } from "react";
import { useSearchParams } from "react-router";

import { LessonList } from "@/components/lab/lesson-list";
import { LessonView } from "@/components/lab/lesson-view";
import { usePolled } from "@/components/lab/use-polled";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { LabLessonInfo } from "@/lib/api";
import { useApi } from "@/lib/api-context";

/** The lesson to show: `?lesson=` when it names one, else the first not finished, else the first. */
function pickLesson(lessons: LabLessonInfo[], wanted: string | null): LabLessonInfo {
  return (
    lessons.find((l) => l.id === wanted) ??
    lessons.find((l) => l.state !== "finished") ??
    lessons[0]
  );
}

/**
 * The Lab page (US11.4): twelve small fine-tuning lessons that run on the CPU with a tiny model,
 * each with a guess, the curves, a results table and a plain explanation.
 */
export function LabPage() {
  const api = useApi();
  const [params] = useSearchParams();
  const [tick, setTick] = useState(0);
  const list = usePolled(
    () => api.getLab(),
    (d) => d.active !== null,
    "lab",
    tick,
  );

  let body;
  if (list.state === "loading") {
    body = (
      <div className="flex flex-col gap-2" aria-busy="true">
        <p className="text-ink-muted">Reading the lab…</p>
        <Skeleton className="h-8 w-full bg-panel" />
      </div>
    );
  } else if (list.state === "error") {
    body = (
      <div className="flex flex-col items-start gap-3">
        <p role="alert" className="text-sm text-danger">
          {list.error.message}
        </p>
        <Button variant="outline" size="sm" onClick={() => setTick((t) => t + 1)}>
          Try again
        </Button>
      </div>
    );
  } else {
    const { lessons, active } = list.data;
    const shown = pickLesson(lessons, params.get("lesson"));
    const running = active === null ? null : (lessons.find((l) => l.id === active) ?? null);
    body = (
      <div className="grid min-w-0 gap-8 lg:grid-cols-[18rem_minmax(0,1fr)]">
        <LessonList lessons={lessons} shownId={shown.id} />
        <LessonView
          key={shown.id}
          info={shown}
          active={running}
          onChanged={() => setTick((t) => t + 1)}
        />
      </div>
    );
  }

  return (
    <div className="flex w-full flex-col gap-6 px-[var(--gutter)] py-8">
      <div className="flex max-w-[75ch] flex-col gap-2">
        <h1 className="text-[28px] font-semibold">Lab</h1>
        <p className="text-ink">
          Small experiments that show what each fine-tuning choice does. Guess first, run the
          lesson, then compare the curves with your guess.
        </p>
        {list.state === "ready" && (
          <p className="font-mono text-xs text-muted-foreground">
            {`${list.data.model.name} · ${list.data.model.layers} layers · runs on the CPU only`}
          </p>
        )}
      </div>
      {body}
    </div>
  );
}
