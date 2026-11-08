import { Link } from "react-router";

import { BestSoFar } from "@/components/best-so-far";
import { HalftoneHeadline } from "@/components/halftone-headline";
import { Button } from "@/components/ui/button";
import { useRuns } from "@/lib/queries";

/** The site focus ring (2 px accent outline, 2 px offset) over the button's own ring. */
const FOCUS =
  "focus-visible:outline-solid focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange";

/**
 * The landing page (US4.2): the halftone headline at once, then the lab's label and one-line
 * description, the best result so far and the two ways on, Go to training and See scores.
 * The page fills the window below the top bar (`h-14`); the headline grows into the free
 * height above the text block and centres the word in it (AC4.2.5).
 */
export function LandingPage() {
  const runs = useRuns();
  const list = runs.state === "ready" ? runs.data.runs : null;
  const error = runs.state === "error" ? runs.error : null;
  const empty =
    list !== null && !list.some((r) => r.dev_accuracy !== null && Number.isFinite(r.dev_accuracy));

  return (
    <div className="flex min-h-[calc(100svh-3.5rem)] w-full flex-col">
      <HalftoneHeadline />
      <div className="flex flex-col gap-4 border-t-[0.5px] border-hairline px-[var(--gutter)] py-8">
        <p className="label-caps text-ink-muted">A personal fine-tuning lab on this PC</p>
        <p className="text-ink">
          Teaching small open models grade-school math, one measured run at a time.
        </p>
        <div className="mt-4">
          <BestSoFar runs={list} error={error} />
        </div>
        <div className="mt-4 flex items-center gap-4">
          <Button asChild className={FOCUS}>
            <Link to="/training">Go to training</Link>
          </Button>
          <Button asChild variant={empty ? "ghost" : "outline"} className={FOCUS}>
            <Link to="/scores">See scores</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
