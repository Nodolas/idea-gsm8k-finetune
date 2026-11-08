import { useState } from "react";

import { Button } from "@/components/ui/button";
import { toApiError, type LabLesson, type LabLessonInfo } from "@/lib/api";
import { useApi } from "@/lib/api-context";

export interface RunPanelProps {
  lesson: LabLessonInfo;
  data: LabLesson | null;
  running: boolean;
  /** The lesson whose run holds the lab, when it is not this one. */
  other: LabLessonInfo | null;
  onChanged(): void;
}

function progress(lesson: LabLessonInfo, data: LabLesson | null): string | null {
  const name = data?.status.variant ?? null;
  if (name === null) return null;
  const index = lesson.variants.findIndex((v) => v.name === name);
  if (index < 0) return null;
  const label = lesson.variants[index].label;
  const lines = data?.results.find((r) => r.name === name)?.lines ?? [];
  const last = lines.reduce((a, l) => (l.step > a.step ? l : a), lines[0]);
  const where = last ? `step ${last.step} of ${last.total_steps}` : "starting";
  return `Variant ${index + 1} of ${lesson.variants.length}: ${label}, ${where}`;
}

/** Run and stop controls with the running progress, the CPU note and any error. */
export function RunPanel({ lesson, data, running, other, onChanged }: RunPanelProps) {
  const api = useApi();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const act = async (call: () => Promise<unknown>) => {
    setError(null);
    setBusy(true);
    try {
      await call();
    } catch (e) {
      setError(toApiError(e).message);
    } finally {
      setBusy(false);
      onChanged();
    }
  };

  const text = running ? progress(lesson, data) : null;
  const failure = data?.status.state === "failed" ? data.status.message : null;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex max-w-[75ch] flex-col items-start gap-2">
        {running ? (
          <Button variant="outline" disabled={busy} onClick={() => void act(() => api.stopLab())}>
            Stop the lesson
          </Button>
        ) : (
          <Button
            disabled={busy || other !== null}
            onClick={() => void act(() => api.runLabLesson(lesson.id))}
          >
            Run this lesson
          </Button>
        )}
        {other !== null && !running && (
          <p className="text-sm text-ink-muted">
            {`Lesson ${other.number} · ${other.title} is running. Wait for it to end, or stop it from its page.`}
          </p>
        )}
        <p className="text-sm text-ink-muted">
          {`On the CPU, about ${lesson.estimate_minutes} minutes. It never uses the GPU, so a GPU run keeps going.`}
        </p>
      </div>
      {text && <p className="num text-sm text-ink">{text}</p>}
      {failure && (
        <p role="alert" className="text-sm text-danger">
          {failure}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
