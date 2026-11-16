import { Link } from "react-router";

import { FirstTryLine, ProgressLine } from "@/components/course/progress";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/lib/api-context";
import { useAsync } from "@/lib/queries";

/** The site focus ring, as on the landing page's other buttons. */
const FOCUS =
  "focus-visible:outline-solid focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange";

/**
 * The landing page's "Your course" card (AC12.5.10): the progress line and a link on to the
 * course; the error's message when the overview cannot be read (the page around it still renders).
 */
export function CourseCard() {
  const api = useApi();
  const course = useAsync(() => api.getCourse(), [api]);

  let body;
  if (course.state === "loading") {
    body = (
      <div aria-busy="true">
        <p className="sr-only">Reading the course…</p>
        <Skeleton className="h-5 w-64 bg-panel" />
      </div>
    );
  } else if (course.state === "error") {
    body = (
      <p role="alert" className="text-sm text-danger">
        {course.error.message}
      </p>
    );
  } else {
    body = (
      <>
        <ProgressLine progress={course.data.progress} />
        <FirstTryLine progress={course.data.progress} />
        <div>
          <Button asChild variant="outline" className={FOCUS}>
            <Link to="/course">Continue the course</Link>
          </Button>
        </div>
      </>
    );
  }

  return (
    <section
      aria-labelledby="your-course-heading"
      className="flex flex-col gap-3 border-t-[0.5px] border-hairline px-[var(--gutter)] py-8"
    >
      <h2 id="your-course-heading" className="label-caps text-ink-muted">
        Your course
      </h2>
      {body}
    </section>
  );
}
