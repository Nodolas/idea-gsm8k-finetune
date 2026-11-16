import { useState } from "react";

import { Prose } from "@/components/course/prose";
import { Button } from "@/components/ui/button";
import { toApiError, type CourseQuestion, type QuizResult } from "@/lib/api";
import { useApi } from "@/lib/api-context";
import { cn } from "@/lib/utils";

export interface QuizProps {
  stepId: string;
  questions: CourseQuestion[];
  /** The step's quiz was passed at some time (from the service). */
  passed: boolean;
  /** Called after answers were sent, so the step and the overview are read again. */
  onSubmitted(): void;
}

/**
 * "Check what you learned": one native radio group per question; "Check my answers" sends one
 * option per question; each question then reads "Right" or "Not quite" with the right option and
 * its explanation; with all right the step reads "Quiz passed", else "Try again" clears the
 * choices (AC12.5.7).
 */
export function Quiz({ stepId, questions, passed, onSubmitted }: QuizProps) {
  const api = useApi();
  const [choices, setChoices] = useState<Array<number | null>>(() => questions.map(() => null));
  const [result, setResult] = useState<QuizResult | null>(null);
  const [retry, setRetry] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const answeredBefore = questions.length > 0 && questions.every((q) => q.answered);
  const mode: "open" | "result" | "saved" = result
    ? "result"
    : answeredBefore && !retry
      ? "saved"
      : "open";
  const complete = choices.every((c) => c !== null);

  const submit = async () => {
    setError(null);
    setBusy(true);
    try {
      const answer = await api.submitCourseQuiz(
        stepId,
        choices.map((c) => c ?? 0),
      );
      setResult(answer);
      onSubmitted();
    } catch (e) {
      setError(toApiError(e).message);
    } finally {
      setBusy(false);
    }
  };

  const again = () => {
    setChoices(questions.map(() => null));
    setResult(null);
    setRetry(true);
    setError(null);
  };

  const quizPassed = mode === "result" ? (result?.passed ?? false) : passed;

  return (
    <div className="flex min-w-0 flex-col gap-5">
      {questions.map((question, i) => {
        const verdict = mode === "result" ? (result?.results[i] ?? null) : null;
        const rightOption =
          mode === "result"
            ? (verdict?.right_option ?? null)
            : mode === "saved"
              ? question.right
              : null;
        const explanation =
          mode === "result"
            ? (verdict?.explanation ?? null)
            : mode === "saved"
              ? question.explanation
              : null;
        return (
          <fieldset key={i} className="flex min-w-0 flex-col gap-2" disabled={mode !== "open"}>
            <legend className="mb-1 max-w-[75ch] font-medium text-ink">{question.prompt}</legend>
            {question.options.map((option, j) => (
              <label
                key={j}
                data-right-option={rightOption === j ? "" : undefined}
                className={cn(
                  "flex max-w-[75ch] cursor-pointer items-start gap-2 text-ink",
                  rightOption === j && "text-ok",
                )}
              >
                <input
                  type="radio"
                  name={`course-${stepId}-q${i}`}
                  checked={choices[i] === j}
                  onChange={() => setChoices((prev) => prev.map((c, k) => (k === i ? j : c)))}
                  className="mt-1 accent-orange"
                />
                <span>
                  {option}
                  {rightOption === j ? (
                    <span className="text-sm">{" (the right answer)"}</span>
                  ) : null}
                </span>
              </label>
            ))}
            {verdict ? (
              <p className={cn("num font-medium", verdict.right ? "text-ok" : "text-danger")}>
                {verdict.right ? "Right" : "Not quite"}
              </p>
            ) : null}
            {explanation ? <Prose text={explanation} className="text-sm" /> : null}
          </fieldset>
        );
      })}
      {quizPassed && mode !== "open" ? (
        <p role="status" className="num font-medium text-ok">
          Quiz passed
        </p>
      ) : null}
      <div className="flex flex-wrap items-center gap-3">
        {mode === "open" ? (
          <Button disabled={busy || !complete} onClick={() => void submit()}>
            Check my answers
          </Button>
        ) : mode === "result" && result?.passed ? null : (
          <Button variant="outline" onClick={again}>
            {mode === "saved" && passed ? "Answer again" : "Try again"}
          </Button>
        )}
        {mode === "open" && !complete ? (
          <p className="text-sm text-ink-muted">Choose one option for each question.</p>
        ) : null}
      </div>
      {error ? (
        <p role="alert" className="max-w-[75ch] text-sm text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}
