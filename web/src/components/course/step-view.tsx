import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router";

import { GpuRuns } from "@/components/course/run-area";
import {
  DesignsView,
  ReadDesigns,
  TokensView,
  WeightsView,
} from "@/components/course/inspect-views";
import { OwnWords } from "@/components/course/own-words";
import { Prose } from "@/components/course/prose";
import { Quiz } from "@/components/course/quiz";
import { ComparisonTable, MemoryTable } from "@/components/course/tables";
import { hasActiveRun, useCourseStep, type StepData } from "@/components/course/use-step";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { CourseStep } from "@/lib/api";
import { KIND_WORDS, LESSON_STATE_WORDS, STEP_STATE_WORDS } from "@/lib/course";
import { cn } from "@/lib/utils";

export interface StepViewProps {
  stepId: string;
  /** Called when the step's state, run part or quiz changed, so the overview is read again. */
  onProgress(): void;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex min-w-0 flex-col gap-3">
      <h3 className="text-lg font-semibold">{title}</h3>
      {children}
    </section>
  );
}

function LessonBlock({ step }: { step: CourseStep }) {
  const lesson = step.lesson;
  if (lesson === null) return <p className="text-ink-muted">This step has no lab lesson.</p>;
  return (
    <div className="flex max-w-[75ch] flex-col gap-2 rounded-sm border-[0.5px] border-hairline bg-panel p-3">
      <p className="text-ink">{`Lesson ${lesson.number} · ${lesson.title}`}</p>
      <p className="text-ink-muted">{lesson.question}</p>
      <p className="num text-xs text-ink-muted">
        {`State: ${LESSON_STATE_WORDS[lesson.state] ?? lesson.state}`}
      </p>
      <Link
        to={{ pathname: "/lab", search: `?lesson=${lesson.id}` }}
        className="self-start rounded-sm text-orange underline"
      >
        {`Open lesson ${lesson.number} in the Lab`}
      </Link>
    </div>
  );
}

function RunArea({
  data,
  onChanged,
  onDesignsStarted,
}: {
  data: StepData;
  onChanged(): void;
  onDesignsStarted(): void;
}) {
  const { step, status } = data;
  switch (step.step.kind) {
    case "gpu":
      return (
        <GpuRuns
          stepId={step.step.id}
          runs={step.runs}
          status={status}
          notice={step.notice ?? null}
          onChanged={onChanged}
        />
      );
    case "lab":
      return <LessonBlock step={step} />;
    case "inspect": {
      const designs = step.architectures;
      if (designs === null)
        return <ReadDesigns stepId={step.step.id} onStarted={onDesignsStarted} />;
      if (step.step.id === "c02") return <TokensView data={designs} />;
      if (step.step.id === "c03") return <WeightsView data={designs} />;
      return <DesignsView data={designs} />;
    }
    default:
      return null;
  }
}

function Extra({ step }: { step: CourseStep }) {
  if (step.memory !== null) return <MemoryTable rows={step.memory} />;
  if (step.comparison !== null) return <ComparisonTable rows={step.comparison} />;
  return null;
}

function StepBody({
  data,
  onChanged,
  onDesignsStarted,
  onProgress,
}: {
  data: StepData;
  onChanged(): void;
  onDesignsStarted(): void;
  onProgress(): void;
}) {
  const { step } = data;
  const summary = step.step;
  const [revealed, setRevealed] = useState(false);
  const questionsShown = summary.kind === "read" || summary.run_done || revealed;

  return (
    <>
      <Section title="Why this step">
        <Prose text={step.why} />
      </Section>
      <Prose text={step.body} />
      <Extra step={step} />
      {summary.kind !== "read" ? (
        <Section title="What this step runs">
          <RunArea data={data} onChanged={onChanged} onDesignsStarted={onDesignsStarted} />
        </Section>
      ) : null}
      <Section title="Check what you learned">
        {questionsShown ? (
          <Quiz
            stepId={summary.id}
            questions={step.questions}
            passed={summary.quiz_passed}
            onSubmitted={() => {
              onChanged();
              onProgress();
            }}
          />
        ) : (
          <div className="flex flex-col items-start gap-2">
            <p className="max-w-[75ch] text-sm text-ink-muted">
              The questions open once this step's run part is done. You can also answer them now.
            </p>
            <Button variant="outline" onClick={() => setRevealed(true)}>
              I have read this, show the questions
            </Button>
          </div>
        )}
      </Section>
      <Section title="In your own words">
        <OwnWords
          stepId={summary.id}
          prompt={step.own_words_prompt}
          saved={step.own_words}
          modelAnswer={step.model_answer}
        />
      </Section>
    </>
  );
}

/** The step's progress marks; a change tells the page to read the overview again. */
function useProgressSignal(step: CourseStep | null, onProgress: () => void): void {
  const mark = step ? `${step.step.state}|${step.step.run_done}|${step.step.quiz_passed}` : null;
  const last = useRef<string | null>(null);
  const callback = useRef(onProgress);
  useEffect(() => {
    callback.current = onProgress;
  });
  useEffect(() => {
    if (mark === null) return;
    if (last.current !== null && last.current !== mark) callback.current();
    last.current = mark;
  }, [mark]);
}

/** One shown step (AC12.5.3): why, body, what it runs, the questions and own words. */
export function StepView({ stepId, onProgress }: StepViewProps) {
  const [tick, setTick] = useState(0);
  const [watchDesigns, setWatchDesigns] = useState(false);
  const loaded = useCourseStep(stepId, tick, watchDesigns);
  const step = loaded.state === "ready" ? loaded.data.step : null;
  useProgressSignal(step, onProgress);

  if (loaded.state === "loading") {
    return (
      <div className="flex flex-col gap-2" aria-busy="true">
        <p className="text-ink-muted">Reading the step…</p>
        <Skeleton className="h-8 w-full bg-panel" />
      </div>
    );
  }
  if (loaded.state === "error") {
    return (
      <div className="flex flex-col items-start gap-3">
        <p role="alert" className="max-w-[75ch] text-sm text-danger">
          {loaded.error.message}
        </p>
        <Button variant="outline" size="sm" onClick={() => setTick((t) => t + 1)}>
          Try again
        </Button>
      </div>
    );
  }

  const { step: shown } = loaded.data;
  const summary = shown.step;
  const reload = () => setTick((t) => t + 1);
  return (
    <article data-step={summary.id} className="flex min-w-0 flex-col gap-6">
      <header className="flex flex-col gap-2">
        <p className="label-caps text-ink-muted">{shown.part_title}</p>
        <h2 className="text-[22px] font-semibold">{`Step ${summary.number} · ${summary.title}`}</h2>
        <p className="num flex flex-wrap items-center gap-2 text-sm text-ink-muted">
          <span className={cn(summary.state === "done" && "text-ok")}>
            {STEP_STATE_WORDS[summary.state]}
          </span>
          <span aria-hidden="true">·</span>
          <span>{KIND_WORDS[summary.kind]}</span>
          {hasActiveRun(shown) ? (
            <>
              <span aria-hidden="true">·</span>
              <span>Updating every 3 seconds</span>
            </>
          ) : null}
        </p>
      </header>
      <StepBody
        data={loaded.data}
        onChanged={reload}
        onDesignsStarted={() => {
          setWatchDesigns(true);
          reload();
        }}
        onProgress={onProgress}
      />
    </article>
  );
}
