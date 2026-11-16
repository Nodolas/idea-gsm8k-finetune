import { useState } from "react";

import { Prose } from "@/components/course/prose";
import { Button } from "@/components/ui/button";
import { toApiError } from "@/lib/api";
import { useApi } from "@/lib/api-context";

export interface OwnWordsProps {
  stepId: string;
  prompt: string;
  saved: string | null;
  modelAnswer: string | null;
}

/** "In your own words": a text box, "Save my answer", then the model answer (AC12.5.8). */
export function OwnWords({ stepId, prompt, saved, modelAnswer }: OwnWordsProps) {
  const api = useApi();
  const [text, setText] = useState(saved ?? "");
  const [shown, setShown] = useState<string | null>(modelAnswer);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    setError(null);
    setBusy(true);
    try {
      const answer = await api.saveCourseOwnWords(stepId, text);
      setShown(answer.model_answer);
    } catch (e) {
      setError(toApiError(e).message);
    } finally {
      setBusy(false);
    }
  };

  const labelId = `own-words-${stepId}`;
  return (
    <div className="flex min-w-0 flex-col gap-3">
      <p id={labelId} className="max-w-[75ch] text-ink">
        {prompt}
      </p>
      <textarea
        aria-labelledby={labelId}
        value={text}
        onChange={(event) => setText(event.target.value)}
        rows={5}
        className="w-full max-w-[75ch] rounded-sm border-[0.5px] border-hairline bg-background p-2 text-ink"
      />
      <div className="flex items-center gap-3">
        <Button disabled={busy} onClick={() => void save()}>
          Save my answer
        </Button>
      </div>
      {error ? (
        <p role="alert" className="max-w-[75ch] text-sm text-danger">
          {error}
        </p>
      ) : null}
      {shown ? (
        <section className="flex flex-col gap-1">
          <h4 className="label-caps text-ink-muted">One way to say it</h4>
          <Prose text={shown} />
        </section>
      ) : null}
    </div>
  );
}
