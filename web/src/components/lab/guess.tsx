import { useState } from "react";

import type { LabLessonInfo } from "@/lib/api";

const keyFor = (lessonId: string) => `gsm8k-lab-guess-${lessonId}`;

/** The guess kept in this browser; every storage access may throw, and then there is none. */
export function readGuess(lessonId: string): string | null {
  try {
    return window.localStorage.getItem(keyFor(lessonId));
  } catch {
    return null;
  }
}

function writeGuess(lessonId: string, option: string): void {
  try {
    window.localStorage.setItem(keyFor(lessonId), option);
  } catch {
    // storage unavailable: the guess lives on this page only
  }
}

export interface GuessProps {
  lesson: LabLessonInfo;
  finished: boolean;
}

/** "Your guess" with three radio options, or "You guessed: ..." once the lesson is finished. */
export function Guess({ lesson, finished }: GuessProps) {
  const [guess, setGuess] = useState<string | null>(() => readGuess(lesson.id));
  const valid = guess !== null && lesson.guess_options.includes(guess) ? guess : null;

  if (finished) {
    return (
      <section className="flex flex-col gap-1">
        <h3 className="text-lg font-semibold">Your guess</h3>
        <p className="text-ink">{valid ? `You guessed: ${valid}` : "No guess made"}</p>
      </section>
    );
  }
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-1 text-lg font-semibold">Your guess</legend>
      <p className="text-ink">{lesson.guess_prompt}</p>
      {lesson.guess_options.map((option) => (
        <label key={option} className="flex items-start gap-2 text-sm text-ink">
          <input
            type="radio"
            name={`lab-guess-${lesson.id}`}
            value={option}
            checked={valid === option}
            onChange={() => {
              setGuess(option);
              writeGuess(lesson.id, option);
            }}
            className="mt-1"
          />
          <span>{option}</span>
        </label>
      ))}
    </fieldset>
  );
}
