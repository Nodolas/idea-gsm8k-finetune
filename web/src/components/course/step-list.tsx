import type { CourseOverview } from "@/lib/api";
import { KIND_WORDS, STEP_STATE_WORDS } from "@/lib/course";
import { cn } from "@/lib/utils";

export interface StepListProps {
  parts: CourseOverview["parts"];
  shownId: string;
  onChoose(stepId: string): void;
}

/** The five parts and their steps as "Step N · <title>" with state and kind in words (AC12.5.2). */
export function StepList({ parts, shownId, onChoose }: StepListProps) {
  return (
    <nav aria-label="Course steps" className="flex min-w-0 flex-col gap-5">
      {parts.map((part) => (
        <section key={part.number} className="flex flex-col gap-1">
          <h3 className="label-caps text-ink-muted">{part.title}</h3>
          <ul className="flex flex-col">
            {part.steps.map((step) => (
              <li
                key={step.id}
                className="flex flex-col gap-0.5 border-b-[0.5px] border-hairline py-2 text-sm"
              >
                <button
                  type="button"
                  onClick={() => onChoose(step.id)}
                  aria-current={step.id === shownId ? "step" : undefined}
                  className={cn(
                    "rounded-sm text-left text-ink-muted hover:text-ink",
                    step.id === shownId &&
                      "text-ink underline decoration-orange decoration-1 underline-offset-[6px]",
                  )}
                >
                  {`Step ${step.number} · ${step.title}`}
                </button>
                <span className="num flex gap-2 text-xs text-ink-muted">
                  <span className={cn(step.state === "done" && "text-ok")}>
                    {STEP_STATE_WORDS[step.state]}
                  </span>
                  <span aria-hidden="true">·</span>
                  <span>{KIND_WORDS[step.kind]}</span>
                </span>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </nav>
  );
}
