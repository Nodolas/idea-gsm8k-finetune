import { useEffect, useRef, useState } from "react";

import type { PolledState } from "@/components/lab/use-polled";
import { toApiError, type CourseStep, type Status } from "@/lib/api";
import { useApi } from "@/lib/api-context";
import { COURSE_POLL_MS } from "@/lib/course";

export interface StepData {
  step: CourseStep;
  /** The service status, read for gpu steps only (who holds the GPU); null when unknown. */
  status: Status | null;
}

interface Held {
  key: string;
  value: PolledState<StepData>;
}

/** Whether one of the step's runs is queued or running. */
export function hasActiveRun(step: CourseStep): boolean {
  return step.runs.some((r) => r.state === "queued" || r.state === "running");
}

/**
 * Reads a course step when `stepId` or `tick` changes, and again every 3 seconds while one of its
 * runs is queued or running (or while `watchDesigns` is set and architectures.json is missing).
 * A new `stepId` starts from loading; a new `tick` keeps the last answer on screen; a failed
 * refresh keeps the last good answer.
 */
export function useCourseStep(
  stepId: string,
  tick: number,
  watchDesigns: boolean,
): PolledState<StepData> {
  const api = useApi();
  const [held, setHeld] = useState<Held>({ key: stepId, value: { state: "loading" } });
  const watchRef = useRef(watchDesigns);
  useEffect(() => {
    watchRef.current = watchDesigns;
  });

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let designPolls = 0;
    const load = async (): Promise<StepData> => {
      const step = await api.getCourseStep(stepId);
      let status: Status | null = null;
      if (step.step.kind === "gpu") {
        try {
          status = await api.getStatus();
        } catch {
          status = null;
        }
      }
      return { step, status };
    };
    const run = () => {
      load().then(
        (data) => {
          if (!alive) return;
          setHeld({ key: stepId, value: { state: "ready", data } });
          const watching = watchRef.current && data.step.architectures === null && designPolls < 40;
          if (watching) designPolls += 1;
          const again = hasActiveRun(data.step) || watching;
          if (again) timer = setTimeout(run, COURSE_POLL_MS);
        },
        (error: unknown) => {
          if (!alive) return;
          setHeld((prev) =>
            prev.key === stepId && prev.value.state === "ready"
              ? prev
              : { key: stepId, value: { state: "error", error: toApiError(error) } },
          );
        },
      );
    };
    run();
    return () => {
      alive = false;
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [api, stepId, tick]);

  return held.key === stepId ? held.value : { state: "loading" };
}
