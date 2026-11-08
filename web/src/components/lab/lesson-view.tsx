import { useState } from "react";

import { Answers } from "@/components/lab/answers";
import { Guess } from "@/components/lab/guess";
import { LabChart } from "@/components/lab/lab-chart";
import { ResultsTable } from "@/components/lab/results-table";
import { RunPanel } from "@/components/lab/run-panel";
import { usePolled } from "@/components/lab/use-polled";
import { Button } from "@/components/ui/button";
import type { LabLessonInfo } from "@/lib/api";
import { useApi } from "@/lib/api-context";
import { verdicts } from "@/lib/lab-verdicts";

export interface LessonViewProps {
  info: LabLessonInfo;
  /** The lesson whose run is going (from the list), or null. */
  active: LabLessonInfo | null;
  onChanged(): void;
}

/** One lesson: its text, guess, run controls, charts, table, verdicts, samples and big-run text. */
export function LessonView({ info, active, onChanged }: LessonViewProps) {
  const api = useApi();
  const [tick, setTick] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const lessonState = usePolled(
    () => api.getLabLesson(info.id),
    (d) => d.status.state === "running",
    info.id,
    tick,
  );
  const data = lessonState.state === "ready" ? lessonState.data : null;
  const lesson = data?.lesson ?? info;
  const state = data?.status.state ?? info.state;
  const finished = state === "finished";
  const running = state === "running" || active?.id === info.id;
  const other = active !== null && active.id !== info.id ? active : null;
  const results = data?.results ?? [];
  const hasLines = results.some((r) => r.lines.length > 0);
  const hasSummary = results.some((r) => r.summary !== null);
  const happened = finished ? verdicts(info.id, results) : [];

  return (
    <article className="flex min-w-0 flex-col gap-6">
      <header className="flex max-w-[75ch] flex-col gap-2">
        <h2 className="text-[22px] font-semibold">{`Lesson ${lesson.number}: ${lesson.title}`}</h2>
        <p className="text-ink">{lesson.question}</p>
        <p className="text-sm text-ink-muted">{lesson.watch}</p>
        <ul className="flex flex-col gap-1 text-sm">
          {lesson.variants.map((v) => (
            <li key={v.name}>
              <span className="text-ink">{v.label}</span>
              <span className="text-ink-muted">{" · "}</span>
              <span className="text-ink-muted">{v.changes}</span>
            </li>
          ))}
        </ul>
      </header>

      <div className="max-w-[75ch]">
        <Guess lesson={lesson} finished={finished} />
      </div>

      <RunPanel
        lesson={lesson}
        data={data}
        running={running}
        other={other}
        onChanged={() => {
          setTick((t) => t + 1);
          onChanged();
        }}
      />

      {lessonState.state === "error" && (
        <div className="flex flex-col items-start gap-2">
          <p role="alert" className="text-sm text-danger">
            {lessonState.error.message}
          </p>
          <Button variant="outline" size="sm" onClick={() => setTick((t) => t + 1)}>
            Try again
          </Button>
        </div>
      )}

      {hasLines ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <LabChart kind="train-loss" title="Training loss" results={results} />
          <LabChart kind="dev-loss" title="Dev loss" results={results} />
        </div>
      ) : (
        data !== null &&
        !running && (
          <p className="text-ink-muted">Not run yet: press Run this lesson to fill the charts.</p>
        )
      )}

      {hasSummary && <ResultsTable lessonId={info.id} results={results} />}

      {happened.length > 0 && (
        <section className="flex max-w-[75ch] flex-col gap-2">
          <h3 className="text-lg font-semibold">What happened</h3>
          <ul className="list-disc pl-5 text-sm text-ink">
            {happened.map((sentence) => (
              <li key={sentence}>{sentence}</li>
            ))}
          </ul>
        </section>
      )}

      {finished ? <Answers key={info.id} lessonId={info.id} results={results} /> : null}

      <section className="flex max-w-[75ch] flex-col gap-2">
        {finished || revealed ? (
          <>
            <h3 className="text-lg font-semibold">Why it happens</h3>
            <p className="text-ink">{lesson.why}</p>
          </>
        ) : (
          <Button
            variant="outline"
            size="sm"
            className="self-start"
            onClick={() => setRevealed(true)}
          >
            Show the explanation now
          </Button>
        )}
      </section>

      {finished && (
        <>
          <section className="flex max-w-[75ch] flex-col gap-2">
            <h3 className="text-lg font-semibold">For the big runs</h3>
            <p className="text-ink">{lesson.big_run}</p>
          </section>
          <section className="flex max-w-[75ch] flex-col gap-2">
            <h3 className="text-lg font-semibold">Check question</h3>
            <p className="text-ink">{lesson.check}</p>
          </section>
        </>
      )}
    </article>
  );
}
