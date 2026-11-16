import { useState } from "react";
import { useSearchParams } from "react-router";

import { PartBars, FirstTryLine, ProgressLine } from "@/components/course/progress";
import { StepList } from "@/components/course/step-list";
import { StepView } from "@/components/course/step-view";
import { usePolled } from "@/components/lab/use-polled";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { CourseOverview } from "@/lib/api";
import { useApi } from "@/lib/api-context";

/** The step to show: `?step=` when it names one, else the next step, else the first. */
function pickStep(overview: CourseOverview, wanted: string | null): string {
  const all = overview.parts.flatMap((part) => part.steps);
  if (wanted !== null && all.some((step) => step.id === wanted)) return wanted;
  return overview.next_step ?? all[0]?.id ?? "c01";
}

/**
 * The Course page (US12.5): the guided path through the project in 24 steps, with progress, the
 * parts and steps, and the shown step with its runs, questions and own words.
 */
export function CoursePage() {
  const api = useApi();
  const [params, setParams] = useSearchParams();
  const [tick, setTick] = useState(0);
  const overview = usePolled(
    () => api.getCourse(),
    () => false,
    "course",
    tick,
  );
  const refresh = () => setTick((t) => t + 1);

  const choose = (stepId: string) => {
    setParams({ step: stepId });
    api.openCourseStep(stepId).then(refresh, () => undefined);
  };

  let body;
  if (overview.state === "loading") {
    body = (
      <div className="flex flex-col gap-2" aria-busy="true">
        <p className="text-ink-muted">Reading the course…</p>
        <Skeleton className="h-8 w-full bg-panel" />
      </div>
    );
  } else if (overview.state === "error") {
    body = (
      <div className="flex flex-col items-start gap-3">
        <p role="alert" className="text-sm text-danger">
          {overview.error.message}
        </p>
        <Button variant="outline" size="sm" onClick={refresh}>
          Try again
        </Button>
      </div>
    );
  } else {
    const data = overview.data;
    const shownId = pickStep(data, params.get("step"));
    const next = data.parts.flatMap((p) => p.steps).find((s) => s.id === data.next_step) ?? null;
    body = (
      <>
        <section aria-label="Your progress" className="flex flex-col gap-3">
          <ProgressLine progress={data.progress} />
          <FirstTryLine progress={data.progress} />
          <PartBars parts={data.parts} />
          <div>
            {next ? (
              <Button onClick={() => choose(next.id)}>
                {`Continue with step ${next.number}: ${next.title}`}
              </Button>
            ) : (
              <p className="num font-medium text-ok">Course complete</p>
            )}
          </div>
        </section>
        <div className="grid min-w-0 gap-8 lg:grid-cols-[22rem_minmax(0,1fr)]">
          <StepList parts={data.parts} shownId={shownId} onChoose={choose} />
          <StepView key={shownId} stepId={shownId} onProgress={refresh} />
        </div>
      </>
    );
  }

  return (
    <div className="flex w-full flex-col gap-6 px-[var(--gutter)] py-8">
      <div className="flex max-w-[75ch] flex-col gap-2">
        <h1 className="text-[28px] font-semibold">Course</h1>
        <p className="text-ink">
          A guided path through the whole project in 24 steps: how a base model is scored, how model
          designs differ, how fine-tuning works, and the pipeline. Read, run, answer, then say it in
          your own words.
        </p>
      </div>
      {body}
    </div>
  );
}
