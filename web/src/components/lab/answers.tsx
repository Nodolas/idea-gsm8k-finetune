import { useState } from "react";

import type { LabVariantResult } from "@/lib/api";
import { endedVariants, orderVariants } from "@/lib/lab-verdicts";

/** "Answers before and after": the chosen variant's sample problems (AC11.4.7). */
export function Answers({ lessonId, results }: { lessonId: string; results: LabVariantResult[] }) {
  const ordered = orderVariants(lessonId, endedVariants(results));
  const [chosen, setChosen] = useState<string | null>(null);
  if (ordered.length === 0) return null;
  const current = ordered.find((e) => e.name === chosen) ?? ordered[0];
  return (
    <section className="flex flex-col gap-3">
      <h3 className="text-lg font-semibold">Answers before and after</h3>
      <div className="flex items-center gap-2 text-sm">
        <label htmlFor="lab-answers-variant">Variant</label>
        <select
          id="lab-answers-variant"
          value={current.name}
          onChange={(event) => setChosen(event.target.value)}
          className="rounded-sm border-[0.5px] border-hairline bg-background px-2 py-1 text-ink"
        >
          {ordered.map((e) => (
            <option key={e.name} value={e.name}>
              {e.label}
            </option>
          ))}
        </select>
      </div>
      <ul className="flex flex-col gap-4">
        {current.summary.samples.map((sample, i) => (
          <li key={i} className="flex max-w-[75ch] flex-col gap-1 text-sm">
            <p className="text-ink">{sample.question}</p>
            <p className="text-ink-muted">
              <span>Right answer: </span>
              <span className="num">{sample.gold}</span>
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              <div className="min-w-0">
                <p className="text-xs text-ink-muted">Before training</p>
                <p className="num whitespace-pre-wrap break-words">{sample.before}</p>
              </div>
              <div className="min-w-0">
                <p className="text-xs text-ink-muted">After training</p>
                <p className="num whitespace-pre-wrap break-words">{sample.after}</p>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
